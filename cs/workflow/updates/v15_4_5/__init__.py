#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
import pathlib

from cdb import CADDOK, cdbuuid, imex, sqlapi
from cdb.comparch import protocol

def export_data(name, control_lines):
    export_file = pathlib.Path(
        CADDOK.TMPDIR,
        "workflow15.4.5-%s-%s.exp"%(name,cdbuuid.create_uuid())
    )

    try:
        imex.export(
            ignore_errors=False,
            control_file=None,
            control_lines=control_lines,
            output_file=str(export_file),
        )
    except Exception as e:
        protocol.logError("Backup failed:\n\n %s \n\naborting"%(e))
        raise

    return export_file


class RemoveObsoleteTimes(object):
    """
    Removes the timestamps from every workflow-template 
    """    
    def run(self, is_template = 1):
        oldFields = [
            {
                "table": "cdbwf_process",
                "where": "is_template = %s"%(is_template),
                "fields": ["start_date", "deadline"],
            },
            {
                "table": "cdbwf_task", 
                "where": "cdb_process_id IN (SELECT cdb_process_id FROM cdbwf_process WHERE is_template = %s)"%(is_template),
                "fields": [
                    "start_date", 
                    "start_date_plan", 
                    "end_date_act", 
                    "deadline"
                    ]},
        ]

        export_file = export_data("predefined-fields", [
                "* FROM {}".format(old["table"])
                for old in oldFields
            ])

        protocol.logMessage("Exported the tables %s to %s" % (
                ", ".join([old["table"] for old in oldFields]),
                export_file
            ))
        for data in oldFields:
            for record in sqlapi.RecordSet2(data["table"], data["where"]):
                record.update(**{x: record[x] for x in data["fields"]})

pre = []
post = [RemoveObsoleteTimes]

if __name__ == "__main__":
    RemoveObsoleteTimes().run(is_template=0)
