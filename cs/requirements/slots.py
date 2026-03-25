# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals
import logging
from cdb import sig
from cs.classification import ClassificationConstants
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue

LOG = logging.getLogger(__name__)


@sig.connect(RQMSpecObject, list, "req_item_set_position", "pre_mask")
def preset_req_item_position_data(requirements, ctx):
    if not ctx.uses_webui:  # workaround for E064206
        ctx.skip_dialog()
    RQMSpecObject._req_item_set_position_pre_mask(ctx)


@sig.connect(RQMSpecObject, list, "req_item_set_position", "now")
def req_item_set_position_now(requirements, ctx):
    RQMSpecObject._req_item_set_position_now(ctx)


@sig.connect(TargetValue, list, "req_item_set_position", "pre_mask")
def preset_tv_item_position_data(requirements, ctx):
    if not ctx.uses_webui:  # workaround for E064206
        ctx.skip_dialog()
    TargetValue._tv_item_set_position_pre_mask(ctx)


@sig.connect(TargetValue, list, "req_item_set_position", "now")
def tv_item_set_position_now(requirements, ctx):
    TargetValue._tv_item_set_position_now(ctx)


@sig.connect(RQMSpecification, "classification_update", "pre")
def set_persistent_flag_spec(obj, data):
    data[ClassificationConstants.PERSISTENT_VALUES_CHECKSUM] = True


@sig.connect(RQMSpecObject, "classification_update", "pre")
def set_persistent_flag_spec_object(obj, data):
    data[ClassificationConstants.PERSISTENT_VALUES_CHECKSUM] = True


@sig.connect(TargetValue, "classification_update", "pre")
def set_persistent_flag_target_value(obj, data):
    data[ClassificationConstants.PERSISTENT_VALUES_CHECKSUM] = True
