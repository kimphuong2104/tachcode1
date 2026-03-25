# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cdb import sig
from cdb.objects import Object

from cs.objectdashboard.dashboard import GET_REFERENCE_CLASSNAMES


class NotesContent(Object):
    """
    Manages content for the Project Notes Widgets.
    """

    __classname__ = __maps_to__ = "cdbpcs_notes_content"


@sig.connect(GET_REFERENCE_CLASSNAMES)
def register_class_def():
    "Register class definition"
    return NotesContent
