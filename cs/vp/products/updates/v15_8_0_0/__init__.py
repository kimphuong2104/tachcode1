# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.comparch.updutils import TranslationCleaner


class RemoveLanguages(object):
    """
    Removes languages 'tr' and 'zh'.
    """

    def run(self):
        TranslationCleaner('cs.vp.products', ['zh', 'tr']).run()


pre = []
post = [RemoveLanguages]
