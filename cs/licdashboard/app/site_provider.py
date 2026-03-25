# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Implementation of specific site providers
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import six

from cdb import util
from cdb.objects.org import Organization, Person

# Exported objects
__all__ = []


class SiteProviderBase(object):
    """
    The base class for all site providers that can be used with the
    license dashboard.
    """

    _UNKNOWN_SITE_ID = -42424
    _UNKNOWN_SITE_NAME = None

    def __init__(self, persnos):
        """
        Init the provider. `persnos` is a list of personal numbers.
        The code will call `get_site_id_by_person` only for this
        persons.
        """
        self.persnos = persnos
        self.unknown_sites = False

    @classmethod
    def get_unknown_site_name(cls):
        """
        Returns the name of the unknown site.
        """
        if cls._UNKNOWN_SITE_NAME is None:
            cls._UNKNOWN_SITE_NAME = util.get_label("web.licdashboard.unknown_site")
            if not cls._UNKNOWN_SITE_NAME:
                cls._UNKNOWN_SITE_NAME = "Unknown"
        return cls._UNKNOWN_SITE_NAME

    @classmethod
    def get_unknown_site_id(cls):
        """
        Returns the id of the unknown site.
        """
        return cls._UNKNOWN_SITE_ID

    def _get_site(self, site_id):
        """
        Overwrite this function to provide your own implementation of
        `get_site`. The site object returned should have a
        `__getitem__` implementation to access the sites attributes`.
        These are at least ``site_id``, ``name`` and ``region``. You might
        add additional attributes to dislay them in the license token table.
        """
        return None

    def _get_site_by_person(self, persno):
        """
        Overwrite this function to provide your own implementation of
        `get_site_by_person`.
        """
        return None

    def has_unknown_sites(self):
        """
        Returns ``True`` if there has been a call that fails to
        retrieve a site in the past.
        """
        return self.unknown_sites

    def get_site(self, site_id):
        """
        Retrieve the site for the given id or ``None`` if
        there is no such site.
        """
        result = self._get_site(site_id)
        if result is None:
            self.unknown_sites = True
        return result

    def get_site_by_person(self, persno):
        """
        Retrieve the site assigned to the person
        or ``None`` if there is no such site.
        """
        result = self._get_site_by_person(persno)
        if result is None:
            self.unknown_sites = True
        return result

    def get_site_id_by_person(self, persno):
        """
        Retrieve the site_id configured for the person or
        `get_unknown_site_id` if no site is configured.
        You have to overwrite this function in your custom provider.
        """
        site = self.get_site_by_person(persno)
        if site:
            return site["site_id"]
        else:
            return self.get_unknown_site_id()

    def get_sites(self):
        """
        Return an iterable of all sites.
        You have to overwrite this function in your custom provider.
        """
        return []

    def is_available(self):
        """
        Returns ``True`` if the provider can be used. The
        base class returns ``True``. If you need additional checks
        you have to overwrite this function.
        """
        return True

    @classmethod
    def get_unknown_site(cls):
        """
        Returns the unknown site that is used if no site can
        be calculated for an user.
        """
        return {
            "site_id": cls.get_unknown_site_id(),
            "name": cls.get_unknown_site_name(),
            "region": "",
        }


class OrganizationSiteProvider(SiteProviderBase):
    """
    This provider uses the organization assignment of an user
    as a site.
    """

    def __init__(self, persnos):
        super(OrganizationSiteProvider, self).__init__(persnos)
        self.person2org = None
        self.orgs = None

    def _init_orgs(self):
        """
        Initializes `self.orgs` if not yet done.
        """
        if self.orgs is not None:
            return
        self._init_person2org()
        orgs = Organization.Query(
            Organization.org_id.one_of(*list(six.itervalues(self.person2org)))
        )
        self.orgs = {
            org.org_id: {"site_id": org.org_id, "name": org.name, "region": org.country}
            for org in orgs
        }

    def _init_person2org(self):
        """
        Initializes `self.person2site` if not yet done.
        """
        if self.person2org is not None:
            return
        persons = Person.Query(
            Person.personalnummer.one_of(*self.persnos),
            columns=["personalnummer", "org_id"],
        )
        self.person2org = {p.personalnummer: p.org_id for p in persons}

    def _get_site(self, site_id):
        self._init_orgs()
        return self.orgs.get(site_id, None)

    def _get_site_by_person(self, persno):
        """
        Retrieve the site assigned to the person
        or ``None`` if there is no such site.
        """
        self._init_person2org()
        return self.get_site(self.person2org.get(persno))

    def get_sites(self):
        self._init_orgs()
        return list(six.itervalues(self.orgs))


