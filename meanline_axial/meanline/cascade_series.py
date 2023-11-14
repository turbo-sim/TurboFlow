import numpy as np
import pandas as pd
from scipy import optimize
import CoolProp as CP
from ..properties import FluidCoolProp_2Phase
from . import loss_model as lm
from . import deviation_model as dm
from scipy.optimize._numdiff import approx_derivative

from .. import math
from .. import utilities as util


# Keys of the information that should be stored in results
KEYS_KINEMATIC = [
    "u",
    "v",
    "v_m",
    "v_t",
    "alpha",
    "w",
    "w_m",
    "w_t",
    "beta",
]

KEYS_PROPS_STATIC = ["p", "T", "h", "s", "d", "Z", "a", "mu", "k", "cp", "cv", "gamma"]
KEYS_PROPS_STAG_ABS = [f"{key}0" for key in KEYS_PROPS_STATIC]
KEYS_PROPS_STAG_REL = [f"{key}0_rel" for key in KEYS_PROPS_STATIC]
KEYS_LOSSES = lm.KEYS_LOSSES

KEYS_PLANE = (
    KEYS_KINEMATIC
    + KEYS_PROPS_STATIC
    + KEYS_PROPS_STAG_ABS
    + KEYS_PROPS_STAG_REL
    + KEYS_LOSSES
    + [
        "Ma",
        "Ma_rel",
        "Re",
        "mass_flow",
        "rothalpy",
        "blockage",
    ]
)
"""List of keys for the plane performance metrics of the turbine. 
This list is used to ensure the structure of the 'plane' dictionary in various functions."""


KEYS_CASCADE = [
    "loss_total",
    "loss_profile",
    "loss_clearance",
    "loss_secondary",
    "loss_trailing",
    "loss_incidence",
    "dh_s",
    "Ma_crit",
    "mass_flow_crit",
    "d_crit",
    "w_crit",
    "p_crit",
    "beta_crit",
    "incidence",
    "density_correction",
]
"""List of keys for the cascade performance metrics of the turbine. 
This list is used to ensure the structure of the 'cascade' dictionary in various functions."""

KEYS_OVERALL = [
    "PR_tt",
    "PR_ts",
    "mass_flow_rate",
    "efficiency_tt",
    "efficiency_ts",
    "efficiency_ts_drop_kinetic",
    "efficiency_ts_drop_losses",
    "power",
    "torque",
    "angular_speed",
    "exit_flow_angle",
    "exit_velocity",
    "spouting_velocity",
    "last_blade_velocity",
    "blade_jet_ratio",
    "h0_in",
    "h0_out",
    "h_out_s",
]
"""List of keys for the overall performance metrics of the turbine. 
This list is used to ensure the structure of the 'overall' dictionary in various functions."""

KEYS_STAGE = [
    "reaction",
]
"""List of keys for the stage performance metrics of the turbine. 
This list is used to ensure the structure of the 'stage' dictionary in various functions."""


def evaluate_cascade_series(
    variables,
    boundary_conditions,
    geometry,
    fluid,
    model_options,
    reference_values,
):
    """
    Compute the performance of an axial turbine by evaluating a series of cascades.

    This function evaluates the each evaluating each cascade in the series.
    It begins by loading essential inputs such as geometry, boundary conditions, and reference values, which are integral to the assessment process.

    The evaluation proceeds cascade by cascade, employing two key functions in a structured sequence:

    1. `evaluate_cascade`: Compute flow at the inlet station, throat, and exit planes of each cascade. In addition, this function evaluates
    the turbine performance at the critical point, which is essential to model the correct behavior under choking conditions.
    2. `evaluate_cascade_interspace`: Calculate the flow conditions after the interspace between consecutive cascades to obtain conditions at the inlet of the next cascade.

    As the function iterates through each cascade, it accumulates data in a structured format. The results are organized into a dictionary that includes:

    - 'cascade': Contains data specific to each cascade in the series, including loss coefficients and critical conditions.
    - 'plane': Contains data specific to each flow station, including thermodynamic properties and velocity triangles.
    - 'stage': Contains data specific to each turbine stage, including degree of reaction.
    - 'overall': Summarizes the overall performance of the turbine, including total mass flow rate, efficiency, power output, and other key performance indicators.
    - 'residuals': Summarizes the mismatch in the nonlinear system of equations used to model the turbine.

    .. note::

        The output of this function can only be regarded as a physically meaningful solution when the equations are fully closed (i.e., all residuals are close to zero).
        Therefore, this function is intended to be used within a root-finding or optimization algorithm that systematically adjusts the input variables to drive the residuals to zero and close the system of equations.

    Parameters
    ----------
    Parameters description here

    Returns
    -------
    Returns description here


    """
    # Load variables
    number_of_cascades = geometry["number_of_cascades"]
    h0_in = boundary_conditions["h0_in"]
    s_in = boundary_conditions["s_in"]
    alpha_in = boundary_conditions["alpha_in"]
    angular_speed = boundary_conditions["omega"]

    # Load reference_values
    h_out_s = reference_values["h_out_s"]  # FIXME: bad plaement of h_out_s variable?
    v0 = reference_values["v0"]
    s_range = reference_values["s_range"]
    s_min = reference_values["s_min"]
    angle_range = reference_values["angle_range"]
    angle_min = reference_values["angle_min"]

    # Initialize results structure
    results = {
        "plane": pd.DataFrame(columns=KEYS_PLANE),
        "cascade": pd.DataFrame(columns=KEYS_CASCADE),
        "stage": {},
        "overall": {},
        "geometry": geometry,
        "reference_values": reference_values,
        "boundary_conditions": boundary_conditions,
    }

    # initialize residual arrays
    residuals = {}

    # Rename turbine inlet velocity
    v_in = variables["v_in"] * v0

    for i in range(number_of_cascades):
        # Update angular speed
        angular_speed_cascade = angular_speed * (i % 2)

        # update geometry for current cascade #FIXME for new geometry model
        geometry_cascade = {
            key: values[i]
            for key, values in geometry.items()
            if key not in ["number_of_cascades", "number_of_stages"]
        }

        # Rename vairables
        cascade = "_" + str(i + 1)
        w_throat = variables["w_throat" + cascade] * v0
        w_out = variables["w_out" + cascade] * v0
        s_throat = variables["s_throat" + cascade] * s_range + s_min
        s_out = variables["s_out" + cascade] * s_range + s_min
        beta_out = variables["beta_out" + cascade] * angle_range + angle_min
        v_crit_in = variables["v*_in" + cascade]
        w_crit_out = variables["w*_out" + cascade]
        s_crit_out = variables["s*_out" + cascade]

        # Evaluate current cascade
        cascade_inlet_input = {
            "h0": h0_in,
            "s": s_in,
            "alpha": alpha_in,
            "v": v_in,
        }
        cascade_throat_input = {"w": w_throat, "s": s_throat}
        cascade_exit_input = {
            "w": w_out,
            "beta": beta_out,
            "s": s_out,
        }
        critical_cascade_input = {
            "v*_in": v_crit_in,
            "w*_out": w_crit_out,
            "s*_out": s_crit_out,
        }
        cascade_residuals = evaluate_cascade(
            cascade_inlet_input,
            cascade_throat_input,
            cascade_exit_input,
            critical_cascade_input,
            fluid,
            geometry_cascade,
            angular_speed_cascade,
            results,
            model_options,
            reference_values,
        )

        # Add cascade residuals to residual arrays
        cascade_residuals = util.add_string_to_keys(cascade_residuals, f"_{i+1}")
        residuals.update(cascade_residuals)

        # Calculate input of next cascade (Assume no change in density)
        if i != number_of_cascades - 1:
            (
                h0_in,
                s_in,
                alpha_in,
                v_in,
            ) = evaluate_cascade_interspace(
                results["plane"]["h0"].values[-1],
                results["plane"]["v_m"].values[-1],
                results["plane"]["v_t"].values[-1],
                results["plane"]["d"].values[-1],
                geometry_cascade["radius_mean_out"],
                geometry_cascade["A_out"],
                geometry["radius_mean_in"][i + 1],
                geometry["A_in"][i + 1],
                fluid,
            )

    # Add exit pressure error to residuals
    p_calc = results["plane"]["p"].values[-1]
    p_error = (p_calc - boundary_conditions["p_out"]) / boundary_conditions["p0_in"]
    residuals["p_out"] = p_error

    # Additional calculations
    loss_fractions = compute_efficiency_breakdown(results)
    results["cascade"] = pd.concat([results["cascade"], loss_fractions], axis=1)

    # Compute stage performance
    results["stage"] = pd.DataFrame([compute_stage_performance(results)])

    # Compute overall perfrormance
    results["overall"] = pd.DataFrame([compute_overall_performance(results)])

    # Store all residuals for export
    results["residuals"] = residuals

    # Store the input variables
    results["independent_variables"] = variables

    # Retain only variables defined per cascade
    geom_cascades = {
        key: value
        for key, value in geometry.items()
        if len(util.ensure_iterable(value)) == number_of_cascades
    }
    results["geometry"] = pd.DataFrame([geom_cascades])

    return results


