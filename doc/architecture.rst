Architecture & flow
===================

Depending on the kind of structure of the config, we need different
parsers.  A rules file declares the type information of every element
in the config, along with optional custom functions that can validate
the config values, and would typically have the same structure as the
config file (but it's not necessarily).  Below we outline what we
expect to be the most commonly used structure.

The hierarchical parser
------------------------

The following diagram represents the general flow.

.. image :: images/config_parsing_flow.png

The configuration keys are organised in an hierarchical tree,
effectively a nested dictionary.  First we create an easy to look-up
list of path objects (which themselves are a sequence of keys) to make
the dictionary easily addressable and queryable.

.. image :: images/dict_processing.png

Since the types are nested, the parser starts at the leaf nodes, walks
up the hierarchy, and transforms the dictionary specifying the types
to a master config Python type.  This happens iteratively; starting
with the leaf nodes, they are remapped to Python types:

.. image :: images/dict_transform_1.png

The step is then repeated as we traverse up the hierarchy tree to
create the master config type.

.. image :: images/dict_transform_2.png
