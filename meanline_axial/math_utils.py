import numpy as np

def softmax_logsumexp(x, alpha, axis=None, keepdims=False):
    """
    Approximate the maximum of an array using the log-sum-exp method.

    This method approximates the maximum (or minimum) operation using the 
    following equation:

    .. math::

       \text{logsumexp}(x) = \frac{1}{\alpha} \log \left( \sum_i \exp(\alpha (x_i - \text{shift})) \right) + \text{shift}

    where the shift is defined as:

    .. math::

       \text{shift} = \text{sign}(\alpha) \max_i \text{sign}(\alpha) x_i

    Shifting the array values prevents numerical overflow due to the finite precision of floating-point operations

    Parameters
    ----------
    x : array_like
        Input data.
    alpha : float
        Sharpness parameter. Positive values approximate the maximum, 
        while negative values approximate the minimum.
    axis : None or int or tuple of ints, optional
        Axis or axes along which to operate. By default, flattened input is
        used. If this is a tuple of ints, the maximum is selected over 
        multiple axes, instead of a single axis or all the axes as before.
        This has the same behavior as the `axis` parameter in `numpy.max`.
    keepdims : bool, optional
        If this is set to True, the axes which are reduced are left
        in the result as dimensions with size one. With this option,
        the result will broadcast correctly against the input array.
        This behavior is consistent with the `keepdims` parameter in `numpy.max`.

    Returns
    -------
    max_approx : ndarray or scalar
        Approximated maximum (or minimum for negative alpha) of x. If `axis` 
        is None, the result is a scalar value. If `axis` is an int, the result 
        is an array of dimension ``x.ndim - 1``. If `axis` is a tuple, the 
        result is an array of dimension ``x.ndim - len(axis)``.

    """

    # Determine the shift for numerical stability
    shift_value = np.sign(alpha) * np.max(np.sign(alpha) * x, axis=axis, keepdims=True)

    # Compute log-sum-exp with the shift and scale by alpha
    log_sum = np.log(np.sum(np.exp(alpha * (x - shift_value)), axis=axis, keepdims=True))

    # Normalize the result by alpha and correct for the shift
    approx_max = (log_sum + alpha * shift_value) / alpha

    # Handle keepdims
    if not keepdims:
        if isinstance(axis, tuple):
            for ax in sorted(axis, reverse=True):
                approx_max = np.squeeze(approx_max, axis=ax)
        elif isinstance(axis, int):
            approx_max = np.squeeze(approx_max, axis=axis)

    return approx_max


def softmax_boltzmann(x, alpha, axis=None, keepdims=False):
    """
    Approximate the maximum of an array using the Boltzmann weighted average.

    The Boltzmann weighted average is defined as:

    .. math::

       \text{max\_boltzmann}(x) = \frac{\sum_i x_i \exp(\alpha (x_i - \text{shift}))}{\sum_i \exp(\alpha (x_i - \text{shift}))}

    where the shift is defined as:

    .. math::

       \text{shift} = \text{sign}(\alpha) \max_i \text{sign}(\alpha) x_i

    Shifting the array values prevents numerical overflow due to the finite precision of floating-point operations

    Parameters
    ----------
    xi : array_like
        Input data.
    alpha : float
        Sharpness parameter. Positive values approximate the maximum, 
        while negative values approximate the minimum.
    axis : None or int or tuple of ints, optional
        Axis or axes along which to operate. By default, flattened input is
        used. If this is a tuple of ints, the maximum is selected over 
        multiple axes, instead of a single axis or all the axes as before.
        This has the same behavior as the `axis` parameter in `numpy.max`.
    keepdims : bool, optional
        If this is set to True, the axes which are reduced are left
        in the result as dimensions with size one. With this option,
        the result will broadcast correctly against the input array.
        This has the same behavior as the `axis` parameter in `numpy.max`.

    Returns
    -------
    max_approx : ndarray or scalar
        Approximate maximum of `x` using the Boltzmann method.
    """
    
    # Compute the shift for numerical stability
    shift = np.sign(alpha) * np.max(np.sign(alpha) * x, axis=axis, keepdims=True)

    # Compute the weighted sum (numerator) of the elements of x
    weighted_sum = np.sum(x * np.exp(alpha * (x - shift)), axis=axis, keepdims=True)
    
    # Compute the sum of the softmax weights (denominator)
    weight_sum = np.sum(np.exp(alpha * (x - shift)), axis=axis, keepdims=True)

    # Compute the Boltzmann-weighted average avoiding division by zero
    max_approx = weighted_sum / (weight_sum + np.finfo(float).eps)

    if not keepdims:
        # Remove the dimensions of size one if keepdims is False
        max_approx = np.squeeze(max_approx, axis=axis)
    
    return max_approx


