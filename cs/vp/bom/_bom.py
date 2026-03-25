#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

# pylint: disable-msg=R0901,R0201,R0904,E0203,W0212,W0201

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import misc
from cdb.classbody import classbody
from cdb.rte import require_config

from cs.vp.bom import AssemblyComponent
from cs.tools.batchoperations import TypeDefinition

# Sentinel: raise when "std-solution" is not set
require_config("std-solution")


@classbody
class AssemblyComponent(object):

    def initDimensions(self, ctx):
        """
        Hinweis: Bei Stücklistenausleitung aus Kopplungen sind die
        Attribute für Bemaßungen ggf. nicht vorhanden.
        """
        dim_attrs = ['netto_laenge', 'netto_breite', 'netto_hoehe', 'netto_durchm']
        for attr in dim_attrs:
            if self.HasField(attr) and self[attr] == '':
                self[attr] = 0

    def on_relship_copy_post(self, ctx):
        if ctx.error:
            return

    def presetJoinedAttributes(self, ctx):
        """
        Evaluates the Component-Join to fill
        all attributes that can be retrieved from self.Item
        """
        if self.teilenummer and self.Item:
            objhandle = None
            from cdb.platform.mom import entities
            comp_join = entities.DDClassJoin.ByKeys("bom_item", "cdb_bom_item2component")
            if comp_join:
                try:
                    for field in comp_join.DependingFields:
                        try:
                            ctx.set(field.field_name, self.Item[field.joined_field_name])
                        except:
                            # Seems to be a joined attribute that is not part of the
                            # base relation and therefore not available within cdb.objects
                            if not objhandle:
                                objhandle = self.Item.ToObjectHandle()
                                if objhandle.is_valid():
                                    ctx.set(field.field_name, objhandle.getValue(field.joined_field_name, False))
                except Exception as exc:
                    # No raise because in many cases the preset is no necessary and
                    # the maximum error is an annoying info message to the user
                    misc.cdblogv(misc.kLogErr, 0, "Failed to presetJoinedAttributes:%s" % str(exc))

    event_map = {
        (('create'), 'pre_mask'): ('presetJoinedAttributes'),
        (('create', 'copy', 'modify'), 'pre'): ('initDimensions')
    }
