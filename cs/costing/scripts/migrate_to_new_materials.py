# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import logging
from cdb import sqlapi

LOG = logging.getLogger(__name__)


class MigrateToNewMaterials(object):
    @staticmethod
    def updateComponents():
        """Updates the cdbpco_component table so that parts refer to the new material records."""

        sqlapi.SQL("""UPDATE cdbpco_component
                      SET material_object_id=(SELECT cdb_object_id
                                              FROM csmat_material
                                              WHERE short_name=werkstoff_nr)
                      WHERE werkstoff_nr IS NOT NULL OR werkstoff_nr <> ''""")

    @staticmethod
    def updateParameterValues():
        """Updates the cdbpco_para_val table so that parts refer to the new material records."""

        sqlapi.SQL("""UPDATE cdbpco_para_val
                          SET material_object_id=(SELECT cdb_object_id
                                                  FROM csmat_material
                                                  WHERE short_name=werkstoff_nr)
                          WHERE werkstoff_nr IS NOT NULL OR werkstoff_nr <> ''""")

    @staticmethod
    def run():
        MigrateToNewMaterials.updateComponents()
        MigrateToNewMaterials.updateParameterValues()


if __name__ == "__main__":
    MigrateToNewMaterials.run()
