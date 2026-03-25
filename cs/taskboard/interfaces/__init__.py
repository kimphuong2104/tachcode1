#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Common interface of |cs.taskboard|
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cs.taskboard.interfaces.board_adapter import BoardAdapter
from cs.taskboard.interfaces.register import REGISTER_BOARD_ADAPTER
from cs.taskboard.interfaces.row_mapper import RowMapper
from cs.taskboard.interfaces.column_mapper import ColumnMapper
from cs.taskboard.interfaces.context_adapter import ContextAdapter
from cs.taskboard.interfaces.display_attributes import DisplayAttributes
from cs.taskboard.interfaces.card_adapter import CardAdapter
