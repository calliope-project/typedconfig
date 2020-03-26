Ruleset specification
=====================

The basic config item has the following properties:

- ``type``: type information
- ``opts``: options for the type information, can be two kinds:

  - if passing keyword arguments to a type factory function like
    ``pydantic.types.conint`` the option is a dictionary,
  - if passing a sequence through ``[..]``, the option is a list.

- ``validator``: function bound to this config item that checks validity
- ``validator_opts``: options for how the validator behaves
- ``doc``: config documentation
- ``id``: currently unused

The default parser expects the config items are organised
hierarchically (like an inverted tree); the parser allows multiple
root nodes, effectively allowing for multiple configuration
hierarchies in parallel.

Requirements
------------

- The ``type`` property is mandatory for a leaf node, however a branch
  node may not have one.
- The ``opts`` property maybe present *only* if ``type`` is.
- All nodes may have a ``validator``, it is a factory function that
  returns the real validator, a ``classmethod`` with all of the
  configuration keys at the same level bound to a list inside a
  closure.  The factory function returns a dictionary, with the
  classmethod as value.  The expected signatures are:

  - factory: ``Callable[[str, Sequence[str]], Dict[str, classmethod]]``
  - validator: it should have the signature required by ``pydantic``,
    first argument is the class type, followed by the key value, and a
    dictionary of keys with values that passed validation.

    ::

       def factory(key: str, keys: Sequence[str], **opts) -> Dict[str, classmethod]:
           @validator(key, **opts)
           def my_validator(cls, _val, values):
               if fail(_val, values):
                   raise ValueError()
               return _val
       
           return {"my_validator": my_validator}

- The ``validator_opts`` property is passed on as keyword arguments to
  the ``validator`` decorator.

Example
-------

An example in YAML format follows::

  KEY1:
    Key1:
      type: Type1
      opts: {"opt1": v1, "opt2": v2}  # passed on as: Type1(opt1=v1, opt2=v2)
  KEY2:
    Key2:
      type: Type2
      validator: my_check  # importable function conforming to API
      validator_opts: {"opt": val}
    Key3:
      type: Type3
      opts: [option1, option2]  # passed on as: Type3[option1, option2]
