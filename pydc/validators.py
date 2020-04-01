from typing import Callable, Dict, Sequence, get_type_hints

from pydantic import validator

__all__ = ["range_check"]


# TODO: rewrite as a simple function, where the parameters are injected into
# the closure in a generic factory method
def range_check(
    key: str, keys: Sequence[str], **opts
) -> Dict[str, classmethod]:
    @validator(key, **opts)
    def _range_check(cls, _max, values):
        """Validator function for a range config object"""
        if keys[0] in values and values[keys[0]] > _max:
            raise ValueError(f"bad range: {values[keys[0]]} > {_max}")
        return _max

    return {"range_check": _range_check}


# type hints for a validator factory
_annotations = get_type_hints(range_check)
validator_factory_t = Callable[
    [v for k, v in _annotations.items() if k != "return"],
    _annotations["return"],
]
