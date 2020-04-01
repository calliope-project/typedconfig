DataConfig
==========
|unittests| |coverage|

PyDataConfig provides a set of factory methods and parsers to
automatically generate a type system based on a set of rules, which
can then be used to validate config files.

Typically config files are relatively simple in terms of the data
structures they need to represent.  However configuration for
scientific software can often require some degree of complexity; as if
it is *almost data*!

*PyDataConfig* has been written to meet the needs of the energy
modelling framework Calliope_, as it often needs to express complex
relationships and constraints to configure a run.  Since it also
relies on external solver libraries, it also needs to pass on various
configuration options to these underlying libraries.

The default parser organises information in a hierarchy.  You can
specify a ruleset defining the type and validation rules for each key.
A config type is then generated from the ruleset, which can then be
used to validate a config file.

.. _Calliope: github.com/calliope-project/calliope

.. |unittests| image:: https://github.com/suvayu/dataconfig/workflows/Unit%20tests/badge.svg
   :target: https://github.com/suvayu/dataconfig/actions

.. |coverage| image:: https://codecov.io/gh/suvayu/dataconfig/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/suvayu/dataconfig
