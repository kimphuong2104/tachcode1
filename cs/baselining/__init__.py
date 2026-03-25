#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import logging

from cdb import sqlapi
from cdb.objects.core import ByID, Object
from cs.audittrail import WithAuditTrail

LOG = logging.getLogger(__name__)


class Baseline(Object, WithAuditTrail):
    __classname__ = "ce_baseline"
    __maps_to__ = "ce_baseline"

    def fill_system_attribute_mask_fields(self, ctx):
        for field_name in [
            "ce_baseline_creator",
            "ce_baseline_cdate",
            "ce_baseline_creation_type",
        ]:
            if field_name + "_mask" in ctx.dialog.get_attribute_names():
                ctx.set(field_name + "_mask", getattr(self, field_name))

    def insert_trailing_space_to_info_tag(self, ctx):
        if (
            "ce_baseline_info_tag" in ctx.dialog.get_attribute_names()
            and ctx.dialog.ce_baseline_info_tag
            != ctx.previous_values.ce_baseline_info_tag
        ):
            stmt = """
            {relation} SET ce_baseline_info_tag = '{ce_baseline_info_tag_new}' WHERE
            cdb_object_id = '{cdb_object_id}'
            """
            sqlapi.SQLupdate(
                stmt.format(
                    relation=Baseline.__maps_to__,
                    ce_baseline_info_tag_new=sqlapi.quote(
                        self.ce_baseline_info_tag + " "
                    ),
                    cdb_object_id=self.cdb_object_id,
                )
            )

    def delete_baseline_contents(self, ctx):
        if not self.ce_baselined_object_id:
            LOG.warning(
                """Only baseline head object has been deleted,
                deleting baseline contents is NOT supported
                for context objects without cdb_object_id."""
            )
        else:
            baseline_ctx_object = ByID(self.ce_baselined_object_id)
            if baseline_ctx_object:
                from cs.baselining.support import BaselineTools

                current_obj = BaselineTools.get_current_obj(baseline_ctx_object)
                current_obj.remove_all_baseline_elements(
                    ce_baseline_id=self.cdb_object_id, check_access=True
                )

    event_map = {
        (("info", "modify"), "pre_mask"): "fill_system_attribute_mask_fields",
        ("modify", "post"): "insert_trailing_space_to_info_tag",
        ("delete", "post"): "delete_baseline_contents",
    }
