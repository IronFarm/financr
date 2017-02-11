from bokeh.charts import Line, output_file, show


def plot_column(data, column_name, save=True, display=True):
    plot = Line(data, y=column_name, plot_width=1200, plot_height=600)

    if save:
        output_file('plots/' + column_name + '.html')

    if display:
        show(plot)

    return plot
