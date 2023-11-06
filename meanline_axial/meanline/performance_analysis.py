# -*- coding: utf-8 -*-
"""
Created on Tue Oct  3 08:40:52 2023

@author: laboan
"""

import os
import yaml
import itertools
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from . import cascade_series as cs
from .design_optimization import CascadesOptimizationProblem
from ..solver import (
    NonlinearSystemSolver,
    OptimizationSolver,
    NonlinearSystemProblem,
    OptimizationProblem,
)
from ..utilities import (
    set_plot_options,
    print_dict,
    print_boundary_conditions,
    flatten_dataframe,
    convert_numpy_to_python,
    ensure_iterable,
    print_operation_points,
)
from datetime import datetime


set_plot_options()


name_map = {"lm": "Lavenberg-Marquardt", "hybr": "Powell's hybrid"}




def compute_performance(
    operation_points,
    case_data,
    filename=None,
    output_dir="output",
):
    """
    Compute and export the performance of each specified operation point to an Excel file.

    This function handles two types of input for operation points:
    1. An explicit list of dictionaries, each detailing a specific operation point.
    2. A dictionary where each key has a range of values, representing the cross-product
       of all possible operation points. It generates the Cartesian product of these ranges
       internally.

    For each operation point, it computes performance based on the provided case data and compiles
    the results into an Excel workbook with multiple sheets for various data sections.

    Parameters
    ----------
    operation_points : list of dict or dict
        A list of operation points where each is a dictionary of parameters, or a dictionary of parameter
        ranges from which operation points will be generated.
    case_data : dict
        A dictionary containing necessary data structures and parameters for computing performance at each operation point.
    filename : str, optional
        The name for the output Excel file. If not provided, a default name with a timestamp is generated.
    output_dir : str, optional
        The directory where the Excel file will be saved. Defaults to 'output'.

    Returns
    -------
    str
        The absolute path to the created Excel file.

    Raises
    ------
    TypeError
        If `operation_points` is neither a list of dictionaries nor a dictionary with ranges.

    Notes
    -----
    - The function validates the input operation points, and if they are given as ranges, it generates
    all possible combinations. Performance is computed for each operation point, and the results are
    then stored in a structured Excel file with separate sheets for each aspect of the data (e.g.,
    overall, plane, cascade, stage, solver, and solution data).
    - The initial guess for the first operation point is set to a default value. For subsequent operation
    points, the function employs a strategy to use the closest previously computed operation point's solution
    as the initial guess. This approach is based on the heuristic that similar operation points have similar
    performance characteristics, which can improve convergence speed and robustness of the solution process.

    See Also
    --------
    generate_operation_points : For generation of operation points from ranges.
    validate_operation_point : For validation of individual operation points.
    compute_operation_point : For computing the performance of a single operation point.
    """

    # Check the type of operation_points argument
    if isinstance(operation_points, dict):
        # Convert ranges to a list of operation points
        operation_points = generate_operation_points(operation_points)
    elif not isinstance(operation_points, list):
        msg = "operation_points must be either list of dicts or a dict with ranges."
        raise TypeError(msg)

    # Validate each operation point
    for operation_point in operation_points:
        validate_operation_point(operation_point)

    # Create a directory to save simulation results
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define filename with unique date-time identifier
    if filename == None:
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"performance_analysis_{current_time}"

    # Export simulation settings as YAML file
    config_data = {k: v for k, v in case_data.items() if v}  # Filter empty entries and
    config_data = convert_numpy_to_python(config_data, precision=12)
    config_file = os.path.join(output_dir, f"{filename}.yaml")
    with open(config_file, "w") as file:
        yaml.dump(config_data, file, default_flow_style=False, sort_keys=False)

    # Initialize lists to hold dataframes for each operation point
    operation_point_data = []
    overall_data = []
    plane_data = []
    cascade_data = []
    stage_data = []
    solver_data = []
    solution_data = []

    # Loop through all operation points
    print_operation_points(operation_points)
    for i, operation_point in enumerate(operation_points):
        print()
        print(f"Computing operation point {i+1} of {len(operation_points)}")
        print_boundary_conditions(operation_point)

        try:
            # Define initial guess
            if i == 0:
                # Use default initial guess for the first operation point
                x0 = None
                print(f"Using default initial guess")
            else:
                closest_x, closest_index = find_closest_operation_point(
                    operation_point,
                    operation_points[:i],  # Use up to the previous point
                    solution_data[:i],  # Use solutions up to the previous point
                )
                print(f"Using solution from point {closest_index+1} as initial guess")
                x0 = closest_x

            # Compute performance
            solver = compute_single_operation_point(
                operation_point, case_data, initial_guess=x0
            )

            # Retrieve solver data
            solver_status = {
                "completed": True,
                "success": solver.solution.success,
                "message": solver.solution.message,
                "grad_count": solver.convergence_history["grad_count"][-1],
                "func_count": solver.convergence_history["func_count"][-1],
                "func_count_total": solver.convergence_history["func_count_total"][-1],
                "norm_residual_last": solver.convergence_history["norm_residual"][-1],
                "norm_step_last": solver.convergence_history["norm_step"][-1],
            }

            # Collect data
            operation_point_data.append(pd.DataFrame([operation_point]))
            overall_data.append(pd.DataFrame([case_data["overall"]]))
            plane_data.append(flatten_dataframe(case_data["plane"]))
            cascade_data.append(flatten_dataframe(case_data["cascade"]))
            stage_data.append(flatten_dataframe(case_data["stage"]))
            solver_data.append(pd.DataFrame([solver_status]))
            solution_data.append(cs.scale_to_real_values(solver.solution.x, case_data))

        except Exception as e:
            print(
                f"An error occurred while computing the operation point {i+1}/{len(operation_points)}:\n\t{e}"
            )

            # Retrieve solver data
            solver_status = {"completed": False}

            # Collect data
            operation_point_data.append(pd.DataFrame([operation_point]))
            overall_data.append(pd.DataFrame([{}]))
            plane_data.append(pd.DataFrame([{}]))
            cascade_data.append(pd.DataFrame([{}]))
            stage_data.append(pd.DataFrame([{}]))
            solver_data.append(pd.DataFrame([solver_status]))
            solution_data.append([])

    # Dictionary to hold concatenated dataframes
    dfs = {
        "operation point": pd.concat(operation_point_data, ignore_index=True),
        "overall": pd.concat(overall_data, ignore_index=True),
        "plane": pd.concat(plane_data, ignore_index=True),
        "cascade": pd.concat(cascade_data, ignore_index=True),
        "stage": pd.concat(stage_data, ignore_index=True),
        "solver": pd.concat(solver_data, ignore_index=True),
    }

    # Add 'operation_point' column to each dataframe
    for sheet_name, df in dfs.items():
        df.insert(0, "operation_point", range(1, 1 + len(df)))

    # Write dataframes to excel
    filepath = os.path.join(output_dir, f"{filename}.xlsx")
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Performance data successfully written to {filepath}")


