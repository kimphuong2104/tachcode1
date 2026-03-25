# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com
#

import logging
import collections
from cdb import util
from cdb import tools
from cs.vp.bom.web.utils import get_fallback_site

LOG = logging.getLogger(__name__)

class SiteFilterPurpose(object):
    LOAD_TREE_DATA = 0
    LOAD_DIFF_TABLE_DATA = 1
    FIND_DIFFERENCE = 2
    SEARCH = 3
    SYNC_VIEW = 4


class OtherSiteTransparencyBehavior(object):
    DISPLAY_NORMAL = 0
    DISPLAY_BOM_GREYED = 1
    DISPLAY_ITEM_GREYED = 2


class StandardSiteFilter(object):

    @classmethod
    def site_bom_filter(cls, flat_bom, selected_sites=None, purpose=None):
        if not selected_sites:
            return flat_bom

        result = []
        for comp in flat_bom:
            in_site = not comp.site_object_id or comp.site_object_id in selected_sites
            comp._from_other_site = not in_site
            result.append(comp)
        return result

    @classmethod
    def get_other_site_transparency_behavior(cls):
        return OtherSiteTransparencyBehavior.DISPLAY_BOM_GREYED


class MatchSelectedSitesFilter(object):

    @classmethod
    def site_bom_filter(cls, flat_bom, selected_sites=None, purpose=None):
        # This filter removes positions that don't belong to a selected site.
        # If bom components have the same position number, but different sites,
        # these components are considered as alternatives. If no alternative matches exactly to a selected site,
        # the fallback site is kept, if exists.
        # This filtering logic is only applied for diff calculation, searching and internal xBOM Manager functions.
        # For loading of the displayed tree data (SiteFilterPurpose.LOAD_TREE_DATA) nothing is filtered out.
        # Nodes are greyed out in the frontend instead.

        if not selected_sites:
            return flat_bom

        fallback_site = get_fallback_site()

        def is_fallback_site(c):
            site_object_id = c.site_object_id if c.site_object_id else ""
            return site_object_id == fallback_site or site_object_id == ""

        flat_bom_dict = collections.defaultdict(list)
        for comp in flat_bom:
            flat_bom_dict[(comp.baugruppe, comp.b_index, comp.position)].append(comp)

        result = []
        for comp in flat_bom:
            siblings = flat_bom_dict[(comp.baugruppe, comp.b_index, comp.position)]

            site_oids = [
                sibling.site_object_id or ''  # replace None with ''
                for sibling in siblings
            ]

            in_site = False
            if comp.site_object_id in selected_sites:
                # the position matches a selected site
                in_site = True
            elif is_fallback_site(comp) and not any(site_object_id in site_oids for site_object_id in selected_sites):
                # the position belongs to a fallback site and no other position matches a selected site
                in_site = True

            if purpose == SiteFilterPurpose.LOAD_TREE_DATA:
                comp._from_other_site = not in_site
                result.append(comp)
            else:
                if in_site is True:
                    comp._from_other_site = False
                    result.append(comp)
        return result

    @classmethod
    def get_other_site_transparency_behavior(cls):
        return OtherSiteTransparencyBehavior.DISPLAY_ITEM_GREYED


_filter_class = None


def get_site_bom_filter_class():
    global _filter_class
    if _filter_class is None:
        prop_val = util.get_prop("bmsf")  # bom manager site filter
        if prop_val:
            try:
                _filter_class = tools.getObjectByName(prop_val)
            except ImportError:
                LOG.error("Invalid site bom filter defined by property 'bmsf': %s" % prop_val)
                raise
        else:
            _filter_class = StandardSiteFilter
        LOG.info("Using site bom filter: %s" % _filter_class)
    return _filter_class


def site_bom_filter(flat_bom, selected_sites=None, purpose=None):
    return get_site_bom_filter_class().site_bom_filter(flat_bom, selected_sites=selected_sites, purpose=purpose)
