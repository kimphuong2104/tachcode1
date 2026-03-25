# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Command-line tool to print control statements for exporting a workflow template
(cdbwf_process) including its structure.

The export includes all objects required for it to run, such as tasks,
briefcases and constraints.

.. warning ::

    The export does _not_ include protocol entries, activities and referenced
    objects. For details, please see the administrator manual.

Usage:

  powerscript -m cs.workflow.updates.tools.export_process P00000000 > P00000000.ctl
  cdbexp -c P00000000.ctl -o P00000000.exp
  cdbimp P00000000.exp

"""

import sys
from cs.workflow.processes import Process

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


PID = "cdb_process_id='{cdb_process_id}'"
OID = "cdb_object_id='{cdb_object_id}'"
EXPORT = [
    # table, where
    # important: always put nested selects first
    # to support deletions by custom updates!

    ('cdbwf_process_pyrule_assign', PID),
    # Briefcase contents (missing content objects)
    ('cdbfolder_content', 'cdb_folder_id IN '
                          '(SELECT cdb_object_id FROM cdbwf_briefcase '
                          'WHERE {})'.format(PID)),
    ('cdbwf_briefcase', PID),
    ('cdbwf_briefcase_link', PID),
    ('cdbwf_form_template', 'cdb_object_id IN ( '
                            'SELECT form_template_id FROM cdbwf_form '
                            'WHERE {})'.format(PID)),
    ('cdbwf_form', PID),
    ('cdbwf_form_contents_txt', OID),
    ('cdbwf_constraint', PID),
    ('cdbwf_filter_parameter', PID),
    ('cdbwf_info_message', PID),
    # main nodes
    ('cdbwf_process', PID),
    ('cdbwf_task', PID),
]


def get_process_with_cycles(process):
    """
    Recursively finds all the sub-processes.
    The result contains the processes in order from leaves
    to the root.
    """

    cycles = []

    for cycle in process.Cycles:
        cycles.extend(
            get_process_with_cycles(cycle)
        )

    cycles.append(process)
    return cycles


def get_workflow_export_control(process_id):
    process = Process.ByKeys(process_id)

    if not process:
        raise ValueError("Process '{}' does not exist".format(process_id))

    all_processes = get_process_with_cycles(process)

    for proc in all_processes:
        values = dict(proc)

        for table, where in EXPORT:
            try:
                yield "* FROM {} WHERE {}".format(table, where.format(**values))
            except KeyError as k:
                raise AttributeError("Process '{}' has no attribute '{}'".format(
                    proc.cdb_process_id,
                    k.args[0]))


def print_workflow_export_control(process_id):
    for line in get_workflow_export_control(process_id):
        print(line)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    print_workflow_export_control(sys.argv[1])
