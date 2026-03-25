#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cdb import auth, sqlapi
from cdb.util import PersonalSettings, get_roles
from cs.taskmanager.user_views import SELECTED

TASKS_ADMIN = "Administrator: My Tasks"


def offer_admin_ui():
    common_roles = get_roles("GlobalContext", "", auth.persno)
    return TASKS_ADMIN in common_roles


class ModelWithUserSettings(object):
    __id1__ = "cs.taskmanager"

    def __init__(self):
        self.settings = PersonalSettings()
        self.settings.invalidate()

    def _get_setting(self, id2):
        if id2 == SELECTED:
            condition = "personalnummer = '{}' AND setting_id2 LIKE '{}--%'".format(
                auth.persno, id2
            )
            result = sqlapi.RecordSet2(
                table="cdb_usr_setting",
                condition=condition,
                columns=["setting_id2", "value"],
            )
        else:
            result = self.settings.getValueOrDefault(self.__id1__, id2, None)
        return result

    def _set_setting(self, id2, value):
        self.settings.setValue(self.__id1__, id2, value)
