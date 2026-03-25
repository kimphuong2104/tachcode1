#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module cdblic.generic_metrics

Generic Metrics for inclusion into the license report

Gathers some generic metrics from the system, to
get an approximation of the system size.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import logging

from cdb import sqlapi

# Exported objects
__all__ = [
    "MetricGatherer",
    "CollectorError",
]


class CollectorError(Exception):
    pass


class MetricGatherer(object):
    """
    Gather some specific metric from the system.
    """

    name = 'AbstractMetrics'
    versions = (
        '9.8', '9.9.0', '10.0', '10.1',
        '15.0', '15.1', '15.2', '15.3', '15.4')

    def __init__(self, version):
        """ Initialize for the given system version
        """
        self.log = logging.getLogger('cdblic.metrics.%s' % self.name)
        self.target_version = version.replace('.', '_')

    def collect(self, target_dict):
        """ Gather data and put it include it into the target_dict
        """
        versioned_collector = '_collect_%s' % self.target_version
        try:
            collector = getattr(self, versioned_collector)
            self.log.debug("Using versioned collector for %s", self.target_version)
        except AttributeError:
            self.log.debug("No versioned collector, using generic collector")
            collector = self._collect_generic

        if callable(collector):
            return collector(target_dict)
        else:
            self.log.error("Collector %s isn't a callable", repr(collector))
            raise CollectorError("Collector function isn't callable")


class UserStatisticsGatherer(MetricGatherer):
    """
    Gather user specific system data

    - Number of registered users
    - LDAP setup present and using 'sync'
      (to see if dynamic user registration is in use)
    - Number of active users (e.g. active=1)

    """

    name = "UserMetrics"

    def __init__(self, version):
        super(UserStatisticsGatherer, self).__init__(version)
        from cdb.objects.org import User
        self.userclass = User

    def _collect_generic(self, target_dict):
        d = {
            'registered_users': self.get_registered_user_count(),
            'active_users': self.get_active_user_count(),
            'has_dynamic_creation': self.has_dynamic_user_creation(),
        }
        for k, v in d.items():
            key = '%s.%s' % (self.name, k)
            target_dict[key] = v

    def get_registered_user_count(self):
        return len(self.userclass.Query())

    def get_active_user_count(self):
        return len(self.userclass.KeywordQuery(active_account='1'))

    def has_dynamic_user_creation(self):
        """ Check if users could be created automagically
            (e.g. via LDAP)

            returns:
            yes if ldap is configured and a server has it
            no  if it isn't configured
            maybe if ldap is configured or server setup
        """
        self.log.debug("Checking for ldap usesyncrules configuration")
        # 1. have an ldap configuration with sync = 1
        try:
            sql = """SELECT usesyncrules FROM cdb_ldap_conf WHERE default_connection = 1"""
            rs = sqlapi.RecordSet2(sql=sql)
        except RuntimeError:
            have_ldap_conf = False
        else:
            for row in rs:
                if row.usesyncrules == 1:
                    have_ldap_conf = True
                    break
            else:
                have_ldap_conf = False

        self.log.debug("Checking for ldap or SSO service configuration")
        # 2. have a service configured with ldap/sso
        # this is version specific

        # TODO: 15.1 version to detect LDAP sync
        have_ldap_svc = False

        if have_ldap_conf and have_ldap_svc:
            return "yes"
        elif have_ldap_conf or have_ldap_svc:
            return "maybe"
        else:
            return "no"


# Guard importing as main module
if __name__ == "__main__":
    d = {}
    import pprint

    from cdb import version
    ug = UserStatisticsGatherer(version.verstring(0))
    ug.collect(d)
    pprint.pprint(d)
