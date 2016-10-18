import datetime
from time import sleep

import configparser
import pandas as pd
import requests
from bokeh.charts import Line, output_file, show
from lxml import html

import hl

config = configparser.ConfigParser()
config.read('config.ini')

username = config.get('HL', 'username')
dob = config.get('HL', 'dob')
password = config.get('HL', 'password')

price_history_url = 'http://markets.ft.com/data/funds/tearsheet/historical'


def get_fund_price_history(name, fund_isin, start_date):

    print 'Downloading price history for {}'.format(name)
    row_xpath = ('.//*[@class="mod-ui-table mod-tearsheet-historical-prices__results mod-ui-table--freeze-pane"]'
                 '/tbody/tr')
    get_more_rows_xpath = './/*[@class="o-buttons mod-tearsheet-historical-prices__moreButton mod-ui-hide-small-below"]'

    result = requests.get(price_history_url, params={'s': fund_isin})
    # TODO sometimes the result is not the expected page
    if not result.url.count('tearsheet'):
        sleep(10)
        return get_fund_price_history(name, fund_isin, start_date)

    parsed_html = html.fromstring(result.content)
    price_factor = 1.0 if result.url.count('GBX') else 100.0

    # Load initial data
    table_rows = parsed_html.findall(row_xpath)
    # TODO sometimes this date is wrong
    next_date = parsed_html.find(get_more_rows_xpath).attrib['data-mod-results-startdate']
    symbol = parsed_html.find(get_more_rows_xpath).attrib['data-mod-symbol']

    price_history = []
    for row in table_rows:
        date = row.find('td/span[1]').text
        date = datetime.datetime.strptime(date, '%A, %B %d, %Y')
        price = float(row.findall('td')[1].text) * price_factor

        price_history.append((date, name, price))

    while price_history[-1][0] > start_date:
        extra_results = requests.get('http://markets.ft.com/data/equities/ajax/getmorehistoricalprices',
                                     params={'resultsStartDate': next_date, 'symbol': symbol,
                                             'isLastRowStriped': 'false'})

        next_date = extra_results.json()['data']['startDate']

        # TODO this logic is identical to that above
        for row in html.fragments_fromstring(extra_results.json()['data']['html']):
            date = row.find('td/span[1]').text
            date = datetime.datetime.strptime(date, '%A, %B %d, %Y')
            price = float(row.findall('td')[1].text) * price_factor

            price_history.append((date, name, price))

    return price_history


if __name__ == '__main__':
    account_data = hl.download_account_data(username, dob, password)
    transaction_history = hl.create_transaction_history(account_data)
    total_holdings = transaction_history.groupby(level='fund')[['units', 'cost']].cumsum()

    price_data = []
    for holding in account_data:
        start_date = total_holdings.loc(axis=0)[:, holding['name']].index.values[0][0]
        price_data.extend(get_fund_price_history(holding['name'], holding['isin'], start_date))

    price_history = pd.DataFrame.from_records(price_data, columns=['date', 'fund', 'fund_price'])
    price_history['date'] = pd.to_datetime(price_history['date'], dayfirst=True)
    price_history = price_history.set_index(['date', 'fund']).sort_index()

    all_data = pd.concat([price_history, total_holdings], axis=1)
    all_data = all_data.unstack('fund').fillna(method='ffill').stack()
    all_data['value'] = all_data.eval('fund_price * units / 100')

    value_history = all_data.groupby(level='date')[['cost', 'value']].sum().dropna()
    value_history['ratio'] = value_history.eval('value / cost')
    value_history['profit'] = value_history.eval('value - cost')

    value_plot = Line(value_history, y='value', plot_width=1200, plot_height=600)
    output_file('total_value.html')
    show(value_plot)

    ratio_plot = Line(value_history, y='ratio', plot_width=1200, plot_height=600)
    output_file('ratio.html')
    show(ratio_plot)

    profit_plot = Line(value_history, y='profit', plot_width=1200, plot_height=600)
    output_file('profit.html')
    show(profit_plot)

    print 'exit'
