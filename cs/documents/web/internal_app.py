# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Base App for internal document JSON-APIs
"""


__docformat__ = "restructuredtext en"


from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal


class InternalDocApp(JsonAPI):
    pass


@Internal.mount(path="cs-documents", app=InternalDocApp)
def mount_to_internal():
    return InternalDocApp()


# Guard importing as main module
if __name__ == "__main__":
    pass
