# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Module __init__

Install task for cs.office to disable CDB_Edit
and change the lock policy for office file types.
"""

from cdb import sqlapi
from cdb.comparch import protocol


class ChangeEditFlags(object):
    def run(self):  # pylint: disable=no-self-use
        # Update lockpolicy
        # and disable WSD_Edit in Web-UI
        office_file_types = [
            "MS-Excel",
            "MS-Excel:XLSB",
            "MS-Excel:XLSX",
            "MS-PowerPoint",
            "MS-PowerPoint:PPTM",
            "MS-PowerPoint:PPTX",
            "MS-Project",
            "MS-Visio",
            "MS-Visio:VSDX",
            "MS-Word",
            "MS-Word:DOCM",
            "MS-Word:DOCX",
        ]
        office_list = ", ".join(["'%s'" % sqlapi.quote(ft) for ft in office_file_types])
        sql = "cdb_filetype set ft_lock_policy=7 where ft_name in ({})".format(
            office_list
        )
        rows = sqlapi.SQLupdate(sql)
        protocol.logMessage("Lockmode update for {} office filetypes done".format(rows))

        # disabled CDB_Edit for document in WEB UI
        sql_edit = "cdb_operations set offer_in_web_ui=0 where name='CDB_Edit' and classname = 'document'"
        rows = sqlapi.SQLupdate(sql_edit)
        protocol.logMessage(
            "Classic edit operation in Web UI dectivated for document ({}).".format(rows)
        )


post = [ChangeEditFlags]
