import re
import yaml
import numbers
import numpy as np

from . import numeric as num


def read_configuration_file(filename):
    """Reads and a YAML configuration file"""
    # Read configuration file
    try:
        with open(filename, "r") as file:
            config = yaml.safe_load(file)
    except Exception as e:
        raise Exception(
            f"Error parsing configuration file: '{filename}'. Original error: {e}"
        )

    # Convert options to Numpy when possible
    config = convert_configuration_options(config)

    return config


def convert_configuration_options(config):
    """
    Processes configuration data by evaluating string expressions as numerical values and converting lists to numpy arrays.

    This function iteratively goes through the configuration dictionary and converts string representations of numbers
    (e.g., "1+2", "2*np.pi") into actual numerical values using Python's `eval` function. It also ensures that all numerical
    values are represented as Numpy types for consistency across the application.

    Parameters
    ----------
    config : dict
        The configuration data loaded from a YAML file, typically containing a mix of strings, numbers, and lists.

    Returns
    -------
    dict
        The postprocessed configuration data where string expressions are evaluated as numbers, and all numerical values
        are cast to corresponding NumPy types.

    Raises
    ------
    ConfigurationError
        If a list contains elements of different types after conversion, indicating an inconsistency in the expected data types.
    """

    def convert_strings_to_numbers(data):
        """
        Recursively converts string expressions within the configuration data to numerical values.

        This function handles each element of the configuration: dictionaries are traversed recursively, lists are processed
        element-wise, and strings are evaluated as numerical expressions. Non-string and valid numerical expressions are
        returned as is. The conversion supports basic mathematical operations and is capable of recognizing Numpy functions
        and constants when used in the strings.

        Parameters
        ----------
        data : dict, list, str, or number
            A piece of the configuration data that may contain strings representing numerical expressions.

        Returns
        -------
        The converted data, with all string expressions evaluated as numbers.
        """
        if isinstance(data, dict):
            return {
                key: convert_strings_to_numbers(value) for key, value in data.items()
            }
        elif isinstance(data, list):
            return [convert_strings_to_numbers(item) for item in data]
        elif isinstance(data, bool):
            return data
        elif isinstance(data, str):
            # Evaluate strings as numbers if possible
            try:
                data = eval(data)
                return convert_numbers_to_numpy(data)
            except (NameError, SyntaxError, TypeError):
                return data
        elif isinstance(data, numbers.Number):
            # Convert Python number types to corresponding NumPy number types
            return convert_numbers_to_numpy(data)
        else:
            return data

    def convert_numbers_to_numpy(data):
        """
        Casts Python native number types (int, float) to corresponding Numpy number types.

        This function ensures that all numeric values in the configuration are represented using Numpy types.
        It converts integers to `np.int64` and floats to `np.float64`.

        Parameters
        ----------
        data : int, float
            A numerical value that needs to be cast to a Numpy number type.

        Returns
        -------
        The same numerical value cast to the corresponding Numpy number type.

        """
        if isinstance(data, int):
            return np.int64(data)
        elif isinstance(data, float):
            return np.float64(data)
        else:
            return data

    def convert_to_arrays(data, parent_key=""):
        """
        Convert lists within the input data to Numpy arrays.

        Iterates through the input data recursively. If a list is encountered, the function checks if all elements are of the same type.
        If they are, the list is converted to a Numpy array. If the elements are of different types, a :obj:`ConfigurationError` is raised.

        Parameters
        ----------
        data : dict or list or any
            The input data which may contain lists that need to be converted to NumPy arrays. The data can be a dictionary (with recursive processing for each value), a list, or any other data type.
        parent_key : str, optional
            The key in the parent dictionary corresponding to `data`, used for error messaging. The default is an empty string.

        Returns
        -------
        dict or list or any
            The input data with lists converted to NumPy arrays. The type of return matches the type of `data`. Dictionaries and other types are returned unmodified.

        Raises
        ------
        ValueError
            If a list within `data` contains elements of different types. The error message includes the problematic list and the types of its elements.

        """
        if isinstance(data, dict):
            return {k: convert_to_arrays(v, parent_key=k) for k, v in data.items()}
        elif isinstance(data, list):
            if not data:  # Empty list
                return data
            first_type = type(data[0])
            if not all(isinstance(item, first_type) for item in data):
                element_types = [type(item) for item in data]
                raise ValueError(
                    f"Option '{parent_key}' contains elements of different types: {data}, "
                    f"types: {element_types}"
                )
            return np.array(data)
        else:
            return data

    # Convert the configuration options to Numpy arrays when relevant
    config = convert_strings_to_numbers(config)
    config = convert_to_arrays(config)

    return config


