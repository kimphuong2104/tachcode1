#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import

import os
import logging
import six

from cdb.objects import ByID
from cdb.objects.cdb_file import CDB_File
from cdb import sqlapi

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


class SetFilenamesProcessor(CmdProcessorBase):
    """
    Changes the server-side filenames.
    Used to enforce keeping partner filenames when indexing/copying.
    """

    name = u"setfilenames"

    def call(self, resultStream, request):
        ret = WsmCmdErrCodes.messageOk

        wsCmdContextObjs = self._rootElement.getChildrenByName(
            "WSCOMMANDS_CONTEXTOBJECT"
        )
        for context in wsCmdContextObjs:
            cdb_object_id = context.cdb_object_id
            new_names = {}
            # first collect names
            for commandObject in context.getChildrenByName("WSCOMMANDS_OBJECT"):
                cdb_wspitem_id = commandObject.local_id
                command = commandObject.getFirstChildByName("COMMAND")
                if not command:
                    return WsmCmdErrCodes.messageNotWellFormed

                if command.action != "set_filename":
                    return WsmCmdErrCodes.messageNotWellFormed

                attributes = command.getFirstChildByName("ATTRIBUTES")
                if not attributes:
                    return WsmCmdErrCodes.messageNotWellFormed

                filename = attributes.attributes["cdbf_name"]
                new_names[cdb_wspitem_id] = filename

            # now rename all files of one document
            if not self._setFilenamesOfObject(cdb_object_id, new_names):
                ret = WsmCmdErrCodes.unknownProcessingError
        return ret

    def _setFilenamesOfObject(self, cdb_object_id, new_names):
        """
        :param cdb_object_id: str
        :param new_names: dict(cdb_wspitem_id -> str)
        :return: bool (success)
        """
        obj = ByID(cdb_object_id)
        if not obj:
            logging.error(
                "SetFilenamesProcessor: cannot find object '%s'", cdb_object_id
            )
            return False

        ret = True
        for cdb_wspitem_id, filename in six.iteritems(new_names):
            success = self._setFilename(obj, cdb_wspitem_id, filename)
            if not success:
                ret = False  # but continue with the other names
        return ret

    def _setFilename(self, obj, cdb_wspitem_id, filename):
        """
        :param obj: Document or compatible class
        :param cdb_wspitem_id: str
        :param filename: str
        :return: bool (success)
        """
        files = CDB_File.Query(
            "cdbf_object_id = '%s' AND (cdb_wspitem_id = '%s' OR cdb_belongsto = '%s')"
            % (
                sqlapi.quote(obj.cdb_object_id),
                sqlapi.quote(cdb_wspitem_id),
                sqlapi.quote(cdb_wspitem_id),
            )
        )
        # rename main file and remember its old name
        old_name = None
        for f in files:
            if not f.cdb_belongsto:
                old_name = f.cdbf_name
                f.cdbf_name = filename
                break
        else:
            logging.error(
                "SetFilenamesProcessor: cannot find file with cdb_wspitem_id '%s' (object '%s')",
                cdb_wspitem_id,
                obj.cdb_object_id,
            )

        # rename belongsto files if they have the same filename pattern
        if old_name:
            for f in files:
                if f.cdb_belongsto:
                    basename, ext = os.path.splitext(f.cdbf_name)
                    if basename.lower() == old_name.lower():
                        f.cdbf_name = filename + ext

        return old_name is not None
