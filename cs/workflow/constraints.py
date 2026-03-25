#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module constraints

This is the documentation for the constraints module.
"""

import logging

from cdb import ue
from cdb import util
from cdb.objects import Forward
from cdb.objects import Object
from cdb.objects import Reference_1

from cs.workflow.protocols import MSGCANCEL
from cs.workflow.pyrules import WithRuleWrapper

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ['Constraint']

fConstraint = Forward(__name__ + ".Constraint")
fBriefcase = Forward("cs.workflow.briefcases.Briefcase")
fRule = Forward("cdb.objects.Rule")
fRuleWrapper = Forward("cs.workflow.pyrules.RuleWrapper")

RULE_CATEGORY = "Task constraint"


class Constraint(Object, WithRuleWrapper):
    __maps_to__ = "cdbwf_constraint"
    __classname__ = "cdbwf_constraint"

    def _get_rule_object_id(self):
        return self.rule_name

    Briefcase = Reference_1(
        fBriefcase,
        fBriefcase.cdb_process_id == fConstraint.cdb_process_id,
        fBriefcase.briefcase_id == fConstraint.briefcase_id
    )

    def get_message_constraint_violated(self, parent):
        """If the constraint is directly linked to a briefcase of the parent, then the violation is
        always because of the briefcase content. Thus the briefcase is mentioned in the error
        message instead of the process or process component.

        :param parent: Process or process component
        :type parent: Object

        :returns: str -- "Constraint violated (object='%s', rule='%s')"

        """
        if self.Briefcase:
            parent = self.Briefcase
        return util.get_label("cdbwf_constraint_violated") % (
            parent.GetDescription(),
            self.getRuleName() or ""
        )

    def is_violated(self, parent):
        """If the constraint is directly linked to a briefcase of the parent, then it is only
        checked on the briefcase, else it is only checked on the process or process component
        itself.

        :param parent: Process or process component
        :type parent: Object

        :returns: Bool

        """
        if not self.Rule:
            logging.error("constraint has no rule: %s", self.GetDescription())
            return True

        if self.Briefcase:
            obj = self.Briefcase
        else:
            obj = parent
        if not self.invert_rule:
            return not self.Rule.match(obj)
        else:
            return self.Rule.match(obj)

    def check_violation(self, parent):
        """Displays an error message and adds it to the protocol, if the constraint is violated.

        :param parent: Process or process component
        :type parent: Object

        :returns: None

        :raises: ue.Exception

        """
        if self.is_violated(parent):
            err_msg = self.get_message_constraint_violated(parent)
            parent.addProtocol(err_msg, MSGCANCEL)
            raise ue.Exception(1024, err_msg)