def evaluate_cascade(
    cascade_inlet_input,
    cascade_throat_input,
    cascade_exit_input,
    critical_cascade_input,
    fluid,
    geometry,
    angular_speed,
    results,
    model_options,
    reference_values,
):
    """
    Evaluate the performance of a single cascade within an axial turbine.

    This function evaluates the performance of a single turbine cascade. The process involves several key steps, each utilizing different sub-functions:

    1. `evaluate_cascade_inlet`: Assesses the inlet conditions of the cascade.
    2. `evaluate_cascade_exit`: Evaluates the exit conditions at both the throat and exit stations.
    3. `evaluate_cascade_critical`: Determines the critical conditions within the cascade.
    4. `compute_choking_residual`: Determines whether the turbine is choked or not depending on the operating conditions and the choking condition specified by the user.

    The function returns a dictionary of residuals that includes the mass balance error at both the throat and exit, loss coefficient errors,
    and the residuals related to the critical state and choking condition.

    Parameters
    ----------
    # Parameters description here

    Returns
    -------
    dict
        A dictionary containing the residuals of the evaluation, which are key indicators of the model's accuracy and physical realism.
    """

    # Define model options
    # TODO Add warnings that some settings have been assumed. This is a dangerous silent behavior as it is now
    # TODO It would make sense to define default values for these options at a higher level, for instance after processing the configuration file
    # TODO an advantage of the approach above is that it is possible to print a warning that will not be shown for each iteration of the solvers
    # loss_model = model_options.get("loss_model", "benner")
    # choking_condition = model_options.get("choking_condition", "deviation")
    # deviation_model = model_options.get("deviation_model", "aungier")
    loss_model = model_options["loss_model"]
    choking_condition = model_options["choking_condition"]
    deviation_model = model_options["deviation_model"]

    # Load reference values
    mass_flow_reference = reference_values["mass_flow_ref"]

    # Evaluate inlet plane
    inlet_plane = evaluate_cascade_inlet(
        cascade_inlet_input, fluid, geometry, angular_speed
    )

    # Evaluate throat plane
    # TODO discuss how to model the effect of "displacement_thickness" correctly
    # TODO only at the throat, at the throat and the exit plane?
    # TODO involve Simone
    # TODO model does not converge if zero blade blockage at the exit plane. Why? Discontinuity?
    cascade_throat_input["rothalpy"] = inlet_plane["rothalpy"]
    cascade_throat_input["beta"] = geometry["metal_angle_te"]
    throat_plane, _ = evaluate_cascade_exit(
        cascade_throat_input,
        fluid,
        geometry,
        inlet_plane,
        angular_speed,
        model_options["throat_blockage"],
        loss_model,
        geometry["radius_mean_throat"],
        geometry["A_throat"],
    )

    # Evaluate exit plane
    cascade_exit_input["rothalpy"] = inlet_plane["rothalpy"]
    exit_plane, loss_dict = evaluate_cascade_exit(
        cascade_exit_input,
        fluid,
        geometry,
        inlet_plane,
        angular_speed,
        model_options["throat_blockage"],
        loss_model,
        geometry["radius_mean_out"],
        geometry["A_out"],
    )

    # Evaluate isentropic enthalpy change
    props_is = fluid.get_props(CP.PSmass_INPUTS, exit_plane["p"], inlet_plane["s"])
    dh_is = exit_plane["h"] - props_is["h"]

    # Evaluate critical state
    # TODO: Pass x_crit as dicitonary to evaluate_lagrangian_gradient?
    critical_cascade_input["h0_in"] = cascade_inlet_input["h0"]
    critical_cascade_input["s_in"] = cascade_inlet_input["s"]
    critical_cascade_input["alpha_in"] = cascade_inlet_input["alpha"]
    x_crit = np.array(
        [
            critical_cascade_input["v*_in"],
            critical_cascade_input["w*_out"],
            critical_cascade_input["s*_out"],
        ]
    )

    # TODO: Wouldnt it make more sense to rename the function "compute_residuals_critical" as "evaluate_cascade_critical"?
    # TODO: then we would have a sequence of calls to: evaluate_cascade_inlet, evaluate_cascade_exit, evaluate_cascade_critical
    residuals_critical, critical_state = evaluate_cascade_critical(
        x_crit,
        critical_cascade_input,
        fluid,
        geometry,
        angular_speed,
        model_options,
        reference_values,
    )

    # Evaluate the choking condition equation
    # TODO move to its own function
    choking_functions = {
        "deviation": lambda: compute_residual_flow_angle(
            geometry, critical_state, throat_plane, exit_plane, deviation_model
        ),
        "mach_critical": lambda: compute_residual_mach_throat(
            critical_state["Ma_rel"], exit_plane["Ma_rel"], throat_plane["Ma_rel"]
        ),
        "mach_unity": lambda: compute_residual_mach_throat(
            1.00, exit_plane["Ma_rel"], throat_plane["Ma_rel"]
        ),
    }

    # Evaluate the choking condition equation
    if choking_condition in choking_functions:
        choking_residual, density_correction = choking_functions[choking_condition]()
    else:
        options = ", ".join(f"'{k}'" for k in choking_functions.keys())
        raise ValueError(
            f"Invalid choking_condition: '{choking_condition}'. Available options: {options}"
        )

    # Create dictionary with equation residuals
    mass_error_throat = inlet_plane["mass_flow"] - throat_plane["mass_flow"]
    mass_error_exit = inlet_plane["mass_flow"] - exit_plane["mass_flow"]
    residuals = {
        "loss_error_throat": throat_plane["loss_error"],
        "loss_error_exit": exit_plane["loss_error"],
        "mass_error_throat": mass_error_throat / mass_flow_reference,
        "mass_error_exit": mass_error_exit / mass_flow_reference,
        **residuals_critical,
        choking_condition: choking_residual,
    }

    # Return plane data in dataframe
    # TODO: add critical state as another plane?
    planes = [inlet_plane, throat_plane, exit_plane]
    for plane in planes:
        results["plane"].loc[len(results["plane"])] = plane

    # Return cascade data in dataframe
    # TODO: how much critical point data do we want to retrieve?
    cascade_data = {
        **loss_dict,
        "dh_s": dh_is,
        "Ma_crit": critical_state["Ma_rel"],
        "mass_flow_crit": critical_state["mass_flow"],
        "w_crit": critical_state["w"],
        "d_crit": critical_state["d"],
        "p_crit": critical_state["p"],
        "beta_crit": critical_state["beta"],
        "incidence": inlet_plane["beta"] - geometry["metal_angle_le"],
        "density_correction": density_correction,
    }
    results["cascade"].loc[len(results["cascade"])] = cascade_data

    return residuals


