"""Network graph parser

- inheritance tree for overrideable properties
- nodes & edges w/ properties

"""

from copy import copy
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple, Type, TypeVar

from glom import Assign, Coalesce, glom, Spec
from glom import Path as gPath
from networkx import (
    DiGraph,
    Graph,
    find_cycle,
    NetworkXNoCycle,
    topological_sort,
)

from typedconfig.factory import make_typedconfig
from typedconfig.helpers import merge_dicts, merge_rules, read_yaml
from typedconfig.parsers.tree import (
    _ConfigIO,
    _filter,
    _is_node,
    _is_mandatory,
    _Path_t,
    _spec_to_type,
    _type_spec,
    del_from_leaf,
    get_from_leaf,
    get_spec,
)


class spec_dict:
    def __init__(self, attrs: Dict):
        attrs, _, leaf_paths = get_spec(attrs)
        self.attrs = attrs
        self.attr_paths = leaf_paths
        self.reset_property()

    def with_property(self, prop: Dict):
        res = copy(self)
        res.set_property(prop)
        return res

    def set_property(self, prop: Dict):
        self.prop = prop
        self.prop_paths = [
            p for p in _filter(prop, _is_node) if p in self.attr_paths
        ]
        self._data = self.prop
        self._paths = self.prop_paths

    def reset_property(self):
        self.prop = self.prop_paths = None
        self._data = self.attrs
        self._paths = self.attr_paths

    def __getitem__(self, path: Tuple):
        return glom(self._data, gPath(*path))

    def __contains__(self, path: Tuple) -> bool:
        return glom(self._data, (Coalesce(gPath(*path), default=False), bool),)

    def __iter__(self):
        return iter(self._paths)

    def filter(self, test: Callable):
        return _filter(self._data, test)


def make_baseprop_t(spec: spec_dict) -> Type:
    """parse attribute rules"""
    # NOTE: assumes the last key is globally unique
    base_spec = {
        str(path[-1]): spec[path] for path in spec.filter(_is_mandatory)
    }
    baseprop_t = _spec_to_type("baseprop", base_spec, bases=(_ConfigIO,))
    return baseprop_t


def attr_defaults(attrs: Dict[str, Dict]) -> Tuple[Dict[str, Dict], Dict]:
    def_key = _type_spec[6]
    # all attributes with defaults
    defaults = get_from_leaf(attrs, [def_key])
    paths = _filter(defaults, lambda p, k, v: def_key in v)
    defaults = glom(defaults, {p[-1]: gPath(*p, def_key) for p in paths})

    # remove default from spec before creating the base property, also remove
    # other unnecessary keys
    attrs = del_from_leaf(attrs, [def_key, "doc", "scaling_label"])
    return attrs, defaults


def properties(
    attrs: Dict[str, Dict], defaults: Dict, props: Dict[str, Dict]
) -> Dict:
    # FIXME: not idempotent, deletes default from attrs, doesn't return default

    # create inheritance tree
    dep_gr = DiGraph()
    dep_gr.add_nodes_from(props.keys())
    dep_gr.add_edges_from(
        (val["parent"], prop) for prop, val in props.items() if "parent" in val
    )
    try:
        find_cycle(dep_gr, orientation="ignore")
    except NetworkXNoCycle:
        pass
    else:
        raise ValueError(f"properties with cyclic dependency: {dep_gr.edges}")

    spec = spec_dict(attrs)
    baseprop_t = make_baseprop_t(spec)

    res = {"baseprop": baseprop_t}
    for prop in topological_sort(dep_gr):  # properties, sorted parent to child
        # attribute value pairs for current property
        conf = spec.with_property(props[prop])
        inherit_from = conf.prop.pop("parent", None)

        _bases = (type(res[inherit_from]),) if inherit_from else (baseprop_t,)
        _spec = {str(path[-1]): spec[path] for path in conf}
        prop_t = _spec_to_type(prop, _spec, bases=_bases)

        inherited = asdict(res[inherit_from]) if inherit_from else {}
        # find applicable attributes with defaults
        _fields = set(defaults).intersection(f.name for f in fields(prop_t))
        _fields -= set(inherited)
        _defaults = {field: defaults[field] for field in _fields}
        current = {path[-1]: conf[path] for path in conf}
        # inherited property attributes maybe overwritten
        kwargs = {**inherited, **_defaults, **current}
        res[prop] = prop_t(**kwargs)
    return res


def nodes(
    attrs: Dict[str, Dict], props: Dict[str, Dict], _nodes: Dict[str, Dict],
) -> List[Tuple[str, Dict]]:
    res: List[Tuple[str, Dict]] = []
    # for node, node_props in _nodes.items():
    #     _props = node_props.pop("properties", {})
    #     _fields = [(key, attrs[key]["type"]) for key in node_props]
    #     for key, _prop in _props.items():
    #         node_props[key] = (
    #             replace(props[key], **_prop)
    #             if isinstance(_prop, dict)
    #             else props[key]
    #         )
    #         _fields += [(key, props[key].__class__)]
    #     node_t = make_typedconfig(node, _fields)
    #     node_t(**node_props)  # discard, only for validation
    #     res += [(node, node_props)]

    node_props = {node: v.pop("properties", {}) for node, v in _nodes.items()}
    nodes = properties(attrs, {}, _nodes)
    for node, _props in node_props.items():
        for pname, vals in _props.items():
            glom(
                node_props,
                Assign(
                    f"{node}.{pname}",
                    replace(props[pname], **vals) if vals else props[pname],
                ),
            )
    from pprint import pprint

    for node in nodes:
        if node == "baseprop":
            continue
        print(node)
        pprint(nodes[node])
        pprint(node_props[node], indent=2)
    return list(nodes.items())


def edges(
    attrs: Dict[str, Dict], props: Dict[str, Dict], _edges: Dict[str, Dict],
) -> List[Tuple[str, str, Dict]]:
    res: List[Tuple[str, str, Dict]] = []
    for loc1, locs in _edges.items():
        _props = locs.pop("properties", {})

        for loc2, edge_props in locs.items():
            if edge_props is None:
                edge_props = {}
            __props = merge_dicts([_props, edge_props.pop("properties", {})])
            __fields = [(key, attrs[key]["type"]) for key in edge_props]
            for key, __prop in __props.items():
                edge_props[key] = (
                    replace(props[key], **__prop)
                    if isinstance(__prop, dict)
                    else props[key]
                )
                __fields += [(key, props[key].__class__)]
            edge_t = make_typedconfig(f"{loc1}_{loc2}", __fields)
            edge_t(**edge_props)  # discard, only for validation
            res += [(loc1, loc2, edge_props)]
    return res


_file_t = TypeVar("_file_t", str, Path)


class Builder:
    _graph = False
    _digraph = False

    def __init__(self, rules: List[_file_t]):
        self.attrs, self.defaults = attr_defaults(
            merge_rules(rules, read_yaml)
        )

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
        self.edges = edges(
            self.attrs, self.props, merge_rules(confs, read_yaml)
        )

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
