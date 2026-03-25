# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com


from cdb import util
from cdb.objects import org


fallback_site = None

def get_fallback_site():
    global fallback_site
    if fallback_site is None:
        fallback_org_id = util.get_prop("forg")
        if fallback_org_id is not None and fallback_org_id != "":
            fallback_org = org.Organization.ByKeys(org_id=fallback_org_id)
            if fallback_org is not None:
                fallback_site = fallback_org.cdb_object_id
            else:
                raise RuntimeError("Invalid org_id %s in property forg" % fallback_org_id)
        else:
            fallback_site = ""

    return fallback_site