def evaluate_cascade_inlet(cascade_inlet_input, fluid, geometry, angular_speed):
    """
    Evaluate the inlet plane parameters of a cascade including velocity triangles,
    thermodynamic properties, and flow characteristics.

    This function calculates various parameters at the inlet of a cascade based on the input geometry,
    fluid properties, and flow conditions. It computes velocity triangles, static and stagnation properties,
    Reynolds and Mach numbers, and the mass flow rate at the inlet.

    Parameters
    ----------
    cascade_inlet_input : dict
        Input parameters specific to the cascade inlet, including stagnation enthalpy ('h0'),
        entropy ('s'), absolute velocity ('v'), and flow angle ('alpha').
    fluid : object
        A fluid object with methods for thermodynamic property calculations.
    geometry : dict
        Geometric parameters of the cascade such as radius at the mean inlet ('radius_mean_in'),
        chord length, and inlet area ('A_in').
    angular_speed : float
        Angular speed of the cascade.

    Returns
    -------
    dict
        A dictionary of calculated parameters at the cascade inlet.
    """
    # Load cascade inlet input
    h0 = cascade_inlet_input["h0"]
    s = cascade_inlet_input["s"]
    v = cascade_inlet_input["v"]
    alpha = cascade_inlet_input["alpha"]

    # Load geometry
    radius = geometry["radius_mean_in"]
    chord = geometry["chord"]
    area = geometry["A_in"]

    # Calculate velocity triangles
    blade_speed = radius * angular_speed
    velocity_triangle = evaluate_velocity_triangle_in(blade_speed, v, alpha)
    w = velocity_triangle["w"]
    w_m = velocity_triangle["w_m"]

    # Calculate static properties
    h = h0 - 0.5 * v**2
    static_properties = fluid.get_props(CP.HmassSmass_INPUTS, h, s)
    rho = static_properties["d"]
    mu = static_properties["mu"]
    a = static_properties["a"]

    # Calculate stagnation properties
    stagnation_properties = fluid.get_props(CP.HmassSmass_INPUTS, h0, s)
    stagnation_properties = util.add_string_to_keys(stagnation_properties, "0")

    # Calculate relative stagnation properties
    h0_rel = h + 0.5 * w**2
    relative_stagnation_properties = fluid.get_props(CP.HmassSmass_INPUTS, h0_rel, s)
    relative_stagnation_properties = util.add_string_to_keys(
        relative_stagnation_properties, "0_rel"
    )

    # Calculate mach, reynolds and mass flow rate for cascade inlet
    Ma = v / a
    Ma_rel = w / a
    Re = rho * w * chord / mu
    m = rho * w_m * area
    rothalpy = h0_rel - 0.5 * blade_speed**2

    # Store results in dictionary
    plane = {
        **velocity_triangle,
        **static_properties,
        **stagnation_properties,
        **relative_stagnation_properties,
        **{key: np.nan for key in KEYS_LOSSES},
        "Ma": Ma,
        "Ma_rel": Ma_rel,
        "Re": Re,
        "mass_flow": m,
        "rothalpy": rothalpy,
        "blockage": np.nan,
    }

    return plane


