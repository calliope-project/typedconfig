import keyword
import types

from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.main import ModelMetaclass


# copied and adapted make_dataclass(..) from cpython/Lib/dataclasses.py
def make_dataconfig(
    cls_name, fields, *, bases=(), namespace=None, **kwargs,
):
    """Return a new dynamically created dataclass.

    The dataclass name will be 'cls_name'.  'fields' is an iterable
    of either (name, type) or (name, type, Field) objects. If type is
    omitted, use the string 'typing.Any'.  Field objects are created by
    the equivalent of calling 'field(name, type [, Field-info])'.

      C = make_dataconfig(
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
            name, tp, = item
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
    # We use `types.new_class()` instead of simply `type()` to allow dynamic creation
    # of generic dataclassses.
    cls = types.new_class(
        cls_name,
        bases,
        {"metaclass": ModelMetaclass},
        lambda ns: ns.update(namespace),
    )
    return pydantic_dataclass(cls, **kwargs)
