import numpy as np
from .. import math


DEVIATION_MODELS = ["aungier", "ainley_mathieson", "zero_deviation", 'borg_agromayor']

def get_subsonic_deviation(Ma_exit, Ma_crit_throat, Ma_crit_exit, geometry, model):
    """
    Calculate subsonic relative exit flow angle based on the selected deviation model.

    Available deviation models:

    - "aungier": Calculate deviation using the method proposed by :cite:`aungier_turbine_2006`.
    - "ainley_mathieson": Calculate deviation using the model proposed by :cite:`ainley_method_1951`.
    - "metal_angle": Assume the exit flow angle is given by the gauge angle (zero deviation).

    Parameters
    ----------
    deviation_model : str
        The deviation model to use (e.g., 'aungier', 'ainley_mathieson', 'zero_deviation').
    Ma_exit : float or numpy.array
        The exit Mach number.
    Ma_crit : float
        The critical Mach number (possibly lower than one).
    opening_to_pitch : float
        The ratio of cascade opening to pitch.

    Returns
    -------
    float
        The relative exit flow angle including deviation in degrees (subsonic flow only).

    Raises
    ------
    ValueError
        If an invalid deviation model is provided.
    """


    # Function mappings for each deviation model
    deviation_model_functions = {
        DEVIATION_MODELS[0]: get_exit_flow_angle_aungier,
        DEVIATION_MODELS[1]: get_exit_flow_angle_ainley_mathieson,
        DEVIATION_MODELS[2]: get_exit_flow_angle_zero_deviation,
        DEVIATION_MODELS[3]: get_exit_flow_angle_borg_agromayor
    }

    # Evaluate deviation model
    if model in deviation_model_functions:
        Ma_exit = np.float64(Ma_exit)
        return deviation_model_functions[model](Ma_exit, Ma_crit_throat, Ma_crit_exit, geometry)
    else:
        options = ", ".join(f"'{k}'" for k in deviation_model_functions)
        raise ValueError(
            f"Invalid deviation model: '{model}'. Available options: {options}"
        )
    
def get_exit_flow_angle_aungier(Ma_exit, Ma_crit_throat, Ma_crit_exit, geometry):
    """
    Calculate deviation angle using the method proposed by :cite:`aungier_turbine_2006`.
    """
    # TODO add equations of Aungier model to docstring
    gauging_angle = geometry["metal_angle_te"]

    # Compute deviation for  Ma<0.5 (low-speed)
    beta_g = 90-abs(gauging_angle)
    delta_0 = math.arcsind(math.cosd(gauging_angle) * (1 + (1 - math.cosd(gauging_angle)) * (beta_g / 90) ** 2)) - beta_g

    # Initialize an empty array to store the results
    delta = np.empty_like(Ma_exit, dtype=float)

    # Compute deviation for Ma_exit < 0.50 (low-speed)
    low_speed_mask = Ma_exit < 0.50
    delta[low_speed_mask] = delta_0

    # Compute deviation for 0.50 <= Ma_exit < 1.00
    medium_speed_mask = (0.50 <= Ma_exit) & (Ma_exit < Ma_crit_exit)
    X = (2 * Ma_exit[medium_speed_mask] - 1) / (2 * Ma_crit_exit - 1)
    delta[medium_speed_mask] = delta_0 * (1 - 10 * X**3 + 15 * X**4 - 6 * X**5)

    # Extrapolate to zero deviation for supersonic flow
    supersonic_mask = Ma_exit >= 1.00
    delta[supersonic_mask] = 0.00

    # Compute flow angle from deviation
    beta = abs(gauging_angle) - delta

    return beta


def get_exit_flow_angle_ainley_mathieson(Ma_exit, Ma_crit_throat, Ma_crit_exit, geometry):
    """
    Calculate deviation angle using the model proposed by :cite:`ainley_method_1951`.
    Equation digitized from Figure 5 of :cite:`ainley_method_1951`.
    """
    # TODO add equations of Ainley-Mathieson to docstring

    gauging_angle = geometry["metal_angle_te"]
        
    # Compute deviation for  Ma<0.5 (low-speed)
    delta_0 = abs(gauging_angle) - (35.0 + (80.0 - 35.0) / (79.0 - 40.0) * (abs(gauging_angle) - 40.0))

    # Initialize an empty array to store the results
    delta = np.empty_like(Ma_exit, dtype=float)

    # Compute deviation for Ma_exit < 0.50 (low-speed)
    low_speed_mask = Ma_exit < 0.50
    delta[low_speed_mask] = delta_0

    # Compute deviation for 0.50 <= Ma_exit < 1.00
    medium_speed_mask = (0.50 <= Ma_exit) & (Ma_exit < 1.00)
    X = (2 * Ma_exit[medium_speed_mask] - 1) / (2 * Ma_crit_exit - 1)
    delta[medium_speed_mask] = delta_0 * (1 - 10 * X**3 + 15 * X**4 - 6 * X**5)
    # FIXME: no linear interpolation now?

    # Extrapolate to zero deviation for supersonic flow
    supersonic_mask = Ma_exit >= 1.00
    delta[supersonic_mask] = 0.00

    # Compute flow angle from deviation
    beta = abs(gauging_angle) - delta
    
    return beta

def get_exit_flow_angle_borg_agromayor(Ma_exit, Ma_crit_throat, Ma_crit_exit, geometry):
    
    # Load geometry
    area_throat = geometry["A_throat"]
    area_exit = geometry["A_out"]
    gauging_angle = geometry["metal_angle_te"]
    
    # Compute deviation for  Ma<0.5 (low-speed)
    beta_inc = (35.0 + (80.0 - 35.0) / (79.0 - 40.0) * (abs(gauging_angle) - 40.0))
    
    # Define limit for incompressible flow angle
    Ma_inc = 0.5
    
    # Compute deviation angle
    x = (Ma_exit - Ma_inc) / (Ma_crit_exit - Ma_inc)
    y = x**2 * (2-x) * (x > 0)
    # y = x**2 * (3-2*x) * (x > 0)
    # a = (abs(gauging_angle) - math.arccosd(area_throat/area_exit))/(Ma_crit_exit**2-2*Ma_crit_exit*Ma_crit_throat+Ma_crit_throat**2)
    # b = -2*a*Ma_crit_throat
    # slope = 2*a*Ma_crit_exit+b
    # slope_normalized = slope*(abs(gauging_angle)-beta_inc)/(Ma_crit_exit - Ma_inc)
    # y = (3-slope_normalized)*x**2+(slope_normalized-2)*x**3
    beta = beta_inc + (abs(gauging_angle) - beta_inc) * y
    
    return beta

def get_exit_flow_angle_zero_deviation(Ma_exit, Ma_crit, opening_to_pitch):
    """
    The exit flow angle is given by the gauge angle at subsonic conditions
    """
    # TODO add equation of zero-deviation to docstring
    return np.full_like(Ma_exit, math.arccosd(opening_to_pitch))