def validate_configuration_file(filename, configuration_schema):
    """Validates configuration fictionary (returns multiple outputs)"""

    # Read configuration file
    config = read_configuration_file(filename)

    # Validate the configuration dictionary
    config, info, error = validate_configuration_options(
        config, configuration_schema,
    )

    return config, info, error

NUMERIC = "<numeric value>"

def validate_configuration_options(config, schema):
    """
    Validates the configuration against the provided schema.
    This function performs several checks, including:

    - Presence of unexpected keys: Ensures there are no extra fields in the configuration
      that are not defined in the schema.
    - Mandatory fields: Checks that all fields marked as mandatory in the schema are present
      in the configuration.
    - Data type validation: Verifies that each field in the configuration matches the expected
      data type(s) defined in the schema. The expected type can be a single type or a combination of types.
    - Valid options: For fields with a specified list of valid values, it checks that the
      field's value in the configuration is one of these valid options. This includes support for numeric values
      where a string placeholder like '<numeric value>' is used in the schema.
    - Default values: For non-mandatory fields that are not present in the configuration,
      assigns a default value if one is specified in the schema.
    - Nested fields: Recursively validates nested dictionaries within the configuration,
      regardless of whether they are presented as individual dictionaries or as lists/arrays
      of dictionaries. The validation is conducted according to the nested schema defined
      under the '_nested' key. This approach ensures consistency in handling nested
      configurations, facilitating flexibility in configuration structure.

    The function raises a :obj:`ConfigurationError` if any discrepancies are found and also includes
    messages for fields where default values are used.

    Parameters
    ----------
    config : dict
        The 'model_options' section of the configuration to be validated.
    schema : dict
        The schema against which the configuration will be validated.

    Returns
    -------
    dict
        The updated configuration dictionary after applying default values.

    Raises
    ------
    ConfigurationError
        If there are any discrepancies between the configuration and the schema.

    .. note::

        The function allows for rapid development and prototyping by bypassing validation for any configuration options
        prefixed with an underscore ``_``. This feature is particularly useful for testing new or experimental settings
        without having to update the entire validation schema.

    """
    # TODO: Consider using a dedicated validation library?

    def validate_field(config, schema, parent, errors, info):
        # Check for unexpected keys
        # Bypass validation for keys starting with '_' to skip options during development
        # Use sorted to preserve order (required for regression tests)
        keys_to_validate_against = set(sorted(schema.keys()))
        keys_to_validate = set(
            k for k in sorted(config.keys()) if not k.startswith("_")
        )
        unexpected_keys = keys_to_validate - keys_to_validate_against
        if unexpected_keys:
            name = parent if parent else "root"
            errors.append(f"Unexpected keys in '{name}': {unexpected_keys}")

        # Loop through all the possible configuration options
        # Use sorted to preserve order (required for regression tests)
        for key in sorted(schema.keys()):
            specs = schema[key]

            # Define option path recursively
            current_path = f"{parent}/{key}" if parent else key

            # Ensure expected_type is a tuple
            # Check needed because some variables can have multiple types
            expected_types = specs["expected_type"]
            if not isinstance(expected_types, tuple):
                expected_types = (
                    tuple(expected_types)
                    if isinstance(expected_types, list)
                    else (expected_types,)
                )

            # Check if the key is present in the configuration
            if key in config:
                # Validate the type
                if not isinstance(config[key], expected_types):
                    type_expected = ", ".join([t.__name__ for t in expected_types])
                    type_actual = type(config[key]).__name__
                    msg = f"Incorrect type for field '{current_path}': '{type_actual}'. Expected {type_expected}"
                    errors.append(msg)

                # Validate option from list if there are valid options defined
                elif specs.get("valid_options") is not None:
                    conf_values = num.ensure_iterable(config[key])
                    for item in conf_values:
                        # Check single value or each item of the list/array
                        if item not in specs["valid_options"] and not (
                            NUMERIC in specs["valid_options"]
                            and isinstance(item, (int, float))
                        ):
                            msg = f"Invalid value '{item}' for field '{current_path}'. Valid options are: {specs['valid_options']}"
                            errors.append(msg)

            # If the key is not present and is mandatory, add error message
            elif specs["is_mandatory"]:
                errors.append(f"Missing required field: '{current_path}'")

            # If the key is not present and is non-mandatory, use the default value if provided
            elif not specs["is_mandatory"] and "default_value" in specs:
                config[key] = specs["default_value"]
                msg = f"Field '{current_path}' not specified; using default value: {specs['default_value']}"
                info.append(msg)

            else:
                errors.append(
                    f"Unexpected configuration for field '{key}'. Revise manually"
                )

            # Recursively validate nested fields
            if "_nested" in specs:
                nested_conf = config.get(key, {})

                # Ensure that nested configurations are iterable (operation_points can be a list of dictionaries)
                nested_conf = (
                    num.ensure_iterable(nested_conf)
                    if specs["_nested"]
                    else nested_conf
                )

                # If it's a list or array of dictionaries, iterate through each item
                if isinstance(nested_conf, (list, np.ndarray)):
                    for item in nested_conf:
                        if isinstance(item, dict):
                            validate_field(
                                item, specs["_nested"], current_path, errors, info
                            )
                        else:
                            errors.append(
                                f"Each item in '{current_path}' must be a dictionary."
                            )
                elif isinstance(
                    nested_conf, dict
                ):  # Single dictionary, validate directly
                    validate_field(
                        nested_conf, specs["_nested"], current_path, errors, info
                    )
                else:
                    errors.append(
                        f"Invalid type for nested field '{current_path}'. Expected a dictionary or list of dictionaries."
                    )

        return config

    # Initialize lists to save errors and messages
    errors, info = [], []

    # Ensure 'settings' exists in config and validate it
    config.setdefault("general_settings", {})
    settings_config = {"general_settings": config["general_settings"]}
    settings_schema = {"general_settings": schema["general_settings"]}
    settings_config = validate_field(
        settings_config, settings_schema, None, errors, info
    )
    if settings_config["general_settings"]["skip_validation"]:
        info = "Configuration validation was skipped."
        return config, info, None

    # Validate the configuration files
    validated_configuration = validate_field(config, schema, None, errors, info)

    if info:
        info.insert(0, "Some parameters were not defined. Using default options:")
        info = "\n".join(info)
    else:
        info = "Configuration options were sucessfully validated."

    if errors:
        return validated_configuration, info, ConfigurationError(errors)

    return validated_configuration, info, None


