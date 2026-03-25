#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.classbody import classbody
from cdb.objects import references
from cs.vp.products import Product
from cs.requirements import fRQMSpecification, RQMSpecification


@classbody
class RQMSpecification(object):
    Product = references.Reference_1(Product, Product.cdb_object_id == fRQMSpecification.product_object_id)


@classbody
class Product(object):
    Specifications = references.Reference_N(fRQMSpecification, fRQMSpecification.product_object_id == Product.cdb_object_id)
