#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from cdb import ddl
from cdb import util
from cdb import sqlapi
from cdb import transaction
from cdb.ddl import Table, Char
from cdb.comparch import content, modules, protocol


class AddObjectIdsToFormContents(object):
    def run(self):
        with transaction.Transaction():
            t = 'cdbwf_form_contents_txt'
            if Table(t).hasColumn('task_id'):
                if Table(t).hasColumn('cdb_object_id'):
                    sqlapi.SQLupdate("""
                        cdbwf_form_contents_txt
                        SET cdb_object_id = (
                            SELECT cdb_object_id
                            FROM cdbwf_form
                            WHERE cdbwf_form_contents_txt.task_id
                                = cdbwf_form.task_id
                                AND cdbwf_form_contents_txt.cdb_process_id
                                    = cdbwf_form.cdb_process_id
                                AND cdbwf_form_contents_txt.form_template_id
                                    = cdbwf_form.form_template_id
                        )"""
                    )

                    protocol.logMessage(
                        "'cdbwf_form_contents_txt.cdb_object_id' initialized"
                    )
                self.removeUniqueContraintOfFormTable()
                self.removeUniqueConstraintsofFormContentsTable()
            else:
                protocol.logMessage(
                    "field 'cdbwf_form_contents_txt.task_id' not found; "
                    "skipping"
                )

    def removeUniqueContraintOfFormTable(self):
        t = Table('cdbwf_form')
        t.dropPrimaryKey()
        pk = ddl.PrimaryKey('cdb_object_id')
        t.setPrimaryKey(pk)
        self.setColContraintNull(t, 'task_id')
        self.setColContraintNull(t, 'cdb_process_id')
        self.setColContraintNull(t, 'form_template_id')

    def removeUniqueConstraintsofFormContentsTable(self):
        t = Table('cdbwf_form_contents_txt')
        t.dropPrimaryKey()
        pk = ddl.PrimaryKey('cdb_object_id', 'zeile')
        t.setPrimaryKey(pk)
        self.setColContraintNull(t, 'task_id')
        self.setColContraintNull(t, 'cdb_process_id')
        self.setColContraintNull(t, 'form_template_id')

    def setColContraintNull(self, t, colname):
        col = t.getColumn(colname)
        col.notnull = 0
        t.modifyAttributes(col)


class InitSortableIDForCdbwf_protocol(object):
    """
    Initializes the new primary key ``cdbwf_protocol.cdbprot_sortable_id``.
    """

    @staticmethod
    def get_sortable_id(table_name, target_col, source_a, source_b):
        """
        Returns SQL expression to initialize `target_col` from columns
        `source_a` and `source_b` in table `table_name`.

        The old values are prepended with ``0`` chars so they stay sortable.
        """
        dbms = sqlapi.SQLdbms()
        target_length = util.tables[table_name].column(target_col).length()

        if dbms == sqlapi.DBMS_SQLITE:
            pre = "0" * target_length
            return "substr('%s' || %s || %s, %d, %d)" % (
                pre, source_a, source_b, -target_length, target_length)

        elif dbms == sqlapi.DBMS_MSSQL:
            return (
                "RIGHT(REPLICATE('0', %d) "
                "+ %s "
                "+ LTRIM(STR(%s))"
                ", %d) " % (
                    target_length, source_a, source_b, target_length,
                )
            )
        elif dbms == sqlapi.DBMS_ORACLE:
            return "LPAD(%s || %s, %d, '0')" % (
                source_a, source_b, target_length)

        else:
            raise RuntimeError("unsupported DBMS: {}".format(dbms))

    def initialize_sortable_id(self):
        max_entry = sqlapi.RecordSet2(
            sql="SELECT MAX(entry_id) AS x FROM cdbwf_protocol")[0].x

        if max_entry and max_entry > 9999999999:
            protocol.logWarning(
                "Cannot initialize cdbwf_protocol.cdbprot_sortable_id. "
                "Entry IDs with more than 10 digits exist, so we cannot "
                "guarantee sortability. "
                "Please migrate manually (takes some time)."
            )
            return

        # First we initialize the new key
        new_value = InitSortableIDForCdbwf_protocol.get_sortable_id(
            "cdbwf_protocol", "cdbprot_sortable_id",
            "cdb_process_id", "entry_id")

        sqlapi.SQLupdate(
            "cdbwf_protocol "
            "SET cdbprot_sortable_id = %s "
            "WHERE cdbprot_sortable_id IS NULL "
            "OR cdbprot_sortable_id = ''" % new_value
        )

        # Try to change the PK
        t = ddl.Table("cdbwf_protocol")
        t.setPrimaryKey(ddl.PrimaryKey("cdbprot_sortable_id"))
        t.dropAttributes("entry_id")

    def run(self):
        if not util.column_exists("cdbwf_protocol", "entry_id"):
            protocol.logMessage("No need to migrate protocol ==> no entry_id")
            return

        with transaction.Transaction():
            self.initialize_sortable_id()

class revertDeletedPatches(object):
    """revert deleted patches for table `mq_wfqueue_status`"""

    __table__ = "mq_wfqueue_status"

    def run(self):
        protocol.logMessage("Reverting patches in {}".format(self.__table__))
        module = modules.Module.ByKeys('cs.workflow')
        content_filter = content.ModuleContentFilter([self.__table__])
        mc = modules.ModuleContent(
            module.module_id,
            module.std_conf_exp_dir,
            content_filter,
        )
        reverted = 0
        for mod_content in mc.getItems(self.__table__).values():
            try:
                mod_content.insertIntoDB()  # Effectively revert patch
                reverted += 1
            except:
                pass  # Already there

        if reverted:
            protocol.logMessage(
                "  {} Reverted patches".format(reverted))

pre = [AddObjectIdsToFormContents, InitSortableIDForCdbwf_protocol]
post = [revertDeletedPatches]
