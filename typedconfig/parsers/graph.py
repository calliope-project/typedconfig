"""Network graph parser

- inheritance tree for overrideable properties
- nodes & edges w/ properties

"""

from copy import copy
from dataclasses import asdict, fields, replace
from functools import partial
import logging
from pathlib import Path
from typing import Callable, Dict, List, Tuple, Type, TypeVar

from glom import Assign, Coalesce, glom
from glom import Path as gPath
from networkx import DiGraph, Graph
from networkx import find_cycle, topological_sort
from networkx import NetworkXNoCycle

from typedconfig import register
from typedconfig.helpers import merge_dicts, merge_rules, read_yaml
from typedconfig.parsers import _ConfigIO
from typedconfig.parsers.tree import (
    path_if,
    is_node,
    is_mandatory,
    spec_to_type,
    _type_spec,
    del_from_leaf,
    get_from_leaf,
    get_spec,
)

log = logging.getLogger(__name__)


class spec_dict:
    """This is a wrapper around the rules dictionary.

    To use it, you need to specialise the rules for a config dictionary.

    >>> spec = spec_dict(rules)  # doctest: +SKIP
    >>> conf = spec.with_property(conf_dict_for_propa)  # doctest: +SKIP

    """

    def __init__(self, attrs: Dict):
        attrs, _, leaf_paths = get_spec(attrs)
        self.attrs = attrs
        self.attr_paths = leaf_paths
        self.reset_property()

    def with_property(self, prop: Dict):
        res = copy(self)
        return res.set_property(prop)

    def set_property(self, prop: Dict):
        self.prop = prop
        self.prop_paths = [p for p in path_if(prop, is_node) if p in self.attr_paths]
        self._data = self.prop
        self._paths = self.prop_paths
        return self

    def reset_property(self):
        self.prop = self.prop_paths = None
        self._data = self.attrs
        self._paths = self.attr_paths

    def __getitem__(self, path: Tuple):
        return glom(self._data, gPath(*path))

    def __contains__(self, path: Tuple) -> bool:
        return glom(self._data, (Coalesce(gPath(*path), default=False), bool))

    def __iter__(self):
        return iter(self._paths)

    def filter(self, test: Callable):
        return path_if(self._data, test)

    def __repr__(self) -> str:
        return str({k: self[k] for k in self})


def make_baseprop_t(spec: spec_dict, name: str = "baseprop") -> Type:
    """Create a base property that other properties inherit from"""
    # NOTE: assumes the last key is globally unique
    base_spec = {str(path[-1]): spec[path] for path in spec.filter(is_mandatory)}
    baseprop_t = spec_to_type(name, base_spec, bases=(_ConfigIO,))
    return baseprop_t


def attr_defaults(attrs: Dict[str, Dict]) -> Tuple[Dict[str, Dict], Dict]:
    """Separate property attribute rules and corresponding default values

    Parameters
    ----------
    attrs : Dict[str, Dict]
        Rules dictionary, each key represents an attribute, and the value is a
        type specification as expected by `typedconfig.parsers.tree`.

    Returns
    -------
    Tuple[Dict[str, Dict], Dict]
        Tuple of the rules dictionary, and defaults separated out.

    """
    def_key = _type_spec[6]
    # all attributes with defaults
    defaults = get_from_leaf(attrs, [def_key])
    paths = path_if(defaults, lambda p, k, v: def_key in v)
    defaults = glom(defaults, {p[-1]: gPath(*p, def_key) for p in paths})

    # remove default from spec before creating the base property, also remove
    # other unnecessary keys
    attrs = del_from_leaf(attrs, [def_key, "doc", "scaling_label"])
    return attrs, defaults


