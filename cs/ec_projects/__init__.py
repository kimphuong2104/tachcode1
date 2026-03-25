#!/usr/bin/env powerscript
# -*- python -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

from cdb.classbody import classbody

from cdb.objects import Reference_1

from cs.ec import EngineeringChange
from cs.pcs.projects import Project


@classbody
class EngineeringChange(object):

    Project = Reference_1(Project, EngineeringChange.cdb_project_id)
