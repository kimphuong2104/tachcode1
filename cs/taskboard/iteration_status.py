# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.classbody import classbody
from cdb.objects import State

# noinspection PyUnresolvedReferences
from cs.taskboard.objects import Iteration  # pylint: disable=unused-import


@classbody
class Iteration(object):

    class NEW(State):
        status = 0

    class EXECUTION(State):
        status = 50

    class COMPLETED(State):
        status = 200
