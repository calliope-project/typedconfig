Ruleset specification
=====================

The basic config item has the following properties:

- ``type``: type information

- ``opts``: options for the type information, can be two kinds:

  - if passing keyword arguments to a type factory function like
    ``pydantic.types.conint`` the option is a dictionary,

  - if passing a sequence through ``[..]``, the option is a list.

- ``validator``: function bound to this config item that checks validity

- ``validator_params``: parameters to bind to the validator function
  scope; a dictionary, where each key value pair is available in the
  function as a local variable

- ``validator_opts``: options for how the validator behaves

- ``root_validator``: boolean, if true, treat the above function as a
  root validator

- ``doc``: config documentation

- ``id``: currently unused

The default parser expects the config items are organised
hierarchically (like an inverted tree); the parser allows multiple
root nodes, effectively allowing for multiple configuration
hierarchies in parallel.

Requirements
------------

- The ``type`` property can only be present at a leaf node, where it
  is mandatory.

- The ``opts`` property maybe present *only* if ``type`` is present.

- All nodes may have a ``validator``; a validator is a parametrised
  function that is wrapped in it's own scope and returned as a
  ``classmethod``.  The parameters (if present) are bound as local
  variables within the scope.  The expected form is::

    def func(cls: Type, val: Any, values: Dict[str, Any], *,
             param1: Any, param2: Any, ...):
        if valid:
            return val

        raise ValueError  # , TypeError, or ValidationError

  Essentially, the arguments before the keyword only arguments, should
  match what is required by ``pydantic``, the first argument is the
  class type (since it's a classmethod), followed by the value of the
  key that is being validated, and finally a dictionary of the
  preceding keys with their corresponding values that has successfully
  passed validation.

- A ``root_validator`` is indicated by setting the ``root_validator``
  key to ``true``.  The expected signature of a root validator
  function is slightly different. As there is no specific key
  associated to the validator, note that ``val`` is absent::

    def func(cls: Type, values: Dict[str, Any], *,
             param1: Any, param2: Any, ...):
        if valid:
            return val

        raise ValueError  # , TypeError, or ValidationError

  **NOTE:** eventhough root validators are not bound to a specific
  key, they need to be specified under a key.  It does not matter
  which key, as long as it is at the same level.  Since there is no
  way to specify multiple validator functions for a key, you will need
  to associate the root validator to a key that does not have one.

- **NOTE:** The function signatures are not enforced when building the
  config type.

- Any parameters that are to be bound in the local scope of the
  validator function as variables, can be set through the
  ``validator_params`` option, it must be a dictionary.

- The ``validator_opts`` property is passed on as keyword arguments to
  the ``validator`` (or ``root_validator``) decorator; it must be a
  dictionary.

Example
-------

An example in YAML format follows::

  KEY1:
    first: 
      type: PositiveInt  # importable type
    second:
      type: PositiveInt
      validator: sum_by_name  # works on 'first' and 'second'
      validator_params: {"total": 15}
      root_validator: true
    nest: 
      leaf: 
        type: conint  # importable factory function
    	opts: {"multiple_of": 5}  # passed on as: conint(multiple_of=5)
  KEY2:
    zero_sum_total:
      foo:
        type: PositiveInt
      bar:
        type: PositiveInt,
        validator: zero_sum  # can be under any key at this level
        validator_params: {"total": 15}
        root_validator: true
    mode:
      type: Literal
      opts: [mode1, mode2]  # passed on as: Literal[mode1, mode2]

Caveats
-------

Creating duplicate validators is not supported in general; it will
raise ``ConfigError``.  Which means the same key name cannot be
repeated in a configuration hierarchy if they share validators.
