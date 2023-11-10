import numpy as np
from .. import math

# Function to check if all items in the array are numeric (floats or ints)
def all_numeric(arr):
    return np.issubdtype(arr.dtype, np.number)


# Function to check if all items in the array are non-negative
def all_non_negative(arr):
    return np.all(arr >= 0)


def validate_axial_turbine_geometry(geom):
    """
    Performs validation of an axial turbine's geometry configuration.

    - Ensures all required geometry parameters are specified in 'geom'.
    - Verifies that no parameters beyond the required set are included.
    - Checks 'number_of_cascades' is an integer and correctly dictates sizes of other parameters.
    - Confirms 'radius_hub' and 'radius_tip' arrays have sizes twice that of 'number_of_cascades'.
    - Validates that all other parameter arrays match the size of 'number_of_cascades'.
    - Asserts that all geometry parameter values are numeric (integers or floats).
    - Ensures non-angle parameters contain only non-negative values.
    - Angle parameters ('metal_angle_leading', 'metal_angle_trailing') can be negative.

    This function is intended as a preliminary check before in-depth geometry analysis.

    Parameters:
    -----------
    geom : dict
        The geometry configuration parameters for the turbine as a dictionary.

    Returns:
    --------
    bool
        True if all validations pass, indicating a correctly structured geometry configuration.
    """

    # Define the list of keys that must be defined in the configuration file
    required_keys = {
        "cascade_type",
        "radius_hub",
        "radius_tip",
        "pitch",
        "chord",
        "stagger_angle",
        "opening",
        "diameter_le",
        "wedge_angle_le",
        "metal_angle_le",
        "metal_angle_te",
        "thickness_te",
        "tip_clearance",
        "thickness_max",
    }

    # Angular variables need not be non-negative
    angle_keys = ["metal_angle_le", "metal_angle_te", "stagger_angle"]

    # Check for extra fields
    extra_keys = geom.keys() - required_keys
    if extra_keys:
        raise KeyError(f"Unexpected geometry parameters: {extra_keys}")

    # Check for required fields
    missing_keys = required_keys - geom.keys()
    if missing_keys:
        raise KeyError(f"Missing geometry parameters: {missing_keys}")

    # Get the number of cascades
    number_of_cascades = len(geom["cascade_type"])

    # Check if cascade_type is correctly defined
    valid_types = np.array(["stator", "rotor"])
    invalid_types = geom["cascade_type"][~np.isin(geom["cascade_type"], valid_types)]
    if invalid_types.size > 0:
        invalid_types_str = ", ".join(invalid_types)
        raise ValueError(
            f"Invalid types in 'cascade_type': {invalid_types_str}. Only 'stator' and 'rotor' are allowed."
        )

    # Check array size and values
    for key, value in geom.items():
        # Skip the cascade_type in the loop
        if key == "cascade_type":
            continue

        # Check that all variables are numpy arrays
        if not isinstance(value, np.ndarray):
            raise TypeError(f"Parameter '{key}' must be a NumPy array.")

        # Check the size of the arrays
        print(key, value)
        if key in ["radius_hub", "radius_tip"]:
            if value.size != 2 * number_of_cascades:
                raise ValueError(
                    f"Size of '{key}' must be twice the number of cascades. Current value: {value}"
                )
        else:
            if value.size != number_of_cascades:
                raise ValueError(
                    f"Size of '{key}' must be equal to number of cascades. Current value: {value}"
                )

        # Check that values of parameters are numeric
        if not all_numeric(value):
            raise ValueError(
                f"Parameter '{key}' must be an array of numeric types. Current value: {value}"
            )

        # Check that non-angle variables are not negative
        if key not in angle_keys and not np.all(value >= 0):
            raise ValueError(
                f"Parameter '{key}' must be an array of non-negative numbers. Current value: {value}"
            )

    return True


