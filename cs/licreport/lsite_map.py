#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module cdblic.lsite_map

Mapping between users and license sites

The mapping has to be filled by the customer,
based on his local setup.

"""
import codecs
import json

from cdb import i18n, sqlapi

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ['SiteMapper']


class SiteMapper(object):

    def __init__(self, tables, event_mapper):
        # Anonymizer
        self._mapper = event_mapper
        self.tables = tables
        self.sites = {}
        self.site2region = {}
        self.user2site = {}
        self.user2persno = {}
        self.init_sites()
        self.init_user2site()

    def map_uname(self, uname):
        """Pseudonymize Login Name"""
        return self._mapper.get_id(u'user', uname)

    def have_regions(self):
        """Do we have multiple regions"""
        return len(self.site2region) > 1

    def init_sites(self):
        localized_name = i18n.colname(
            self.tables['cdbfls_license_site'],
            i18n.default(),
            'name_')
        default_name = i18n.colname(
            self.tables['cdbfls_license_site'],
            'en',
            'name_')
        extra_names = set((default_name, ))
        if localized_name:
            extra_names.add(localized_name)
        rs = sqlapi.RecordSet2(
            self.tables['cdbfls_license_site'],
            columns=['cdb_object_id', 'license_region_id'] + list(extra_names)
        )

        for site in rs:
            site_id = site['cdb_object_id']
            if localized_name:
                name = site[localized_name] if site[localized_name] else site[default_name]
            else:
                name = site[default_name]
            self.sites[site_id] = name
            region = site['license_region_id']
            if region:
                self.site2region[site_id] = region

    def init_user2site(self):
        rs = sqlapi.RecordSet2(
            self.tables['angestellter'],
            columns=["personalnummer", "license_site_id"])

        for row in rs:
            uname = self.map_uname(row['personalnummer'])
            self.user2site[uname] = row['license_site_id']

    def map_user(self, uname):
        """Get the site name, region and id for the given user.

           Returns 'Unknown' if nothing is known.
        """
        site_id = self.user2site.get(uname)
        if site_id is None or not site_id:
            return None, "Unknown", "Unknown"
        else:
            return (site_id,
                    self.sites.get(site_id, "Not found"),
                    self.site2region.get(site_id, "Unknown"))

    def get_persno(self, uname):
        # Get persno for username/login used
        persno = self.user2persno.get(uname)
        if persno is None:
            return "Unknown"
        else:
            return persno

    def site2name(self, site_id):
        return self.sites.get(site_id, u'Unknown')

    def region_sites(self, region):
        """The site names in a region"""
        return list(set(self.site2name(site_id)
                        for site_id, r in self.site2region.items()
                        if r == region))

    def dump(self, fd):
        """Dump the (anonymized) site map to the given fd"""
        d = {
            'sites': self.sites,
            'site2region': self.site2region,
            'user2site': self.user2site,
            'user2person': self.user2persno
        }
        json.dump(d, codecs.getwriter('utf-8')(fd), ensure_ascii=False)

    def load(self, fd):
        """Load the site map from the given fd"""

        d = json.load(fd)
        self.sites = d['sites']
        self.site2region = d['site2region']
        self.user2site = d['user2site']
        self.user2person = d['user2person']
