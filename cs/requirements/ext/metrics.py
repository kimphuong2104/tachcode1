#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from cdb import sig
from cdb.platform.mom import getObjectHandleFromObjectID
from cs.metrics.actions import QCAction
from cs.metrics.qualitycharacteristics import QualityCharacteristic
from cs.tools.semanticlinks import SemanticLink, SemanticLinkType
from cdb.objects.operations import operation


@sig.connect(QCAction, "create", "post")
@sig.connect(QCAction, "copy", "post")
def createSemanticLink(self, ctx):
    if self.qc_object_id:
        qc = QualityCharacteristic.ByKeys(self.qc_object_id)
        if qc.Definition.cdb_module_id == u"cs.requirements":
            objhandle = getObjectHandleFromObjectID(qc.cdbf_object_id)
            if objhandle:
                slt = SemanticLinkType.getValidLinkTypes(obj=None, subject_object_classname=u"cdb_action",
                                                         object_object_classname=objhandle.getClassDef().getClassname())
                if slt:
                    kwargs = {"subject_object_id": self.action_object_id,
                              "object_object_id": qc.cdbf_object_id,
                              "link_type_object_id": slt[0].cdb_object_id}
                    operation("CDB_Create", SemanticLink, **kwargs)
