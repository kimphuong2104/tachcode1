#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

from cs.platform.web import JsonAPI, root


class WorkspacesApp(JsonAPI):
    pass


@root.Internal.mount(app=WorkspacesApp, path="workspaces")
def _mount_app():
    return WorkspacesApp()
