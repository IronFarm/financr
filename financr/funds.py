import logging

import configparser
import pandas as pd

import hl
import plot
import prices

config = configparser.ConfigParser()
config.read('config.ini')

username = config.get('HL', 'username')
dob = config.get('HL', 'dob')
password = config.get('HL', 'password')


def load_price_history():
    try:
        price_history_ = pd.read_csv('price_history.csv', index_col=['date', 'fund'], parse_dates=True)
    except IOError:
        logging.warning('No price history found')

        return None

    return price_history_


if __name__ == '__main__':
    account_data = hl.download_account_data(username, dob, password)
    transaction_history = hl.create_transaction_history(account_data)
    total_holdings = transaction_history.groupby(level='fund')[['units', 'cost']].cumsum()

    saved_price_history = load_price_history()
    price_history = prices.update_price_history(account_data, total_holdings, saved_price_history)
    price_history.to_csv('price_history.csv')

    data_full_detail = pd.concat([price_history, total_holdings], axis=1)
    data_full_detail = data_full_detail.unstack('fund').fillna(method='ffill').stack()
    data_full_detail = data_full_detail.dropna()
    data_full_detail['value'] = data_full_detail.eval('fund_price * units / 100')

    transaction_history.to_csv('transactions.csv')
    data_full_detail.to_csv('data.csv')

    data_by_date = data_full_detail.groupby(level='date')[['cost', 'value']].sum().dropna()
    data_by_date['profit'] = data_by_date.eval('value - cost')
    data_by_date['return'] = data_by_date['profit'] / data_by_date['cost'].max() * 100

    # TODO plot by individual fund
    cost_plot = plot.plot_column(data_by_date, 'cost')
    value_plot = plot.plot_column(data_by_date, 'value')
    profit_plot = plot.plot_column(data_by_date, 'profit')
    return_plot = plot.plot_column(data_by_date, 'return')

    print 'exit'