def evaluate_cascade_exit(
    cascade_exit_input,
    fluid,
    geometry,
    inlet_plane,
    angular_speed,
    blockage,
    loss_model,
    radius,
    area,
):
    """
    Evaluate the parameters at the exit (or throat) of a cascade including velocity triangles,
    thermodynamic properties, and loss coefficients.

    This function calculates various parameters at the exit of a cascade based on the input geometry,
    fluid properties, and flow conditions. It computes velocity triangles, static and stagnation
    properties, Reynolds and Mach numbers, mass flow rate, and loss coefficients. The calculations
    of the mass flow rate considers the blockage induced by the boundary layer displacement thickness.

    Parameters
    ----------
    cascade_exit_input : dict
        Input parameters specific to the cascade exit, including relative velocity ('w'),
        flow angle ('beta'), entropy ('s'), and rothalpy.
    fluid : object
        A fluid object with methods for thermodynamic property calculations.
    geometry : dict
        Geometric parameters of the cascade such as chord length, opening, and area.
    inlet_plane : dict
        Parameters at the inlet plane of the cascade (needed for loss model calculations).
    angular_speed : float
        Angular speed of the cascade.
    blockage : float
        Blockage factor at the cascade exit.
    loss_model : str
        A the loss model used for calculating loss coefficients.
    radius : float
        Mean radius at the cascade exit.
    area : float
        Area of the cascade exit plane.

    Returns
    -------
    tuple
        A tuple containing:

        - plane (dict): A dictionary of calculated parameters at the cascade exit including
          velocity triangles, thermodynamic properties, Mach and Reynolds numbers, mass flow rate,
          and loss coefficients.
        - loss_dict (dict): A dictionary of loss coefficients as calculated by the loss model.

    Warnings
    --------
    The current implementation of this calculation has limitations regarding the relationship between
    the throat and exit areas. It does not function correctly unless these areas are related according
    to the cosine rule. Specifically, issues arise when:

    1. The blockage factor at the throat and the exit are not the same. The code may converge for minor
       discrepancies (about <1%), but larger differences lead to convergence issues.
    2. The "throat_location_fraction" parameter is less than one, implying a change in the throat radius
       or height relative to the exit plane.

    These limitations restrict the code's application to cases with constant blade radius or height, or
    when blockage factors at the throat and exit planes are identical. Future versions aim to address
    these issues, enhancing the code's generality for varied geometrical configurations and differing
    blockage factors at the throat and exit planes.

    """

    # Load cascade exit variables
    w = cascade_exit_input["w"]
    beta = cascade_exit_input["beta"]
    s = cascade_exit_input["s"]
    rothalpy = cascade_exit_input["rothalpy"]

    # Load geometry
    # radius = geometry["radius_mean_out"]
    # area = geometry["A_out"]
    # print("radius", geometry["radius_mean_out"], geometry["radius_mean_throat"])
    # print("area", geometry["A_out"], geometry["A_throat"])
    chord = geometry["chord"]
    opening = geometry["opening"]
    # TODO: we should have flexibility to specify the throat area
    # TODO: Roberto: I did some tests on with the throat area calculations
    # TODO:   1. The code does not converge well if blockage factor at the throat at and the exit is not the same. Why? The code converges for some small differences, but 1-2% is already too much
    # TODO:   2. The code does not converge well if the new geometry input "throat_location_fraction" is not one (meaning that the throat radius is the same as the exit radius)
    # TODO: It seems that both limitations are related to changes in the effective throat area with respect to the exit area
    # TODO: In some cases these factors are not a problem when using the choking condition "mach_critical"
    # TODO: This makes me suspect that the way in which we are handling the deviation model residual is giving problems.
    # TODO: The code should work for cases when the throat are is not exactly given by the cosine rule

    # Calculate velocity triangles
    blade_speed = angular_speed * radius
    velocity_triangle = evaluate_velocity_triangle_out(blade_speed, w, beta)
    v = velocity_triangle["v"]
    w_m = velocity_triangle["w_m"]

    # Calculate static properties
    h = rothalpy + 0.5 * blade_speed**2 - 0.5 * w**2
    static_properties = fluid.get_props(CP.HmassSmass_INPUTS, h, s)
    rho = static_properties["d"]
    mu = static_properties["mu"]
    a = static_properties["a"]

    # Calculate stagnation properties
    h0 = h + 0.5 * v**2
    stagnation_properties = fluid.get_props(CP.HmassSmass_INPUTS, h0, s)
    stagnation_properties = util.add_string_to_keys(stagnation_properties, "0")

    # Calculate relatove stagnation properties
    h0_rel = h + 0.5 * w**2
    relative_stagnation_properties = fluid.get_props(CP.HmassSmass_INPUTS, h0_rel, s)
    relative_stagnation_properties = util.add_string_to_keys(
        relative_stagnation_properties, "0_rel"
    )

    # Calculate mach, reynolds and mass flow rate for cascade inlet
    Ma = v / a
    Ma_rel = w / a
    Re = rho * w * chord / mu
    rothalpy = h0_rel - 0.5 * blade_speed**2
    # TODO: is rothalpy necessary? See calculations above

    # Compute mass flow rate
    blockage_factor = compute_blockage_boundary_layer(blockage, Re, chord, opening)
    mass_flow = rho * w_m * area * (1 - blockage_factor)

    # Evaluate loss coefficient
    # TODO: why not give all variables to the loss model?
    # Introduce safeguard to prevent negative values for Re and Ma
    # Useful to avoid invalid operations during convergence
    min_val = 1e-3
    loss_model_input = {
        "geometry": geometry,
        "loss_model": loss_model,
        "flow": {
            "p0_rel_in": inlet_plane["p0_rel"],
            "p0_rel_out": relative_stagnation_properties["p0_rel"],
            "p_in": inlet_plane["p"],
            "p_out": static_properties["p"],
            "beta_out": beta,
            "beta_in": inlet_plane["beta"],
            "Ma_rel_in": max(min_val, inlet_plane["Ma_rel"]),
            "Ma_rel_out": max(min_val, Ma_rel),
            "Re_in": max(min_val, inlet_plane["Re"]),
            "Re_out": max(min_val, Re),
            "gamma_out": static_properties["gamma"],
        },
    }

    # Compute loss coefficient from loss model
    loss_dict = lm.evaluate_loss_model(loss_model, loss_model_input)

    # Store results in dictionary
    plane = {
        **velocity_triangle,
        **static_properties,
        **stagnation_properties,
        **relative_stagnation_properties,
        **loss_dict,
        "Ma": Ma,
        "Ma_rel": Ma_rel,
        "Re": Re,
        "mass_flow": mass_flow,
        "displacement_thickness": np.nan,  # Not relevant for exit/throat plane
        "rothalpy": rothalpy,
        "blockage": blockage_factor,
    }

    return plane, loss_dict


