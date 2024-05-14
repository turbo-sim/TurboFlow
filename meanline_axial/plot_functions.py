import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def load_data(filename):

    """
    Load performance data from an Excel file.

    This function imports an Excel file containing performance parameters. It reads the data into a dictionary
    named 'performance_data' where each key corresponds to a sheet name in the Excel file, and each value is
    a pandas DataFrame containing the data from that sheet. The data is rounded to avoid precision loss when
    loading from Excel.

    The excel file must contain the following sheets:

        - `operation point`
        - `plane`
        - `cascade`
        - `overall`

    Parameters
    ----------
    filename : str
        The name of the Excel file containing performance parameters.

    Returns
    -------
    dict
        A dictionary containing performance data, where keys are sheet names and values are DataFrames.

    """

    # Read excel file
    performance_data = pd.read_excel(
        filename, sheet_name=["operation point", "plane", "cascade", 
                              #"stage",
                              "overall"]
    )

    # Round off to ignore precision loss by loading data from excel
    for key, df in performance_data.items():
        performance_data[key] = df.round(10)

    return performance_data


def plot_lines(
    performance_data,
    x_key,
    y_keys,
    subsets = None,
    fig=None,
    ax=None,
    xlabel="",
    ylabel="",
    title="",
    labels = None,
    filename=None,
    outdir="figures",
    stack=False,
    color_map="viridis",
    colors = None,
    close_fig=False,
    save_figs=False,
    linestyles = None,
    save_formats=['.png'],
    legend_loc='best',
):
    """
    Plot lines from performance data.

    This function plots lines from performance data. It supports plotting multiple lines on the same axes
    with customizable labels, colors, and linestyles. The resulting plot can be saved to a file if desired.

    Parameters
    ----------
    performance_data : DataFrame
        The performance data to plot.
    x_key : str
        Name of the column in performance_data to be used as x-axis values.
    y_keys : list of str
        Names of the columns in performance_data to be plotted.
    subsets : list, optional
        Name and value of subsets to plot from performance_data. First instance should be a string representing the column name, while the 
        remaining elemnts represet the values defining the subset. Default is None.
    fig : matplotlib.figure.Figure, optional
        An existing figure object. If None, a new figure is created.
    ax : matplotlib.axes.Axes, optional
        An existing axes object. If None, a new axes is created.
    xlabel : str, optional
        The label for the x-axis.
    ylabel : str, optional
        The label for the y-axis.
    title : str, optional
        The title of the plot.
    labels : list of str, optional
        Labels for the plotted lines. Default is None.
    filename : str, optional
        The filename for saving the figure. Default is None.
    outdir : str, optional
        The directory where figures should be saved. Default is 'figures'.
    stack : bool, optional
        Whether to stack the plotted lines. Default is False.
    color_map : str, optional
        The colormap used for the lines. Default is 'viridis'.
    colors : list of str or colors, optional
        Colors for the plotted lines. Default is None.
    close_fig : bool, optional
        Whether to close the figure after plotting. Default is False.
    save_figs : bool, optional
        Whether to save the figure. Default is False.
    linestyles : list of str, optional
        Linestyles for the plotted lines. Default is None.
    save_formats : list of str, optional
        File formats for saving the figure. Default is ['.png'].
    legend_loc : str, optional
        Location for the legend. Default is 'best'.

    Returns
    -------
    matplotlib.figure.Figure
        The figure object.
    matplotlib.axes.Axes
        The axes object.

    """

    # Create figure if not provided
    if fig is None or ax is None:
        fig, ax = plt.subplots(figsize=(6.4, 4.8))

    # Specify title and axes labels
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    # Get data
    if subsets == None:
        x = get_lines(performance_data, x_key)
        y = get_lines(performance_data, y_keys)
    else:
        x = get_lines(performance_data, x_key, subsets=subsets)
        y = get_lines(performance_data, y_keys, subsets=subsets)

    # Get colors
    if colors == None:
        colors = plt.get_cmap(color_map)(np.linspace(0.2, 1.0, len(y)))

    # Get labels
    if labels == None:
        if subsets is not None:
            labels = [f"{subsets[0]} = {subsets[i+1]}" for i in range(len(subsets)-1)]
        elif len(y_keys) > 1:
            labels = [f"{y_keys[i]}" for i in range(len(y))]

    # Get linestyles
    if linestyles == None:
        linestyles = ['-']*len(y)
    
    # Plot figure        
    if stack == True:
        ax.stackplot(x, y, labels=y_keys, colors=colors)

        # Add edges by overlaying lines
        y_arrays = [series.values for series in y]
        cumulative_y = np.cumsum(y_arrays, axis=0)
        for i, series in enumerate(y_arrays):
            if i == 0:
                ax.plot(x, series, color='black', linewidth=0.5)
            ax.plot(x, cumulative_y[i], color='black', linewidth=0.5)
    elif subsets is not None:
        for i in range(len(y)):
            ax.plot(x[i], y[i], label=labels[i], color=colors[i], linestyle = linestyles[i])
    else:
        for i in range(len(y)):
            ax.plot(x, y[i], label=labels[i], color=colors[i], linestyle = linestyles[i])

    # Set margins to zero
    ax.margins(x=0.01, y=0.01)

    # Add legend
    if len(y) > 1:
        ax.legend(loc=legend_loc)
    fig.tight_layout(pad=1, w_pad=None, h_pad=None)

    # Create output directory if it does not exist
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    # Save figure
    if save_figs:
        base_filename = os.path.join(outdir, filename)
        savefig_in_formats(fig, base_filename, formats=save_formats)

    if close_fig:
        plt.close(fig)

    return fig, ax


