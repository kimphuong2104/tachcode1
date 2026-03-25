#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from __future__ import absolute_import

import unittest
from cdb import sqlapi
from cdb.testcase import run_level_setup
from cs.workspaces.wsm_settings import WsmSettings
from cdb.objects.operations import operation


def setUp():
    run_level_setup()


class Test_WsmSettings_ForReading(unittest.TestCase):
    PREFIX = "wsmtestcontext42_"

    def setUp(self):
        self.cleanUp()

    def tearDown(self):
        self.cleanUp()

    def cleanUp(self):
        sqlapi.SQLdelete("FROM wsm_settings WHERE context LIKE '%s%%'" % self.PREFIX)

    def test_noSettingsAvailable(self):
        settings = WsmSettings.find_valid_settings(self.PREFIX + "unused", "3.6")
        assert not settings

    def test_noValidSettingsAvailable(self):
        # given: a settings object in status invalid
        _invalid = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=180
        )
        # when: I try to retrieve a settings object
        settings = WsmSettings.find_valid_settings(self.PREFIX, "3.6")
        # then: no settings are found
        assert not settings

    def test_highestIsReleased(self):
        # given: multiple version, the highest is in status released
        _invalid = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=180
        )
        _editing = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=1, status=0
        )
        released = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=2, status=200
        )
        # when: I try to retrieve a settings object
        settings = WsmSettings.find_valid_settings(self.PREFIX, "3.6")
        # then: the released settings object is found
        assert settings == released

    def test_highestIsEditing(self):
        # given: multiple version, the highest is in status editing,
        #        but there is a lower one in status released
        released = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=200
        )
        _editing = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=1, status=0
        )
        # when: I try to retrieve a settings object
        settings = WsmSettings.find_valid_settings(self.PREFIX, "3.6")
        # then: the released settings object is found
        assert settings == released

    def test_noReleased(self):
        # given: multiple version, none of them released; one invalid
        _editing = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=0
        )
        _invalid = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=1, status=180
        )
        # when: I try to retrieve a settings object
        settings = WsmSettings.find_valid_settings(self.PREFIX, "3.6")
        # then: no 'editing' settings object is found
        assert settings is None

    def test_wrongVersion(self):
        # given: a settings object only exists for a different Workspaces Desktop version
        _releasedFor3_7 = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.7", s_index=0, status=200
        )
        # when: I try to retrieve a settings object
        settings = WsmSettings.find_valid_settings(self.PREFIX, "3.6")
        # then: no 'editing' settings object is found
        assert settings is None


class Test_WsmSettings_ForWriting(unittest.TestCase):
    PREFIX = "wsmtestcontext42_"

    def setUp(self):
        self.cleanUp()

    def tearDown(self):
        self.cleanUp()

    def cleanUp(self):
        sqlapi.SQLdelete("FROM wsm_settings WHERE context LIKE '%s%%'" % self.PREFIX)

    def test_noSettingsAvailable(self):
        context = self.PREFIX + "new"
        settings = WsmSettings.find_settings_to_update(context, "3.6")
        assert settings
        assert settings.context == context
        assert settings.status == 0

    def test_noValidSettingsAvailable(self):
        # given: a settings object in status invalid
        context = self.PREFIX + "new"
        _invalid = WsmSettings.Create(
            context=context, wsm_version="3.6", s_index=0, status=180
        )
        # when: I try to find a settings object for writing
        settings = WsmSettings.find_settings_to_update(context, "3.6")
        # then: a new settings object is created for the context
        assert settings
        assert settings.context == context
        assert settings.status == 0

    def test_highestIsReleased(self):
        # given: multiple version, the highest is in status released
        context = self.PREFIX + "new"
        _invalid = WsmSettings.Create(
            context=context, wsm_version="3.6", s_index=0, status=180
        )
        _released = WsmSettings.Create(
            context=context, wsm_version="3.6", s_index=1, status=200
        )
        _editing = WsmSettings.Create(
            context=context, wsm_version="3.6", s_index=2, status=0
        )
        # when: I try to find a settings object for writing
        settings = WsmSettings.find_settings_to_update(context, "3.6")
        # then: a new settings object is created for the context
        assert settings
        assert settings.context == context
        assert settings.status == 0

    def test_highestIsEditing(self):
        # given: multiple version, the highest is in status editing,
        #        but there is a lower one in status released
        context = self.PREFIX + "new"
        _released = WsmSettings.Create(
            context=context, wsm_version="3.6", s_index=0, status=200
        )
        _editing = WsmSettings.Create(
            context=context, wsm_version="3.6", s_index=1, status=0
        )
        # when: I try to find a settings object for writing
        settings = WsmSettings.find_settings_to_update(context, "3.6")
        # then: a new settings object is created for the context
        assert settings
        assert settings.context == context
        assert settings.status == 0

    def test_noReleased(self):
        # given: multiple version, none of them released; one invalid
        editing = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=0
        )
        _invalid = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=1, status=180
        )
        # when: I try to find a settings object for writing
        settings = WsmSettings.find_settings_to_update(self.PREFIX, "3.6")
        # then: the 'editing' settings object is found
        assert settings == editing

    def test_wrongVersion(self):
        # given: a settings object for a different Workspaces Desktop version
        editing = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=0
        )
        # when: I try to find a settings object for writing
        settings = WsmSettings.find_settings_to_update(self.PREFIX, "3.7")
        # then: a new settings object is created with the correct Workspaces Desktop version
        assert settings
        assert settings != editing
        assert settings.status == 0
        assert settings.wsm_version == "3.7"

    def test_stateChange(self):
        # given: a settings object that is "Neu" and will be changed to
        #        "Valid" and some other settings objects in various states
        invalid = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=180
        )
        released = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=1, status=200
        )
        editing = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=2, status=0
        )

        # when: I change the state of one object to "Valid"
        editing.ChangeState(200)

        # then: then the object is really "Valid"
        #       and all other objects are in state "Invalid"
        assert editing.status == 200
        others = [invalid, released]
        for other in others:
            other.Reload()
            assert other.status == 180


