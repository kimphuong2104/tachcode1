#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com


from cdb import ddl, testcase

from cs.pcs.projects_documents.updates.v15_7_1 import UpdateDocTemplateColumns


class DocTemplateRelations(testcase.RollbackTestCase):
    """
    There are two valid configurations
    1. < 15.4.1 Table with `z_index` and without `use_selected_index`
    2. >= 15.4.1 Table with `z_index` and `use_selected_index`
    """

    def _setup_attributes(self, table):

        self.attributes_added = []
        self.attributes_removed = []

        self.tmp_attribute_name = "use_selected_index"
        self.tmp_attribute = ddl.Char(self.tmp_attribute_name, 20)

        self.index_attribute_name = "z_index"
        self.index_attribute = ddl.Char(self.index_attribute_name, 20)

        if table.hasColumn(self.index_attribute_name):
            return None
        table.addAttributes(self.index_attribute)
        self.assertTrue(
            table.hasColumn(self.index_attribute_name),
            "Test preparation failed. Column has not been added",
        )
        self.attributes_added.append(self.index_attribute)

    def _clean_up(self, table):
        for column in self.attributes_removed:
            table.addAttributes(column)
        for column in self.attributes_added:
            table.dropAttributes(column)

    def test_update_doc_templates_from_before_15_4_1(self):
        """
        Tested on the table `cdbpcs_cl2doctmpl`.
        If it does exist, the temporary attribute is removed for testing purposes
        We are testing only initializing to avoid further schema changes
        We do not perform specific tests after execution.
        We assume that an exception-free run confirms the success.
        """

        table_name = "cdbpcs_cl2doctmpl"
        table = ddl.Table(table_name)

        self._setup_attributes(table)

        # preparing the `use_selected_index` attribute
        if table.hasColumn(self.tmp_attribute_name):
            column = table.getColumn(self.tmp_attribute_name)
            table.dropAttributes(self.tmp_attribute_name)
            self.attributes_removed.append(column)
        self.assertFalse(
            table.hasColumn(self.tmp_attribute_name),
            "Test preparation failed. Column has not been removed.",
        )

        # running update
        try:
            UpdateDocTemplateColumns().init_tmpl_index_column(table, table_name)
        except Exception as error:
            self._clean_up(table)
            raise error

        self._clean_up(table)

    def test_update_doc_templates_from_15_4_1(self):
        """
        Tested on the table `cdbpcs_prj2doctmpl`.
        If it does not exist, the temporary attribute is dropped for testing purposes
        We are testing only initializing to avoid further schema changes
        We do not perform specific tests after execution.
        We assume that an exception-free run confirms the success.
        """

        table_name = "cdbpcs_prj2doctmpl"
        table = ddl.Table(table_name)

        self._setup_attributes(table)

        # preparing the `use_selected_index` attribute
        if not table.hasColumn(self.tmp_attribute_name):
            table.addAttributes(self.tmp_attribute)
            self.attributes_added.append(self.tmp_attribute_name)
        self.assertTrue(
            table.hasColumn(self.tmp_attribute_name),
            "Test preparation failed. Column has not been added.",
        )

        # running update
        try:
            UpdateDocTemplateColumns().init_tmpl_index_column(table, table_name)
        except Exception as error:
            self._clean_up(table)
            raise error

        self._clean_up(table)
