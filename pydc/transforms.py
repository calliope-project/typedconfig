from typing import Callable, Dict, Sequence, get_type_hints


__all__ = ["range_check"]


# a simple transformation for testing purposes
def str_to_int(key: str) -> Dict[str, classmethod]:
    @classmethod(key)
    def _str_to_int(cls, val):
        return int(val)

    return {"str_to_int", _str_to_int}
    
