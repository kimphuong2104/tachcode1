# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Things implemented in cs.web for cs.platform.org
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []

from cdb.objects import org


def _get_phone_nr(nr, remark):
    result = ""
    if nr:
        result = nr
        if remark:
            result += " (%s)" % remark
    return result

def CalculatePersonPhoneNumbers(hook):
    """
    ::PRE_DISPLAY::-Hook for persons
    """
    values = hook.get_new_values()
    persno = values.get("angestellter.personalnummer")
    if persno:
        p = org.Person.ByKeys(persno)
        for attr, nr, t in [("phone_1", "telefon1", "mapped_phonetype1"),
                            ("phone_2", "telefon2", "mapped_phonetype2")]:
            hook.set(attr,
                     _get_phone_nr(getattr(p, nr), getattr(p, t)))


def CalculateOrganizationDetailAttrs(hook):
    """
    ::PRE_DISPLAY::-Hook for organization
    """
    values = hook.get_new_values()
    org_id = values.get("cdb_org.org_id")
    if org_id:
        o = org.Organization.ByKeys(org_id)
        hook.set("phone",
                 _get_phone_nr(getattr(o, "tel1"),
                               getattr(o, "mapped_phonetype1")))
        the_zip = getattr(o, "zip")
        city = getattr(o, "city")
        zip_and_city = ""
        if (city):
            if the_zip:
                zip_and_city = "%s %s" % (the_zip, city)
            else:
                zip_and_city = city
            hook.set("zip_and_city", zip_and_city)