def calculate_throat_radius(radius_in, radius_out):
    """
    Calculate the throat radius using the given rule by Ainley and Mathieson,
    which is (1/6)*radius_in + (5/6)*radius_out.

    Parameters:
    -----------
    radius_in: np.array
        The radius values at the inlet sections.
    radius_out: np.array
        The radius values at the outlet sections.

    Returns:
    --------
    np.array
        The calculated throat radius values.
    """
    return (1 / 6) * radius_in + (5 / 6) * radius_out


def calculate_full_geometry(geometry):
    """
    Computes the complete geometry of an axial turbine based on input geometric parameters.

    Parameters:
    -----------
    geometry (dict): A dictionary containing the input geometry parameters

    Returns:
    --------
    dict: A new dictionary with both the original and newly computed geometry parameters.
    """

    # Create a copy of the input dictionary to avoid mutating the original
    geom = geometry.copy()

    # Get number of cascades
    number_of_cascades = len(geom["cascade_type"])

    # Get number of stages
    if number_of_cascades > 1:
      if math.is_even(number_of_cascades):
          number_of_stages = int(number_of_cascades/2)
      else:
          number_of_stages = int((number_of_cascades-1)/2)
    else:
        number_of_stages = 0

    # Compute axial chord
    axial_chord = geom["chord"] * math.cosd(geom["stagger_angle"])

    # Extract initial radii and compute mean radius
    radius_hub = geom["radius_hub"]
    radius_tip = geom["radius_tip"]
    radius_mean = (radius_hub + radius_tip) / 2  # Average of hub and tip radius

    # Calculate shroud radius by adding clearance to tip radius
    radius_shroud = geom["radius_tip"] + np.repeat(geom["tip_clearance"], 2)

    # Calculate the inner and outer radii for the mean section
    radius_mean_in = radius_mean[::2]  # Even indices: in
    radius_mean_out = radius_mean[1::2]  # Odd indices: out
    radius_mean_throat = calculate_throat_radius(
        radius_mean_in, radius_mean_out
    )  # Calculate throat radii for mean section
    # TODO throat area calculation correct

    # Repeat calculations for hub
    radius_hub_in = radius_hub[::2]
    radius_hub_out = radius_hub[1::2]
    radius_hub_throat = calculate_throat_radius(radius_hub_in, radius_hub_out)

    # Repeat calculations for tip
    radius_tip_in = radius_tip[::2]
    radius_tip_out = radius_tip[1::2]
    radius_tip_throat = calculate_throat_radius(radius_tip_in, radius_tip_out)

    # Repeat calculations for shroud
    radius_shroud_in = radius_shroud[::2]
    radius_shroud_out = radius_shroud[1::2]
    radius_shroud_throat = calculate_throat_radius(radius_shroud_in, radius_shroud_out)

    # Compute hub to tip radius ratio
    hub_tip_ratio = radius_hub / radius_tip
    hub_tip_ratio_in = radius_hub_in / radius_tip_out
    hub_tip_ratio_out = radius_hub_out / radius_tip_out
    hub_tip_ratio_throat = radius_hub_throat / radius_tip_throat

    # Compute areas for the full, in, out, and throat sections
    A = np.pi * (radius_tip**2 - radius_hub**2)
    A_in = np.pi * (radius_tip_in**2 - radius_hub_in**2)
    A_out = np.pi * (radius_tip_out**2 - radius_hub_out**2)
    A_throat = np.pi * (radius_tip_throat**2 - radius_hub_throat**2)

    # Compute blade height at different sections
    height = geom["radius_tip"] - geom["radius_hub"]
    height_in = radius_tip_in - radius_hub_in
    height_out = radius_tip_out - radius_hub_out
    height = (height_in + height_out) / 2

    # Compute flaring angle
    flaring_angle = np.arctan((height_out-height_in)/(2*axial_chord))

    # Compute geometric ratios
    aspect_ratio = height / axial_chord
    pitch_to_chord_ratio = geom["pitch"] / geom["chord"]
    thickness_max_to_chord_ratio = geom["thickness_max"] / geom["chord"]
    thickness_te_to_opening_ratio = geom["thickness_te"] / geom["opening"]
    tip_clearance_to_height = geom["tip_clearance"] / height
    diameter_le_to_chord_ratio = geom["diameter_le"] / geom["chord"]
    # throat_to_exit_opening_ratio =

    # Create a dictionary with the newly computed parameters
    new_parameters = {
        "number_of_stages" : number_of_stages,
        "number_of_cascades": number_of_cascades,
        "axial_chord": axial_chord,
        "radius_mean": radius_mean,
        "radius_shroud": radius_shroud,
        "radius_mean_in": radius_mean_in,
        "radius_mean_out": radius_mean_out,
        "radius_mean_throat": radius_mean_throat,
        "radius_hub_in": radius_hub_in,
        "radius_hub_out": radius_hub_out,
        "radius_hub_throat": radius_hub_throat,
        "radius_tip_in": radius_tip_in,
        "radius_tip_out": radius_tip_out,
        "radius_tip_throat": radius_tip_throat,
        "radius_shroud_in": radius_shroud_in,
        "radius_shroud_out": radius_shroud_out,
        "radius_shroud_throat": radius_shroud_throat,
        "hub_tip_ratio": hub_tip_ratio,
        "hub_tip_ratio_in": hub_tip_ratio_in,
        "hub_tip_ratio_out": hub_tip_ratio_out,
        "hub_tip_ratio_throat": hub_tip_ratio_throat,
        "A": A,
        "A_in": A_in,
        "A_out": A_out,
        "A_throat": A_throat,
        "height": height,
        "height_in": height_in,
        "height_out": height_out,
        "flaring_angle": flaring_angle,
        "aspect_ratio": aspect_ratio,
        "pitch_to_chord_ratio": pitch_to_chord_ratio,
        "thickness_max_to_chord_ratio": thickness_max_to_chord_ratio,
        "thickness_te_to_opening_ratio": thickness_te_to_opening_ratio,
        "tip_clearance_to_height_ratio": tip_clearance_to_height,
        "diameter_le_to_chord_ratio": diameter_le_to_chord_ratio,
    }

    return {**geometry, **new_parameters}