def initialize_solver(cascades_data, method, initial_guess=None):
    """
    Initialize a nonlinear system solver for solving a given problem.

    Parameters:
    ----------
    cascades_data : dict
        A dictionary containing data related to the problem.

    method : str
        The solver method to use.

    initial_guess : array-like or dict, optional
        The initial guess for the solver. If None, a default initial guess is generated.
        If a dictionary is provided, it should contain the following keys:
        - 'R': Initial guess for parameter R (float)
        - 'eta_tt': Initial guess for parameter eta_tt (float)
        - 'eta_ts': Initial guess for parameter eta_ts (float)
        - 'Ma_crit': Initial guess for parameter Mach_crit (float)

    Returns:
    -------
    solver : NonlinearSystemSolver
        A solver object configured to solve the nonlinear system problem.

    Raises:
    ------
    ValueError
        If the provided initial guess is not an array or dictionary.

    Notes:
    -----
    - If an initial guess is provided as an array, it will be used as is.
    - If no initial guess is provided, default values for R, eta_tt, eta_ts, and Ma_crit
      are used to generate an initial guess.
    - If an initial guess is provided as a dictionary, it should include the necessary
      parameters for the problem.

    """

    # Initialize problem object
    problem = CascadesNonlinearSystemProblem(cascades_data)

    # Define initial guess
    if isinstance(initial_guess, np.ndarray):
        pass  # Keep the initial guess as it is
    else:
        if initial_guess is None:
            print("No initial guess provided.")
            print("Generating initial guess from default parameters...")
            R = 0.5
            eta_tt = 0.9
            eta_ts = 0.8
            Ma_crit = 0.95
        elif isinstance(initial_guess, dict):
            R = initial_guess["R"]
            eta_tt = initial_guess["eta_tt"]
            eta_ts = initial_guess["eta_ts"]
            Ma_crit = initial_guess["Ma_crit"]
        else:
            raise ValueError("Initial guess must be an array or dictionary.")

        initial_guess = cs.generate_initial_guess(
            cascades_data, R, eta_tt, eta_ts, Ma_crit
        )

    # Always normalize initial guess
    initial_guess = cs.scale_to_normalized_values(initial_guess, cascades_data)

    # Initialize solver object
    solver = NonlinearSystemSolver(
        problem,
        initial_guess,
        method=method,
        tol=cascades_data["solver"]["tolerance"],
        max_iter=cascades_data["solver"]["max_iterations"],
        derivative_method=cascades_data["solver"]["derivative_method"],
        derivative_rel_step=cascades_data["solver"]["derivative_rel_step"],
        display=cascades_data["solver"]["display_progress"],
    )

    return solver


