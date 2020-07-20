#!/bin/bash

[[ -z $1 ]] && {
    echo "${0##*/}: pydantic source directory not provided"
    exit 1
}

declare PYDANTIC_SRC=$(readlink -f $1)

mkvirtualenv -r $PYDANTIC_SRC/requirements.txt pydc
pip install $(cat requirements.txt | grep -v pydantic)

declare PYTHON_VERSION=$(python -c 'import sys;print("{}.{}".format(*sys.version_info[:2]))')
ln -s $PYDANTIC_SRC/pydantic $VIRTUAL_ENV/lib/python3.8/site-packages
