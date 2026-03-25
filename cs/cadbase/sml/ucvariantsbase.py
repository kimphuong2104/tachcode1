# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module ucvariantsbase

This is the documentation for the ucvariantsbase module.
"""


from __future__ import absolute_import
from cdb.objects.pdd.Files import Sandbox

_ucSupported = False
try:
    from cs.wsm.pkgs.classification import ucAvailable
    from cs.classification.classes import ModelAssignment, ClassificationClass
    from cs.classification import api as cl_api
    _ucSupported = ucAvailable()
except ImportError:
    pass

try:
    # allow import error for building documentation
    # cs.wsm is mandotary for sml/uc function
    # the other caddbase functions should work without workspaces
    from cs.wsm.wsmacslib import checkout_workspace
except ImportError:
    checkout_workspace = None

__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []


def ucSupported():
    return _ucSupported


class SCQueueError(Exception):
    pass


class InvalidGenericError(SCQueueError):
    pass


class AccessViolationError(SCQueueError):
    pass


class InvalidItemError(SCQueueError):
    pass


class NoUcSupport(SCQueueError):
    pass


class MissingModulError(SCQueueError):
    pass


def checkout_structure(dstPath, doc):
    """
    we do not handle conflict. Its just one assembly in m+h instance
    """
    if checkout_workspace is not None:
        sb = Sandbox(dstPath)
        checkout_workspace(sb, doc, ignore_duplicates=False, use_subdir_for_appinfo=False)
        sb.close()


def generics_for_item(item):
    """
    Find matching generic for given item
    :param item: cs.vp.item.Item
    :return dict (cadsystem, view)->(uc_class, generic_doc))
    """
    generics = dict()
    cl_data = cl_api.get_classification(item)
    if cl_data:
        for clscode in cl_data["assigned_classes"]:
            uc_class = ClassificationClass.ByKeys(code=clscode)
            for ma in ModelAssignment.KeywordQuery(classification_class_id=uc_class.cdb_object_id):
                model = ma.Model
                if model.erzeug_system:
                    cad_system = model.erzeug_system.split(":")[0]
                    generics[(cad_system, ma.cad_view)] = (uc_class, model)
    return generics
