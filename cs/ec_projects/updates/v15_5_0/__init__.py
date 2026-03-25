#!/usr/bin/env powerscript
# -*- python -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.comparch.updutils import TranslationCleaner


class RemoveLanguages(object):
    """
    Removes languages 'tr' and 'zh'.
    """

    def run(self):
        TranslationCleaner('cs.ec_projects', ['zh', 'tr']).run()


pre = [RemoveLanguages]
post = []
