import datetime

import pandas as pd
import requests
from lxml import html

PRICE_HISTORY_URL = 'http://markets.ft.com/data/funds/tearsheet/historical'
FALLBACK_URL = 'http://funds.ft.com/uk/Tearsheet/Summary'


def get_fund_price_history(name, isin, start_date):
    print 'Downloading price history for {}'.format(name)

    # Load FT page to get symbol and currency
    result = requests.get(PRICE_HISTORY_URL, params={'s': isin})

    # TODO sometimes the result is not the expected page
    if not result.url.count('tearsheet'):
        result = requests.get(FALLBACK_URL, params={'s': isin})
        parsed_html = html.fromstring(result.content)
        correct_url = parsed_html.find('.//*[@id="wsod"]/ul/li[5]/a').attrib['onclick'].split('\'')[1]
        result = requests.get(correct_url)

    symbol = result.url.split('=')[1]
    price_factor = 1.0 if symbol[-3:] == 'GBX' else 100.0

    next_date = (datetime.date.today() - datetime.date(1900, 1, 1)).days + 3
    price_history = []
    while True:
        results = requests.get('http://markets.ft.com/data/equities/ajax/getmorehistoricalprices',
                               params={'resultsStartDate': next_date, 'symbol': symbol, 'isLastRowStriped': 'false'})

        next_date = results.json()['data']['startDate']

        for row in html.fragments_fromstring(results.json()['data']['html']):
            date = row.find('td/span[1]').text
            date = datetime.datetime.strptime(date, '%A, %B %d, %Y')
            price = float(row.findall('td')[1].text) * price_factor

            price_history.append((date, name, price))

        if price_history[-1][0] <= start_date:
            break

    return price_history


def download_price_history(account_data, total_holdings):
    price_data = []
    for holding in account_data:
        start_date = total_holdings.loc(axis=0)[:, holding['name']].index.values[0][0]
        price_data.extend(get_fund_price_history(holding['name'], holding['isin'], start_date))

    price_history = pd.DataFrame.from_records(price_data, columns=['date', 'fund', 'fund_price'])
    price_history['date'] = pd.to_datetime(price_history['date'], dayfirst=True)
    price_history = price_history.set_index(['date', 'fund']).sort_index()

    return price_history
