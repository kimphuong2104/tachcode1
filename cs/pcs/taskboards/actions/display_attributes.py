#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This class is used to design the cards. Methods of DisplayAttributes
are overwritten to display information about actions at the corresponding
position on the card.
"""

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cdb.classbody import classbody
from cs.actions.taskboards.display_attributes import (  # pylint: disable=unused-import
    ActionDisplayAttributes,
)

from cs.pcs.projects import Project


@classbody
class ActionDisplayAttributes:
    def get_header(self):
        """
        Get the project id and name in the header.
        """
        if self.task.cdb_project_id:
            project = Project.ByKeys(cdb_project_id=self.task.cdb_project_id)
            return f"{project.project_name}"
        return ""
