# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Module supportedclasses

Searches all classes that the client should support.
Classes with for_workspace are the bases classes for
business objects that are possible to create in workspaces

Other classes may exists in workspaces (i.e. cdb_frame)
but are not selectable in load dialog or for creating
objects of this type.

supported_classes are
the standard classes
   document,
   cdb_frame,
   the worksapace class (cdb_wsp),
   part,
   ws_document for teamspaces,
   cdbpcs_project if pcs is installed

in a second step
all configured classes with a wsd_edit operation
are added, if the licensefeature for the
class is available and the class can handle
files

third all classes that are registered by
the entrypoint "cs.workspaces.classes"

are added to the base classes

"""

from __future__ import absolute_import
import collections
import pkg_resources

from cdb import fls
from cdb import constants
from cdb.platform.mom.entities import Entity
from cdb.platform.mom import entities
from cdb.platform.lic import FeatureIDAssignment
from cdb.platform.mom.operations import OperationConfig

pcs_installed = False
try:
    from cs.pcs.projects import Project  # @UnusedImport

    pcs_installed = True
except ImportError:
    pass

sdm_modules_installed = False
try:
    from cs.sdm.variant import Variant  # @UnusedImport

    sdm_modules_installed = True
except ImportError:
    pass


class ClassDescription(object):
    def __init__(
        self,
        classname,
        for_workspaces,
        supported_in_workspace,
        has_files=None,
        labels=None,
    ):
        """
        :param classname: str the cdb classname
        :param has_files: bool: the class supports files
        :param for_workspaces: the class can be used as workspace content and is shown in selection dialogs
        :param supported_in_workspace: bool: may be in content of workspaces (old supprtedObjectClasses)
        :param labels: dict with lang->label with classnames
        """
        self.classname = classname
        self.for_workspaces = for_workspaces
        self.supported_in_workspace = supported_in_workspace
        if has_files is None or labels is None:
            if classname == "kCdbDoc":
                entity = Entity.ByKeys(classname="document")
            else:
                entity = Entity.ByKeys(classname=classname)
            if entity:
                clDef = entities.CDBClassDef(classname)
                if has_files is None:
                    has_files = clDef.hasFiles()
                if labels is None:
                    labels = dict(entity.Label)
        self.has_files = has_files
        if labels is not None:
            self.labels = {k: v for k, v in labels.items() if v}


__docformat__ = "restructuredtext en"


def check_feature(classname):
    features = FeatureIDAssignment.KeywordQuery(
        cdb_classname="cdb_lic_feature_assign_op", classname=classname, name="wsd_edit"
    )
    return all([fls.is_available(f.feature_id) for f in features])


def classes_with_wsd_edit():
    classnames = set()
    for opConfig in OperationConfig.KeywordQuery(name="wsd_edit"):
        classnames.add(opConfig.classname)
    return classnames


def rest_enabled(clDef):
    _rest_methods = [
        constants.kRESTActivePUT,
        constants.kRESTActiveGET,
        constants.kRESTActivePOST,
        constants.kRESTActivePATCH,
    ]
    has_rest = all([clDef.isRESTMethodActivated(m) for m in _rest_methods])
    return has_rest


def get_edit_classes():
    messages = []
    edit_classes = classes_with_wsd_edit()
    valid_classes = []
    for ed_class in edit_classes:
        entity = Entity.ByKeys(ed_class)
        clDef = entities.CDBClassDef(ed_class)
        has_files = clDef.hasFiles()
        feature_enabled = check_feature(ed_class)
        has_rest = rest_enabled(clDef)
        if not has_files:
            messages.append((0, "dropped_class_file %s", ed_class))
        if not has_rest:
            messages.append((0, "dropped_class_rest %s", ed_class))
        if not feature_enabled:
            messages.append((1, "dropped_class_feature %s", ed_class))
        if all([has_rest, has_files, feature_enabled]):
            valid_classes.append(
                ClassDescription(ed_class, True, True, has_files, dict(entity.Label))
            )
    return messages, valid_classes


def get_modul_classes():
    """
    searches for entry points:
    "cs.workspaces.classes": ["supportedclasses = cs.catia.supportedclasses:supprtedClasses"]
    The called function must return a list of tuples (classname(str), forUseInWorkspace(bool))
    """
    additionalClasses = set()
    messages = []
    valid_classes = []
    for ep in pkg_resources.iter_entry_points(group="cs.workspaces.classes"):
        if ep.name == "supportedclasses":
            supportedClassesFunc = ep.load()
            additionalClasses.update(supportedClassesFunc())
    for (ed_class, for_ws) in additionalClasses:
        existing_cl = Entity.ByKeys(classname=ed_class)
        if existing_cl:
            clDef = entities.CDBClassDef(ed_class)
            has_rest = rest_enabled(clDef)
            has_files = clDef.hasFiles()
            if not has_rest:
                messages.append((0, "dropped_class_rest %s", ed_class))
            else:
                valid_classes.append(
                    ClassDescription(
                        ed_class, for_ws, for_ws, has_files, dict(existing_cl.Label)
                    )
                )
        else:
            messages.append((0, "dropped_class_not_exists %s", ed_class))
    return messages, valid_classes


def _merge_classes(classes_dict, new_classes):
    """
    merge classes from new_classes into classes_list
    updates for_workspaces if an external moduls requires the class in workspaces
    """
    for new_class in new_classes:
        existing = classes_dict.get(new_class)
        if existing:
            if new_class.for_workspaces and not existing.for_workspaces:
                existing.for_workspaces = True
        else:
            classes_dict[new_class.classname] = new_class
    return classes_dict


def get_supported_classes(wsp_classname="cdb_wsp"):
    #  Think about: Muss man dieses noch einstellbar machen???
    #  Gibt es installationen wo hier noch eine andere Klasse verwendet wird
    """
    See modul description

    :returns list of "error" tuples, dict classname to ClassDescription
    error tuples (errortype, cdb_error_label, classname)
    errortype 0: Error
              1: Info (i.e. Feature license not available)
              may be only a info result in WSD
    """

    default_base_classes = [
        ClassDescription("document", True, True),
        ClassDescription("kCdbDoc", True, True),
        ClassDescription("part", False, True),
        ClassDescription("cdb_frame", False, True),
        ClassDescription("ws_documents", False, True),
        ClassDescription("cdb_file_base", False, False),
        ClassDescription("cdb_drawing2sheets", False, False),
    ]
    base_classes = {cDes.classname: cDes for cDes in default_base_classes}
    if wsp_classname:
        base_classes[wsp_classname] = ClassDescription(wsp_classname, False, True)

    if pcs_installed:
        base_classes["cdbpcs_project"] = ClassDescription(
            "cdbpcs_project", False, False
        )

    # this only for compatibilty
    # in futrue the modul must add the class by entry point
    if sdm_modules_installed:
        base_classes["cs_sdm_variant"] = ClassDescription("cs_sdm_variant", True, True)

    messages, valid_classes = get_edit_classes()
    base_classes = _merge_classes(base_classes, valid_classes)
    mod_messages, valid_moduls = get_modul_classes()
    base_classes = _merge_classes(base_classes, valid_moduls)
    messages.extend(mod_messages)
    return messages, base_classes
