#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdbwrapc import PersSettings
from cdb.classbody import classbody
from cdb.objects.org import Person


@classbody
class Person(object):
    def getSettingValue(self, setting_id, default=None):
        """
        Returns the value of this user's personal setting identified by
        `setting_id`. If no personal setting is defined for this user,
        return the default value. If a default is not defined either, return
        `default`.
        """
        return PersSettings().getValueOrDefaultForUser(
            setting_id, "", default, self.personalnummer)

    def email_notification_task(self):
        """
        Resolves the setting `user.email_with_task` for this user. Returns True
        if the setting's value converts to True, and the user's `e_mail`
        attribute is not empty.
        """
        return bool(self.e_mail
                    and "1" == self.getSettingValue("user.email_with_task"))
