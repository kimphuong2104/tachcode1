#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import sqlapi


class AddHistoryACD(object):
    def run(self):  # pylint: disable=no-self-use
        if sqlapi.RecordSet2("cdb_auth_cl_cfg", "relation='aenderung'"):
            # The relation is already access controlled - do not add the
            # standard access system
            return
        from cdb.comparch.modules import Module
        from cdb.comparch.optional_content_installer import OptionalContentInstaller

        m = Module.ByKeys("cs.documents")
        installer = OptionalContentInstaller(m, ["AccessControl"])
        installer.install_obj(
            "cdb_acd", acd_id="cs.documents: All Document History Entries"
        )
        installer.install_obj(
            "cdb_auth_cl_cfg", relation="aenderung", auth_class="document_history_entry"
        )


class AddStatusProtocolACD(object):
    def run(self):  # pylint: disable=no-self-use
        if sqlapi.RecordSet2("cdb_auth_cl_cfg", "relation='cdb_z_statiprot'"):
            # The relation is already access controlled - do not add the
            # standard access system
            return

        from cdb.comparch.modules import Module
        from cdb.comparch.optional_content_installer import OptionalContentInstaller

        m = Module.ByKeys("cs.documents")
        installer = OptionalContentInstaller(m, ["AccessControl"])
        installer.install_obj(
            "cdb_acd", acd_id="cs.documents: All Document Statusprotocol Entries"
        )
        installer.install_obj(
            "cdb_auth_cl_cfg",
            relation="cdb_z_statiprot",
            auth_class="document_status_protocol",
        )


pre = []
post = [AddHistoryACD, AddStatusProtocolACD]
