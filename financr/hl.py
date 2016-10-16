import datetime

import configparser
import pandas as pd
import requests
from lxml import html

config = configparser.ConfigParser()
config.read('config.ini')

username = config.get('HL', 'username')
dob = config.get('HL', 'dob')
pwd = config.get('HL', 'pwd')

login_url1 = 'https://online.hl.co.uk/my-accounts/login-step-one'
login_url2 = 'https://online.hl.co.uk/my-accounts/login-step-two'
account_summary_url = 'https://online.hl.co.uk/my-accounts/account_summary/account/22'

price_history_url_base = 'http://markets.ft.com/data/funds/tearsheet/historical?s='


def get_validation_token(content):
    parsed_html = html.fromstring(content)
    validation_token = parsed_html.xpath("//input[@name='hl_vt']/@value")

    return validation_token


def get_list_of_holdings(account_summary):
    parsed_html = html.fromstring(account_summary)

    holding_names = [x.text for x in parsed_html.xpath('//*[@id="holdings-table"]/tbody/tr/td/div/a/span')]
    transaction_urls = [x.attrib['href'] for x in parsed_html.xpath('//*[@id="holdings-table"]/tbody/tr/td[1]/*')]
    detail_urls = [x.attrib['href'].replace('security_details', 'fund_key_features')
                   for x in parsed_html.xpath('//*[@id="holdings-table"]/tbody/tr/td/div/a[@class="factsheet-button"]')]
    return holding_names, transaction_urls, detail_urls


def get_transaction_history_for_url(session, name, url):
    print 'Downloading transaction history for {}'.format(name)
    transaction_rows = './/*[@id="movements-table-container"]/table/tbody/tr'
    data = []

    result = session.get(url)
    parsed_html = html.fromstring(result.content)

    for row in parsed_html.findall(transaction_rows):
        data.append((name, ) + tuple(x.text.strip() for x in row.findall('td')))

    return data


def extract_isin_from_url(session, url):
    isin_path = './/*[@id="security-factsheet"]/div/div[7]/div[2]/div/div/table/tbody/tr[12]/td'

    result = session.get(url)
    parsed_html = html.fromstring(result.content)

    isin = parsed_html.find(isin_path).text.strip()

    return isin


def create_transaction_history(transaction_data):
    transaction_history = pd.DataFrame.from_records(
        transaction_data, exclude=['record'], columns=['fund', 'date', 'type', 'record', 'fund_price', 'units', 'value']
    )
    transaction_history['date'] = pd.to_datetime(transaction_history['date'])
    transaction_history['fund_price'] = transaction_history['fund_price'].apply(lambda x: float(x.replace(',', '')))
    transaction_history['units'] = transaction_history['units'].apply(lambda x: float(x.replace(',', '')))
    transaction_history['value'] = transaction_history['value'].apply(lambda x: float(x.replace(',', '')))
    transaction_history = transaction_history.set_index(['date', 'fund']).sort_index()

    return transaction_history


def get_fund_price_history(session, name, fund_isin, start_date):
    row_xpath = ('.//*[@class="mod-ui-table mod-tearsheet-historical-prices__results mod-ui-table--freeze-pane"]'
                 '/tbody/tr')
    get_more_rows_xpath = './/*[@class="o-buttons mod-tearsheet-historical-prices__moreButton mod-ui-hide-small-below"]'
    result = session.get(price_history_url_base + fund_isin)
    parsed_html = html.fromstring(result.content)

    # Load initial data
    table_rows = parsed_html.findall(row_xpath)
    next_date = parsed_html.find(get_more_rows_xpath).attrib['data-mod-results-startdate']
    symbol = parsed_html.find(get_more_rows_xpath).attrib['data-mod-symbol']

    price_history = []
    for row in table_rows:
        date = row.find('td/span[1]').text
        date = datetime.datetime.strptime(date, '%A, %B %d, %Y')
        price = float(row.findall('td')[1].text)

        price_history.append((date, name, price))

    while price_history[-1][0] > start_date:
        extra_results = my_session.get('http://markets.ft.com/data/equities/ajax/getmorehistoricalprices',
                                       params={'resultsStartDate': next_date, 'symbol': symbol,
                                               'isLastRowStriped': 'false'})

        next_date = extra_results.json()['data']['startDate']

        for row in html.fragments_fromstring(extra_results.json()['data']['html']):
            date = row.find('td/span[1]').text
            date = datetime.datetime.strptime(date, '%A, %B %d, %Y')
            price = float(row.findall('td')[1].text)

            price_history.append((date, name, price))

    return price_history


if __name__ == '__main__':
    my_session = requests.session()

    result = my_session.get(login_url1)
    vt = get_validation_token(result.content)

    result = my_session.post(login_url1, {'hl_vt': vt, 'username': username, 'DoB': dob, 'submit.x': '50',
                                          'submit.y': '20', 'submit': 'login'})

    result = my_session.get(login_url2)
    vt = get_validation_token(result.content)
    parsed_html = html.fromstring(result.content)
    required_chars = [int(x.text) - 1 for x in parsed_html.xpath('//*[@id="login-box-border"]/div/p/strong')]

    result = my_session.post(login_url2, {'hl_vt': vt, 'pChar1': pwd[required_chars[0]],
                                          'pChar2': pwd[required_chars[1]], 'pChar3': pwd[required_chars[2]],
                                          'submit.x': '50', 'submit.y': '20', 'submit': 'login'})
    result = my_session.get(account_summary_url)

    holdings_data = get_list_of_holdings(result.content)
    all_transactions = []
    fund_isins = []
    for name, url, isin_url in zip(holdings_data[0], holdings_data[1], holdings_data[2]):
        history = get_transaction_history_for_url(my_session, name, url)
        all_transactions.extend(history)

        fund_isins.append((name, extract_isin_from_url(my_session, isin_url)))

    transaction_history = create_transaction_history(all_transactions)

    price_history = get_fund_price_history(my_session, name, fund_isins[-1][1], datetime.datetime(2016, 9, 1))

    print 'exit'
