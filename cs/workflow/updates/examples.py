#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


import sys

from cdb import InstallScript

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

FILE = __file__


class WorkflowExamples(InstallScript.CDBCustomUpdateScript):
    """
    Example workflows
    """

    def __init__(self):
        InstallScript.CDBCustomUpdateScript.__init__(self, FILE, self.__doc__)
        self.process_ids = ["RELEASE_PART", "CHANGE_PART_LOOP", "RFQ", "VOTING_SIMPLE", "VOTING_ADVANCED"]
        self.rules = [
            "Parts (DRAFT)",
            "Parts (REVIEW)",
            "wf-designer: briefcase contains exactly 1 part (REVIEW)",
        ]
        self.users = ["external.simons.lisa", "external.busch.roman", "external.enver.julia", "external.moore.tim"]
        self.orgs = ["ONE", "TWO"]
        self.forms = ["form_quotation"]

    def get_export_ctrl(self):
        process = "cdb_process_id IN ('{}')".format(
            "', '".join(self.process_ids))
        rules = "IN ('{}')".format("', '".join(self.rules))
        users = "('{}')".format("', '".join(self.users))
        orgs = "org_id IN ('{}')".format("', '".join(self.orgs))
        forms = "('{}')".format("', '".join(self.forms))

        my_ctrl = [
            # workflows
            "* FROM cdbwf_process WHERE {}".format(process),
            "* FROM cdbwf_process_pyrule_assign WHERE {}".format(process),
            "* FROM cdbfolder_content WHERE cdb_folder_id IN "
            "(SELECT cdb_object_id FROM cdbwf_briefcase WHERE {})".format(
                process),
            "* FROM cdbwf_briefcase WHERE {}".format(process),
            "* FROM cdbwf_briefcase_link WHERE {}".format(process),
            "* FROM cdbwf_form WHERE {}".format(process),
            "* FROM cdbwf_form_contents_txt WHERE {}".format(process),
            "* FROM cdbwf_constraint WHERE {}".format(process),
            "* FROM cdbwf_task WHERE {}".format(process),
            "* FROM cdbwf_filter_parameter WHERE {}".format(process),
            # rules
            "* FROM cdbwf_pyrule WHERE cdb_pyrule {}".format(rules),
            "* FROM cdb_pyrule WHERE name {}".format(rules),
            "* FROM cdb_pypredicate WHERE name {}".format(rules),
            "* FROM cdb_pyterm WHERE name {}".format(rules),
            # users and organizations
            "* FROM angestellter WHERE personalnummer IN {}".format(users),
            "* FROM cdb_global_subj WHERE subject_type='Person' "
            "AND subject_id IN {}".format(users),
            "* FROM cdb_org WHERE {}".format(orgs),
            # form templates
            "* FROM maskenzuordnung WHERE name IN {}".format(forms),
            "* FROM masken WHERE name IN {}".format(forms),
            "* FROM cdbwf_form_template WHERE mask_name IN {}".format(forms),
            # other briefcase contents?
        ]
        return my_ctrl

    def get_export_ctrl_files(self):
        users = "personalnummer IN ('{}')".format("', '".join(self.users))
        return ["angestellter WHERE {}".format(users)]


if __name__ == "__main__":
    sys.argv = [arg.decode("utf-8") for arg in sys.argv]
    InstallScript.run(sys.argv, WorkflowExamples())
