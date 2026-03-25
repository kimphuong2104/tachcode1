#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from cdb import ddl
from cdb import util
from cdb import sqlapi
from cdb import imex
from cdb import transaction
from cdb.ddl import Table, Char
from cdb.comparch import protocol
from tempfile import gettempdir
import pathlib


class RemoveOldFields(object):

    def run(self):
        changes = [
            {
                "table":"cdbwf_form_contents_txt",
                "fields":["cdb_process_id","task_id","form_template_id"]
            },
            {
                "table":"cdbwf_form",
                "fields":["task_id"]
            }
        ]
        exportFile = str(pathlib.Path(
            gettempdir(),
            "upd-v15.4.3.8-workflow-forms.exp"))
        exported = False
        try:
            imex.export(
                ignore_errors = False,
                control_file = None,
                control_lines = [
                    "* FROM {}".format(changes[0]["table"]),
                    "* FROM {}".format(changes[1]["table"]),
                    ],
                output_file = exportFile,
            )
            protocol.logWarning(
                "Exported the tables {0}, {1} into {2}".format(
                    changes[0]["table"],
                    changes[1]["table"],
                    exportFile)
            )
            exported = True
        except Exception as e:
            protocol.logError(
                "The following error occured, while exporting tables" +
                str(e) +
                "aborting"
            )
            raise
        if exported:
            for change in changes:
                table = Table(change["table"])
                for field in change["fields"]:
                    if table.hasColumn(field):
                        table.dropAttributes(field)
                        protocol.logMessage(
                            "'{0}' dropped from {1}".format(field,change["table"])
                        )


pre = [RemoveOldFields]
post = []