class ConfigurationError(Exception):
    """
    Exception class for handling errors in configuration options.

    This exception is raised when discrepancies, inconsistencies, or other issues are detected
    in the configuration options of an application. It is primarily used during the validation
    process of configuration data, where it checks against a predefined schema or set of rules.

    The `ConfigurationError` encapsulates one or more error messages that detail the specific
    problems found in the configuration. These messages provide insights into missing fields,
    data type mismatches, invalid values, and other violations of the configuration schema.

    Attributes
    ----------
    messages : list of str
        A list of error messages that describe all issues detected the configuration.

    Examples
    --------
    >>> raise ConfigurationError(["Invalid value in field 'max_speed'",
                                  "Missing required field: 'engine_type'"])
    ConfigurationError: Configuration errors detected.
    Invalid value in field 'max_speed';
    Missing required field: 'engine_type'
    """

    def __init__(self, messages):
        self.messages = messages
        super().__init__(self._format_message())

    def _format_message(self):
        return "Configuration errors detected.\n" + ";\n".join(self.messages)


def convert_numpy_to_python(data, precision=10):
    """
    Recursively converts numpy arrays, scalars, and other numpy types to their Python counterparts
    and rounds numerical values to the specified precision.

    Parameters:
    - data: The numpy data to convert.
    - precision: The decimal precision to which float values should be rounded.

    Returns:
    - The converted data with all numpy types replaced by native Python types and float values rounded.
    """

    if data is None:
        return None

    if isinstance(data, dict):
        return {k: convert_numpy_to_python(v, precision) for k, v in data.items()}

    elif isinstance(data, list):
        return [convert_numpy_to_python(item, precision) for item in data]

    elif isinstance(data, np.ndarray):
        # If the numpy array has more than one element, it is iterable.
        if data.ndim > 0:
            return [convert_numpy_to_python(item, precision) for item in data.tolist()]
        else:
            # This handles the case of a numpy array with a single scalar value.
            return convert_numpy_to_python(data.item(), precision)

    elif isinstance(
        data,
        (np.integer, np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64),
    ):
        return int(data.item())

    elif isinstance(data, (np.float_, np.float16, np.float32, np.float64)):
        return round(float(data.item()), precision)

    elif isinstance(data, np.bool_):
        return bool(data.item())

    elif isinstance(data, (np.str_, np.unicode_)):
        return str(data.item())

    # This will handle Python built-in types and other types that are not numpy.
    elif isinstance(data, (float, int, str, bool)):
        if isinstance(data, float):
            return round(data, precision)
        return data

    else:
        raise TypeError(f"Unsupported data type: {type(data)}")


