# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$
from urllib.parse import urlencode

from cdb import sig
from cs.variants import Variant
from cs.variants.web.common import update_app_setup
from cs.vp import products

COMPONENT_NAME = "cs-variants-web-maxbom_editor"
VERSION = "15.1.1"


@sig.connect(products.Product, "cs_variant_open_maxbom_editor", "now")
def _open_maxbom_editor_now_for_product(self, ctx):
    url = "/maxbom_editor/%s" % self.cdb_object_id
    ctx.url(url)


@sig.connect(Variant, "cs_variant_open_maxbom_editor", "now")
def _open_maxbom_editor_now_for_variant(self, ctx):
    max_bom_id = getattr(ctx.dialog, "max_bom_id", "")
    variability_model = self.VariabilityModel

    url = "/maxbom_editor/{product_oid}?{params}".format(
        product_oid=variability_model.product_object_id,
        params=urlencode(
            {
                "variantId": self.id,
                "variabilityModel": variability_model.cdb_object_id,
                "maxbom": max_bom_id,
            }
        ),
    )

    ctx.url(url)


def setup_variant_filter(_, request, app_setup):
    update_app_setup(request, app_setup, product=request.app.product)