def compute_single_operation_point(
    boundary_conditions,
    cascades_data,
    initial_guess=None,
):
    """
    Compute an operation point for a given set of boundary conditions using multiple solver methods and initial guesses.

    Parameters:
    ----------
    boundary_conditions : dict
        A dictionary containing boundary conditions for the operation point.

    cascades_data : dict
        A dictionary containing data related to the cascades problem.

    initial_guess : array-like or dict, optional
        The initial guess for the solver. If None, default initial guesses are used.
        If provided, the initial guess should not be scaled (it is scaled internally)

    Returns:
    -------
    solution : object
        The solution object containing the results of the operation point calculation.

    Notes:
    -----
    - This function attempts to compute an operation point for a given set of boundary
      conditions using various solver methods and initial guesses before giving up.
    - The boundary_conditions dictionary should include the necessary parameters for the
      problem.
    - The initial_guess can be provided as an array-like object or a dictionary. If None,
      default values are used for initial guesses.
    - The function iteratively tries different solver methods, including user-specified
      methods and the Levenberg-Marquardt method, to solve the problem.
    - It also attempts solving with a heuristic initial guess and explores different
      initial guesses from parameter arrays.
    - The function prints information about the solver method and any failures during the
      computation.
    - If successful convergence is achieved, the function returns the solution object.
    - If all attempts fail to converge, a warning message is printed.

    """

    # Calculate performance at given boundary conditions with given geometry
    cascades_data["BC"] = boundary_conditions

    # Attempt solving with the specified method
    method = cascades_data["solver"]["method"]
    print(f"Trying to solve the problem using {name_map[method]} method")
    solver = initialize_solver(cascades_data, method, initial_guess=initial_guess)
    try:
        solution = solver.solve()
        success = solution.success
    except Exception as e:
        print(f"Error during solving: {e}")
        success = False
    if not success:
        print(f"Solution failed with {name_map[method]} method")

    # Attempt solving with Lavenberg-Marquardt method
    if method != "lm" and not success:
        method = "lm"
        print(f"Trying to solve the problem using {name_map[method]} method")
        solver = initialize_solver(cascades_data, method, initial_guess=initial_guess)
        try:
            solution = solver.solve()
            success = solution.success
        except Exception as e:
            print(f"Error during solving: {e}")
            success = False
        if not success:
            print(f"Solution failed with {name_map[method]} method")

    # TODO: Attempt solving with optimization algorithms?

    # Attempt solving with a heuristic initial guess
    if isinstance(initial_guess, np.ndarray) and not success:
        method = "lm"
        print("Trying to solve the problem with a new initial guess")
        solver = initialize_solver(cascades_data, method, initial_guess=None)
        try:
            solution = solver.solve()
            success = solution.success
        except Exception as e:
            print(f"Error during solving: {e}")
            success = False

    # Attempt solving using different initial guesses
    if not success:
        N = 11
        x0_arrays = {
            "R": np.linspace(0.0, 0.95, N),
            "eta_ts": np.linspace(0.6, 0.9, N),
            "eta_tt": np.linspace(0.7, 1.0, N),
            "Ma_crit": np.linspace(0.9, 0.9, N),
        }

        for i in range(N):
            x0 = {key: values[i] for key, values in x0_arrays.items()}
            print(f"Trying to solve the problem with a new initial guess")
            print_dict(x0)
            solver = initialize_solver(cascades_data, method, initial_guess=x0)
            try:
                solution = solver.solve()
                success = solution.success
            except Exception as e:
                print(f"Error during solving: {e}")
                success = False
            if not success:
                print(f"Solution failed with {name_map[method]} method")

        if not success:
            print("WARNING: All attempts failed to converge")
            solution = False
            # TODO: Add messages to Log file

    return solver