def properties(
    attr_rules: Dict[str, Dict],
    defaults: Dict,
    props: Dict[str, Dict],
    base_property_name: str = "baseprop",
    type_namespace: str = "dynamic",
) -> Dict:
    """Create a (optional) hierarchy of properties

    Each property is a custom type, and may inherit from any one of the other
    properties.  The set of valid attributes are passed as rules, and the
    property types are constructed based on whether an attribute is present in
    the configuration.  Optionally the property types can be registered under
    the dynamic module 'typedconfig._{type_namespace}', and can be accessed later in the
    same session with an import statement:

    >>> from typedconfig.dynamic import property_t  # doctest: +SKIP

    Parameters
    ----------
    attr_rules : Dict[str, Dict]
        Dictionary with rules for all allowed attributes.  Optional attributes
        are marked by setting the 'optional' key to `True`.
    defaults : Dict
        If certain keys have default values, they should be specified here.
    props : Dict[str, Dict]
        Configuration dictionary of properties to be defined.  Derived
        properties should mark their parent by setting the 'parent' key to
        their parent.
    base_property_name : str (default: 'baseprop')
    type_namespace : str (default: 'dynamic')
        Custom property types are registered under:
        'typedconfig._{type_namespace}'.

    Returns
    -------
    Dict
        Dictionary of property values

    Raises
    ------
    ValueError
        - The properties are validated against the specified rules during
          instantiation, if the failure is due to a bad value.
        - If there is a cycle in the property inheritance hierarchy.
    TypeError
        Same as above, except if the validation fails due to a type mismatch
    AttributeError
        If the attribute rules are erroneous (most likely reason)

    """
    # create inheritance tree
    parent_key = "parent"
    dep_gr = DiGraph()
    dep_gr.add_nodes_from(props.keys())
    dep_gr.add_edges_from(
        (glom(props, i), i[0])
        for i in path_if(props, lambda p, k, v: k == parent_key and v)
    )
    try:
        loop = find_cycle(dep_gr, orientation="original")
    except NetworkXNoCycle:
        # useful for debugging, and maybe visualisation in the future
        # import matplotlib.pyplot as plt
        # import networkx as nx

        # nx.draw(dep_gr, with_labels=True, pos=nx.spring_layout(dep_gr))
        pass
    else:
        raise ValueError(
            f"properties with cyclic dependency: {dep_gr.edges}\nloop={loop}"
        )

    _register = partial(register, submodule=type_namespace)
    spec = spec_dict(attr_rules)
    baseprop_t = _register(make_baseprop_t(spec, base_property_name))

    res = {base_property_name: baseprop_t}
    for prop in topological_sort(dep_gr):  # properties, sorted parent to child
        # attribute value pairs for current property
        conf = spec.with_property(props[prop])
        inherit_from = conf.prop.pop(parent_key, None)

        try:
            _bases = (type(res[inherit_from]),) if inherit_from else (baseprop_t,)
        except AttributeError:
            log.error(f"{inherit_from}: property not defined")
            raise
        else:
            _spec = {str(path[-1]): spec[path] for path in conf}
            prop_t = _register(spec_to_type(prop, _spec, bases=_bases))

        inherited = asdict(res[inherit_from]) if inherit_from else {}
        # find applicable attributes with defaults
        _fields = set(defaults).intersection(f.name for f in fields(prop_t))
        _fields -= set(inherited)
        _defaults = {field: defaults[field] for field in _fields}
        current = {path[-1]: conf[path] for path in conf}
        # inherited property attributes maybe overwritten
        kwargs = {**inherited, **_defaults, **current}
        try:
            res[prop] = prop_t(**kwargs)
        except (TypeError, ValueError) as err:
            log.error(f"Validation failed: {prop_t.__name__}\nkwargs={kwargs}")
            raise
        except:
            log.exception(f"unknown exception: prop={prop}\nkwargs={kwargs}")
            raise
    return res