def softmax_pnorm(x, alpha, axis=None, keepdims=False):
    """
    Approximate the maximum of an array using the p-norm method.

    The p-norm approximation is defined as:

    .. math::

       \text{max\_pnorm}(x) = \left( \sum_i x_i^\alpha \right)^{\frac{1}{\alpha}}

    This approach leverages properties of p-norms to approximate the maximum (or minimum) 
    value in the array based on the chosen value of `alpha`.

    Parameters
    ----------
    x : array_like
        Input data.
    alpha : float
        Exponent value. Large positive values of `alpha` approximate the maximum,
        while large negative values approximate the minimum. Intermediate values
        provide a soft approximation.
    axis : None or int or tuple of ints, optional
        Axis or axes along which to operate. By default, flattened input is
        used. If this is a tuple of ints, the maximum is selected over 
        multiple axes, instead of a single axis or all the axes as before.
    keepdims : bool, optional
        If this is set to True, the axes which are reduced are left
        in the result as dimensions with size one. With this option,
        the result will broadcast correctly against the input array.

    Returns
    -------
    max_approx : ndarray or scalar
        Approximate maximum of `x` using the p-norm method.
    """
    
    # Compute the p-norm approximation
    pnorm_approx = np.sum(np.power(x, alpha), axis=axis, keepdims=True)**(1/alpha)

    if not keepdims:
        # Remove the dimensions of size one if keepdims is False
        pnorm_approx = np.squeeze(pnorm_approx, axis=axis)

    return pnorm_approx


def softmax(x, method='boltzmann', alpha=1.0, axis=None, keepdims=False):
    """
    Approximate the maximum (or minimum) of an array using various methods.
    
    Parameters
    ----------
    x : array_like
        Input data.
    method : str, optional
        Method to be used for the approximation. Supported methods are:
        
        - 'logsumexp'
        - 'boltzmann'
        - 'p-norm'
        
        Default is 'boltzmann'.
    alpha : float, optional
        Sharpness parameter. For 'logsumexp' and 'boltzmann' methods: positive 
        values approximate the maximum, while negative values approximate 
        the minimum. For 'p-norm' method, it represents the exponent value.
    axis : None or int or tuple of ints, optional
        Axis or axes along which to operate. By default, flattened input is
        used. If this is a tuple of ints, the maximum is selected over 
        multiple axes, instead of a single axis or all the axes as before.
    keepdims : bool, optional
        If this is set to True, the axes which are reduced are left
        in the result as dimensions with size one. With this option,
        the result will broadcast correctly against the input array.

    Returns
    -------
    max_approx : ndarray or scalar
        Approximate maximum of `x` using the specified method.

    Raises
    ------
    ValueError
        If an unsupported method is specified.

    Examples
    --------
    >>> data = np.array([0.5, 0.1, 0.8])
    >>> softmax(data, method='logsumexp', alpha=10)
    [approximated result]
    >>> softmax(data, method='p-norm', alpha=3)
    [approximated result]
    """
    
    if method == 'logsumexp':
        return softmax_logsumexp(x, np.abs(alpha), axis, keepdims)
    elif method == "boltzmann":
        return softmax_boltzmann(x, np.abs(alpha), axis, keepdims)
    elif method == 'p-norm':
        return softmax_pnorm(x, np.abs(alpha), axis, keepdims)
    else:
        raise ValueError(f"Unsupported method '{method}'. Supported methods are:\n"
                         "- 'logsumexp'\n"
                         "- 'boltzmann'\n"
                         "- 'p-norm'")


def softmin(x, method='boltzmann', alpha=1.0, axis=None, keepdims=False):
    """
    Approximate the minimum (or maximum) of an array using various methods.
    
    Parameters
    ----------
    x : array_like
        Input data.
    method : str, optional
        Method to be used for the approximation. Supported methods are:
        
        - 'logsumexp'
        - 'boltzmann'
        - 'p-norm'
        
        Default is 'boltzmann'.
    alpha : float, optional
        Sharpness parameter. For 'logsumexp' and 'boltzmann' methods: negative
        values approximate the minimum, while positive values approximate 
        the maximum. For 'p-norm' method, it represents the exponent value.
    axis : None or int or tuple of ints, optional
        Axis or axes along which to operate. By default, flattened input is
        used. If this is a tuple of ints, the minimum is selected over 
        multiple axes, instead of a single axis or all the axes as before.
    keepdims : bool, optional
        If this is set to True, the axes which are reduced are left
        in the result as dimensions with size one. With this option,
        the result will broadcast correctly against the input array.

    Returns
    -------
    min_approx : ndarray or scalar
        Approximate minimum of `x` using the specified method.

    Raises
    ------
    ValueError
        If an unsupported method is specified.

    Examples
    --------
    >>> data = np.array([0.5, 0.1, 0.8])
    >>> softmin(data, method='logsumexp', alpha=-10)
    [approximated result]
    >>> softmin(data, method='p-norm', alpha=-3)
    [approximated result]
    """
    
    if method == 'logsumexp':
        return softmax_logsumexp(x, -np.abs(alpha), axis, keepdims)
    elif method == "boltzmann":
        return softmax_boltzmann(x, -np.abs(alpha), axis, keepdims)
    elif method == 'p-norm':
        return softmax_pnorm(x, -np.abs(alpha), axis, keepdims)
    else:
        raise ValueError(f"Unsupported method '{method}'. Supported methods are:\n"
                         "- 'logsumexp'\n"
                         "- 'boltzmann'\n"
                         "- 'p-norm'")


