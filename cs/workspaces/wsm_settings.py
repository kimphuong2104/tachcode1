#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import logging

from cdb import sqlapi
from cdb import util
from cdb import ue
from cdb import auth

from cdb.objects import Object
from cdb.objects import Reference_N
from cdb.objects import Forward
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation

fWsmSettings = Forward("cs.workspaces.wsm_settings.WsmSettings")


ROLE_STANDARD_APP_DEVELOPER = "Standard App Developer"


class WsmSettings(Object):
    __maps_to__ = "wsm_settings"
    __classname__ = "wsm_settings"

    Files = Reference_N(CDB_File, CDB_File.cdbf_object_id == fWsmSettings.cdb_object_id)

    @staticmethod
    def find_valid_settings(wsm_context, wsm_version):
        """
        :param wsm_context: string
        :param wsm_version: string (for example "3.6")
        :return: WsmSettings object or None
        """
        logging.info(
            "WsmSettings: looking for readable settings container for Workspaces Desktop %s,"
            " using context '%s'",
            wsm_version,
            wsm_context,
        )
        result = None
        releasedSettings = WsmSettings._get_sorted_settings(
            wsm_context, wsm_version, [200]
        )
        if releasedSettings:
            result = releasedSettings[0]
            logging.info(
                "WsmSettings: Found existing settings container with index %s.",
                result.s_index,
            )
        else:
            logging.info("WsmSettings: found no settings container.")
        return result

    @staticmethod
    def find_downloadable_settings_for_admin(wsm_context, wsm_version):
        """
        :param wsm_context: string
        :param wsm_version: string (for example "3.6")
        :return: list of WsmSettings objects
        """
        logging.info(
            "WsmSettings: looking for downloadable settings containers for admin for Workspaces Desktop %s,"
            " using context '%s'",
            wsm_version,
            wsm_context,
        )
        # first look for the newest released settings object
        releasedSO = None
        releasedSettings = WsmSettings._get_sorted_settings(
            wsm_context, wsm_version, [200]
        )
        if releasedSettings:
            releasedSO = releasedSettings[0]
            logging.info(
                "WsmSettings: Found existing (released) settings container with index %s.",
                releasedSO.s_index,
            )
        else:
            logging.info("WsmSettings: found no released settings container.")

        # now check if there is a new (unreleased) settings object with a higher index
        # the admin might want to download that instead
        newNewerSO = None
        newSettings = WsmSettings._get_sorted_settings(wsm_context, wsm_version, [0])
        if newSettings:
            newSetting = newSettings[0]
            if releasedSO is None or newSetting.s_index > releasedSO.s_index:
                newNewerSO = newSetting
                logging.info(
                    "WsmSettings: Found existing (new) settings container with index %s.",
                    newNewerSO.s_index,
                )

        result = []
        if releasedSO is not None:
            result.append(releasedSO)
        if newNewerSO is not None:
            result.append(newNewerSO)
        return result

    @staticmethod
    def find_settings_to_update(wsm_context, wsm_version):
        """
        Finds or creates a settings object that is in state "editing".
        :param wsm_context: string
        :param wsm_version: string (for example "3.6")
        :return: WsmSettings object
        """
        logging.info(
            "WsmSettings: looking for writable settings container for Workspaces Desktop %s,"
            " using context '%s'",
            wsm_version,
            wsm_context,
        )
        # check if the highest valid settings object is in state 'editing';
        # if yes, use it for saving
        nonInvalidSettings = WsmSettings._get_sorted_settings(
            wsm_context, wsm_version, [0, 200]
        )
        if nonInvalidSettings:
            highest = nonInvalidSettings[0]
            if highest.status == 0:
                logging.info(
                    "WsmSettings: Found existing settings container with index %s.",
                    highest.s_index,
                )
                return highest

        # otherwise create a new settings object with the right "index" value
        newSettings = None
        logging.info(
            "Creating new index with context: '%s', wsm_version: '%s'",
            wsm_context,
            wsm_version,
        )
        keys = {"context": wsm_context, "wsm_version": wsm_version}
        if util.check_access("wsm_settings", keys, "create"):
            args = {"context": wsm_context, "wsm_version": wsm_version, "status": 0}
            newSettings = operation("CDB_Create", WsmSettings, **args)
            logging.info(
                "WsmSettings: created new settings container with index %s.",
                newSettings.s_index,
            )
        else:
            logging.error(
                "WsmSettings: can't create settings container because of missing 'create' right."
            )

        return newSettings

    @staticmethod
    def _get_sorted_settings(context, wsm_version, stati=None):
        query = "context = '%s' AND wsm_version = '%s'" % (
            sqlapi.quote(context),
            sqlapi.quote(wsm_version),
        )
        if stati is not None:
            query += " AND status IN (%s)" % ",".join(str(s) for s in stati)
        return WsmSettings.Query(query, "s_index DESC")

    def _isWsdDeveloper(self):
        roles = util.get_roles("GlobalContext", "", auth.persno)
        return ROLE_STANDARD_APP_DEVELOPER in roles

    def on_create_pre_mask(self, ctx):
        ctx.set("status", 0)
        ctx.set("s_index", 0)
        ctx.set_writeable("context")
        ctx.set_writeable("wsm_version")
        if self._isWsdDeveloper():
            ctx.set_writeable("s_index")  # to be able to create template settings

    def on_create_pre(self, ctx):
        # set s_index automatically (except for negative values which are used for template settings)
        if self.s_index is None or self.s_index >= 0:
            ctx.set(
                "s_index",
                WsmSettings._find_lowest_free_index(self.context, self.wsm_version),
            )

    def on_copy_pre_mask(self, ctx):
        ctx.set_writeable("context")
        ctx.set_writeable("wsm_version")
        if self._isWsdDeveloper():
            ctx.set_writeable("s_index")  # to be able to create template settings

    def on_copy_pre(self, ctx):
        # set s_index automatically (even when copying template settings)
        ctx.set(
            "s_index",
            WsmSettings._find_lowest_free_index(self.context, self.wsm_version),
        )

    @staticmethod
    def _find_lowest_free_index(context, wsm_version):
        res = 0
        existing = WsmSettings._get_sorted_settings(context, wsm_version)
        if existing:
            res = existing[0].s_index + 1
        return res

    def on_state_change_post(self, ctx):
        # changed state from "New" or "Invalid" to "Valid"
        if ctx.old.status in ["0", "180"] and ctx.new.status == "200":
            # set all other "Valid" versions to "Invalid"
            allForContext = self._get_sorted_settings(
                self.context, self.wsm_version, [200]
            )
            for settings in allForContext:
                if settings.s_index != self.s_index:
                    oldState = settings.status
                    try:
                        settings.ChangeState(180)
                    except RuntimeError as e:
                        raise ue.Exception(
                            "cdb_konfstd_008", "%s" % oldState, "%s" % 180, e
                        )
