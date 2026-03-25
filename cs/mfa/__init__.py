#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals, print_function

"""
Multi Factor Authentication Module

Contains basic infrastructure for multi factor authentication plugins.
"""

import io
import json
import logging
import os

from cdb import fls
from cdb import rte
from cdb import tools
from cdb.authentication.iauthenticator import IAuthenticator, AuthPlugin
from cdb.tools import load_callable

from cs.mfa import exc
from cs.mfa.classes import MFAPluginSettings


LOG = logging.getLogger(__name__)


class MFAAuthenticator(IAuthenticator):
    """
        Class to be used as base class for multi factor authentication (mfa) plugins

        Load and set automatically the underlying/following authentication plugin.
    """

    #: Configuration items for the Login UI
    MFA_CONF = {
        # Label to show above the mfa entry field
        'mfa_label': 'cs_mfa_login_mfacode_label',
        # Icon to show
        'mfa_icon': '/static/images/Password-White.png',
        # Placeholder text inside the mfa entry field
        'mfa_placeholder': 'cs_mfa_login_mfacode_label',
    }

    #: Path for the configuration file
    MFA_CONF_PATH = os.path.join(rte.environ['CADDOK_BASE'], 'etcd', 'mfa.json')

    def __init__(self, mfa_plugin_name, *args, **kwargs):
        self.plugin_name = mfa_plugin_name

        # Setup license
        self._lic_errors = []
        try:
            fls.allocate_server_license('MFA_001')
            self._lic = True
        except fls.LicenseError as e:
            LOG.exception("Failed to allocate license")
            self._lic = False
            self._lic_errors.append(e)

        self.auth_plugin_successor = self.init_successor_plugin()

        self.write_mfa_conf()

    def find_successor(self):
        """
        Find the successor plugin configuration

        :returns: An :py:class:`AuthPlugin` configuration.
        """
        setting = MFAPluginSettings.ByKeys(auth_plugin_name=self.plugin_name)
        if setting is None or not setting.CheckAccess('read'):
            raise exc.ConfigAccessError()
        plugin_conf = AuthPlugin.ByKeys(name=setting.auth_plugin_successor_name)
        if plugin_conf is None:
            raise exc.ConfigAccessError("Auth plugin not found")
        return plugin_conf

    def init_successor_plugin(self):
        """Load and initialize the successor plugin

           :param plugin_conf: A :py:class:`AuthPlugin` configuration.
           :returns: Tuple of plugin instance and callback.
        """
        plugin_conf = self.find_successor()
        if plugin_conf is None:
            raise exc.MFAException("No successor plugin configured",
                                   self.plugin_name)
        plugin_class = tools.getObjectByName(plugin_conf.fqpyname)
        return plugin_class()

    def get_mfa_conf(self):
        """
        Override this method to specify the mfa plugin configuration values
        :return: A dictionary containing at least the keys 'mfa_label', 'mfa_icon' and 'mfa_placeholder'
        """
        return self.MFA_CONF

    def write_mfa_conf(self):
        """
        Writes the mfa plugin configuration to $(CADDOK_BASE)/etcd/mfa.json
        so that the system login dialog can use its information.
        """
        mfa_path = self.MFA_CONF_PATH
        mfa_conf = {
            self.plugin_name: self.get_mfa_conf()
        }
        LOG.info("Writing mfa.json to path '%s'", mfa_path)
        with io.open(mfa_path, 'w+') as fd:
            json.dump(mfa_conf, fd)

    def can_change_password(self):
        """
        Forward the change password decision to the successor plugin
        """
        return self.auth_plugin_successor.can_change_password()

    def change_password(self, user, old_password, new_password, language):
        """
        Forward the password change to the successor plugin
        """
        LOG.info('change_password for user %s', user)
        return self.auth_plugin_successor.change_password(
            user, old_password, new_password, language)

    def get_user_info(self, username, language):
        """
        Forward the user info call to the successor plugin
        """
        LOG.debug('get_user_info %s', username)
        return self.auth_plugin_successor.get_user_info(username, language)
