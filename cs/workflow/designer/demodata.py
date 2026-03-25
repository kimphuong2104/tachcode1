#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module cs.workflow.designer.demodata
"""


def create_demo():
    from cs.workflow.designer.wfinterface import Process
    p = Process.CreateProcess()
    p.CreateTask(ttype="execution", title="T01")
    t2 = p.CreateTask(ttype="approval", title="T02")
    p.CreateTask(
        ttype="execution",
        title="T03",
        relative_position="parallel",
        other_task=t2)
    print("Created:", p.cdb_process_id)


def query_processes():
    from cs.workflow.designer.wfinterface import Process
    print("Found:", Process.Query().cdb_process_id)


def fix_copy_bug():
    # Fix the bug while copying process or saving process as template
    # for cs.workflow.git instance
    from cdb.platform.mom.relships import Relship
    relship = Relship.ByKeys("cdbwf_rp2doc")
    if relship:
        relship.Update(rs_profile="cdb_readonly_1_N")
    print("Done. Please restart cdb server process.")

if __name__ == "__main__":
    prompt = ("Choose one of:\n"
              "1. create a demo process\n"
              "2. query processes\n"
              "3. fix the bug while copying process\n")
    choice = input(prompt)
    if choice == "1":
        create_demo()
    elif choice == "2":
        query_processes()
    elif choice == "3":
        fix_copy_bug()