def find_closest_operation_point(current_op_point, operation_points, solution_data):
    """
    Find the solution vector and index of the closest operation point in the historical data.

    Parameters
    ----------
    current_op_point : dict
        The current operation point we want to compare.
    operation_points : list of dict
        A list of historical operation points to search through.
    solution_data : list
        A list of solution vectors corresponding to each operation point.

    Returns
    -------
    tuple
        A tuple containing the closest solution vector and the one-based index of the closest operation point.

    """
    min_distance = float("inf")
    closest_point_x = None
    closest_index = None

    for i, op_point in enumerate(operation_points):
        distance = get_operation_point_distance(current_op_point, op_point)
        if distance < min_distance:
            min_distance = distance
            closest_point_x = solution_data[i]
            closest_index = i

    return closest_point_x, closest_index


def get_operation_point_distance(point_1, point_2, delta=1e-8):
    """
    Calculate the normalized distance between two operation points, with special consideration
    for angle measurements and prevention of division by zero for very small values.

    Parameters
    ----------
    point_1 : dict
        First operation point with numeric values.
    point_2 : dict
        Second operation point with numeric values.
    delta : float, optional
        A small constant to prevent division by zero. Default is 1e-8.

    Returns
    -------
    float
        The calculated normalized distance.
    """
    deviation_array = []
    for key in point_1:
        if isinstance(point_1[key], (int, float)) and key in point_2:
            value_1 = point_1[key]
            value_2 = point_2[key]

            if key == "alpha_in":
                # Handle angle measurements with absolute scale normalization
                deviation = np.abs(value_1 - value_2) / (np.pi / 2)
            else:
                # Compute the relative difference with protection against division by zero
                max_val = max(abs(value_1), abs(value_2), delta)
                deviation = abs(value_1 - value_2) / max_val

            deviation_array.append(deviation)

    # Calculate the two-norm of the deviations
    return np.linalg.norm(deviation_array)


