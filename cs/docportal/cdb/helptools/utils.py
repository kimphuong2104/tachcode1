# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
Module cs.docportal.cs.docportal.cdb.helptools.utils

Various utils for HelpID processing.

"""
from pathlib import Path

from cdb import CADDOK


def find_inventories(path: Path) -> list[str]:
    """
    Get all ``objects.inv`` files contained in a given directory recursively.
    :param path: a given directory
    :return: a list of strings to the found files
    """
    inventories = []
    for node in path.rglob('objects.inv'):
        inventories.append(str(node))

    return inventories


def find_package_doc_roots() -> dict[str, Path]:
    """
    Returns a dictionary that contains the package name as key and the documentation
    directory as value.
    Packages without a documentation directory are not part of the result.
    """
    from cdb.comparch import packages

    result = {}
    for package in packages.get_package_names():
        documentation_dir = get_package_doc_dir(package)
        if documentation_dir:
            result[package] = documentation_dir
    return result


def get_package_doc_dir(package_name: str) -> Path:
    """
    Returns the path where the documentation of the package should be located.
    :param package_name: package name of which we want to find the doc location
    :return: Either the corresponding Path or ``None``
    """
    if package_name == 'cs.platform':
        from cdb.comparch import packages

        documentation_dir = Path(packages.get_package_dir(package_name)) / 'doc'
    else:
        documentation_dir = Path(CADDOK.BASE) / 'docs' / package_name

    if documentation_dir.is_dir():
        return documentation_dir
