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
