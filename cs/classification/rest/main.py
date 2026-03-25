#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.platform.web import JsonAPI
from cs.platform.web import root

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class ClassificationInternalApp(JsonAPI):  # only for internal stuff

    def __init__(self, *args, **kwargs):
        super(ClassificationInternalApp, self).__init__(*args, **kwargs)


@root.Internal.mount(app=ClassificationInternalApp, path="classification")  # only for internal stuff
def _mount_internal_app():
    return ClassificationInternalApp()


class ClassificationByIDApp(JsonAPI):

    def __init__(self, *args, **kwargs):
        super(ClassificationByIDApp, self).__init__(*args, **kwargs)


@ClassificationInternalApp.mount(app=ClassificationByIDApp, path='byid')
def _mount_byid():
    return ClassificationByIDApp()


class ClassificationInternalSearchApp(JsonAPI):  # only for cs.web fork remove in 15.2

    def __init__(self, *args, **kwargs):
        super(ClassificationInternalSearchApp, self).__init__(*args, **kwargs)


@root.Internal.mount(app=ClassificationInternalSearchApp, path='classification_search')
def _mount_search():
    return ClassificationInternalSearchApp()
