# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com


from cdb import ddl, sqlapi

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class UpdatePartsAttributes:
    """
    Update the attributes field teilenummer, t_index in class cdb_action
    based on the already existing values of part_object_id
    """

    def run(self):
        t = ddl.Table("teile_stamm")
        if t.exists():
            sqlapi.SQLupdate(
                "cdb_action SET "
                "teilenummer=(SELECT teile_stamm.teilenummer FROM teile_stamm "
                "WHERE teile_stamm.cdb_object_id = cdb_action.part_object_id), "
                "t_index=(SELECT teile_stamm.t_index FROM teile_stamm "
                "WHERE teile_stamm.cdb_object_id = cdb_action.part_object_id) "
                "WHERE cdb_action.teilenummer IS NULL "
                "AND cdb_action.part_object_id IS NOT NULL "
                "AND cdb_action.part_object_id <> ''"
            )


pre = []
post = [UpdatePartsAttributes]
