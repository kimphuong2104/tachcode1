#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


class AddNewObjectRoleACD(object):

    def run(self):
        from cdb.comparch.optional_content_installer import OptionalContentInstaller
        from cdb.comparch.modules import Module

        m = Module.ByKeys("cs.workflow")
        installer = OptionalContentInstaller(m, ["AccessControl"])
        installer.install_obj("cdb_acd", acd_id='cdbwf: All Object Roles')
        installer.install_obj("cdb_auth_cl_cfg", relation='cdbwf_orole', auth_class='cdbwf')


pre = []
post = [AddNewObjectRoleACD]
