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

The graph parser
----------------

The graph parser works slightly differently, it is either used to
create an inheritance graph, as set of nodes, and a graph of nodes
connected by edges.

The item in the inheritance graph represents a `property` which can
have a set of attributes, which are defined by a set of rules.  The
attributes may not be nested.  When a config for properties is
provided, it is inspected and the correct set of rules are picked, and
a "property type" is constructed.  The property inheritance hierarchy
starts with the base property type `baseprop_t`.  All newly created
types are registered in the module namespace `typedconfig._dynamic`
(configurable), and can be imported later in other parts of the code
with a regular python import statement.  The config indicates the
inheritance relationship by setting the `parent` key.  If the config
has a cycle, an exception is raised.

A set of nodes can be defined with a similar set of rules, with a set
of attributes defined for each node.  However there is no inheritance
relationship.  Each node also holds a set of properties under the
special attribute `techs`.  The values of the attributes of the
individual properties can be overridden for each node.

The graph of interconnected nodes with edges works similarly as above.
Like nodes, edges can also have attributes, and includes a special
attribute `techs`, which holds edge properties.

Usage notes
===========

When using the hierarchical parser, it is not possible to refer to
arbitrary attributes in the config type during the validation step.

```
key1:
  ...
key1_options:
  opt_a:
    ...
  opt_b:
    ...
  opt_c:
    ...
``

In the above example, it is not possible to refer to any sub-keys
under ``key1`` from ``key1_options``.  It is however possible to refer
to keys at the same level or deeper, with one restriction.  The
refered key has to come before the key being validated, and the
refered key has to pass validation.  In the above example, validation
of ``opt_b`` can refer to ``opt_a``, but not ``opt_c``, similarly,
validation of ``opt_c`` can refer to both ``opt_a`` and ``opt_b``, and
``opt_a`` can refer to nothing.  This is done by looking for the
desired key in the ``values`` parameter (a dictionary) in the
validator function (see specification document).
