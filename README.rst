PydantiConfig
=============

This library provides a set of factory methods and parsers to
automatically generate a type system, that can be used to validate
config files.

Typically config files are relatively simple in terms of the data
structures they need to represent.  However configuration for
scientific software can often require some degree of complexity.
*PydantiConfig* has been written to meet the needs of the energy
modelling framework Calliope_, as it often needs to express complex
relationships and constraints.


.. _Calliope: github.com/calliope-project/calliope
