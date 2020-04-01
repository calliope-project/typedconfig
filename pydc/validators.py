__all__ = ["range_check"]


def range_check(cls, _max, values, *, min_key):
    """Validator function for a range config object"""
    if min_key in values and values[min_key] > _max:
        raise ValueError(f"bad range: {values[min_key]} > {_max}")
    return _max
