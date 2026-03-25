#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb.objects import NULL
from cdb.objects import ByID
from cs.vp.products import Product


def vp_compute_amount_comp(qc):
    pr = Product.ByKeys(qc.cdbf_object_id)

    non_unvalid_maxboms = [mb for mb in pr.MaxBoms if mb.status != 180]
    if non_unvalid_maxboms:
        mb = non_unvalid_maxboms[0]
        return len([comp for comp in mb.resolveComponents()
                    if comp.t_kategorie == "Einzelteil"])
    else:
        return NULL


def vp_compute_amount_variants(qc):
    product = ByID(qc.cdbf_object_id)
    return len(product.AllVariants)
