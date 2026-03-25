#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

import morepath
from cs.vp.bomcreator.main import BomcreatorApp


class App(morepath.App):
  pass


@BomcreatorApp.mount(app=App, path='/internal')
def _mount_app():
  return App()