TypedConfig
==========
|unittests| |coverage|

``TypedConfig`` provides a set of factory methods and parsers to
automatically generate a type system based on a set of rules, which
can then be used to validate config files.

Typically config files are relatively simple in terms of the data
structures they need to represent.  However configuration for
scientific software can often require some degree of complexity;
sometimes even *deeply intertwined* with the data!

``TypedConfig`` has been specifically written to meet the needs of the
energy modelling framework Calliope_, as it often needs to express
complex relationships and constraints to configure a run.  Since it
also relies on external solver libraries, it also needs to pass on
various configuration options to these underlying libraries.

The default parser organises information in a hierarchically as a
tree.  You can specify a ruleset defining the type and validation
rules for each key in the tree.  A master config type is generated
from the ruleset, which can then be used to validate a config file.

.. _Calliope: https://github.com/calliope-project/calliope

.. |unittests| image:: https://github.com/calliope-project/dataconfig/workflows/Unit%20tests/badge.svg
   :target: https://github.com/calliope-project/dataconfig/actions

.. |coverage| image:: https://codecov.io/gh/calliope-project/dataconfig/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/calliope-project/dataconfig
