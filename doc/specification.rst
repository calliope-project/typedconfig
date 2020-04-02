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
- ``validator_params``: parameters to bind to the validator function
  scope; a dictionary, where each key value pair is available in the
  function as a local variable
- ``root_validator``: boolean, if true, apply this as a root validator
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
- All nodes may have a ``validator``; a validator is a parametrised
  function that is wrapped in it's own scope and returned as a
  ``classmethod``.  The parameters (if present) are bound as local
  variables within the scope.  The expected form is::

    def func(cls: Type, val: Any, values: Dict[str, Any], *,
             param1: Any, param2: Any, ...):
        if valid:
            return val

        raise ValueError  # , TypeError, or ValidationError

  Essentially, the beginning part of the signature, before the keyword
  only arguments should match what is required by ``pydantic``, the
  first argument is the class type (since it's a classmethod),
  followed by the key value, and a dictionary of the preceding keys
  with their corresponding values that passed validation.

  A ``root_validator`` is indicated by setting the ``root_validator``
  key to ``true``.  The expected signature for the validator function
  changes slightly; note that ``val`` is missing, as there is no
  specific key associated to the validator now::

    def func(cls: Type, values: Dict[str, Any], *,
             param1: Any, param2: Any, ...):
        if valid:
            return val

        raise ValueError  # , TypeError, or ValidationError

  The function signatures are not checked when building the config type.
- The ``validator_opts`` property is passed on as keyword arguments to
  the ``validator`` decorator, it should be a dictionary.
- Any parameters can be passed through the ``validator_params``
  option, it should be a dictionary.

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

Caveats
-------

Creating duplicate validators is not supported in general; it will
raise ``ConfigError``.  Which means the same key name cannot be
repeated in a configuration hierarchy if they share validators.
