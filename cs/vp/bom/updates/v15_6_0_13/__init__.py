# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import sqlapi


class SetTypeObjectIdDefault(object):
    """
    Sets `type_object_id` to an empty string where it is set to NULL
    """
    def run(self):
        sqlapi.SQLupdate("teile_stamm set type_object_id='' where type_object_id is NULL")


pre = []
post = [SetTypeObjectIdDefault]


if __name__ == "__main__":
    SetTypeObjectIdDefault().run()
