# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import sqlapi


class UpdateTimeUnits(object):
    """
    Until now the time unit attributes ``cswp_task.time_unit_setup_time`` and ``cswp_task.time_unit_machine_time``
    contained the default value `Minute` and if changed by the user, the label of the selected unit as defined by
    ``cs_unit.symbol_label_<iso_lang>``.
    With service level 1 these attributes contain the language neutral unit symbol as defined by ``cs_unit.symbol``.
    Existing data is migrated by the update task ``UpdateTimeUnits`` automatically.
    """

    def _fix_units(self, attr_name):
        rset = sqlapi.RecordSet2(sql="select count(*) c from cswp_task where %s not in (select symbol from cs_unit)" %
                                     attr_name)
        if rset[0].c > 0:
            sqlapi.SQLupdate("cswp_task set %s = 'minute' where %s = 'Minute'" % (attr_name, attr_name))

            sqlapi.SQLupdate("cswp_task set %s = (select symbol from cs_unit where "
                             "symbol_label_de = cswp_task.%s) "
                             "where %s in (select symbol_label_de from cs_unit)" % (attr_name, attr_name, attr_name))

            sqlapi.SQLupdate("cswp_task set %s = (select symbol from cs_unit where "
                             "symbol_label_en = cswp_task.%s) "
                             "where %s in (select symbol_label_en from cs_unit)" % (attr_name, attr_name, attr_name))

    def run(self):
        self._fix_units("time_unit_setup_time")
        self._fix_units("time_unit_machine_time")

pre = []
post = [UpdateTimeUnits]