def get_lines(performance_data, column_name, subsets=None):
    """
    Retrieve lines of data from the specified column in `performance_data`.

    This function returns a list of array from the specified column(s) of the performance data.
    If no subset is specified, it returns lines covering all rows in `performance_data`. If a subset
    is specified, it returns lines covering only the rows that match the specified subset.        

    Parameters
    ----------
    performance_data : DataFrame
        The DataFrame containing the performance data.
    column_name : str or list of str
        The name(s) of the column(s) from which to retrieve data.
    subsets : list, optional
        Name and value of subsets to get data from performance_data. First instance should be a string representing the column name, while the 
        remaining elemnts represet the values defining the subset. Default is None.

    Returns
    -------
    list
        A list of arrays from the specified column(s) of performance_data.

    """

    # Get lines covering all rows in performance_data
    if subsets == None:
        # Get single line
        if isinstance(column_name, str):
            return get_column(performance_data, column_name)
        # Get several columns
        else:
            lines = []
            for column in column_name:
                lines.append(get_column(performance_data, column))
            return lines

    subsets[1:] = [round(value, 10) for value in subsets[1:]]
    # Get lines covering given subset
    lines = []
    for val in subsets[1:]:
        if isinstance(column_name, str):
            indices = get_subset(performance_data, subsets[0], val)
            lines.append(get_column(performance_data, column_name)[indices])
        else:
            for column in column_name:
                indices = get_subset(performance_data, subsets[0], val)
                lines.append(get_column(performance_data, column)[indices])

    return lines

def find_column(performance_data, column_name):
    """
    Find the sheet containing the specified column in `performance_data`.

    This function searches through all sheets in `performance_data` to find the one containing the specified column.
    If the column is found, it returns the name of the sheet. If the column is not found, it raises an exception.

    Parameters
    ----------
    performance_data : dict
        A dictionary containing sheets of performance data, where keys are sheet names and values are DataFrames.
    column_name : str
        The name of the column to find.

    Returns
    -------
    str
        The name of the sheet containing the specified column.

    Raises
    ------
    Exception
        If the specified column is not found in any sheet of performance_data.

    """

    for key in performance_data.keys():
        if any(element == column_name for element in performance_data[key].columns):
            return key

    raise Exception(f"Could not find column {column_name} in performance_data")


def get_column(performance_data, column_name):
    """
    Retrieve a column of data from `performance_data`. 

    This function retrieves the specified column of data from `performance_data` by finding the sheet containing 
    the column using the `find_column` function. It then returns the column as a pandas Series.

    Parameters
    ----------
    performance_data : dict
        A dictionary containing sheets of performance data, where keys are sheet names and values are DataFrames.
    column_name : str
        The name of the column to retrieve.

    Returns
    -------
    pandas.Series
        The column of data corresponding to column_name.

    """
    sheet = find_column(performance_data, column_name)

    return performance_data[sheet][column_name]


def get_subset(performance_data, column_name, row_value):
    """
    Retrieve the index of rows in `performance_data` where `column_name` equals `row_value`.

    This function retrieves the index of rows in `performance_data` where the specified column (`column_name`) 
    equals the specified value (`row_value`). It first finds the sheet containing the column using the 
    `find_column` function, then returns the index of rows where the column has the specified value.

    Parameters
    ----------
    performance_data : dict
        A dictionary containing sheets of performance data, where keys are sheet names and values are DataFrames.
    column_name : str
        The name of the column to search for `row_value`.
    row_value : object
        The value to match in `column_name`.

    Returns
    -------
    pandas.Index
        The index of rows where `column_name` equals `row_value`.
    
    """
    sheet = find_column(performance_data, column_name)

    return performance_data[sheet][
        performance_data[sheet][column_name] == row_value
    ].index


