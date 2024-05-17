import os
import sys
import copy
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import meanline_axial as ml 

# Define running option
# test = "optimization"
test = "performance_analysis"

# Run calculations
if test == "performance_analysis":

    # Load configuration file
    CONFIG_FILE = os.path.abspath("test_performance_analysis.yaml")
    config = ml.read_configuration_file(CONFIG_FILE)

    # Compute performance map according to config file
    operation_points = config["operation_points"]
    solvers = ml.compute_performance(operation_points, config, initial_guess = None, export_results=None, stop_on_failure=True)
    
    
    # if not solvers[0].problem.results["overall"]["efficiency_ts"].values[-1] == 79.10385195685564:
    #     print("Efficiency fail")
    # if not solvers[0].convergence_history["norm_residual"][-1] == 1.652715242355494e-10:
    #     print("Residual fail")
    # if not solvers[0].convergence_history["func_count"][-1] == 11:
    #     print("Number of iterations fail")

    # # Load configuration file
    # CONFIG_FILE = os.path.abspath("test_performance_analysis_evaluate_cascade_critical.yaml")
    # config = ml.read_configuration_file(CONFIG_FILE)

    # # Compute performance map according to config file
    # operation_points = config["operation_points"]
    # solvers = ml.compute_performance(operation_points, config, initial_guess = None, export_results=None, stop_on_failure=True)
    # if not solvers[0].problem.results["overall"]["efficiency_ts"].values[-1] == 79.1050040422735:
    #     print("Efficiency fail")
    # if not solvers[0].convergence_history["norm_residual"][-1] == 1.0806939526929114e-08:
    #     print("Residual fail")
    # if not solvers[0].convergence_history["func_count"][-1] == 18:
    #     print("Number of iterations fail")

elif test == "optimization":

    # Load configuration file
    CONFIG_FILE = os.path.abspath("test_optimization.yaml")
    config = ml.read_configuration_file(CONFIG_FILE)
    solvers = ml.compute_optimal_turbine(config, initial_guess = None)

    # if not solvers.convergence_history["constraint_violation"][-1] == 4.0832313918937047e-10:
    #     print("constraint violation fails")
    # if not solvers.convergence_history["grad_count"][-1] == 80:
    #     print("Number of iterations fails")
    # if not solvers.convergence_history["objective_value"][-1] ==  -0.9084032430486514:
    #     print("Objecitve function fails")


# Keep figures open
plt.show()