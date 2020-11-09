from itertools import product

__all__ = [
    "range_check",
    "quadrant",
    "threshold",
    "mult_of",
    "zero_sum",
    "sum_by_name",
    "inheritance",
]


def range_check(cls, _max, values, *, min_key):
    """Validator function for a range config object"""
    if min_key in values and values[min_key] > _max:
        raise ValueError(f"bad range: {values[min_key]} > {_max}")
    return _max


def quadrant(cls, values, *, axes, signs):
    if all(k in values for k in axes) and all(
        values[k] * s > 0 for k, s in zip(axes, signs) if s != 0
    ):
        return values

    raise ValueError(f"{values} not in quadrant: {signs}")


def threshold(cls, val, values, *, threshold):
    if val > threshold:
        raise ValueError(f"above threshold: {val} > {threshold}")
    return val


def mult_of(cls, val, values, *, factor):
    if val % factor == 0:
        return val
    raise ValueError(f"{val} is not a multiple of {factor}")


def zero_sum(cls, values, *, total):
    mysum = sum(values.values())
    if mysum != total:
        raise ValueError(f"{list(values.values())} do not add up to {total}")
    return values


def sum_by_name(cls, values, *, total):
    mysum = values.get("first", 0) + values.get("second", 0)
    if mysum != total:
        raise ValueError(f"{list(values.values())} do not add up to {total}")
    return values


def inheritance(cls, val, values, *, allowed_in):
    # if issubclass(cls, allowed_in):  # FIXME: get the types
    #     raise ValueError(f"{cls} does not inherit from either of {allowed_in}")

    # MRO ends in the base property class, and object, remove those
    if any(
        map(
            lambda i: i[0] in i[1],
            product(allowed_in, map(str, cls.mro()[:-2])),  # FIXME: nasty hack
        )
    ):
        return val
    raise TypeError(f"{cls} does not inherit from either of {allowed_in}")
