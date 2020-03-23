"""PyDataConfig"""

from pathlib import Path

from setuptools import setup, find_packages

requirements = Path("requirements.txt").read_text().strip().split("\n")

setup(
    name="PyDataConfig",
    version="0.1.dev0",
    description="A type system with data validation for configuration files.",
    url="https://github.com/calliope-project/pydataconfig",
    packages=find_packages(exclude=["doc", "tests", "tmp"]),
    install_requires=requirements,
)