def evaluate_cascade_interspace(
    h0_exit,
    v_m_exit,
    v_t_exit,
    rho_exit,
    radius_exit,
    area_exit,
    radius_inlet,
    area_inlet,
    fluid,
):
    """
    Calculate the inlet conditions for the next cascade based on the exit conditions of the previous cascade.

    This function computes the inlet thermodynamic and velocity conditions the next cascade using the exti conditions
    from the previous cascade and the flow equations for the interspace between cascades.

    Assumptions:

    1. No heat transfer (conservation of stagnation enthalpy)
    2. No friction (conservation of angular momentum)
    3. No density variation (incompressible limit)


    Parameters
    ----------
    h0_exit : float
        Stagnation enthalpy at the exit of the previous cascade.
    v_m_exit : float
        Meridional component of velocity at the exit of the previous cascade.
    v_t_exit : float
        Tangential component of velocity at the exit of the previous cascade.
    rho_exit : float
        Fluid density at the exit of the previous cascade.
    radius_exit : float
        Radius at the exit of the previous cascade.
    area_exit : float
        Flow area at the exit of the previous cascade.
    radius_inlet : float
        Radius at the inlet of the next cascade.
    area_inlet : float
        Flow area at the inlet of the next cascade.
    fluid : object
        A fluid object with methods for thermodynamic property calculations (e.g., CoolProp fluid).

    Returns
    -------
    tuple
        A tuple containing:

        - h0_in (float): Stagnation enthalpy at the inlet of the next cascade.
        - s_in (float): Entropy at the inlet of the next cascade.
        - alpha_in (float): Flow angle at the inlet of the next cascade (in radians).
        - v_in (float): Magnitude of the velocity vector at the inlet of the next cascade.

    Warnings
    --------
    The assumption of constant density leads to a small inconsistency in the thermodynamic state,
    manifesting as a slight variation in entropy across the interspace. In future versions of the
    code, it is recommended to evaluate the interspace with a 1D model for the flow in annular ducts
    to improve accuracy and consistency in the analysis.
    """

    # Assume no heat transfer
    h0_in = h0_exit

    # Assume no friction (angular momentum is conserved)
    v_t_in = v_t_exit * radius_exit / radius_inlet

    # Assume density variation is negligible
    v_m_in = v_m_exit * area_exit / area_inlet

    # Compute velocity vector
    v_in = np.sqrt(v_t_in**2 + v_m_in**2)
    alpha_in = math.arctand(v_t_in / v_m_in)

    # Compute thermodynamic state
    h_in = h0_in - 0.5 * v_in**2
    rho_in = rho_exit
    stagnation_properties = fluid.get_props(CP.DmassHmass_INPUTS, rho_in, h_in)
    s_in = stagnation_properties["s"]

    return h0_in, s_in, alpha_in, v_in


def evaluate_cascade_critical(
    x_crit,
    critical_cascade_input,
    fluid,
    geometry,
    angular_speed,
    model_options,
    reference_values,
):
    """
    Compute the gradient of the Lagrange function of the critical mass flow rate and the residuals of mass
    conservation and loss computation equations at the throat.

    This function addresses the determination of the critical point in a cascade, which is defined as the
    point of maximum mass flow rate for a given set of inlet conditions. Traditional approaches usually
    treat this as an optimization problem, seeking to maximize the flow rate directly. However, this
    function adopts an alternative strategy by converting the optimality condition into a set of equations.
    These equations involve the gradient of the Lagrangian associated with the critical mass flow rate
    and include equality constraints necessary to close the problem.

    By transforming the problem into a system of equations, this approach allows the evaluation of the critical
    point without directly solving an optimization problem. One significant advantage of this
    equation-oriented method is that it enables the coupling of these critical condition equations with the
    other modeling equations. This integrated system of equations can then be efficiently solved using gradient-based
    root finding algorithms (e.g., Newton-Raphson solvers).

    Such a coupled solution strategy, as opposed to segregated approaches where nested systems are solved
    sequentially and iteratively, offers superior computational efficiency. This method thus provides
    a more direct and computationally effective way of determining the critical conditions in a cascade.

    Parameters
    ----------
    x_crit : numpy.ndarray
        Array containing [v_in*, v_throat*, s_throat*].
    critical_cascade_input : dict
        Dictionary containing critical cascade data.
    fluid : object
        A fluid object with methods for thermodynamic property calculations.
    geometry : dict
        Geometric parameters of the cascade.
    angular_speed : float
        Angular speed of the cascade.
    model_options : dict
        Options for the model used in the critical condition evaluation.
    reference_values : dict
        Reference values used in the calculation, including the reference mass flow rate.

    Returns
    -------
    tuple
        - residuals_critical (dict): Dictionary containing the residuals of the Lagrange function
          and the constraints ('L*', 'm*', 'Y*').
        - critical_state (dict): Dictionary containing state information at the critical conditions.


    .. note::

        The evaluation of the critical conditions is essential for the correct modeling of choking.

    """

    # Load reference values
    mass_flow_ref = reference_values["mass_flow_ref"]

    # Define critical state dictionary to store information
    critical_state = {}

    # Evaluate the current cascade at critical conditions
    f0 = compute_critical_values(
        x_crit,
        critical_cascade_input,
        fluid,
        geometry,
        angular_speed,
        critical_state,
        model_options,
        reference_values,
    )

    # Evaluate the Jacobian of the evaluate_critical_cascade function
    J = compute_critical_jacobian(
        x_crit,
        critical_cascade_input,
        fluid,
        geometry,
        angular_speed,
        critical_state,
        model_options,
        reference_values,
        f0,
    )

    # Rename gradients
    a11, a12, a21, a22, b1, b2 = (
        J[1, 0],
        J[2, 0],
        J[1, 1 + 1],
        J[2, 1 + 1],
        -1 * J[0, 0],
        -1 * J[0, 1 + 1],
    )  # For isentropic

    # Calculate the Lagrange multipliers explicitly
    eps = 1e-9  # TODO Division by zero sometimes?
    l1 = (a22 * b1 - a12 * b2) / (a11 * a22 - a12 * a21 + eps)
    l2 = (a11 * b2 - a21 * b1) / (a11 * a22 - a12 * a21 + eps)

    # Evaluate the last equation
    df, dg1, dg2 = J[0, 2 - 1], J[1, 2 - 1], J[2, 2 - 1]  # for isentropic
    grad = (df + l1 * dg1 + l2 * dg2) / mass_flow_ref

    # Return last 3 equations of the Lagrangian gradient (df/dx2+l1*dg1/dx2+l2*dg2/dx2 and g1, g2)
    g = f0[1:]  # The two constraints
    residual_values = np.insert(g, 0, grad)
    residual_keys = ["L*", "m*", "Y*"]
    residuals_critical = dict(zip(residual_keys, residual_values))

    return residuals_critical, critical_state


