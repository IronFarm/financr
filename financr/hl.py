import pandas as pd
import requests
from lxml import html

LOGIN_STEP_ONE_URL = 'https://online.hl.co.uk/my-accounts/login-step-one'
LOGIN_STEP_TWO_URL = 'https://online.hl.co.uk/my-accounts/login-step-two'
ACCOUNT_SUMMARY_URL = 'https://online.hl.co.uk/my-accounts/account_summary/account/22'


def find_validation_token(content):
    parsed_html = html.fromstring(content)
    validation_token = parsed_html.find('.//input[@name="hl_vt"]').attrib['value']

    return validation_token


def login_session(session, username, dob, password):
    result = session.get(LOGIN_STEP_ONE_URL)
    validation_token = find_validation_token(result.content)
    session.post(LOGIN_STEP_ONE_URL, {'hl_vt': validation_token, 'username': username, 'DoB': dob, 'submit.x': '50',
                                      'submit.y': '20', 'submit': 'login'})

    result = session.get(LOGIN_STEP_TWO_URL)
    validation_token = find_validation_token(result.content)
    parsed_html = html.fromstring(result.content)
    required_chars = [int(x.text) - 1 for x in parsed_html.findall('.//*[@id="login-box-border"]/div/p/strong')]
    session.post(LOGIN_STEP_TWO_URL, {'hl_vt': validation_token, 'pChar1': password[required_chars[0]],
                                      'pChar2': password[required_chars[1]], 'pChar3': password[required_chars[2]],
                                      'submit.x': '50', 'submit.y': '20', 'submit': 'login'})


def get_list_of_holdings(session):
    result = session.get(ACCOUNT_SUMMARY_URL)
    parsed_html = html.fromstring(result.content)

    holdings = []
    for row in parsed_html.findall('.//*[@id="holdings-table"]/tbody/tr'):
        holding = {
            'name': row.find('td/div/a/span').text,
            'transaction_url': row.find('td[1]/a').attrib['href'],
            'detail_url': row.find('.//*[@class="factsheet-button"]').attrib['href'].replace('security_details',
                                                                                             'fund_key_features'),
            'total_units': float(row.find('td[3]/span').text.replace(',', ''))
        }
        holdings.append(holding)

    return holdings


def download_transaction_history(session, name, url):
    print 'Downloading transaction history for {}'.format(name)

    transaction_rows = './/*[@id="movements-table-container"]/table/tbody/tr'
    transaction_history = []

    try:
        result = session.get(url)
    except requests.ConnectionError:
        print 'Error fetching transaction history for {}'.format(name)
        return transaction_history
    parsed_html = html.fromstring(result.content)

    for row in parsed_html.findall(transaction_rows):
        transaction_history.append(tuple(x.text.strip() for x in row.findall('td')))

    return transaction_history


def get_isin_from_url(session, url):
    result = session.get(url)
    parsed_html = html.fromstring(result.content)

    isin = parsed_html.find('.//*[th="ISIN code:"]/td').text.strip()

    return isin


def get_account_data_for_holdings(my_session, holdings):
    account_data = []
    for holding in holdings:
        account = {
            'name': holding['name'],
            'transaction_history': download_transaction_history(my_session, holding['name'],
                                                                holding['transaction_url']),
            'isin': get_isin_from_url(my_session, holding['detail_url']),
            'total_units': holding['total_units']
        }
        account_data.append(account)

    return account_data


def download_account_data(username, dob, password):
    my_session = requests.session()

    login_session(my_session, username, dob, password)
    holdings = get_list_of_holdings(my_session)
    account_data = get_account_data_for_holdings(my_session, holdings)

    return account_data


def create_transaction_history(account_data):
    transactions = []
    for holding in account_data:
        for transaction in holding['transaction_history']:
            transactions.append((holding['name'],) + transaction)

    transaction_history = pd.DataFrame.from_records(
        transactions, exclude=['record'], columns=['fund', 'date', 'type', 'record', 'fund_price', 'units', 'cost']
    )
    transaction_history['date'] = pd.to_datetime(transaction_history['date'], dayfirst=True)
    transaction_history['fund_price'] = transaction_history['fund_price'].apply(lambda x: float(x.replace(',', '')))
    transaction_history['units'] = transaction_history['units'].apply(lambda x: float(x.replace(',', '')))
    transaction_history['cost'] = transaction_history['cost'].apply(lambda x: float(x.replace(',', '')))

    try:
        archived_transactions = pd.read_csv('archived_transactions.csv', parse_dates=[0])
        transaction_history = pd.concat([transaction_history, archived_transactions])
    except IOError:
        pass

    transaction_history = transaction_history.query('not (units > 0.0 and fund_price == 0.0)')
    transaction_history = transaction_history.set_index(['date', 'fund']).sort_index()

    return transaction_history
