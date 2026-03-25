# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module appinfohandler

This is the documentation for the appinfohandler module.
"""

import codecs
from lxml import etree as ElementTree
import os.path
import shutil
import six


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = []


def parse_xml(filename):
    """
    lxml wraper for bug with chinese unicode filenames
    :param filename: unicode str
    """
    if six.PY2:
        assert isinstance(filename, six.text_type)
        with open(filename, "r") as fd:
            tree = ElementTree.parse(fd)
    else:
        tree = ElementTree.parse(filename)
    return tree


def write_prettify(tree, fname, encoding="utf-8"):
    """
    prettifies given xml tree
    :param tree: ElementTree
    :param fname: string filename of result xml file
    :param encoding: string encoding of result xml file
    """
    pretty_str = ElementTree.tostring(tree, encoding=encoding,
                                      pretty_print=True)
    pretty_str = pretty_str.decode(encoding)

    with codecs.open(fname, "w", encoding) as f:
        if "utf-8" == encoding:
            f.write("<?xml version='1.0' encoding='utf-8'?>\n")
        f.write(pretty_str)


def abs_to_rel(fname, root_path):
    """
    Convert absolute path filename to basename if root_path is None
    or to a relative path if oath is inside root_path,
    else return the input path.
    Change pPaths to UNIX conventions
    """
    if root_path is not None:
        ret_path = fname
        common_prefix = os.path.commonprefix([fname, root_path])
        if common_prefix:
            # We are on the same drive
            rel_path = os.path.relpath(fname, root_path)
            # We are not inside rootPath, use absolute path
            if not rel_path.startswith(".."):
                ret_path = rel_path
    else:
        ret_path = os.path.basename(fname)
    return ret_path.replace("\\", "/")


def remove_path(root, element_name, root_path=None):
    """
    Remove the absolute pathname from the gven element
    """
    for el in root.findall(".//%s" % element_name):
        p = el.attrib["path"]
        el.attrib["path"] = abs_to_rel(p, root_path)


def remove_rel_paths(fname, prettify=True):
    """
    Replace all paths in appinfo by basename
    :param fname: string filename of an appinfo file
    :param prettify: boolean determines whether the result is pretified or not
    """
    path_holding_items = ["cadreference", "link"]
    tree = parse_xml(fname)
    backup = fname + ".bak"
    shutil.copy2(fname, backup)
    root = tree.getroot()
    for item_name in path_holding_items:
        remove_path(root, item_name)
    new_name = fname + ".new"

    if prettify:
        write_prettify(tree, new_name)
    else:
        tree.write(new_name)

    shutil.copy2(new_name, fname)


def abs_path_to_rel_path(fname, root_path, prettify=True):
    """
    If path is an absolute path and path is a file or directory below
    root_path, convert the absolute path to a relative path

    :param fname: string filename of an appinfo file
    :param root_path: string
    :param prettify: boolean determines whether the result is pretified or not
    """
    path_holding_items = ["cadreference", "link"]
    tree = parse_xml(fname)
    backup = fname + ".bak"
    shutil.copy2(fname, backup)
    root = tree.getroot()
    for item_name in path_holding_items:
        remove_path(root, item_name, root_path)
    new_name = fname + ".new"

    if prettify:
        write_prettify(tree, new_name)
    else:
        tree.write(new_name)

    shutil.copy2(new_name, fname)


class AppinfoHandler(object):
    def __init__(self, filename):
        tree = parse_xml(filename)
        self._root = tree.getroot()

    def get_sheet_ids(self):
        """
        :returns List of sheet ids sorted by sheet number
        """
        sheet_dict = self.get_sheets_by_sort_value()
        sorted_keys = list(sheet_dict.keys())
        sorted_keys.sort()
        sheets = []
        for k in sorted_keys:
            sheets.append(sheet_dict[k].attrib["id"])
        return sheets

    def get_sheets_by_sort_value(self):
        """
        :returns dict sortval -> sheet-element
        """
        sheet_dict = {}
        no_sort_val_sheets = []
        for sheet in self._root.findall(".//sheet"):
            sort_val = sheet.attrib.get("sortval")
            if sort_val and sort_val.isdigit():
                sheet_dict[int(sort_val)] = sheet
            else:
                no_sort_val_sheets.append(sheet)
        max_sort_val = -1
        if list(sheet_dict.keys()):
            max_sort_val = max(sheet_dict.keys())
        for s in no_sort_val_sheets:
            max_sort_val += 1
            sheet_dict[max_sort_val] = s
        return sheet_dict


# Guard importing as main module
if __name__ == "__main__":
    pass
