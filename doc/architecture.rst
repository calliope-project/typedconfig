Architecture & flow
===================

Depending on the kind of structure of the config, we need different
parsers.

The hierarchical parser
------------------------

The following diagram represents the general flow.

.. image :: images/config_parsing_flow.svg

The configuration keys are organised in an hierarchical tree, a nested
dictionary.  So first we create an easy to look-up list of path
objects (which themselves are a sequence keys) to make the dictionary
easily addressable and queryable.

.. image :: images/dict_processing.svg

Since the types are nested, the parser starts at the leaf nodes, walks
up the hierarchy, and transforms the dictionary from the type
specifications to a master config type.  This happens in two steps;
first the leaf nodes are remapped to config types:

.. image :: images/dict_transform_1.svg

The step is then repeated as we traverse up the hierarchy tree to
create the master config type.

.. image :: images/dict_transform_2.svg