def render_and_evaluate(expression, data):
    """
    Render variables prefixed with '$' in an expression and evaluate the resulting expression.

    This function processes an input string `expr`, identifying all occurrences of variables
    indicated by a leading '$' symbol. Each such variable is resolved to its value from the
    provided `context` dictionary. The expression with all variables resolved is then evaluated
    and the result is returned.

    This function is useful to render strings defined in a YAML configuration file to values
    that are calculated within the code and stored in a dicitonary.

    Parameters
    ----------
    expr : str
        The expression string containing variables to be rendered. Variables in the
        expression are expected to be prefixed with a '$' symbol.
    data : dict
        A dictionary containing variables and their corresponding values. These variables
        are used to render values in the expression.

    Returns
    -------
    The result of evaluating the rendered expression. The type of the result depends on the
    expression.

    Notes
    -----
    - `pattern`: A regular expression pattern used to identify variables within the expression.
      Variables are expected to be in the format `$variableName`, potentially with dot-separated
      sub-properties (e.g., `$variable.property`).

    - `replace_with_value`: An inner function that takes a regex match object and returns
      the value of the variable from `context`. `match.group(1)` returns the first captured
      group from the matched text, which in this case is the variable name excluding the
      leading '$' symbol. For example, in `$variableName`, `match.group(1)` would return
      `variableName`.

    - The function uses Python's `eval` for evaluation, which should be used cautiously as
      it can execute arbitrary code. Ensure that the context and expressions are from a trusted
      source.
    """
    # Pattern to find $variable expressions
    pattern = re.compile(r"\$(\w+(\.\w+)*)")

    # Function to replace each match with its resolved value
    def replace_with_value(match):
            nested_key = match.group(1)
            try:
                value = render_nested_value(nested_key, data)
                if isinstance(value, np.ndarray):
                    return "np.array(" + repr(value.tolist()) + ")"
                else:
                    return repr(value)
            except KeyError:
                raise KeyError(f"Variable '{nested_key}' not found in the provided data context.")


    try:
        # Replace all $variable with their actual values
        resolved_expr = pattern.sub(replace_with_value, expression)

        # Check if any unresolved variables remain
        if "$" in resolved_expr:
            raise ValueError(f"Unresolved variable in expression: '{resolved_expr}'")

        # Now evaluate the expression
        return eval(resolved_expr)
    
    except SyntaxError as e:
        raise SyntaxError(f"Syntax error in '{expression}': {e}")
    except Exception as e:
        # Enhanced error message
        raise TypeError(f"Error evaluating expression '{expression}': {e}.\n"
                        "If the expression is meant to use data from the configuration, "
                        "ensure each variable is prefixed with '$'. For example, use '$variable_name' "
                        "instead of 'variable_name'.")  


def render_nested_value(nested_key, data):
    """
    Retrieves a value from a nested structure (dictionaries or objects with attributes) using a dot-separated key.

    This function is designed to navigate through a combination of dictionaries and objects. For an object to be
    compatible with this function, it must implement a `keys()` method that returns its attribute names.

    This function is intended as a subroutine of the more genera ``render_expression``

    Parameters
    ----------
    nested_key : str
        A dot-separated key string that specifies the path in the structure.
        For example, 'level1.level2.key' will retrieve data['level1']['level2']['key'] if data is a dictionary,
        or data.level1.level2.key if data is an object or a combination of dictionaries and objects.

    data : dict or object
        The starting dictionary or object from which to retrieve the value. This can be a nested structure
        of dictionaries and objects.

    Returns
    -------
    value
        The value retrieved from the nested structure using the specified key.
        The type of the value depends on what is stored at the specified key in the structure.

    Raises
    ------
    KeyError
        If the specified nested key is not found in the data structure. The error message includes the part
        of the path that was successfully traversed and the available keys or attributes at the last valid level.
    """
    keys = nested_key.split(".")
    value = data
    traversed_path = []

    for key in keys:
        if isinstance(value, dict):
            # Handle dictionary-like objects
            if key in value:
                traversed_path.append(key)
                value = value[key]
            else:
                valid_keys = ", ".join(value.keys())
                traversed_path_str = (
                    ".".join(traversed_path) if traversed_path else "root"
                )
                raise KeyError(
                    f"Nested key '{key}' not found at '{traversed_path_str}'. Available keys: {valid_keys}"
                )
        elif hasattr(value, key):
            # Handle objects with attributes
            traversed_path.append(key)
            value = getattr(value, key)
        else:
            traversed_path_str = ".".join(traversed_path)
            available_keys = ", ".join(value.keys())
            raise KeyError(
                f"Key '{key}' not found in object at '{traversed_path_str}'. Available keys: {available_keys}"
            )

    if not num.is_numeric(value):
        raise ValueError(
            f"The key '{nested_key}' is not numeric. Key value is: {value}"
        )

    return value
