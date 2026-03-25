# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com


from cdb import sqlapi


class UpdateActualValuesStatusChangeFlag:
    def run(self):
        # update all projects, so that
        # the act_vals_status_chng flag is set to True
        sqlapi.SQLupdate("cdbpcs_project SET act_vals_status_chng = 1")


pre = []
post = [UpdateActualValuesStatusChangeFlag]
