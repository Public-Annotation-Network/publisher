#!/usr/bin/env python

"""The setup script."""

from setuptools import setup

with open("requirements.txt", "r") as f:
    requirements = [x for x in map(str.strip, f.read().split("\n")) if x != ""]

setup(
    author="Dominik Muhs",
    author_email="dmuhs@protonmail.ch",
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Natural Language :: English",
        "Typing :: Typed",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Public Annotations Network Publisher Node",
    install_requires=requirements,
    include_package_data=True,
    name="pan_publisher",
    packages=["pan_publisher"],
    url="https://github.com/Public-Annotation-Network/publisher",
    version="0.1.0",
    zip_safe=False,
)