def nodes(attr_rules: Dict[str, Dict], props: Dict, _nodes: Dict[str, Dict]) -> Dict:
    """Create nodes that are related by an inheritance hierarchy.

    Each node has a set of attributes (which can be inherited by a child), and
    a special attribute ``techs`` holds a set of properties.

    Parameters
    ----------
    attr_rules : Dict[str, Dict]
        Dictionary with rules for all allowed attributes.  Optional attributes
        are marked by setting the 'optional' key to `True`.
    props : Dict[str, Dict]
        Dictionary of defined properties
    _nodes : Dict[str, Dict]
        Configuration dictionary of nodes to be defined.

    Returns
    -------
    Dict
        Dictionary of nodes with associated properties

    """
    # FIXME: use a generic term like "properties" instead of "techs"
    for node, val in _nodes.items():
        _props = {
            pname: replace(props[pname], **prop) if prop else props[pname]
            for pname, prop in val.pop("techs", {}).items()
        }
        glom(_nodes, Assign(f"{node}.techs", _props, missing=dict))

    # add rule for dictionary of properties
    attr_rules.update({"techs": {"type": "Dict"}})
    attrs, defaults = attr_defaults(attr_rules)
    res = properties(attrs, defaults, _nodes, "basenode")
    return res


def edges(
    attr_rules: Dict[str, Dict], props: Dict[str, Dict], _edges: Dict[str, Dict]
) -> Dict[Tuple[str, str], Dict]:
    """Create a set of edges between a set of interconnected nodes.

    Each edge has a set of attributes, and a special attribute ``techs`` holds
    a set of properties.

    Parameters
    ----------
    attr_rules : Dict[str, Dict]
        Dictionary with rules for all allowed attributes.  Optional attributes
        are marked by setting the 'optional' key to `True`.
    props : Dict[str, Dict]
        Dictionary of defined properties
    _edges : Dict[str, Dict]
        Configuration dictionary of edges to be defined.

    Returns
    -------
    Dict

        Dictionary of edges with associated properties; the key is a tuple of
        node names that are connected by that edge: ``(node1, node2)``.  There
        is a base edge type, which is available under the special key:
        ``("baseedge", "")``.

    """
    __edges = {}
    __edge_namemap = {}
    # FIXME: use a generic term like "properties"
    for node1, nodes in _edges.items():
        _props_n1 = nodes.pop("techs", {})
        for node2, _props_n2 in nodes.items():
            # merge properties from N1 and N2; N2 may override N1
            _props_n2 = {} if _props_n2 is None else _props_n2
            edge_props = merge_dicts([_props_n1, _props_n2.pop("techs", {})])
            # update properties
            _props_n2["techs"] = {
                pname: replace(props[pname], **prop) if prop else props[pname]
                for pname, prop in edge_props.items()
            }
            # edges with concatenated keys
            edge_name = f"{node1}_{node2}"
            __edges[edge_name] = _props_n2
            __edge_namemap[edge_name] = (node1, node2)

    # add rule for dictionary of properties
    attr_rules.update({"techs": {"type": "Dict"}})
    attrs, defaults = attr_defaults(attr_rules)
    res = properties(attrs, defaults, __edges, "baseedge")
    res = {
        ("baseedge", "") if k == "baseedge" else __edge_namemap[k]: v
        for k, v in res.items()
    }
    return res


_file_t = TypeVar("_file_t", str, Path)


class Builder:
    _graph = False
    _digraph = False

    def __init__(self, rules: List[_file_t]):
        self.attrs, self.defaults = attr_defaults(merge_rules(rules, read_yaml))

    def make_properties(self, confs: List[_file_t]):
        self.props = properties(
            self.attrs, self.defaults, merge_rules(confs, read_yaml)
        )

    def add_nodes(self, attrs, confs: List[_file_t]):
        self.nodes = nodes(
            merge_rules(attrs, read_yaml),
            self.props,
            merge_rules(confs, read_yaml),
        )

    def add_edges(self, confs: List[_file_t]):
        self.edges = edges(self.attrs, self.props, merge_rules(confs, read_yaml))

    @property
    def graph(self):
        if not self._graph:
            self._graph = Graph()
            self._graph.add_nodes_from(self.nodes)
            self._graph.add_edges_from(self.edges)
        return self._graph

    @property
    def digraph(self):
        if not self._digraph:
            self._graph = DiGraph()
            self._graph.add_nodes_from(self.nodes)
            self._graph.add_edges_from(self.edges)
        return self._graph

    def reset(self):
        self._graph = self._digraph = False