def savefig_in_formats(fig, path_without_extension, formats=[".png", ".svg", ".pdf", ".eps"]):
    """
    Save a given matplotlib figure in multiple file formats.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure object to be saved.
    path_without_extension : str
        The full path to save the figure excluding the file extension.
    formats : list of str, optional
        A list of string file extensions to specify which formats the figure should be saved in.
        Default is ['.png', '.svg', '.pdf', ".eps"].

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> fig, ax = plt.subplots()
    >>> ax.plot([0, 1], [0, 1])
    >>> save_fig_in_formats(fig, "/path/to/figure/filename")

    This will save the figure as "filename.png", "filename.svg", and "filename.pdf" in the "/path/to/figure/" directory.
    """
    for ext in formats:
        fig.savefig(f"{path_without_extension}{ext}", bbox_inches="tight")

def plot_axial_radial_plane(geometry):

    r"""
    Plot the turbine geometry in an axial-radial plane.

    This function plots the turbine geometry in an axial-radial plane. It takes the turbine geometry data
    as input, including the radii at the inner and outer hub and tip, the number of cascades, and the axial
    chord lengths. It then constructs and displays the plot, which represents the turbine blades in the
    axial-radial plane.

    Parameters
    ----------
    geometry : dict
        A dictionary containing turbine geometry data including:

        - `radius_hub_in` (array-like) : Inner hub radii at each cascade.
        - `radius_hub_out` (array-like) : Outer hub radii at each cascade.
        - `radius_tip_in` (array-like) : Inner tip radii at each cascade.
        - `radius_tip_out` (array-like) : Outer tip radii at each cascade.
        - `number_of_cascades` (int) : Number of cascades in the turbine.
        - `axial_chord` (array-like) : Axial chord lengths at each cascade.

    Returns
    -------
    matplotlib.figure.Figure
        The generated figure.
    matplotlib.axes.Axes
        The generated axes.
    
    """
    
    # Load data
    radius_hub_in = geometry["radius_hub_in"]
    radius_hub_out = geometry["radius_hub_out"]
    radius_tip_in = geometry["radius_tip_in"]
    radius_tip_out = geometry["radius_tip_out"]
    number_of_cascades = geometry["number_of_cascades"]
    axial_chord = geometry["axial_chord"]
    
    
    dx = 0.05*max(axial_chord) # Axial spacing between cascades

    # Define x-points
    x = np.array([])
    for i in range(len(axial_chord)):
        x = np.append(x, np.sum(axial_chord[0:i+1]) + i*dx)
        x = np.append(x, np.sum(axial_chord[0:i+1]) + (i+1)*dx)
    x[1:] = x[0:-1]
    x[0] = 0

    # Define hub and tip points 
    y_hub = np.array([val for pair in zip(radius_hub_in, radius_hub_out) for val in pair])
    y_tip = np.array([val for pair in zip(radius_tip_in, radius_tip_out) for val in pair])

    # Plot cascades
    fig, ax = plt.subplots()
    colors = ["0.5", "0.8"] # Colors for stator and rotor rwo respectively
    for i in range(number_of_cascades):    
        ax.plot(x[i*2:(i+1)*2], y_tip[i*2:(i+1)*2], 'k') # Plot tip 
        ax.plot(x[i*2:(i+1)*2],  y_hub[i*2:(i+1)*2], 'k') # Plt hub 
        ax.plot([x[i*2:(i+1)*2][0], x[i*2:(i+1)*2][0]], [y_hub[i*2:(i+1)*2][0], y_tip[i*2:(i+1)*2][0]], 'k') # Plot inlet vertical line
        ax.plot([x[i*2:(i+1)*2][1], x[i*2:(i+1)*2][1]], [y_hub[i*2:(i+1)*2][1], y_tip[i*2:(i+1)*2][1]], 'k') # Plot outlet vertical line
        
        ax.fill_between(x[i*2:(i+1)*2], y_hub[i*2:(i+1)*2], y_tip[i*2:(i+1)*2], color = colors[i%2]) # Fill cascade with color

    # Set plot options 
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("Axial direction")
    ax.set_ylabel("Radial direction")
    plt.show()
    
    return fig, ax
