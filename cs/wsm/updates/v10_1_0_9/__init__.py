#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

from cdb import sqlapi


class ChangeBomMethodNamesAfterRefactoring(object):
    def run(self):
        fqpynames = [
            (
                "cs.vp.bomcreator.wsmbomtools.ComponentStructureBOMReader",
                "cs.vp.bomcreator.componentstructurebomreader.ComponentStructureBOMReader",
            ),
            (
                "cs.vp.bomcreator.wsmbomtools.CADBomInfoReader",
                "cs.vp.bomcreator.cadbominforeader.CADBomInfoReader",
            ),
            (
                "cs.vp.bomcreator.wsmbomtools.CADBomInfoReaderWithReferences",
                "cs.vp.bomcreator.cadbominforeader.CADBomInfoReaderWithReferences",
            ),
            (
                "cs.vp.bomcreator.wsmbomtools.TakeReaderFromDocument",
                "cs.vp.bomcreator.takereaderfromdocument.TakeReaderFromDocument",
            ),
            (
                "cs.vp.bomcreator.wsmbomtools.RecursiveBOMReader",
                "cs.vp.bomcreator.componentstructurebomreader.RecursiveBOMReader",
            ),
        ]
        for old_name, new_name in fqpynames:
            sqlapi.SQLupdate(
                "bom_method set class_name = '%s' where class_name = '%s'"
                % (new_name, old_name)
            )


pre = []
post = [ChangeBomMethodNamesAfterRefactoring]
