from typing import Callable, Dict, Sequence, get_type_hints
from pandas import Timedelta

__all__ = ["str_to_timedelta"]


# trivial implementation for testint purposes
def str_to_timedelta(val: str):
    return Timedelta(val)
