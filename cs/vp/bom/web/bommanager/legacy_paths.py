# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$
from itertools import zip_longest

import morepath
from webob import exc

from cs.vp.bom.web.bommanager import make_bommanager_url
from cs.vp.bom.web.bommanager.main import BommanagerApp


# Taken from https://docs.python.org/2.7/library/itertools.html#recipes
# Would also be part of `pip install more-itertools` for python 3
def grouper(iterable, n, fillvalue=None):
    """Collect data into fixed-length chunks or blocks"""
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return zip_longest(fillvalue=fillvalue, *args)


# For legacy support redirecting every url which has "something" after lbom
@BommanagerApp.path("{lbom_oid}/{something}", absorb=True)
class BommanagerLegacyModel(object):
    VALID_PATH_KEYS = {
        "rbom", "variability_model", "product", "variant", "signature", "site", "site2"
    }

    def __init__(self, lbom_oid, something, absorb):
        self.lbom_oid = lbom_oid

        self.path_elements = [something]
        self.path_elements.extend(absorb.split("/"))

    def get_redirect_url(self):
        # If last entry has no value pair partner in list it will receive value None
        path_pairs = dict(grouper(self.path_elements, 2))

        for each_key in path_pairs.keys():
            if each_key not in BommanagerLegacyModel.VALID_PATH_KEYS:
                raise exc.HTTPNotFound()

        return make_bommanager_url(self.lbom_oid, path_pairs)


@BommanagerApp.view(model=BommanagerLegacyModel)
def legacy_redirect(model, _):
    return morepath.redirect(model.get_redirect_url())
