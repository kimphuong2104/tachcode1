#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-
# $Id$
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import rte, sig
from cs.documents import Document


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def connect_effectivities():
    sig.connect(Document, "copy", "pre_mask")(reset_effectivity_dates)
    sig.connect(Document, "copy", "pre")(set_never_effective)
    sig.connect(Document, "create", "pre")(set_never_effective_if_unset)
    sig.connect(Document, "index", "pre")(set_never_effective)
    sig.connect(Document, "state_change", "post")(set_effectivity_dates_on_state_change)


def reset_effectivity_dates(self, ctx):
    self.reset_effectivity_dates(ctx)


def set_never_effective_if_unset(self, ctx):
    self.set_never_effective(ctx, keep_existing=True)


def set_never_effective(self, ctx):
    self.set_never_effective(ctx, keep_existing=False)


def set_effectivity_dates_on_state_change(self, ctx):
    self.set_effectivity_dates_on_state_change(ctx)
