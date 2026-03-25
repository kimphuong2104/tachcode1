#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
import six
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from collections import defaultdict

from cdb import constants
from cdb.platform.mom import getObjectHandlesFromRESTIDs, SimpleArguments, SimpleArgument
from cdb.platform.mom.entities import CDBClassDef
from cdb.platform.mom.operations import OperationInfo
from cs.platform.web.rest import support


class WebFileUploadHelper(object):
    __FileRegistry = {}
    CALLBACK_METHOD = "cs.web.components.ui_support.utils.WebFileUploadHelper.get_stream"
    @staticmethod
    def get_stream(streamid):
        stream = WebFileUploadHelper.__FileRegistry.pop(streamid)

        # stream is stringIO
        if getattr(stream, "getvalue", None):
            import tempfile
            newstream = tempfile.TemporaryFile()
            newstream.write(stream.getvalue())
            newstream.seek(0)
            stream.close()
            return newstream

        return stream

    @staticmethod
    def append_stream(streamid, stream):
        WebFileUploadHelper.__FileRegistry[streamid] = stream


class SimpleWebUIArguments(SimpleArguments):
    """
    List of SimpleArguments. The constructor automatically adds
    an argument, that gives the operation a hint that it is run
    with the WebUI.
    """

    def __init__(self, **kwargs):
        """
        Converts the key-value pairs given in `kwargs` to
        `SimpleArgument` objects and appends them to `self`.
        """
        SimpleArguments.__init__(self, **kwargs)
        name = constants.kArgumentUsesWebUI
        if name not in kwargs:
            self.append(SimpleArgument(name, "1"))

        name = constants.kArgumentWebStreamCallback
        if name not in kwargs:
            self.append(SimpleArgument(name, WebFileUploadHelper.CALLBACK_METHOD))


def get_handles_from_restitems(for_items):
    # First collect favorite entries for the same REST name
    cls2rest_ids = defaultdict(list)
    for item in for_items:
        cls2rest_ids[item.rest_name].append(item.rest_id)
    # For each REST name, collect object handles with one call. Make sure to
    # retrieve only those items that the user has access to.
    all_handles = {}
    for rest_name, rest_ids in six.iteritems(cls2rest_ids):
        if rest_name:
            try:
                all_handles[rest_name] = getObjectHandlesFromRESTIDs(rest_name,
                                                                     rest_ids,
                                                                     check_access=True)
            except ValueError:
                # Fail safe if rest id of the class changed in the object is not
                # constructable (maybe temporary, so don't delete it).
                pass

    # Collect results in the order of the items given as input. For entries
    # where the target object could not be found (either deleted, or no rights)
    # a None value is returned.
    return [all_handles.get(item.rest_name, {}).get(item.rest_id, None) if item.rest_name else None
            for item in for_items]


def get_handles_from_restitems_for_class(for_items, classname):
    cdef = CDBClassDef(classname)
    rest_ids = [item.rest_id for item in for_items]
    # Implementation comments see aboves
    try:
        handles = getObjectHandlesFromRESTIDs(cdef, rest_ids, check_access=True)
        return [handles.get(item.rest_id, None) for item in for_items]
    except ValueError:
        return []


def class_available_in_ui(cldef):
    """ Determines whether a class is visible in the Web UI. This means (for now)
        that it has a REST name, and that at least one of the "Info" and "Search"
        operations is enabled for the Web UI.
    """
    if not cldef.getRESTName():
        return False
    for op_name in (constants.kOperationShowObject, constants.kOperationSearch):
        op_info = OperationInfo(cldef.getClassname(), op_name)
        if bool(op_info and op_info.offer_in_webui()):
            return True
    return False


def resolve_ui_name(rest_or_ui_name):
    """ Given a name that can be either a REST name or a UI name, returns a tuple
        of (<Classname>, <REST name>, <UI name>). If `rest_or_ui_name` is already
        a REST name, then the classname will be the root class that has this REST
        name configured, and UI name will be the same as the REST name, Otherwise,
        the classname will be that of the class that has the UI name configured,
        and the REST name will be the one for the corresponding root class.

        If `rest_or_ui_name` can't be resolved at all, classname will be None.
    """
    cldef = CDBClassDef.findByUIName(rest_or_ui_name)
    if cldef:
        return (cldef.getClassname(), cldef.getRESTName(), cldef.getUIName())
    return (None, None, None)


def ui_name_for_class(cdef):
    """"Returns the UI name for class cdef. This is either a configured GUI name
        if one exists, or else the REST name.
    """
    return cdef.getUIName()


def ui_name_for_classname(clsname):
    """ Like `ui_name_for_class`, but takes a classname instead of a class object
        as input.
    """
    cdef = CDBClassDef(clsname)
    return cdef.getUIName()


def get_classname_from_app_link(link):
    """ Returns the corresponding class name for a link if it points to a class page.
    """
    url_prefix = "/info/"
    if link and link.startswith(url_prefix):
        return resolve_ui_name(link[len(url_prefix):])[0]
    return None


def drl_encode_strings(ss):
    """ Creates a drl-message from the provided list of strings
    """
    return '@'.join([s.replace('\\', '\\\\').replace('@', '\\at') for s in ss])
