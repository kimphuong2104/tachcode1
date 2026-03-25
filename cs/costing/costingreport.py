#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
from cdb import ue
from cdb.objects import Object


class ReportConfiguration(Object):
    __maps_to__ = "cdbpco_costing_report_config"
    __classname__ = "cdbpco_costing_report_config"

    event_map = {
            (('create', 'copy'), 'pre_mask'): 'update_position',
            (('create', 'copy', 'modify'), 'dialogitem_change'): 'change_type',
            ('cdbpcs_costs_change_position', 'now'): 'change_positions'
    }

    def update_position(self, ctx):
        config_rows = ReportConfiguration.KeywordQuery(schema_object_id=self.schema_object_id)
        if config_rows:
            self.position_costing_report = max(config_rows.position_costing_report) + 10
            return
        self.position_costing_report = 10

    def change_positions(self, ctx):
        fields_to_move = self.PersistentObjectsFromContext(ctx)
        row_name_first_selection = fields_to_move[0]['row_name']
        position_costing_first_selection = fields_to_move[0]['position_costing_report']

        classname2 = None
        for f in fields_to_move:
            if not classname2:
                classname2 = f.__classname__
            if f.__classname__ != classname2:
                raise ue.Exception("op_costing_report_set_position_multi_class")

        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name="cdb_costing_report_rowname",
                                classname=classname2,
                                schema_object_id=self.schema_object_id)
        else:
            row_name_second_selection = ReportConfiguration.ByKeys(ctx.catalog_selection[0].cdb_object_id)['row_name']
            position_costing_second_selection = ReportConfiguration.ByKeys(ctx.catalog_selection[0].cdb_object_id)['position_costing_report']

            all_config = ReportConfiguration.KeywordQuery(schema_object_id=self.schema_object_id)
            max_position_costing = max(all_config.position_costing_report)
            index = -1
            for f in all_config:
                index += 1
                if f.position_costing_report == position_costing_first_selection:
                    if position_costing_first_selection > position_costing_second_selection:
                        if position_costing_second_selection < max_position_costing:
                            all_config[index]['position_costing_report'] = position_costing_second_selection + 10
                    elif position_costing_first_selection < position_costing_second_selection:
                        all_config[index]['position_costing_report'] = position_costing_second_selection
                elif f.position_costing_report == position_costing_second_selection:
                    if position_costing_first_selection < position_costing_second_selection:
                        all_config[index]['position_costing_report'] = position_costing_second_selection - 10
                else:
                    if f.position_costing_report < position_costing_first_selection:
                        if f.position_costing_report > position_costing_second_selection:
                            all_config[index]['position_costing_report'] += 10
                    elif f.position_costing_report > position_costing_first_selection:
                        if f.position_costing_report < position_costing_second_selection:
                            all_config[index]['position_costing_report'] -= 10
        return

    def change_type(self, ctx):
        if ctx.changed_item == "row_type":
            if ctx.dialog.row_type == "Empty":
                ctx.set_fields_readonly(["row_name", "param_object_id"])
                ctx.set_optional("row_name")
                ctx.set_optional("param_object_id")
                ctx.set("row_name_de", "")
                ctx.set("row_name_en", "")
                ctx.set("param_object_id", "")
            elif ctx.dialog.row_type == "Parameter":
                ctx.set_fields_writeable(["row_name", "param_object_id"])
                ctx.set_mandatory("row_name")
                ctx.set_mandatory("param_object_id")
