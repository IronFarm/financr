import datetime
import json

import pandas as pd
import requests
from lxml import html

PRICE_HISTORY_URL = 'http://markets.ft.com/data/funds/tearsheet/historical'
FALLBACK_URL = 'http://funds.ft.com/uk/Tearsheet/Summary'


def get_fund_price_history(name, isin, min_date):
    print 'Downloading price history for {}'.format(name)

    # Load FT page to get symbol and currency
    result = requests.get(PRICE_HISTORY_URL, params={'s': isin})

    # TODO sometimes the result is not the expected page
    if not result.url.count('tearsheet'):
        print 'First attempt at price download failed, using fallback URL'
        result = requests.get(FALLBACK_URL, params={'s': isin})
        parsed_html = html.fromstring(result.content)
        correct_url = parsed_html.find('.//*[@id="wsod"]/ul/li[5]/a').attrib['onclick'].split('\'')[1]
        result = requests.get(correct_url)

    currency_code = html.fromstring(result.content).find(".//*span[@class='mod-ui-data-list__label']").text[-4:-1]
    price_factor = 1.0 if currency_code == 'GBX' else 100.0

    end_date = datetime.date.today()
    symbol = json.loads(
        html.fromstring(result.content).find(".//*section[@class='mod-tearsheet-add-to-watchlist']").attrib['data-mod-config']
    )['xid']
    price_history = []
    while True:
        start_date = end_date - datetime.timedelta(days=364)
        results = requests.get('https://markets.ft.com/data/equities/ajax/get-historical-prices',
                               params={'startDate': start_date, 'endDate': end_date, 'symbol': symbol})

        for row in html.fragments_fromstring(results.json()['html']):
            date = row.find('td/span[1]').text
            date = datetime.datetime.strptime(date, '%A, %B %d, %Y')
            price = float(row.findall('td')[1].text) * price_factor  # Convert prices to pence

            price_history.append((date, name, price))

        if start_date < min_date:
            break

        # TODO test this
        end_date = start_date - datetime.timedelta(days=1)

    return price_history


def download_price_history(account_data, total_holdings):
    price_data = []
    for holding in account_data:
        start_date = total_holdings.loc(axis=0)[:, holding['name']].index.values[0][0].date()
        price_data.extend(get_fund_price_history(holding['name'], holding['isin'], start_date))

    price_history = pd.DataFrame.from_records(price_data, columns=['date', 'fund', 'fund_price'])
    price_history['date'] = pd.to_datetime(price_history['date'], dayfirst=True)
    price_history = price_history.set_index(['date', 'fund']).sort_index()

    return price_history
