#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.projects import Project


class CalculateCriticalPathValues:
    """
    Calls recalculate method on filtered projects to calculate the
    critical path values.
    """

    def run(self):
        # discard the templates, msp scheduled,
        # completed (200), discarded (180) and frozen (60) projects
        projects = Project.Query(
            "template=0 AND msp_active=0 AND status NOT IN (60, 180, 200)"
        )
        for project in projects:
            project.recalculate()
        print(f"Critical path attributes calculated for {len(projects)} project(s).")


if __name__ == "__main__":
    CalculateCriticalPathValues().run()
