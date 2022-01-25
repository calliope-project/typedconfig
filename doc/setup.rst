Setup
=====

You can add your own validators by importing the singleton object
``NS`` from ``typedconfig.helpers``, and adding the module names (full
dotted name: ``package.module.submodule``) with ``NS.add_modules``.

The validators should also be included in a list in the module level
variable ``__all___``.

When refering to other directories/files in a config file, there
are two situations:

1. refering to another directory/file w.r.t. your current working
   directory; in this case you can use any of the restricted types
   provided by ``pydantic``.

2. refering to another file w.r.t. to the config file; this is not
   entirely supported, instead before reading the config, you can
   specify a config directory, then the file path will be validated
   w.r.t. this directory.  This can be achieved by using the type
   ``ConfFilePath`` from ``typedconfig._types``.
