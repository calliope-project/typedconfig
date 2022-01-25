import keyword
import types
from typing import Any, Callable, Dict

from pydantic import root_validator, validator
from pydantic.dataclasses import dataclass as pydantic_dataclass

_vmap_t = Dict[str, classmethod]


# copied and adapted make_dataclass(..) from cpython/Lib/dataclasses.py
def make_typedconfig(cls_name, fields, *, bases=(), namespace=None, **kwargs):
    """Return a new dynamically created dataclass.

    The dataclass name will be 'cls_name'.  'fields' is an iterable
    of either (name, type) or (name, type, Field) objects. If type is
    omitted, use the string 'typing.Any'.  Field objects are created by
    the equivalent of calling 'field(name, type [, Field-info])'.

      C = make_typedconfig(
          "C", [("x", int), ("y", int, field(init=False))], bases=(Base,)
      )

    is equivalent to:

      @dataclass
      class C(Base):
          x: int
          y: int = field(init=False)

    For the bases and namespace parameters, see the builtin type() function.

    The parameters init, repr, eq, order, unsafe_hash, and frozen are passed to
    pydantic_dataclass().
    """

    if namespace is None:
        namespace = {}
    else:
        # Copy namespace since we're going to mutate it.
        namespace = namespace.copy()

    # While we're looking through the field names, validate that they
    # are identifiers, are not keywords, and not duplicates.
    seen = set()
    anns = {}
    for item in fields:
        if len(item) == 2:
            name, tp = item
        elif len(item) == 3:
            # FIXME: field spec is ignored, see _process_class in
            # pydantic.dataclasses
            name, tp, spec = item
            namespace[name] = spec
        else:
            raise TypeError(f"Invalid field: {item!r}")

        if not isinstance(name, str) or not name.isidentifier():
            raise TypeError(f"Field names must be valid identifiers: {name!r}")
        if keyword.iskeyword(name):
            raise TypeError(f"Field names must not be keywords: {name!r}")
        if name in seen:
            raise TypeError(f"Field name duplicated: {name!r}")

        seen.add(name)
        anns[name] = tp

    namespace["__annotations__"] = anns
    # We use `types.new_class()` instead of simply `type()` to allow dynamic
    # creation of generic dataclassses.
    cls = types.new_class(cls_name, bases, {}, lambda ns: ns.update(namespace))

    return pydantic_dataclass(cls, **kwargs)


def make_validator(func: Callable, key: str, *, opts: Dict = {}, **params) -> _vmap_t:
    """Create a validator classmethod by wrapping a function in a closure

    Parameters
    ----------
    func : Callable
        Function to use as a validator.  The function should conform to the
        following argspec:

          FullArgSpec(args=['cls', 'val', 'values'], varargs=None, kwonlyargs=[...])

    key : str
        Key to associate validator with.  If key is "falsy" (empty string,
        None, etc), a root_validator is created instead.

    opts : Dict

    **params
        Keyword arguments to be passed on to the validator function `func`

    Returns
    -------
    Dict[str, classmethod]
        A dictionary with the validator function wrapped as a classmethod

          {'function_name' : classmethod(func)}

    """
    # NOTE: cannot use functools.partial because pydantic does very restrictive
    # function signature checks.  The module and qualitative names are also
    # expected to be set.

    def wrapper_key(cls, val, values):
        return func(cls, val, values, **params)

    def wrapper_root(cls, values):
        return func(cls, values, **params)

    wrapper = wrapper_key if key else wrapper_root

    def stringify(params: Dict[str, Any]) -> str:
        return f"[{','.join(f'{k}={v}' for k, v in params.items())}]"

    # NOTE: pydantic validates a dataclass by the creating a new model
    # (subclass of BaseModel) from the type annotations, and validator methods
    # in the dataclass definition.  BaseModel specifies a custom metaclass,
    # which internally uses a data structure (ValidatorGroup) that aggregates
    # all validators and groups them by the class attribute they are associated
    # with.  Unfortunately when retrieving the validators from the data
    # structure, it returns a dictionary where the key is func.__name__.  This
    # means the wrapping function's name has to be uniquified.
    #
    # Strictly speaking, adding the parameters to the name is not necessary,
    # but it is there for easier debugging when required.
    wrapper.__name__ = f"{key}_" + func.__name__ + stringify(params)

    # NOTE: pydantic keeps a global registry of all validators as
    # <module>.<qualified name>[*] and prevents reuse unless explicitly
    # overridden with allow_reuse=True; see _prepare_validator in
    # pydantic/class_validators.py.  We still set the qualified name to be
    # consistent with the name.
    #
    # [*] to understand qualified name (<type>.__qualname__), see:
    # https://docs.python.org/3/glossary.html#term-qualified-name
    wrapper.__qualname__ = wrapper.__name__
    opts = {"allow_reuse": True, **opts}

    decorator = validator(key, **opts) if key else root_validator(**opts)
    return {func.__name__: decorator(wrapper)}