def generate_operation_points(performance_map):
    """
    Generates a list of dictionaries representing all possible combinations of
    operation points from a given performance map. The performance map is a
    dictionary where keys represent parameter names and values are the ranges
    of values for those parameters. The function ensures that the combinations
    are generated such that the parameters related to pressure ('p0_in' and
    'p_out') are the last ones to vary, effectively making them the first
    parameters to sweep through in the operation points.

    Parameters:
    - performance_map (dict): A dictionary with parameter names as keys and
      lists of parameter values as values.

    Returns:
    - operation_points (list of dict): A list of dictionaries, each representing
      a unique combination of parameters from the performance_map.
    """
    # Make sure all values in the performance_map are iterables
    performance_map = {k: ensure_iterable(v) for k, v in performance_map.items()}

    # # Reorder performance map keys to first sweep is always through pressure
    # priority_keys = ["p0_in", "p_out"]
    # other_keys = [k for k in performance_map.keys() if k not in priority_keys]
    # keys_order = other_keys + priority_keys
    # performance_map = {
    #     k: performance_map[k] for k in keys_order if k in performance_map
    # }

    # Create all combinations of operation points
    keys, values = zip(*performance_map.items())
    operation_points = [
        dict(zip(keys, combination)) for combination in itertools.product(*values)
    ]

    return operation_points


def validate_operation_point(op_point):
    """
    Validates that an operation point has exactly the required fields:
    'fluid_name', 'p0_in', 'T0_in', 'p_out', 'alpha_in', 'omega'.

    Parameters:
    - op_point: dict
        A dictionary representing an operation point.

    Raises:
    - ValueError: If the dictionary does not contain the required fields or contains extra fields.
    """
    REQUIRED_FIELDS = {"fluid_name", "p0_in", "T0_in", "p_out", "alpha_in", "omega"}
    fields = set(op_point.keys())
    if fields != REQUIRED_FIELDS:
        missing = REQUIRED_FIELDS - fields
        extra = fields - REQUIRED_FIELDS
        raise ValueError(
            f"Operation point validation error: "
            f"Missing fields: {missing}, Extra fields: {extra}"
        )



class CascadesNonlinearSystemProblem(NonlinearSystemProblem):
    def __init__(self, cascades_data):
        cs.calculate_number_of_stages(cascades_data)
        cs.update_fixed_params(cascades_data)
        cs.check_geometry(cascades_data)

        # Define reference mass flow rate
        v0 = cascades_data["fixed_params"]["v0"]
        d_in = cascades_data["fixed_params"]["d0_in"]
        A_in = cascades_data["geometry"]["A_in"][0]
        m_ref = A_in * v0 * d_in  # Reference mass flow rate
        cascades_data["fixed_params"]["m_ref"] = m_ref

        self.cascades_data = cascades_data

    def get_values(self, vars):
        residuals = cs.evaluate_cascade_series(vars, self.cascades_data)

        return residuals


class CascadesOptimizationProblem(OptimizationProblem):
    def __init__(self, cascades_data, R, eta_tt, eta_ts, Ma_crit, x0=None):
        cs.calculate_number_of_stages(cascades_data)
        cs.update_fixed_params(cascades_data)
        cs.check_geometry(cascades_data)

        # Define reference mass flow rate
        v0 = cascades_data["fixed_params"]["v0"]
        d_in = cascades_data["fixed_params"]["d0_in"]
        A_in = cascades_data["geometry"]["A_in"][0]
        m_ref = A_in * v0 * d_in  # Reference mass flow rate
        cascades_data["fixed_params"]["m_ref"] = m_ref

        if x0 == None:
            x0 = cs.generate_initial_guess(cascades_data, R, eta_tt, eta_ts, Ma_crit)
        self.x0 = cs.scale_to_normalized_values(x0, cascades_data)
        self.cascades_data = cascades_data

    def get_values(self, vars):
        residuals = cs.evaluate_cascade_series(vars, self.cascades_data)
        self.f = 0
        self.c_eq = residuals
        self.c_ineq = None
        objective_and_constraints = self.merge_objective_and_constraints(
            self.f, self.c_eq, self.c_ineq
        )

        return objective_and_constraints

    def get_bounds(self):
        n_cascades = self.cascades_data["geometry"]["n_cascades"]
        lb, ub = cs.get_dof_bounds(n_cascades)
        bounds = [(lb[i], ub[i]) for i in range(len(lb))]
        return bounds

    def get_n_eq(self):
        return self.get_number_of_constraints(self.c_eq)

    def get_n_ineq(self):
        return self.get_number_of_constraints(self.c_ineq)
