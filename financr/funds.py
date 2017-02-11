import configparser
import pandas as pd
from bokeh.charts import Line, output_file, show

import hl
import prices

config = configparser.ConfigParser()
config.read('config.ini')

username = config.get('HL', 'username')
dob = config.get('HL', 'dob')
password = config.get('HL', 'password')


if __name__ == '__main__':
    account_data = hl.download_account_data(username, dob, password)
    transaction_history = hl.create_transaction_history(account_data)
    total_holdings = transaction_history.groupby(level='fund')[['units', 'cost']].cumsum()

    price_history = prices.download_price_history(account_data, total_holdings)

    data_full_detail = pd.concat([price_history, total_holdings], axis=1)
    data_full_detail = data_full_detail.unstack('fund').fillna(method='ffill').stack()
    data_full_detail['value'] = data_full_detail.eval('fund_price * units / 100')

    data_by_date = data_full_detail.groupby(level='date')[['cost', 'value']].sum().dropna()
    data_by_date['profit'] = data_by_date.eval('value - cost')
    data_by_date['return'] = data_by_date['profit'] / data_by_date['cost'].max() * 100

    # TODO factor out plotting
    # TODO plot by individual fund
    value_plot = Line(data_by_date, y='cost', plot_width=1200, plot_height=600)
    output_file('plots/total_cost.html')
    show(value_plot)

    value_plot = Line(data_by_date, y='value', plot_width=1200, plot_height=600)
    output_file('plots/total_value.html')
    show(value_plot)

    profit_plot = Line(data_by_date, y='profit', plot_width=1200, plot_height=600)
    output_file('plots/total_profit.html')
    show(profit_plot)

    return_plot = Line(data_by_date, y='return', plot_width=1200, plot_height=600)
    output_file('plots/total_return.html')
    show(return_plot)

    print 'exit'