def check_axial_turbine_geometry(geometry):
    """
    Checks if the geometry parameters are within the predefined recommended ranges.


    .. table:: Recommended Parameter Ranges and References

        +------------------------+------------+------------+--------------------------------+
        | Variable               | LowerLimit | UpperLimit | Reference(s)                   |
        +========================+============+============+================================+
        | chord                  | 5e-3       | inf        | Manufacturing                  |
        +------------------------+------------+------------+--------------------------------+
        | height                 | 5e-3       | inf        | Manufacturing                  |
        +------------------------+------------+------------+--------------------------------+
        | thickness_max          | 1e-3       | inf        | Manufacturing                  |
        +------------------------+------------+------------+--------------------------------+
        | thickness_te           | 5e-4       | inf        | Manufacturing                  |
        +------------------------+------------+------------+--------------------------------+
        | tip_clearance          | 2e-4       | inf        | Manufacturing                  |
        +------------------------+------------+------------+--------------------------------+
        |                        |            |            |                                |
        +------------------------+------------+------------+--------------------------------+
        |                        |            |            |                                |
        +------------------------+------------+------------+--------------------------------+
        |                        |            |            |                                |
        +------------------------+------------+------------+--------------------------------+
        |                        |            |            |                                |
        +------------------------+------------+------------+--------------------------------+
        |                        |            |            |                                |
        +------------------------+------------+------------+--------------------------------+
        |                        |            |            |                                |
        +------------------------+------------+------------+--------------------------------+
        |                        |            |            |                                |
        +------------------------+------------+------------+--------------------------------+

    Parameters:
    -----------
    geometry (dict): A dictionary containing the computed geometry of the turbine.

    Returns:
    --------
    list: A list of messages with a summary of the checks.
    """

    # TODO: Check that this function behaves as intended
    # Make table of correct values and give reference to motivation
    # TODO angles are correct for rotor/statos
    # Tip clearance can be zero for rotor
    # TODO angles in degree
    # TODO flaring angle calculation
    # - The tip clearance can be zero for stator blades
    # Saravanamutttoo
    # % Flow angle  opening to pitch rule {343--344}
    # % Flaring angles p.~332
    # % Angle convention steam-gas 316
    # % Aspect ratio values p.~345
    # % Axial spacing values p.~333
    # % 2D flow assumption hub-tip-ratio p.~204

    msgs = []
    cascade_types = geometry['cascade_type']  # Assuming 'cascade_type' is directly within 'geometry'
    warnings = []  # List to store parameters with "WARNING" status
    # Initialize a list to store variables outside the recommended range
    outside_range_variables = []


    # Define good practice ranges for each parameter
    recommended_ranges = {
        "chord": {"min": 5e-3, "max": np.inf},  # Manufacturing
        "height": {"min": 5e-3, "max": np.inf},  # Manufacturing
        "thickness_max": {"min": 1e-3, "max": np.inf},  # Manufacturing
        "thickness_te": {"min": 5e-4, "max": np.inf},  # Manufacturing
        "tip_clearance": {"min": 2e-4, "max": np.inf},  # Manufacturing
        "hub_tip_ratio": {
            "min": 0.50,
            "max": 0.95,
        },  # Figure 6 of :cite:`kacker_mean_1982`
        "aspect_ratio": {
            "min": 0.8,
            "max": 5.0,
        },  # Section 7.3 of :cite:`saravanamuttoo_gas_2008` and Figure 13 of :cite:`kacker_mean_1982`
        "pitch_to_chord_ratio": {
            "min": 0.3,
            "max": 1.1,
        },  # Figure 4 of :cite:`ainley_method_1951`
        "stagger_angle": {
            "min": -10,
            "max": +70,
        },  # Figure 5 of :cite:`kacker_mean_1982`
        "metal_angle_le": {
            "min": -60,
            "max": +25,
        },  # Figure 5 of :cite:`kacker_mean_1982`
        "metal_angle_te": {
            "min": +40,
            "max": +80,
        },  # Figure 4 of :cite:`ainley_method_1951`
        "wedge_angle_le": {
            "min": 10,
            "max": 60,
        },  # Figure 2 from :cite:`benner_influence_1997` and Figure 10 from :cite:`pritchard_eleven_1985`
        "diameter_le_to_chord_ratio": {
            "min": 0.03,
            "max": 0.30,
        },  # Table 1 :cite:`moustapha_improved_1990`
        "thickness_max_to_chord_ratio": {
            "min": 0.05,
            "max": 0.30,
        },  # Figure 4 of :cite:`kacker_mean_1982`
        "thickness_te_to_opening_ratio": {
            "min": 0.00,
            "max": 0.40,
        },  # Figure 14 of :cite:`kacker_mean_1982`
        "tip_clearance_to_height_ratio": {
            "min": 0.0,
            "max": 0.05,
        },  # Figure 7 of :cite:`dunham_improvements_1970`
    }

    special_angles = ["metal_angle_le", "metal_angle_te", "stagger_angle"]

    # # Iterate over each good practice parameter and perform checks
    # for parameter, limits in recommended_ranges.items():
    #     if parameter == "cascade_type":
    #         continue  # Skip the cascade_type entry

    #     lb, ub = limits["min"], limits["max"]
    #     value_array = geometry[parameter]

    #     for index, value in enumerate(np.atleast_1d(value_array)):

    #         if parameter in special_angles:
    #             blade_type = cascade_types[index]
    #             if blade_type == "rotor":
    #                 lb, ub = -ub, -lb  # Reverse limits for rotor blades

    #         if parameter == "tip_clearance":
    #             blade_type = cascade_types[index]
    #             if blade_type == "stator":
    #                     lb = 0


    #         if not lb <= value <= ub:
    #             msgs.append(
    #                 f"{parameter}[{index}]={value:0.4f} is out of recommended range ({lb}, {ub}) for {blade_type}."
    #             )


    # if not msgs:
    #     msgs.append("All parameters are within recommended ranges")

    # Header for the geometry report

    report_width = 80

    msgs.append("-" * report_width)  # Horizontal line

    msgs.append("Axial turbine geometry Report".center(report_width))
    msgs.append("-" * report_width)  # Horizontal line


    # Table header with four columns
    table_header = f" {'Parameter':<34}{'Value':>8}{'Range':>20}{'In range?':>14}"
    msgs.append(table_header)
    msgs.append("-" * report_width)  # Horizontal line

    # Iterate over each good practice parameter and perform checks
    for parameter, limits in recommended_ranges.items():
        if parameter == "cascade_type":
            continue  # Skip the cascade_type entry

        lb, ub = limits["min"], limits["max"]
        value_array = geometry[parameter]

        for index, value in enumerate(np.atleast_1d(value_array)):

            # Determine cascade type for special cases
            blade_type = cascade_types[index % len(cascade_types)]

            if parameter in special_angles and blade_type == "rotor":
                lb, ub = -ub, -lb  # Reverse limits for rotor blades

            if parameter == "tip_clearance":
                if blade_type == "stator":
                    lb = 0.0
                elif blade_type == "rotor":
                    lb = limits["min"]

            # Check if the value is within the recommended range
            in_range = lb <= value <= ub

            # Create a formatted message in table format using f-strings
            bounds = f"({lb:+0.2f}, {ub:+0.2f})"
            formatted_message = f" {parameter+'_'+str(index):<34}{value:>+8.4f}{bounds:>20}{str(in_range):>14}"
            msgs.append(formatted_message)

            # Append variables outside the recommended range to the list
            if not in_range:
                outside_range_variables.append(f"{parameter}_{index}")


    # Footer for the geometry report
    msgs.append("-" * report_width)  # Horizontal line


    if not outside_range_variables:
        msgs.append(" Report summary: All parameters are within recommended ranges.")
    else:
        msgs.append(" Report Summary: Some parameters are outside recommended ranges.")
        for warning in outside_range_variables:
            msgs.append(f"     - {warning}")

    # Footer for the geometry report
    msgs.append("-" * report_width)  # Horizontal line


    msg = "\n".join(msgs)

    return msg





# def create_partial_geometry_from_optimization_variables(x_opt, cascade_data):

#     pitch_to_chord_ratio = x_opt[0]
#     aspect_ratio = x_opt[1]
#     hub_to_tip_ratio = x_opt[2]

#     specific_speed = x_opt[3]
#     blade_jet_ratio = x_opt[4]

#     omega = specific_speed * (...)
#     spouting_velocity = cascade_data["spouting_velocity"]

#     # Compute exit radius from speed
#     blade_speed = blade_jet_ratio * spouting_velocity
#     radius_mean_out = blade_speed / omega

#     radius_type = ... # constant_mean, constant_hub, constant_tip

#     if radius_type == "constant_mean":
#         radius_hub = radius_mean_out* (...)
#         radius_tip = radius_mean_out* (...)

#     else:



#  Two scenatios for optimization
#  1. design from scratch
#  2. design from existing geometry
    # Calculate the x_opt from "geometry" entry of configuration file
    # Getting the x_opt_0 is not a problem
    # We still need to define the fixed parameters / DOF and also the ub/lb and the constraint values 

    # If config optimization defines initial guess for variable it uses it. If it does not define it, it tries to get it from geometyr. If geometry is not defined, then raises and error
    # Something similar for the bounds of the optimization

