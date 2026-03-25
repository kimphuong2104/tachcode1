# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.platform.web import JsonAPI
from cs.platform.web import root

MOUNT_PATH = 'rqm-diff'


class DiffAPI(JsonAPI):
    pass


@root.Internal.mount(app=DiffAPI, path=MOUNT_PATH)
def _mount_api():
    return DiffAPI()
