# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

from cdb import sig, typeconversion, util
from cs.variants import Variant
from cs.vp import products

COMPONENT_NAME = "cs-variants-web-editor"
VERSION = "15.1.1"
STATUS_FILTER_DISCRIMINATOR = "cs.variants.variant_editor.statusFilter"


@sig.connect(products.Product, "cs_variant_editor", "now")
def _open_variant_editor_now(self, ctx):
    url = "/variant_editor/%s" % self.cdb_object_id
    ctx.url(url)


def get_initial_applied_filter_data_for_variant_editor():
    personal_settings = util.PersonalSettings()

    saved = typeconversion.to_bool(
        personal_settings["cs.variants.variant_filter.status.saved"]
    )
    invalid = typeconversion.to_bool(
        personal_settings["cs.variants.variant_filter.status.invalid"]
    )
    not_evaluated = typeconversion.to_bool(
        personal_settings["cs.variants.variant_filter.status.notEvaluated"]
    )

    return {
        STATUS_FILTER_DISCRIMINATOR: {
            "saved": saved,
            "invalid": invalid,
            "notEvaluated": not_evaluated,
            "onlyIncomplete": False,
        }
    }


def get_variant_manager_setup_information(variability_models):
    variability_model_variants_ids = Variant.KeywordQuery(
        variability_model_id=[vm.cdb_object_id for vm in variability_models]
    ).cdb_object_id

    initial_table_limit = util.get_prop("veir")
    if initial_table_limit == "" or initial_table_limit is None:
        initial_table_limit = 200

    limit_increment = util.get_prop("velm")
    if limit_increment == "" or limit_increment is None:
        limit_increment = 100

    app_setup_data = {
        "variability_model_variants_ids": variability_model_variants_ids,
        "initial_table_limit": int(initial_table_limit),
        "limit_increment": int(limit_increment),
        "initial_applied_filter_data": get_initial_applied_filter_data_for_variant_editor(),
    }

    return app_setup_data
