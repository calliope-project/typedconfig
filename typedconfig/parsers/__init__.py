"""Parsers

Strictly speaking, the modules in this sub-package are not parsers, they don't
parse the config file themselves.  It relies on dedicated parsers like
`pyyaml`, `json`, etc to parse the files into a python data structure like a
dictionary.  The functions provided by the moduels can then traverse the
dictionary and parse the rules and dynamically generate a configuration type
which can be used to validate the config file provided by the user.

"""
