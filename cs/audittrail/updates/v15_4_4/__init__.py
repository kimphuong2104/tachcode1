# coding: utf-8
from __future__ import absolute_import
import json
from cdb import sqlapi


class RemoveAuditTrailViewSetting(object):
    def run(self):
        sqlapi.SQLdelete("FROM cdb_setting "
                         "WHERE cdb_module_id = 'cs.audittrail' "
                         "AND setting_id = 'cs.webcomponents.table' "
                         "AND setting_id2 = 'cdb_audittrail_view@cdb_audittrail_view'")
        sqlapi.SQLdelete("FROM cdb_usr_setting "
                         "WHERE setting_id = 'cs.webcomponents.table' "
                         "AND setting_id2 = 'cdb_audittrail_view@cdb_audittrail_view'")
        sqlapi.SQLdelete("FROM cdb_setting_long_txt "
                         "WHERE setting_id = 'cs.webcomponents.table' "
                         "AND setting_id2 = 'cdb_audittrail_view@cdb_audittrail_view'")
        sqlapi.SQLdelete("FROM cdb_usr_setting_long_txt "
                         "WHERE setting_id = 'cs.webcomponents.table' "
                         "AND setting_id2 = 'cdb_audittrail_view@cdb_audittrail_view'")


pre = []
post = [RemoveAuditTrailViewSetting]