class LicenseSiteProvider(SiteProviderBase):
    """
    This provider uses the assignments to the license site class
    introduced with |elements_15_5|
    """

    def __init__(self, persnos):
        super(LicenseSiteProvider, self).__init__(persnos)
        self.person2site = None
        self.sites = None

    def _init_sites(self):
        """
        Initializes `self.orgs` if not yet done.
        """
        if self.sites is not None:
            return
        try:
            from cdb.fls import LicenseSite

            self._init_person2site()
            used = set(self.person2site.values())
            self.sites = {
                site.cdb_object_id: {
                    "site_id": site.cdb_object_id,
                    "name": site.name,
                    "region": site.license_region_id,
                }
                for site in LicenseSite.Query()
                if site.cdb_object_id in used
            }
        except ImportError:
            # No license reporting module ==> no site info
            self.sites = {}

    def _init_person2site(self):
        """
        Initializes `self.person2site` if not yet done.
        """
        if self.person2site is not None:
            return
        persons = Person.Query(
            Person.personalnummer.one_of(*self.persnos),
            columns=["personalnummer", "license_site_id"],
        )
        self.person2site = {p.personalnummer: p.license_site_id for p in persons}

    def _get_site(self, site_id):
        self._init_sites()
        return self.sites.get(site_id, None)

    def _get_site_by_person(self, persno):
        """
        Retrieve the site assigned to the person
        or ``None`` if there is no such site.
        """
        self._init_person2site()
        return self.get_site(self.person2site.get(persno))

    def get_sites(self):
        self._init_sites()
        return list(six.itervalues(self.sites))

    def is_available(self):
        """
        Returns ``True`` if the provider can be used. The
        base class returns ``True``. If you need additional checks
        you have to overwrite this function.
        """
        self._init_sites()
        if self.sites:
            return True
        return False


class PersonCitySiteProvider(SiteProviderBase):
    """
    This provider uses the city attribute of a person as the site.
    """

    def __init__(self, persnos):
        super(PersonCitySiteProvider, self).__init__(persnos)
        self.person2site = None
        self.sites = None

    def _init(self):
        """
        Initializes `self.orgs` if not yet done.
        """
        if self.person2site is not None:
            return
        persons = Person.Query(
            Person.personalnummer.one_of(*self.persnos),
            columns=["personalnummer", "city", "country"],
        )
        self.person2site = {p.personalnummer: p.city for p in persons}
        self.sites = {
            person.city: {
                "site_id": person.city,
                "name": person.city,
                "region": person.country,
            }
            for person in persons
            if person.city
        }

    def _get_site(self, site_id):
        self._init()
        return self.sites.get(site_id, None)

    def _get_site_by_person(self, persno):
        """
        Retrieve the site assigned to the person
        or ``None`` if there is no such site.
        """
        self._init()
        return self.get_site(self.person2site.get(persno))

    def get_sites(self):
        self._init()
        return list(six.itervalues(self.sites))


class TestProvider(SiteProviderBase):
    """
    Just vor testing purposes - maps each person to a person
    specific site.
    """

    def __init__(self, persnos):
        super(TestProvider, self).__init__(persnos)

    def _get_site(self, site_id):
        return {"site_id": site_id, "name": site_id, "region": ""}

    def _get_site_by_person(self, persno):
        """
        Retrieve the site assigned to the person
        or ``None`` if there is no such site.
        """
        return self.get_site(persno)

    def get_sites(self):
        return [self._get_site(pno) for pno in self.persnos]


# Guard importing as main module
if __name__ == "__main__":
    pass
