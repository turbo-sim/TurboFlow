import os
import sys
import copy
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import meanline_axial as ml 

# Define running option
CASE = 2

# Load configuration file
CONFIG_FILE = os.path.abspath("kofskey1972_1stage.yaml")
config = ml.read_configuration_file(CONFIG_FILE)

# ml.print_dict(config)

x0 = {'w_out_1': 244.42314206706558,
  's_out_1': 3787.6640308614674,
  'beta_out_1': 64.43917617780212,
  'v*_in_1': 84.77882078058266,
  'w*_throat_1': 309.3325769414344,
  's*_throat_1': 3789.968019275075,
  'w*_out_1': 309.3325771576979,
  's*_out_1': 3789.968019282878,
  'w_out_2': 240.72352688455877,
  's_out_2': 3797.034102749199,
  'beta_out_2': -61.497567096277514,
  'v*_in_2': 250.04121537545407,
  'w*_throat_2': 292.4919351280035,
  's*_throat_2': 3800.736468314427,
  'w*_out_2': 259.39028119411665,
  's*_out_2': 3798.4449806382895,
  'v_in': 81.88511236557443}


# Run calculations
if CASE == 1:
    # Compute performance map according to config file
    operation_points = config["operation_points"]

    solvers = ml.compute_performance(operation_points, config, initial_guess = None, export_results=True, stop_on_failure=True)

elif CASE == 2:
    # Compute performance map according to config file
    operation_points = config["performance_map"]
    # omega_frac = np.asarray([0.5, 0.7, 0.9, 1.0])
    omega_frac = np.asarray(1.00)
    operation_points["omega"] = operation_points["omega"]*omega_frac
    solvers = ml.compute_performance(operation_points, config, initial_guess = None)

elif CASE == 3:
    
    # Load experimental dataset
    sheets =  ['Mass flow rate', 'Torque', 'Total-to-static efficiency', 'alpha_out']
    data = pd.read_excel("./experimental_data_kofskey1972_1stage_raw.xlsx", sheet_name=sheets)
    
    pressure_ratio_exp = []
    speed_frac_exp = []
    for sheet in sheets:
        pressure_ratio_exp += list(data[sheet]['PR'].values)
        speed_frac_exp += list(data[sheet]["omega"].values/100)

    pressure_ratio_exp = np.array(pressure_ratio_exp)
    speed_frac_exp = np.array(speed_frac_exp)

    # Generate operating points with same conditions as dataset
    operation_points = []
    design_point = config["operation_points"]
    for PR, speed_frac in zip(pressure_ratio_exp, speed_frac_exp):
        if not speed_frac in [0.3, 0.5]: # 30 and 50% desing speed not included in validation plot
            current_point = copy.deepcopy(design_point)
            current_point['p_out'] = design_point["p0_in"]/PR
            current_point['omega'] = design_point["omega"]*speed_frac
            operation_points.append(current_point)

    # Compute performance at experimental operating points   
    ml.compute_performance(operation_points, config)

# Show plots
# plt.show()

    # DONE add option to give operation points as list of lists to define several speed lines
    # DONE add option to define range of values for all the parameters of the operating point, including T0_in, p0_in and alpha_in
    # DONE all variables should be ranged to create a nested list of lists
    # DONE the variables should work if they are scalars as well
    # DONE implemented closest-point strategy for initial guess of performance map
    # DONE implement two norm of relative deviation as metric

    # TODO update plotting so the different lines are plotted separately
    # TODO seggregate solver from initial guess in the single point evaluation
    # TODO improve geometry processing
    # TODO merge optimization and root finding problems for performance analysis
    