def compute_critical_values(
    x_crit,
    critical_cascade_input,
    fluid,
    geometry,
    angular_speed,
    critical_state,
    model_options,
    reference_values,
):
    """
    Compute cascade performance at the critical conditions

    This function is evaluates the performance of a cascade at its critical operating point defined by:

        1. Critical inlet relative velocity,
        2. Critical throat relative velocity,
        3. Critical throat entropy.

    Using these variables, the function calculates the critical mass flow rate and residuals of the mass balance and the loss model equations.

    Parameters
    ----------
    x_crit : numpy.ndarray
        Array containing scaled critical variables [v_in*, v_throat*, s_throat*].
    critical_cascade_input : dict
        Dictionary containing critical cascade input parameters, including inlet conditions and geometry.
    fluid : object
        A fluid object with methods for thermodynamic property calculations.
    geometry : dict
        Geometric parameters of the cascade.
    angular_speed : float
        Angular speed of the cascade.
    critical_state : dict
        Dictionary to store the critical state information.
    model_options : dict
        Options for the model used in the critical condition evaluation.
    reference_values : dict
        Reference values used in the calculations, including mass flow reference and other parameters.

    Returns
    -------
    numpy.ndarray
        An array containing the computed mass flow at the throat plane and the residuals
        for mass conservation and loss coefficient error.

    """

    # Define model options
    loss_model = model_options["loss_model"]

    # Load reference values
    mass_flow_ref = reference_values["mass_flow_ref"]
    v0 = reference_values["v0"]
    s_range = reference_values["s_range"]
    s_min = reference_values["s_min"]

    # Load geometry
    theta_out = geometry["metal_angle_te"]

    # Load input for critical cascade
    # TODO: use dictionary for input variables, not array indices
    # TODO: variables passed should already scaled as in evaluate_cascade()?
    s_in = critical_cascade_input["s_in"]
    h0_in = critical_cascade_input["h0_in"]
    alpha_in = critical_cascade_input["alpha_in"]
    v_in, w_throat, s_throat = (
        x_crit[0] * v0,
        x_crit[1] * v0,
        x_crit[2] * s_range + s_min,
    )

    # Evaluate inlet plane
    critical_inlet_input = {
        "v": v_in,
        "s": s_in,
        "h0": h0_in,
        "alpha": alpha_in,
    }
    inlet_plane = evaluate_cascade_inlet(
        critical_inlet_input, fluid, geometry, angular_speed
    )

    # Evaluate throat plane
    critical_exit_input = {
        "w": w_throat,
        "s": s_throat,
        "beta": theta_out,
        "rothalpy": inlet_plane["rothalpy"],
    }

    throat_plane, loss_dict = evaluate_cascade_exit(
        critical_exit_input,
        fluid,
        geometry,
        inlet_plane,
        angular_speed,
        model_options["throat_blockage"],
        loss_model,
        geometry["radius_mean_throat"],
        geometry["A_throat"],
    )

    # Add residuals
    residuals = np.array(
        [
            (inlet_plane["mass_flow"] - throat_plane["mass_flow"]) / mass_flow_ref,
            throat_plane["loss_error"],
        ]
    )

    # TODO: why not pass the entire throat_plane as critical state?
    critical_state["mass_flow"] = throat_plane["mass_flow"]
    critical_state["Ma_rel"] = throat_plane["Ma_rel"]
    critical_state["d"] = throat_plane["d"]
    critical_state["w"] = throat_plane["w"]
    critical_state["p"] = throat_plane["p"]
    critical_state["beta"] = throat_plane["beta"]

    output = np.insert(residuals, 0, throat_plane["mass_flow"])

    return output


def compute_critical_jacobian(
    x,
    critical_cascade_input,
    fluid,
    geometry,
    angular_speed,
    critical_state,
    model_options,
    reference_values,
    f0,
):
    """
    Compute the Jacobian matrix of the critical cascade evaluation using finite differences.

    This function approximates the Jacobian of a combined function that includes the mass flow rate value,
    mass balance residual, and loss model evaluation residual at the critical point. It uses forward finite
    difference approximate the partial derivatives of the Jacobian matrix.

    Parameters
    ----------
    x : numpy.ndarray
        Array of input variables for the critical cascade function.
    critical_cascade_input : dict
        Dictionary containing critical cascade input parameters.
    fluid : object
        A fluid object with methods for thermodynamic property calculations.
    geometry : dict
        Geometric parameters of the cascade.
    angular_speed : float
        Angular speed of the cascade.
    critical_state : dict
        Dictionary to store the critical state information.
    model_options : dict
        Options for the model used in the critical condition evaluation.
    reference_values : dict
        Reference values used in the calculation.
    f0 : numpy.ndarray
        The function value at x, used for finite difference approximation.

    Returns
    -------
    numpy.ndarray
        The approximated Jacobian matrix of the critical cascade function.

    """

    # Define finite difference relative step size
    # TODO specify in configuration file
    eps = 1e-3 * x

    # Approximate problem Jacobian by finite differences
    jacobian = approx_derivative(
        compute_critical_values,
        x,
        method="2-point",
        f0=f0,
        abs_step=eps,
        args=(
            critical_cascade_input,
            fluid,
            geometry,
            angular_speed,
            critical_state,
            model_options,
            reference_values,
        ),
    )

    return jacobian


def evaluate_velocity_triangle_in(u, v, alpha):
    """
    Compute the velocity triangle at the inlet of the cascade.

    This function calculates the components of the velocity triangle at the
    inlet of a cascade, based on the blade speed, absolute velocity, and
    absolute flow angle. It computes both the absolute and relative velocity
    components in the meridional and tangential directions, as well as the
    relative flow angle.

    Parameters
    ----------
    u : float
        Blade speed.
    v : float
        Absolute velocity.
    alpha : float
        Absolute flow angle in radians.

    Returns
    -------
    dict
        A dictionary containing the following properties:

        - "u" (float): Blade velocity.
        - "v" (float): Absolute velocity.
        - "v_m" (float): Meridional component of absolute velocity.
        - "v_t" (float): Tangential component of absolute velocity.
        - "alpha" (float): Absolute flow angle in radians.
        - "w" (float): Relative velocity magnitude.
        - "w_m" (float): Meridional component of relative velocity.
        - "w_t" (float): Tangential component of relative velocity.
        - "beta" (float): Relative flow angle in radians.
    """

    # Absolute velocities
    v_t = v * math.sind(alpha)
    v_m = v * math.cosd(alpha)

    # Relative velocities
    w_t = v_t - u
    w_m = v_m
    w = np.sqrt(w_t**2 + w_m**2)

    # Relative flow angle
    beta = math.arctand(w_t / w_m)

    # Store in dict
    vel_in = {
        "u": u,
        "v": v,
        "v_m": v_m,
        "v_t": v_t,
        "alpha": alpha,
        "w": w,
        "w_m": w_m,
        "w_t": w_t,
        "beta": beta,
    }

    return vel_in


def evaluate_velocity_triangle_out(u, w, beta):
    """
    Compute the velocity triangle at the outlet of the cascade.

    This function calculates the components of the velocity triangle at the
    outlet of a cascade, based on the blade speed, relative velocity, and
    relative flow angle. It computes both the absolute and relative velocity
    components in the meridional and tangential directions, as well as the
    absolute flow angle.

    Parameters
    ----------
    u : float
        Blade speed.
    w : float
        Relative velocity.
    beta : float
        Relative flow angle in radians.

    Returns
    -------
    dict
        A dictionary containing the following properties:

        - "u" (float): Blade velocity.
        - "v" (float): Absolute velocity.
        - "v_m" (float): Meridional component of absolute velocity.
        - "v_t" (float): Tangential component of absolute velocity.
        - "alpha" (float): Absolute flow angle in radians.
        - "w" (float): Relative velocity magnitude.
        - "w_m" (float): Meridional component of relative velocity.
        - "w_t" (float): Tangential component of relative velocity.
        - "beta" (float): Relative flow angle in radians.
    """

    # Relative velocities
    w_t = w * math.sind(beta)
    w_m = w * math.cosd(beta)

    # Absolute velocities
    v_t = w_t + u
    v_m = w_m
    v = np.sqrt(v_t**2 + v_m**2)

    # Absolute flow angle
    alpha = math.arctand(v_t / v_m)

    # Store in dict
    vel_out = {
        "u": u,
        "v": v,
        "v_m": v_m,
        "v_t": v_t,
        "alpha": alpha,
        "w": w,
        "w_m": w_m,
        "w_t": w_t,
        "beta": beta,
    }

    return vel_out


