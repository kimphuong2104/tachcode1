#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=bare-except

from cdb import ddl, sqlapi, transaction
from cdb.comparch import content, modules, protocol
from cdb.objects import paginated
from cdb.platform.mom.entities import Class
from cs.taskmanager.userdata import Tags


class TagSchemaChange(object):
    """
    Primary key change in cs_tasks_tag.
    """

    __tag_attr__ = "tag"
    __txt__ = "cs_tasks_tag_txt"

    def run(self):
        tag_class = Class.ByKeys(Tags.__classname__)

        if tag_class:
            # tag_class is None if updating from cs.taskmanager < 15.3.1

            table = ddl.Table(Tags.__maps_to__)
            tag_column = ddl.Char(self.__tag_attr__, 255, default="''")

            with transaction.Transaction():
                if table.hasColumn(self.__tag_attr__):
                    table.modifyAttributes(tag_column)
                else:
                    table.addAttributes(tag_column)
                    table.reflect(force_reload=True)

                sqlapi.SQLupdate(
                    "{} SET {}='' WHERE {} IS NULL".format(
                        Tags.__maps_to__, self.__tag_attr__, self.__tag_attr__
                    )
                )
                table.setPrimaryKey(
                    ddl.PrimaryKey("persno", "task_object_id", self.__tag_attr__)
                )
                table.reflect(force_reload=True)

                tag_class.compile(force=True)
                protocol.logMessage("you may now drop '{}'".format(self.__txt__))
        else:
            protocol.logMessage(
                "class '{}' does not exist - "
                "skipping update".format(Tags.__classname__)
            )


class MigrateTags(object):
    """
    Migrate existing tags from long text to single entries. Needed to
    efficiently support typeahead suggestions of existing user tags.
    """

    __tag_attr__ = "tag"
    __txt__ = "cs_tasks_tag_txt"

    def run(self):
        table = ddl.Table(self.__txt__)
        # E049339 when updating from a pre-15.3.0 installation,
        # long text relation has never existed
        if table.exists():
            old_tags = Tags.Query()

            for page in paginated(old_tags):
                for old_tag in page:
                    with transaction.Transaction():
                        text = sqlapi.RecordSet2(
                            self.__txt__,
                            "persno='{}' AND task_object_id='{}'".format(
                                old_tag.persno, old_tag.task_object_id
                            ),
                            addtl="ORDER BY zeile ASC",
                        )

                        if text:
                            tags_txt = "".join([t.text for t in text])

                            for tag in set(tags_txt.split(",")):
                                vals = {
                                    "persno": old_tag.persno,
                                    "task_object_id": old_tag.task_object_id,
                                    "tag": tag.strip(),
                                }
                                if not Tags.KeywordQuery(**vals):
                                    Tags.Create(**vals)

            with transaction.Transaction():
                sqlapi.SQLdelete("FROM {} WHERE tag=''".format(Tags.__maps_to__))

            protocol.logMessage("Tags successfully migrated.")
        else:
            protocol.logWarning(
                "Skip tag migration because relation {} is missing. If you are"
                " updating from cs.taskmanager < 15.3.0, you can ignore this "
                "message".format(self.__txt__)
            )


class EnsureDefaultUser(object):
    """Always re-insert user and role assignments for cs.taskmanager.dflt"""

    def run(self):
        m = modules.Module.ByKeys("cs.taskmanager")
        for rel, key in [
            ("angestellter", "personalnummer"),
            ("cdb_global_subj", "subject_id"),
        ]:
            content_filter = content.ModuleContentFilter([rel])
            mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

            for mod_content in mc.getItems(rel).values():
                if mod_content.getAttr(key) == "cs.taskmanager.dflt":
                    try:
                        # Effectively revert patch
                        mod_content.insertIntoDB()
                    except:  # nosec # noqa: E722
                        pass  # Already there


class UpdateTableSettings(object):
    def run(self):
        protocol.logMessage(
            "skipping obsolete update script 'InitializeTableSettings'",
        )


pre = [TagSchemaChange]
post = [EnsureDefaultUser, UpdateTableSettings, MigrateTags]
