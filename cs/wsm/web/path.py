#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Revision: "$Id$"
#

from .main import WorkspacesApp
from .model import WorkspacesModel


@WorkspacesApp.path(path="", model=WorkspacesModel)
def _workspaces_model():
    return WorkspacesModel()