def compute_residual_mach_throat(Ma_crit, Ma_exit, Ma_throat, alpha=-100):
    """
    Calculate the residual between the actual Mach number at the throat and the target value.

    This function computes the target Mach number using a smooth maximum approximation of the
    critical Mach number and the exit Mach number. The smooth maximum function is used to avoid
    a discontinuity in slope at the critical Mach. The residual is computed as the difference
    between the target Mach number and the actual Mach number at the throat.

    Parameters
    ----------
    Ma_crit : float
        Critical Mach number, above which flow is considered supersonic.
    Ma_exit : float
        Mach number at the exit of the flow domain.
    Ma_throat : float
        Mach number at the throat of the flow domain.
    alpha : float, optional
        A parameter used in the smooth maximum function to control its behavior.
        Default is -100.

    Returns
    -------
    tuple
        A tuple containing:

        - ressidual (float): The residual between the target and throat Mach numbers.
        - density_correction (float): No density correction required in this model (returns NaN).

    """
    # Mach number at the throat cannot be higher than Ma_crit
    # Smooth maximum prevents slope discontinuity at the switch
    Ma_array = np.array([Ma_crit, Ma_exit])
    Ma_target = math.smooth_max(Ma_array, method="boltzmann", alpha=alpha)

    # Retrieve residual for current solution
    residual = Ma_throat - Ma_target

    # No density correction required in this model
    density_correction = np.nan

    return residual, density_correction


def compute_residual_flow_angle(
    geometry, critical_state, throat_plane, exit_plane, subsonic_deviation_model
):
    """
    Compute the residual between actual and target flow angles at the exit plane of a cascade.

    This function calculates the deviation angle of the flow at the exit plane based on the provided geometry,
    critical state, throat plane, and exit plane data. It considers both subsonic and supersonic conditions,
    applying different models accordingly.

    Parameters
    ----------
    geometry : dict
        A dictionary containing the cascade geometry information such as area, opening, and pitch.
    critical_state : dict
        A dictionary containing the critical state information including mass flow ('mass_flow')
        and relative Mach number ('Ma_rel').
    throat_plane : dict
        A dictionary containing throat plane data.
    exit_plane : dict
        A dictionary containing exit plane data.
    subsonic_deviation_model : str
        A string specifying the model used for calculating the deviation angle at subsonic conditions.

    Returns
    -------
    tuple
        A tuple containing:

        - residual (float): The difference between the cosine of the modeled and actual flow angles.
        - density_correction (float): The density correction factor used in supersonic conditions
          (returns NaN for subsonic conditions).

    Warnings
    --------
    The density correction factor computed for supersonic conditions is a temporary solution
    to account for numerical errors in nested finite difference calculations. This approach
    may need revision or replacement in future versions of the code.
    """
    # Load cascade geometry
    area = geometry["A_out"]
    opening = geometry["opening"]
    pitch = geometry["pitch"]

    # Load calculated critical condition
    m_crit = critical_state["mass_flow"]
    Ma_crit = critical_state["Ma_rel"]

    # Load throat plane data
    # Ma_throat = throat_plane["Ma_rel"]
    # blockage = exit_plane["blockage"] # Should blockage be at the throat?

    # Load exit plane
    Ma = exit_plane["Ma_rel"]
    rho = exit_plane["d"]
    w = exit_plane["w"]
    beta = exit_plane["beta"]
    blockage = exit_plane["blockage"]

    # Compute exit flow angle
    # TODO: discuss if it should be Ma_throat or Ma_exit || Ma_throat in inequelity fails
    if Ma <= Ma_crit:
        density_correction = np.nan
        beta_model = dm.get_subsonic_deviation(
            Ma, Ma_crit, opening / pitch, subsonic_deviation_model
        )
    else:
        density_correction = throat_plane["d"] / critical_state["d"]
        cos_beta = m_crit / rho / w / area / (1 - blockage) * density_correction
        beta_model = math.arccosd(cos_beta)
        # Density correction needed above critical condition to fix numerical error caused by nested finite differences

    # Compute error of guessed beta and deviation model
    residual = math.cosd(beta_model) - math.cosd(beta)

    return residual, density_correction


def compute_blockage_boundary_layer(throat_blockage, Re, chord, opening):
    """
    Calculate the blockage factor due to boundary layer displacement thickness.

    This function computes the blockage factor caused by the boundary layer
    displacement thickness at a given flow station. The blockage factor affects
    mass flow rate calculations effectively reducing the flow area.

    The blockage factor can be determined through various methods, including:

        1. Calculation based on a correlation for the displacement thickness of turbulent boundary layer over a flat plate with zero pressure gradient.
        2. Using a numerical value specified directly by the user.


    Parameters
    ----------
    throat_blockage : str or float or None
        The method or value for determining the throat blockage. It can be
        a string specifying a model name ('flat_plate_turbulent'), a numeric
        value between 0 and 1 representing the blockage factor directly, or
        None to use a default calculation method.
    Re : float, optional
        Reynolds number, used if `throat_blockage` is 'flat_plate_turbulent'.
    chord : float, optional
        Chord length, used if `throat_blockage` is 'flat_plate_turbulent'.
    opening : float, optional
        Throat opening size, used to calculate the blockage factor when
        `throat_blockage` is None or a numeric value.

    Returns
    -------
    float
        The calculated blockage factor, a value between 0 and 1, where 1
        indicates full blockage and 0 indicates no blockage.

    Raises
    ------
    ValueError
        If `throat_blockage` is an invalid option, or required parameters
        for the chosen method are missing.
    """

    if throat_blockage == "flat_plate_turbulent":
        displacement_thickness = 0.048 / Re ** (1 / 5) * 0.9 * chord
        blockage_factor = 2 * displacement_thickness / opening

    elif isinstance(throat_blockage, (float, int)) and 0 <= throat_blockage <= 1:
        blockage_factor = throat_blockage

    elif throat_blockage is None:
        blockage_factor = 0.00

    else:
        raise ValueError(
            f"Invalid throat blockage option: '{throat_blockage}'. "
            "Valid options are 'flat_plate_turbulent', a numeric value between 0 and 1, or None."
        )

    return blockage_factor


