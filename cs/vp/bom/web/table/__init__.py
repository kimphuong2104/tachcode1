# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

from cdb import sig

from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent


VERSION = "15.7.0"


class BomTableOperationManager(object):
    def __init__(self):
        self.last_completed_operation = {}

    def set_last_completed_operation(self, frontend_identifier, operation):
        self.last_completed_operation[frontend_identifier] = operation

    def get_last_completed_operation(self, frontend_identifier):
        if frontend_identifier not in self.last_completed_operation:
            return None
        return self.last_completed_operation[frontend_identifier]


OPERATION_MANAGER = BomTableOperationManager()


def mark_operation_completed(ctx):
    if 'bomtable_operation_uuid' in ctx.sys_args.get_attribute_names() and \
            'bomtable_operation_frontend_identifier' in ctx.sys_args.get_attribute_names():
        OPERATION_MANAGER.set_last_completed_operation(
            ctx.sys_args.bomtable_operation_frontend_identifier,
            ctx.sys_args.bomtable_operation_uuid
        )


@sig.connect(AssemblyComponent, "create", "post")
@sig.connect(AssemblyComponent, "copy", "post")
@sig.connect(AssemblyComponent, "modify", "post")
@sig.connect(Item, "modify", "post")
@sig.connect(Item, "wf_step", "post")
def __mark_operation_completed(_, ctx):
    mark_operation_completed(ctx)
