from typing import Callable, Dict, Sequence, get_type_hints


__all__ = ["str_to_int"]


# a simple transformation for testing purposes
def str_to_int() -> Dict[str, classmethod]:
    @classmethod
    def _str_to_int(cls, val):
        return int(val)

    return {"str_to_int": _str_to_int}
    