def compute_efficiency_breakdown(results):
    """
    Compute the breakdown of total-to-static efficiency drops due to various loss components in cascades.

    This function calculates the fraction of total-to-static efficiency drop attributed to each loss component
    in a turbine cascade. A correction factor for the re-heating effect is applied to align the sum of individual
    cascade losses with the total observed change in enthalpy and ensure consistency with
    the overall total-to-static efficiency.

    Parameters
    ----------
    results : dict
        The data for the cascades, including plane and cascade specific parameters.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing efficiency drop fractions for each loss type in each cascade.
        Columns are named as 'efficiency_drop_{loss_type}', where 'loss_type' includes:

        - 'profile'
        - 'incidence'
        - 'secondary'
        - 'clearance'
        - 'trailing'

    """
    # Load parameters
    h_out_s = results["reference_values"]["h_out_s"]
    h0_in = results["plane"]["h0"].values[0]
    h_out = results["plane"]["h"].values[-1]
    cascade = results["cascade"]
    number_of_cascades = results["geometry"]["number_of_cascades"]

    # Compute a correction factor due to re-heating effect
    dhs_total = h_out - h_out_s
    dhs_sum = cascade["dh_s"].sum()
    correction = dhs_total / dhs_sum

    # Initialize DataFrame
    loss_types = ["profile", "incidence", "secondary", "clearance", "trailing"]
    breakdown = pd.DataFrame(columns=[f"efficiency_drop_{type}" for type in loss_types])

    # Loss breakdown in each cascade
    for i in range(number_of_cascades):
        # Construct column names dynamically based on loss_types
        col_names = [f"loss_{type}" for type in loss_types]

        # Retrieve values for each specified column and compute the fractions
        fracs = cascade.loc[i, col_names] / cascade.loc[i, "loss_total"]
        dh_s = cascade["dh_s"][i]
        efficiency_drop = correction * dh_s / (h0_in - h_out_s)

        # Append efficiency drop breakdown
        breakdown.loc[len(breakdown)] = (fracs * efficiency_drop).values

    return breakdown


def compute_stage_performance(results):
    """
    Calculate the stage performance metrics of the turbine

    Parameters
    ----------
    number_of_stages : int
        The number of stages in the cascading system.
    planes : dict
        A dictionary containing performance data at each station.

    Returns
    -------
    dict
        A dictionary with calculated stage parameters. Currently, this includes:
        - 'R' (numpy.ndarray): An array of degree of reaction values for each stage.

    Warnings
    --------
    This function currently only computes the degree of reaction. Other stage parameters,
    which might be relevant for a comprehensive analysis of the cascading system, are not
    computed in this version of the function. Future implementations may include additional
    parameters for a more detailed stage analysis.

    """

    # Only proceed if there are stages
    number_of_stages = results["geometry"]["number_of_stages"]
    if number_of_stages == 0:
        return {}

    # Calculate the degree of reaction for each stage using list comprehension
    h = results["plane"]["h"].values
    R = np.array(
        [
            (h[i * 6 + 2] - h[i * 6 + 5]) / (h[i * 6] - h[i * 6 + 5])
            for i in range(number_of_stages)
        ]
    )

    # Store all variables in dictionary
    stages = {"reaction": R}

    # Check the dictionary has the expected keys
    util.validate_keys(stages, KEYS_STAGE, KEYS_STAGE)

    return stages


def compute_overall_performance(results):
    """
    Calculate the overall performance metrics of the turbine

    This function extracts necessary values from the 'results' dictionary, performs calculations to determine
    overall performance metrics, and stores these metrics in the "overall" dictionary. The function also checks
    that the overall dictionary has all the expected keys and does not contain any unexpected keys.

    The keys for the 'overall' dictionary are defined in the :obj:`KEYS_OVERALL` list. Refer to its documentation
    for the complete list of keys.

    Parameters
    ----------
    results : dict
        A dictionary containing various operational parameters at each flow station

    Returns
    -------
    dict
        An updated dictionary with a new key 'overall' containing the calculated performance metrics.
        The keys for these metrics are defined in :obj:`KEYS_OVERALL`.
    """

    # TODO: Refactor so results is the only required argument
    # TODO: recalculate h_out_s and v0 from results data might be a simple solution
    # TODO: angular speed could be saved at each cascade. This would be needed anyways if we want to extend the code to machines with multiple angular speeds in the future (e.g., a multi-shaft gas turbine)
    angular_speed = results["boundary_conditions"]["omega"]
    v0 = results["reference_values"]["v0"]
    h_out_s = results["reference_values"]["h_out_s"]  # FIXME: bad plaement of h_out_s variable?

    # Calculation of overall performance
    p = results["plane"]["p"].values
    p0 = results["plane"]["p0"].values
    h0 = results["plane"]["h0"].values
    v_out = results["plane"]["v"].values[-1]
    u_out = results["plane"]["u"].values[-1]
    mass_flow = results["plane"]["mass_flow"].values[-1]
    exit_flow_angle = results["plane"]["alpha"].values[-1]
    PR_tt = p0[0] / p0[-1]
    PR_ts = p0[0] / p[-1]
    h0_in = h0[0]
    h0_out = h0[-1]
    efficiency_tt = (h0_in - h0_out) / (h0_in - h_out_s - 0.5 * v_out**2)
    efficiency_ts = (h0_in - h0_out) / (h0_in - h_out_s)
    efficiency_ts_drop_kinetic = 0.5 * v_out**2 / (h0_in - h_out_s)
    efficiency_ts_drop_losses = 1.0 - efficiency_ts - efficiency_ts_drop_kinetic
    power = mass_flow * (h0_in - h0_out)
    torque = power / angular_speed

    # Store all variables in dictionary
    overall = {
        "PR_tt": PR_tt,
        "PR_ts": PR_ts,
        "mass_flow_rate": mass_flow,
        "efficiency_tt": efficiency_tt,
        "efficiency_ts": efficiency_ts,
        "efficiency_ts_drop_kinetic": efficiency_ts_drop_kinetic,
        "efficiency_ts_drop_losses": efficiency_ts_drop_losses,
        "power": power,
        "torque": torque,
        "angular_speed": angular_speed,
        "exit_flow_angle": exit_flow_angle,
        "exit_velocity": v_out,
        "spouting_velocity": v0,
        "last_blade_velocity": u_out,
        "blade_jet_ratio": u_out / v0,
        "h0_in": h0_in,
        "h0_out": h0_out,
        "h_out_s": h_out_s,
    }

    # Check the dictionary has the expected keys
    util.validate_keys(overall, KEYS_OVERALL, KEYS_OVERALL)

    return overall
