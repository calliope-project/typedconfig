"""Network graph parser

- inheritance tree for overrideable properties
- nodes & edges w/ properties

"""

from dataclasses import asdict, replace
from pathlib import Path
from typing import Dict, List, Tuple, TypeVar

from networkx import (
    DiGraph,
    Graph,
    find_cycle,
    NetworkXNoCycle,
    topological_sort,
)

from typedconfig.factory import make_typedconfig
from typedconfig.helpers import merge_dicts, merge_rules, read_yaml
from typedconfig.parsers.tree import _str_to_spec


def attr_types(attrs: Dict[str, Dict]) -> Dict[str, Dict]:
    """parse attribute rules"""
    return {key: _str_to_spec(key, spec) for key, spec in attrs.items()}


def properties(attrs: Dict[str, Dict], props: Dict[str, Dict]) -> Dict:
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

    res = {}
    for prop in topological_sort(dep_gr):  # properties, sorted parent to child
        conf = props[prop]
        inherit_from = conf.pop("parent", None)

        _bases = (type(res[inherit_from]),) if inherit_from else ()
        _fields = [(key, attrs[key]["type"]) for key in conf]
        prop_t = make_typedconfig(prop, _fields, bases=_bases)

        inherited = asdict(res[inherit_from]) if inherit_from else {}
        # inherited property attributes maybe overwritten
        res[prop] = prop_t(**{**inherited, **conf})
    return res


# - nodes & edges
# - mandatory attributes
# - default properties
# - overridden properties


def nodes(
    attrs: Dict[str, Dict], props: Dict[str, Dict], _nodes: Dict[str, Dict],
) -> List[Tuple[str, Dict]]:
    res = []
    for node, node_props in _nodes.items():
        _props = node_props.pop("properties", {})
        _fields = [(key, attrs[key]["type"]) for key in node_props]
        for key, _prop in _props.items():
            node_props[key] = (
                replace(props[key], **_prop)
                if isinstance(_prop, dict)
                else props[key]
            )
            _fields += [(key, props[key].__class__)]
        node_t = make_typedconfig(node, _fields)
        node_t(**node_props)  # discard, only for validation
        res += [(node, node_props)]
    return res


def edges(
    attrs: Dict[str, Dict], props: Dict[str, Dict], _edges: Dict[str, Dict],
) -> List[Tuple[str, Dict]]:
    res = []
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

    def __init__(self, *rules: _file_t):
        self.attrs = attr_types(merge_rules(rules, read_yaml))

    def make_properties(self, *confs: _file_t):
        self.props = properties(self.attrs, merge_rules(confs, read_yaml))

    def add_nodes(self, *confs: _file_t):
        self.nodes = nodes(
            self.attrs, self.props, merge_rules(confs, read_yaml)
        )

    def add_edges(self, *confs: _file_t):
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