class Test_WsmSettings_Copy(unittest.TestCase):
    PREFIX = "wsmtestcontext42_"

    def setUp(self):
        self.cleanUp()

    def tearDown(self):
        self.cleanUp()

    def cleanUp(self):
        sqlapi.SQLdelete("FROM wsm_settings WHERE context LIKE '%s%%'" % self.PREFIX)

    def test_copyWithIdenticalContextAndVersion(self):
        # GIVEN: an existing settings object
        s1 = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=0
        )
        # WHEN: I create a copy of the settings object
        #       without changing any attributes
        s2 = operation("CDB_Copy", s1)

        # THEN: the index is automatically incremented,
        #       the other attributes are unchanged
        assert s2.s_index == 1
        assert s2.context == self.PREFIX
        assert s2.wsm_version == "3.6"

        # WHEN: I create another copy
        s3 = operation("CDB_Copy", s1)
        # THEN: the index is set to the next available value
        assert s3.s_index == 2
        assert s3.context == self.PREFIX
        assert s3.wsm_version == "3.6"

    def test_copyWithChangedVersion(self):
        # GIVEN: an existing settings object
        s1 = WsmSettings.Create(
            context=self.PREFIX, wsm_version="3.6", s_index=0, status=0
        )
        # WHEN: I create a copy for a different Workspaces Desktop version
        s2 = operation("CDB_Copy", s1, wsm_version="3.7")
        # THEN: the new settings object has the lowest available index for
        #       the combination of (wsm_version, context)
        assert s2.s_index == 0
        assert s2.context == self.PREFIX
        assert s2.wsm_version == "3.7"


class Test_WsmSettings_Create(unittest.TestCase):
    PREFIX = "wsmtestcontext42_"

    def setUp(self):
        self.cleanUp()

    def tearDown(self):
        self.cleanUp()

    def cleanUp(self):
        sqlapi.SQLdelete("FROM wsm_settings WHERE context LIKE '%s%%'" % self.PREFIX)

    def test_createMultiple(self):
        # GIVEN: a database without any settings objects with the given context
        # WHEN: I create a new settings object
        s1 = operation(
            "CDB_Create",
            "wsm_settings",
            context=self.PREFIX,
            wsm_version="3.6",
            status=0,
        )
        # THEN: the index is 0
        assert s1.s_index == 0

        # WHEN: I create another settings object with the same params
        s2 = operation(
            "CDB_Create",
            "wsm_settings",
            context=self.PREFIX,
            wsm_version="3.6",
            status=0,
        )
        # THEN: the index is 1
        assert s2.s_index == 1


if "__main__" == __name__:
    suite1 = unittest.makeSuite(Test_WsmSettings_ForReading)
    suite2 = unittest.makeSuite(Test_WsmSettings_ForWriting)
    suite3 = unittest.makeSuite(Test_WsmSettings_Copy)
    alltests = unittest.TestSuite([suite1, suite2, suite3])
    runner = unittest.TextTestRunner()
    runner.run(alltests)
