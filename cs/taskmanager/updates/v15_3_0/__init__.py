#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi
from cdb.comparch import modules, protocol
from cs.taskmanager.userdata import Tags

from .common import Migrater


class TagsMigrater(Migrater):
    """
    migrate to new class using its objects interface (long text)
    immediately delete old records, as table will be kept
    """

    __table_old__ = "cdb_app_obj_setting"
    __table_new__ = "cs_tasks_tag"
    __where__ = "setting_id='elink.apps.taskmanager.tags'"

    def __init__(self):
        self.migrated_count = 0
        self.deleted_count = 0

    def _copy(self, record):
        if record["value"]:
            Tags.SetTaskTags(
                record["personalnummer"],
                record["cdbf_object_id"],
                record["value"].split(","),
            )
            self.migrated_count += 1

        record.delete()
        self.deleted_count += 1

    def _old_records(self):
        return sqlapi.RecordSet2(self.__table_old__, self.__where__)

    def _report(self):
        protocol.logMessage(
            "{}: migrated {} entries, deleted {} old ones".format(
                self.__class__.__name__, self.migrated_count, self.deleted_count
            )
        )


class ReadStatusMigrater(Migrater):
    """
    migrate to new class
    immediately delete old records, as table will be kept
    """

    __table_old__ = "cdb_app_obj_setting"
    __table_new__ = "cs_tasks_read_status"
    __where__ = "setting_id='elink.apps.taskmanager.taskRead'"

    def __init__(self):
        self.migrated_count = 0
        self.deleted_count = 0

    def _transform(self, record):
        return sqlapi.Record(
            self.__table_new__,
            persno=record["personalnummer"],
            task_object_id=record["cdbf_object_id"],
            read_status=1,
        )

    def _copy(self, record):
        if record["value"] == "true":
            Migrater._copy(self, record)
            self.migrated_count += 1

        record.delete()
        self.deleted_count += 1

    def _old_records(self):
        return sqlapi.RecordSet2(self.__table_old__, self.__where__)

    def _report(self):
        protocol.logMessage(
            "{}: migrated {} entries, deleted {} old ones".format(
                self.__class__.__name__, self.migrated_count, self.deleted_count
            )
        )


class InstallOptionalChanges(object):
    """
    make sure new access control domains are installed
    """

    def run(self):
        mod = modules.Module.ByKeys("cs.taskmanager")
        prot_id = protocol.ProtocolContext.current_protocol_id()
        mod.install_optional_changes(prot_id)


class MigrateUserData(object):
    """
    migrate user tags and read status; immediately delete old entries after
    successful migration
    """

    def run(self):
        for migrater in [TagsMigrater, ReadStatusMigrater]:
            try:
                migrater().migrate()
            except Exception as e:
                protocol.logError(
                    "{} failed".format(migrater), details_longtext="{}".format(e)
                )
                raise


class UpdateTableSettings(object):
    def run(self):
        protocol.logMessage(
            "skipping obsolete update script 'UpdateTableSettings'",
        )


pre = []
post = [InstallOptionalChanges, MigrateUserData, UpdateTableSettings]
