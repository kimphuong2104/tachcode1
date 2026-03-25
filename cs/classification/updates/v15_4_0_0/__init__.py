# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi
from cdb.comparch.updutils import TranslationCleaner
from cdb.platform import PropertyDescription
from cdb.platform import PropertyValue


class RemoveLanguages(object):
    """
    Removes languages 'tr' and 'zh'.
    """

    def run(self):
        TranslationCleaner('cs.classification', ['zh', 'tr']).run()


class UpdateAllPropertiesFolder(object):

    def run(self):
        sqlapi.SQLupdate(
            """
            cs_property_folder SET name_de = 'Alle', name_en = 'All' 
            WHERE cdb_object_id='bd6c0540-dc7b-11e6-8c8d-28d24433bf35'
            """
        )


class UpdateSystemProperties(object):
    """
    Updates the system properties to make sure that the new property "iecp" exists.
    """

    def create_prop(self, attr, value, helptext):
        prop = PropertyDescription.ByKeys(attr)
        if not prop:
            PropertyDescription.Create(
                attr=attr, helptext=helptext, cdb_module_id="cs.classification"
            )
            PropertyValue.Create(
                attr=attr,
                value=value,
                subject_type="Common Role",
                subject_id="public",
                cdb_module_id="cs.classification"
            )

    def run(self):
        self.create_prop("iecp", "0", "Initial view of pictures assigned to a class (0=collapsed, 1=expanded)")


class UpdatePhysicalUnits(object):
    """
    Updates the physical units catalog to reflect the removal of the definition for Nm and density from the
    python code.
    """

    def run(self):
        sqlapi.SQLupdate(
            """
            cs_unit SET symbol_label_de='Nm', symbol_label_en='Nm', symbol='N*m'
            WHERE cdb_object_id='24a7fe84-d607-11e9-a9c1-5c514f5488ea'
            """
        )
        sqlapi.SQLupdate(
            """
            cs_unit SET name_de='Kilogramm / Kubikmeter', name_en='Kilogram / Cubic Meter', symbol='kg/m³'
            WHERE cdb_object_id='acb2874d-989c-11ec-b234-d0abd596f9e6'
            """
        )


pre = []
post = [RemoveLanguages, UpdateAllPropertiesFolder, UpdateSystemProperties, UpdatePhysicalUnits]
