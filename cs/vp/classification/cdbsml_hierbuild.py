#!/usr/bin/env powerscript
# -*- coding: iso-8859-1 -*-
# vim: set fileencoding=latin1 :
# -*- Python -*-
# $Id$
#
# Copyright (C) 1990 - 2003 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     smldecomp.py
# Author:   frank
# Creation: 15.09.04
# Purpose:

from cdb import ue
from cs.vp.classification import sml


def doit(ctx):
    # cdbsml_cg_hier aktualisieren
    sml.cgroup_hierarchy()
    sml.rebuild_smldecomp()


if __name__ == '__main__':
    ue.run(doit, "cdbscript")
