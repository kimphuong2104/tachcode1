# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import collections
import datetime
import gc
import json
import logging
import os
import sys
import tempfile
from os import remove
import urllib.parse
from cdb import (ElementsError, auth, cdbuuid, fls, i18n, misc, objects,
                 oracle, rte, sig, sqlapi, transactions, ue, util)
from cdb.dberrors import DBError
from cdb.objects import Forward, operations, references
from cdb.objects.cdb_file import CDB_File
from cdb.objects.core import Object
from cdb.objects.objectlifecycle import State, Transition
from cdb.objects.org import Organization, Person, WithSubject
from cdb.objects.rules import Rule
from cdb.platform.gui import Label
from cdb.platform.mom import entities, relships
from cdb.platform.mom.fields import (DDField, DDMultiLangField,
                                     DDMultiLangFieldBase,
                                     DDMultiLangMappedField)
from cdb.platform.olc import StateDefinition
from cdb.storage.index.tesjobqueue import TESJobQueue
from cdb.typeconversion import from_legacy_date_format
from cdbwrapc import CDBClassDef, getFileTypeByFilename
from cs.activitystream.objects import Channel, SystemPosting
from cs.audittrail import AuditTrailDetail, AuditTrailObjects, WithAuditTrail
from cs.baselining import Baseline
from cs.baselining.support import BaselineTools
from cs.classification import (ClassificationChecksum, ObjectClassification,
                               ObjectPropertyValue)
from cs.classification import api as classification_api
from cs.classification.classes import ClassificationClass
from cs.classification.object_classification import ClassificationData
from cs.classification.tools import (get_active_classification_languages,
                                     get_addtl_objref_value, preset_mask_data)
from cs.documents import Document
from cs.metrics.qcclasses import WithQualityCharacteristic
from cs.metrics.qualitycharacteristics import ObjectQualityCharacteristic
from cs.metrics.targetprocessor import InvalidTargetValue, TargetProcessor
from cs.platform.web.rest import support
from cs.requirements import rating, rqm_utils
from cs.requirements.base_classes import WithRQMBase
from cs.requirements.classes import (RequirementCategory, RequirementPriority,
                                     RQMImportProcessRun, RQMProtocol,
                                     RQMProtocolLogging,
                                     RQMSpecificationCategory,
                                     RQMSpecObjectIssueReference,
                                     fRQMExportProcessRun,
                                     fRQMImportProcessRun,
                                     fRQMSpecificationDocumentReference,
                                     fRQMSpecificationStateProtocol,
                                     fRQMSpecObjectDocumentReference)
from cs.requirements.exceptions import ExcelImportError
from cs.requirements.rqm_utils import RQMHierarchicals
from cs.requirements_reqif.exceptions import ReqIFInterfaceError
from cs.sharing.share_objects import WithSharing
from cs.tools import semanticlinks
from cs.tools.powerreports import WithPowerReports
from cs.tools.semanticlinks import (SemanticLink, SemanticLinkType,
                                    WithSemanticLinks)
from cs.workflow.briefcases import BriefcaseContent

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
__all__ = ["RQMSpecObject", "RQMSpecification", "TargetValue"]
LOG = logging.getLogger(__name__)
fRQMSpecObject = Forward(__name__ + ".RQMSpecObject")
fRQMSpecification = Forward(__name__ + ".RQMSpecification")
fTargetValue = Forward(__name__ + ".TargetValue")
fProject = Forward("cs.pcs.projects.Project")
fProduct = Forward("cs.vp.products.Product")


class RQMSpecObject (WithSubject, WithSemanticLinks, BriefcaseContent, WithPowerReports, WithSharing,
                     WithQualityCharacteristic, WithRQMBase, WithAuditTrail):
    __classname__ = "cdbrqm_spec_object"
    __maps_to__ = "cdbrqm_spec_object"
    __maps_to_view__ = "cdbrqm_spec_object_v"
    __number_format__ = "R%09d"
    __number_key__ = "RQM_SPEC_OBJECT_NR_SEQ"
    __readable_id_field__ = "specobject_id"
    __parent_object_id_field__ = "parent_object_id"
    __context_object_id_field__ = "specification_object_id"
    __description_attrname_format__ = "cdbrqm_spec_object_desc_{iso}"
    __short_description_attrname_format__ = "name_{iso}"
    __reference_field__ = "specobject_object_id"

    Files = references.Reference_N(CDB_File, CDB_File.cdbf_object_id == fRQMSpecObject.cdb_object_id)
    Specification = references.Reference_1(fRQMSpecification,
                                           fRQMSpecification.cdb_object_id == fRQMSpecObject.specification_object_id)

    ParentRequirement = ParentSpecObject = references.Reference_1(fRQMSpecObject,
                                                                  fRQMSpecObject.cdb_object_id == fRQMSpecObject.parent_object_id)
    SubRequirements = ChildrenSpecObjects = references.Reference_N(fRQMSpecObject,
                                                                   fRQMSpecObject.parent_object_id == fRQMSpecObject.cdb_object_id,
                                                                   order_by=fRQMSpecObject.position)
    TargetValues = references.Reference_N(fTargetValue,
                                          fTargetValue.requirement_object_id == fRQMSpecObject.cdb_object_id,
                                          order_by=[fTargetValue.pos, fTargetValue.targetvalue_id])
    Baselines = references.ReferenceMethods_N(fRQMSpecObject,
                                              lambda self: BaselineTools.get_baselines(self))
    BaselineDetails = references.Reference_1(
        Baseline,
        Baseline.ce_baseline_id == fRQMSpecObject.ce_baseline_id
    )

    AllVersions = references.Reference_N(
        fRQMSpecObject,
        fRQMSpecObject.ce_baseline_origin_id == fRQMSpecObject.ce_baseline_origin_id,
        fRQMSpecObject.cdb_object_id != fRQMSpecObject.cdb_object_id  # all other but self
    )

    AllVersionsInIndex = references.Reference_N(
        fRQMSpecObject,
        fRQMSpecObject.ce_baseline_object_id == fRQMSpecObject.ce_baseline_object_id,
        fRQMSpecObject.cdb_object_id != fRQMSpecObject.cdb_object_id  # all other but self
    )

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the specification, project, product the object itself.
        """
        channels = [self, self.Specification]
        if self.Specification.Project:
            channels.append(self.Specification.Project)
        if self.Specification.Product:
            channels.append(self.Specification.Product)
        return channels

    def referencedAuditTrailObjects(self):
        refs = [self, self.Specification]
        if self.ParentRequirement:
            refs.append(self.ParentRequirement)
            parent = self.ParentRequirement
            while parent:
                parent = parent.ParentRequirement
                if parent:
                    refs.append(parent)
        return refs

    def on_preview_now(self, ctx):
        preview_url = "/cs-requirements-web-richtext?cdb_object_id=%s&restname=spec_object&preview=1&readonly=1&fieldname=cdbrqm_spec_object_desc_"
        ctx.setPreviewURL(preview_url % self.cdb_object_id)

    def _get_Documents(self):
        return [x.Document for x in fRQMSpecObjectDocumentReference.KeywordQuery(specobject_object_id=self.cdb_object_id)]

    Documents = references.ReferenceMethods_N(Document, _get_Documents)
    DocumentRefs = references.Reference_N(fRQMSpecObjectDocumentReference, fRQMSpecObjectDocumentReference.specobject_object_id == fRQMSpecObject.cdb_object_id)

    def _tree_up_reference(self):
        # a spec object parent is a parent spec object or (XOR) the specification
        parent_spec_object = self.ParentSpecObject
        if parent_spec_object is None:
            return self.Specification
        return parent_spec_object

    def _tree_down_reference(self):
        # a spec object has target values or (XOR) child spec objects
        childs = self.ChildrenSpecObjects.Execute()
        if childs:
            return childs
        else:
            return self.TargetValues

    def get_reqif_description(self):
        return self.name

    def get_reqif_long_name(self):
        return self.specobject_id

    def makePosition(self, ctx=None):
        if 'rqm_position_overwrite' not in rte.environ:
            return RQMSpecObject.lookupPosition(self.parent_object_id,
                                                specification_object_id=self.specification_object_id)
        else:
            return int(rte.environ.get('rqm_position_overwrite'))

    def _is_template(self):
        return self.Specification.is_template if not hasattr(self, 'is_template') else self.is_template

    @classmethod
    def lookupPosition(cls, parent_object_id, specification=None, specification_object_id=None):
        position = 1
        if specification is None and specification_object_id is not None:
            specification = RQMSpecification.ByKeys(cdb_object_id=specification_object_id)
            specification = specification if specification is None or specification.CheckAccess("read") else None
        if specification:
            position = 1
            parent_object_id = parent_object_id if parent_object_id is not None else ''
            mymax = sqlapi.RecordSet2(cls.__maps_to__,
                                      (RQMSpecObject.specification_object_id == specification.cdb_object_id) &
                                      (RQMSpecObject.parent_object_id == parent_object_id),
                                      columns=["MAX(position) p"])
            if mymax and mymax[0].p:
                position = int(mymax[0].p) + 1
        return position

    @classmethod
    def _req_item_set_position_pre_mask(cls, ctx):
        if ctx.uses_webui:
            specification_object_id, parent_obj, _ = rqm_utils.get_objects_to_move_data(
                cls, ctx, 'ParentRequirement'
            )
            ctx.set('parent_object_id', parent_obj.cdb_object_id if parent_obj is not None else '=""')
            ctx.set('specification_object_id', specification_object_id)

    @classmethod
    def _req_item_set_position_now(cls, ctx):
        specification_object_id, parent_obj, objs_to_move = rqm_utils.get_objects_to_move_data(
            cls, ctx, 'ParentRequirement'
        )
        if not ctx.uses_webui and not ctx.catalog_selection:
            browser_attr = {
                "parent_object_id": (parent_obj.cdb_object_id if parent_obj is not None else '=""'),
                "specification_object_id": specification_object_id
            }
            ctx.start_selection(catalog_name="cdbrqm_spec_object_brows2", **browser_attr)
        else:
            if ctx.uses_webui:
                if ctx.dialog.new_predecessor:
                    selected_req = RQMSpecObject.ByKeys(ctx.dialog.new_predecessor)
                else:
                    raise ue.Exception("cdbrqm_no_pos")
            else:
                selected_req = RQMSpecObject.ByKeys(ctx.catalog_selection[0]["cdb_object_id"])
            cls._move_req_positions(specification_object_id, selected_req, objs_to_move)
            cls._resetPositions(
                specification_object_id=selected_req.specification_object_id,
                parent_object_id=selected_req.parent_object_id
            )
            if selected_req.Specification:
                selected_req.Specification.update_sortorder(ctx)
            if selected_req.parent_object_id:
                util.refresh_structure_node(selected_req.parent_object_id, 'cdbrqm_spec_object_overview')
                util.refresh_structure_node(selected_req.parent_object_id, 'cdbrqm_specification_overview')
            else:
                util.refresh_structure_node(selected_req.specification_object_id, 'cdbrqm_specification_overview')

    @classmethod
    def _resetPositions(
        cls,
        specification_object_id,
        parent_object_id,
        inserted_object=None,
        inserted_object_position=None
    ):
        """ Re-numbers every RQMSpecObject's position only
        within a specific level according to the database ordering for that level.
        Optionally it supports a single object which has to be inserted at a certain position"""
        spec_objs = RQMSpecObject.KeywordQuery(
            specification_object_id=specification_object_id,
            parent_object_id=parent_object_id, order_by='position'
        )
        i = 1
        # TODO: Performance
        for spec_obj in spec_objs:
            if inserted_object is not None and inserted_object_position == i:
                # insert the optionally given object at specificed position and
                # move all others one position behind
                inserted_object.position = i
                i += 1
            if inserted_object is not None and spec_obj.cdb_object_id == inserted_object.cdb_object_id:
                # the inserted object already has its new position so this position can be filled with
                # another object
                continue
            spec_obj.position = i
            i += 1
        if inserted_object is not None and inserted_object_position == i:
            # insert the optionally given object at specificed position
            # this is needed when the new position is at the end and the inserted object
            # was found before (continue)
            inserted_object.position = i

    @classmethod
    def _move_req_positions(cls, specification_object_id, selected_req, reqs_to_move):
        if selected_req is not None:
            target_field = int(selected_req.position)
            positions_to_move = len(reqs_to_move)
            qry = "UPDATE %s" \
                " SET position = position+%d" \
                " WHERE specification_object_id='%s'" \
                " AND parent_object_id='%s'" \
                " AND position > %d" % (cls.__maps_to__,
                                        positions_to_move,
                                        specification_object_id,
                                        selected_req.parent_object_id,
                                        target_field)
            sqlapi.SQL(qry)
            for req in reqs_to_move:
                target_field += 1
                req.position = target_field

    def _getlevel(self, level=0):
        if self.ParentRequirement:
            level = self.ParentRequirement._getlevel(level + 1)
        return level

    def make_sortorder(self, ctx=None):
        obj = RQMSpecObject.ByKeys(self.cdb_object_id)
        if obj.ParentRequirement:
            obj.sortorder = obj.ParentRequirement.sortorder + "/" + str(obj.position).zfill(5)
        else:
            prefix = "/" if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE else ""
            obj.sortorder = prefix + str(obj.position).zfill(5)

    def set_chapter(self, ctx=None):
        obj = RQMSpecObject.ByKeys(self.cdb_object_id)
        chapter = ""
        if obj.ParentRequirement:
            chapter = obj.ParentRequirement.chapter + ".%s" % (len(obj.ParentRequirement.SubRequirements))
        else:
            chapter = "%s" % (len(RQMSpecObject.KeywordQuery(specification_object_id=obj.specification_object_id,
                                                             parent_object_id="")))
        obj.chapter = chapter

    def preset_rating_class(self, ctx):
        # preset classification class for the creation of a requirement
        if "classification_web_ctrl" not in ctx.sys_args.get_attribute_names():
            classification_data = classification_api.get_new_classification(
                ["RQM_RATING"], narrowed=False
            )
            preset_mask_data(classification_data, ctx)

    def isLeafReq(self):
        self.Reload()
        r = Rule.ByKeys('cdbrqm: Leaf Requirement')
        result = r.match(self)
        return result

    def validateRankedDown(self, ctx):
        if not self.isLeafReq():
            priorities_by_priority = RequirementPriority.get_priorities_by_priority()
            rank = priorities_by_priority.get(self.priority).rank if self.priority in priorities_by_priority else -sys.maxsize - 1
            not_allowed_priorities = [s.priority for s in priorities_by_priority.values() if s.rank > rank]
            if hasattr(ctx, 'cdbtemplate') and ctx.cdbtemplate:
                objects.core.ByID(ctx.cdbtemplate.cdb_object_id)
            reqs_with_not_allowed_priorities = self.SubRequirements.KeywordQuery(priority=not_allowed_priorities)
            if reqs_with_not_allowed_priorities:
                higher_priority = priorities_by_priority.get(reqs_with_not_allowed_priorities[0].priority).ml_name
                raise ue.Exception("cdbrqm_priority_constraint_down", self.GetDescription(), higher_priority, higher_priority)

    def _get_parent_ids(self, ids=None):
        if ids is None:
            ids = {}
        if self.ParentSpecObject:
            parent_ids = self.ParentSpecObject._get_parent_ids(ids)
            ids[self.ParentSpecObject.cdb_object_id] = 1  # dummy value
            ids.update(parent_ids)
            return ids
        else:
            return ids

    def ensure_no_cycle(self, ctx):
        source = rqm_utils._get_source_object(self, ctx, fRQMSpecObject)
        if source is not None:
            cycle = False
            if self.parent_object_id == source.cdb_object_id:
                cycle = True
            else:
                parent_ids = self._get_parent_ids()
                if source.cdb_object_id in parent_ids:
                    cycle = True
            if cycle:
                raise ue.Exception("cdbrqm_ensure_no_self_parent")

    def ensureNoTargetValues(self, ctx):
        if self.ParentRequirement and self.ParentRequirement.TargetValues:
            raise ue.Exception("cdbrqm_no_move_target_value")

    def deletemoveTargetValue(self, ctx):
        if self.CheckAccess("create"):
            if self.ParentRequirement and self.ParentRequirement.TargetValues:
                if 'question_move_target_value' not in ctx.dialog.get_attribute_names():
                    msgbox = ctx.MessageBox('cdbrqm_move_target_value', [],
                                            'question_move_target_value', ctx.MessageBox.kMsgBoxIconQuestion)
                    msgbox.addCancelButton(is_dflt=1)
                    msgbox.addButton(ctx.MessageBoxButton('button_delete', 'delete'))
                    msgbox.addButton(ctx.MessageBoxButton('cdbrqm_button_move', 'move'))
                    ctx.show_message(msgbox)
                else:
                    result = ctx.dialog.question_move_target_value
                    if result == 'delete':
                        for tv in self.ParentRequirement.TargetValues:
                            operations.operation("CDB_Delete", tv)
                    elif result == 'move':
                        tvs = ""
                        for tv in self.ParentRequirement.TargetValues:
                            tvs += "%s;" % tv.cdb_object_id
                        ctx.keep("move_target_values", tvs)

    def presetValues(self, ctx):
        if not self.weight and not ctx.dragged_obj:
            ctx.set("weight", 1)
        if ctx.action in ('modify', 'info'):
            if (
                not self.CheckAccess("rqm_richtext_save") or
                not self.CheckAccess("save") or
                ctx.action == 'info'
            ):
                readonly_url = '/cs-requirements-web-richtext?readonly=1&restname=spec_object&cdb_object_id={}'.format(
                    self.cdb_object_id
                )
                ctx.set_elink_url(
                    "richtext_desc", readonly_url
                )
                ctx.set_readonly(".richtext_desc")

    def setSpecificationReadOnly(self, ctx):
        ctx.set_readonly("specification_object_id")

    def set_act_value(self, act_value=None, guetegrad=None):
        if act_value is not None and (act_value == "" or
                                      rqm_utils.isValidFloat(act_value)):
            if guetegrad is None:
                guetegrad = 'manuell'
            fls.allocate_license('RQM_036')
            if self.isLeafReq() and not self.TargetValues:
                old_value = self.act_value
                qcd = rqm_utils.getQCFulfillmentDef()
                qc = self.ObjectQualityCharacteristics.KeywordQuery(cdbqc_def_object_id=qcd.cdb_object_id)[0]
                qc.set_actual_value(act_value, guetegrad=guetegrad)
                if old_value != act_value:
                    audittrail = self.createAuditTrail('modify')
                    if audittrail:
                        self.createAuditTrailDetail(audittrail_object_id=audittrail.audittrail_object_id,
                                                    clsname=self.GetClassname(),
                                                    attribute="act_value",
                                                    old_value=old_value,
                                                    new_value=act_value)

    @classmethod
    def makeNumber(cls):
        return WithRQMBase.makeNumber(cls)

    def setNumber(self, ctx=None):
        self.specobject_id, maxno = RQMSpecObject.makeNumber()
        self.maxno = maxno
        if not self.ext_specobject_id:
            self.ext_specobject_id = self.specobject_id
        self.cdb_object_id = cdbuuid.create_uuid()
        self.ce_baseline_object_id = self.cdb_object_id
        self.ce_baseline_origin_id = cdbuuid.create_uuid()

    def reset_external_fields(self, ctx, source_obj=None):
        source = rqm_utils._get_source_object(self, ctx, RQMSpecObject, source_obj)
        if (
            source is not None and
            "followup_cdbrqm_new_revision" not in ctx.ue_args.get_attribute_names()
        ):
            self.ext_specobject_id = ""
            self.reqif_id = ""
            self.ce_baseline_origin_id = cdbuuid.create_uuid()

    def aggregateRankedUp(self, ctx):
        if self.priority:
            priorities_by_name = RequirementPriority.get_priorities_by_priority()
            if self.priority and self.priority in priorities_by_name:
                rank = priorities_by_name.get(self.priority).rank
                parent = self.ParentRequirement
                while parent:
                    if not parent.priority or \
                        parent.priority not in priorities_by_name or \
                            priorities_by_name.get(parent.priority).rank < rank:
                        parent.priority = self.priority
                    parent = parent.ParentRequirement

    def copy_subobjects(self, ctx=None, source_obj=None, processed_objs=None,
                        semlinks_to_create=None, **kwargs):
        source = rqm_utils._get_source_object(self, ctx, RQMSpecObject, source_obj)

        kwargs.update(dict(cdb_classname=self.GetClassname(),
                           root_dst_obj=self,
                           specification_object_id=self.specification_object_id))
        results = super(RQMSpecObject, self).copy_subobjects(
            ctx,
            source,
            processed_objs,
            semlinks_to_create,
            **kwargs
        )
        self.Specification.update_sortorder(ctx)
        if source_obj is not None:
            return results

    @classmethod
    def tree_copy_pre_cb_func(cls, source_obj, static_properties, **kwargs):
        attrs = WithRQMBase.tree_copy_pre_cb_func(source_obj, static_properties, **kwargs)
        attrs.update(
            {'template_oid': source_obj.cdb_object_id
             }
        )
        level = kwargs.get('level', 0)
        followup_cdbrqm_new_revision = kwargs.get("followup_cdbrqm_new_revision", 0)
        root_dst_obj = static_properties.get('root_dst_obj')
        # root objects (copied by kernel copy) already have a new number
        if (root_dst_obj is None or level != 0) and followup_cdbrqm_new_revision == 0:
            new_req_id, new_req_maxno = RQMSpecObject.makeNumber()
            attrs.update(dict(
                specobject_id=new_req_id,
                maxno=new_req_maxno,
                ext_specobject_id='',
                reqif_id=''
            ))
        if root_dst_obj and isinstance(root_dst_obj, RQMSpecification):
            if level == 1:
                # top spec objects have no parent -> therefore override the parent_object_id
                attrs.update(dict(parent_object_id=""))
            elif 'parent_object_id' in static_properties:
                # all other spec objects should have their corresponding parent_object_ids -> therefore remove the overridden parent_object_id
                del static_properties['parent_object_id']
        return attrs

    @classmethod
    def tree_copy_post_cb_func(cls, source_obj, dest_obj, processed_objs, static_properties, **kwargs):
        followup_cdbrqm_new_revision = kwargs.get("followup_cdbrqm_new_revision", 0)
        # generate new empty qc for requirement which was copied source_obj->dest_obj (but not for level 0 as this is done by WithQualityCharacteristics)
        # or in case of index creation copy the old_values
        if followup_cdbrqm_new_revision == 1:
            source_qc = rqm_utils.getFulfillmentQC(source_obj)
            if source_qc:
                source_qc.Copy(cdbf_object_id=dest_obj.cdb_object_id)
        elif kwargs.get("level") > 0:
            dest_classname = dest_obj.GetClassname()
            args = {"cdbf_object_id": dest_obj.cdb_object_id,
                    "classname": dest_classname}
            rqm_utils.createQC(**args)

    def preset_bm(self, ctx):
        ctx.set("specification_object_id", self.specification_object_id)

    def execute_bm(self, ctx):
        from cs.audittrail import config
        if self.cdb_object_id == ctx.objects[0].cdb_object_id:
            with transactions.Transaction():
                objs = self.PersistentObjectsFromContext(ctx)
                new_parent_max_position = None
                dialog_values = {
                    attr_name: ctx.dialog[attr_name] for attr_name in ctx.dialog.get_attribute_names()}
                if 'parent_object_id' in dialog_values and dialog_values['parent_object_id']:
                    new_parent_object_id = dialog_values['parent_object_id']
                    if new_parent_object_id:
                        if new_parent_object_id in [o.cdb_object_id for o in objs]:
                            raise ue.Exception("cdbrqm_batch_modification_parent_inside_set")
                        new_parent_object = RQMSpecObject.ByKeys(cdb_object_id=new_parent_object_id)
                        new_specification_object_id = None
                        if 'specification_object_id' in dialog_values:
                            new_specification_object_id = dialog_values['specification_object_id']
                        if new_parent_object.specification_object_id != new_specification_object_id:
                            raise ue.Exception("cdbrqm_batch_modification_inconsistent_spec_parent")
                    stmt = """
                        SELECT
                            MAX(position) position
                        FROM %s
                            WHERE parent_object_id='%s' AND specification_object_id='%s'
                    """
                    stmt = stmt % (
                        RQMSpecObject.__maps_to__,
                        sqlapi.quote(dialog_values.get('parent_object_id', '')),
                        sqlapi.quote(
                            dialog_values.get('specification_object_id', self.specification_object_id)
                        )
                    )
                    new_parent_max_positions = sqlapi.RecordSet2(sql=stmt)
                    if new_parent_max_positions:
                        new_parent_max_position = new_parent_max_positions[0]['position']
                if (
                    'specification_object_id' in dialog_values and
                    dialog_values['specification_object_id'] != self.specification_object_id and
                    not (
                        (
                            'parent_object_id' in dialog_values and
                            dialog_values['parent_object_id'] != ''
                        ) or (
                            'empty_parent_object_id' in dialog_values and
                            bool(int(dialog_values['empty_parent_object_id']))
                        )
                    )
                ):
                    moved_ids = []
                    for obj in objs:
                        moved_ids.append(obj.cdb_object_id)
                    for obj in objs:
                        if obj.parent_object_id and obj.parent_object_id not in moved_ids:
                            raise ue.Exception('cdbrqm_bm_inconsistent_move', obj.GetDescription())
                update_sortorder = False
                for obj in objs:
                    update_obj = {}
                    audittrail_obj = {}
                    audittrail = obj.createAuditTrail('modify')
                    if new_parent_max_position is not None and 'position' in obj:
                        # see E061691 expectations
                        # add the max position of the new parent to ensure the elements
                        # will be moved to the end but stay in their previous order
                        new_position = obj.position + new_parent_max_position
                        update_obj['position'] = new_position
                        audittrail_obj['position'] = new_position
                    for attr_name in ctx.dialog.get_attribute_names():
                        attr_value = ctx.dialog[attr_name]
                        if attr_value != "":
                            if "$empty" in attr_value and attr_name in obj:
                                update_obj[attr_name] = ""
                                audittrail_obj[attr_name] = ""
                            elif "$empty" in attr_value and attr_name.startswith("mapped_"):
                                update_obj[attr_name.replace('mapped_', '', 1)] = ""
                                audittrail_obj[attr_name.replace('mapped_', '', 1)] = ""
                            elif attr_name.startswith("empty_") and bool(int(attr_value)):
                                update_obj[attr_name.replace('empty_', '', 1)] = ""
                                audittrail_obj[attr_name.replace('empty_', '', 1)] = ""
                            else:
                                if attr_name in obj:
                                    if attr_name in update_obj and update_obj[attr_name] == "":
                                        continue
                                    else:
                                        update_obj[attr_name] = attr_value
                                elif (
                                    attr_name.startswith("mapped_") and
                                    attr_name.replace('mapped_', '', 1) in obj
                                ):
                                    audittrail_obj[attr_name] = attr_value
                    if audittrail:
                        for k, v in audittrail_obj.items():
                            if v != obj[k] and k in config[self.GetClassname()]["fields"]:
                                self.createAuditTrailDetail(audittrail_object_id=audittrail.audittrail_object_id,
                                                            clsname=self.GetClassname(),
                                                            attribute=k,
                                                            old_value=obj[k],
                                                            new_value=v)
                    old_parent_object_id = obj.parent_object_id
                    old_specification_object_id = obj.specification_object_id
                    obj.Update(**update_obj)
                    obj.Reload()
                    if 'parent_object_id' in update_obj:
                        update_sortorder = True
                        old_parent = RQMSpecObject.ByKeys(old_parent_object_id)
                        if old_parent:
                            old_parent.Reload()
                            if not old_parent.SubRequirements:
                                tf_kpi = old_parent.FulfillmentQualityCharacteristic
                                if tf_kpi:
                                    tf_kpi.set_actual_value(None, guetegrad=u"manuell")
                                WithRQMBase.aggregate_qc(old_parent, True)
                            else:
                                # old parent has a changed set of children therefore aggregate
                                # not only up_structure but also calculate the old_parent itself
                                WithRQMBase.aggregate_qc(old_parent, False)
                        WithRQMBase.aggregate_qc(obj, True)
                    if (
                        'specification_object_id' in update_obj and
                        obj.specification_object_id != old_specification_object_id
                    ):
                        # move all following requirements/target values found by
                        # recursive statement to the new specification as well
                        sub_object_ids = RQMHierarchicals.getObjectIdsRecursive(obj)
                        reqs = fRQMSpecObject.KeywordQuery(cdb_object_id=sub_object_ids)
                        tvs = fTargetValue.KeywordQuery(cdb_object_id=sub_object_ids)
                        for sub_obj in (reqs + tvs):
                            audittrail = sub_obj.createAuditTrail('modify')
                            if audittrail:
                                if 'specification_object_id' in config[sub_obj.GetClassname()]["fields"]:
                                    self.createAuditTrailDetail(
                                        audittrail_object_id=audittrail.audittrail_object_id,
                                        clsname=sub_obj.GetClassname(),
                                        attribute='specification_object_id',
                                        old_value=sub_obj['specification_object_id'],
                                        new_value=obj.specification_object_id
                                    )
                        reqs.Update(specification_object_id=obj.specification_object_id)
                        tvs.Update(specification_object_id=obj.specification_object_id)
                if update_sortorder:
                    # see E061691 - close gaps in position numbers
                    self.Specification.recalculate_positions()
                    self.Specification.update_sortorder(ctx)

    def change_fulfillment(self, ctx):
        if self.cdb_object_id == ctx.objects[0].cdb_object_id:
            failed = []
            failed_objs = []

            for obj in self.PersistentObjectsFromContext(ctx):
                if not obj.isLeafReq() or self.TargetValues:
                    failed.append(obj.GetDescription())
                    failed_objs.append(obj.cdb_object_id)

            if len(ctx.objects) == len(failed):
                raise ue.Exception('cdbrqm_change_fulfillment_failed')
            if failed and 'question_change_fulfillment_ask_continue' not in ctx.dialog.get_attribute_names():
                if len(failed) > 5:
                    failed = failed[:5]
                    failed.append("...")
                msgbox = ctx.MessageBox('cdbrqm_change_fulfillment_ask_continue', ['\n'.join(failed)],
                                        'question_change_fulfillment_ask_continue', ctx.MessageBox.kMsgBoxIconQuestion)
                msgbox.addButton(ctx.MessageBoxButton('button_skip', 'skip'))
                msgbox.addCancelButton()
                ctx.keep('failed_objs', ';'.join(failed_objs))
                ctx.show_message(msgbox)
            with transactions.Transaction():
                for obj in self.PersistentObjectsFromContext(ctx):
                    if 'failed_objs' in ctx.ue_args.get_attribute_names() and \
                       obj.cdb_object_id in ctx.ue_args.failed_objs:
                        continue
                    if ctx.action == "cdbrqm_easy_fulfilled":
                        obj.set_act_value(100)
                    else:
                        obj.set_act_value(0)
                    ctx.refresh_tables(["cdbrqm_spec_object"])

    def presetCategory(self, ctx):
        if not self.category:
            name = ""
            default_category = RequirementCategory.getDefaultCategory()
            if default_category:
                name = default_category.name
            ctx.set('category', name)

    @classmethod
    def create_from_template(cls, ctx):
        """
        Create a requirement by selecting an template and copying it
        """

        def _uniquote(s):
            if isinstance(s, str):
                v = s.encode('utf-8')
            else:
                v = s
            return urllib.parse.quote(v)

        if misc.CDBApplicationInfo().rootIsa(misc.kAppl_HTTPServer):
            from cs.requirements.web.template_create_app.main import TemplateCreateApp
            url = TemplateCreateApp.MOUNT_PATH + "/spec_object"
            if ctx.relationship_name:
                # We have to provide information about the relationship and the
                # parent
                rs = relships.Relship.ByKeys(ctx.relationship_name)
                cdef = entities.CDBClassDef(rs.referer)
                o = support._RestKeyObj(cdef, ctx.parent)
                key = support.rest_key(o)
                url += u"?classname=%s&rs_name=%s&keys=%s" % \
                       (_uniquote(rs.referer),
                        _uniquote(rs.rolename),
                        _uniquote(key))

            ctx.url(url)

        if not ctx.catalog_selection:
            state = StateDefinition.ByKeys(objektart=u"cdbrqm_specification",
                                           statusnummer=200)
            browser_attr = {
                "joined_status_name": state.StateText['']
            }
            ctx.start_selection(catalog_name="cdbrqm_specification_template", **browser_attr)
        elif "start_selection" in ctx.ue_parameter.get_attribute_names() and \
                ctx.ue_parameter.start_selection == u"cdbrqm_specification_template":
            specification_object_id = ctx.catalog_selection[0]["cdb_object_id"]
            browser_attr = {
                "specification_object_id": specification_object_id
            }
            ctx.start_selection(catalog_name="cdbrqm_spec_obj_template", **browser_attr)
        else:
            cdb_object_id = ctx.catalog_selection[0]["cdb_object_id"]
            template = cls.ByKeys(cdb_object_id=cdb_object_id)
            ctx.set_followUpOperation("CDB_Copy", keep_rship_context=True,
                                      predefined=[("is_template", 0)],
                                      op_object=template)

    def reset_fulfillment(self, ctx=None):

        def _reset_fulfillment(parent, obj, next_elems, level, **context_data):
            LOG.debug('_reset_fulfillment called on %s', obj)
            tf_kpi = obj.FulfillmentQualityCharacteristic
            if tf_kpi:
                old_value = self.act_value
                tf_kpi.set_actual_value(None, guetegrad=u"manuell")
                if old_value:
                    audittrail = self.createAuditTrail('modify')
                    if audittrail:
                        self.createAuditTrailDetail(audittrail_object_id=audittrail.audittrail_object_id,
                                                    clsname=self.GetClassname(),
                                                    attribute="act_value",
                                                    old_value=old_value,
                                                    new_value="")

        self._walk(self, _reset_fulfillment)

    def setEvaluationDate(self, ctx=None):
        if ctx.action == "cdbrqm_reset_fulfillment":

            def _set_evaluation_date(parent, obj, next_elems, level, **context_data):
                LOG.debug('_reset_fulfillment called on %s', obj)
                tf_kpi = obj.FulfillmentQualityCharacteristic
                if tf_kpi:
                    obj.Update(cdbrqm_edate=datetime.datetime.now(),
                               cdbrqm_epersno=auth.persno)

            self._walk(self, _set_evaluation_date)
        else:
            for obj in self.PersistentObjectsFromContext(ctx):
                obj.Update(cdbrqm_edate=datetime.datetime.now(),
                           cdbrqm_epersno=auth.persno)

    def moveTargetValue(self, ctx):
        if 'move_target_values' in ctx.ue_args.get_attribute_names():
            tvs = ctx.ue_args.move_target_values.split(";")
            tvs = TargetValue.KeywordQuery(cdb_object_id=tvs)
            tvs.Update(requirement_object_id=self.cdb_object_id)
            self.reset_fulfillment()

    def setDefined(self, ctx):
        if self.is_defined == 0:
            r = self.ParentRequirement
            while r:
                r.is_defined = 0
                r = r.ParentRequirement
        else:
            if self.SubRequirements:
                object_ids = RQMHierarchicals.getObjectIdsRecursive(self)
                reqs = RQMSpecObject.KeywordQuery(cdb_object_id=object_ids)
                reqs.Update(is_defined=1)

    def setParentID(self, ctx):
        if not self.ParentRequirement or self.ParentRequirement.specification_object_id != self.specification_object_id:
            ctx.set("parent_object_id", "")

    def _handle_new_sub_req(self, ctx):
        if ctx.mode == 'pre_mask':
            for fname in ctx.dialog.get_attribute_names():
                if fname not in ['specification_object_id', 'fulfillment_kpi_active']:
                    ctx.set(fname, '')
            # default values:
            specobject_id, _ = self.makeNumber()
            self.fillAuthorField(ctx)
            ctx.set('specobject_id', specobject_id)
            ctx.set('parent_object_id', self.cdb_object_id)
            ctx.set('is_defined', 0)
            ctx.set('weight', 1)
            ctx.set('position', 0)
            if ctx.dialog.category == "":
                default_category = RequirementCategory.getDefaultCategory()
            else:
                default_category = RequirementCategory.ByKeys(ctx.dialog.category)
            if default_category:
                cat_name = default_category.name
                ctx.set('category', cat_name)
                for iso_code in i18n.Languages():
                    if hasattr(default_category, iso_code):
                        ctx.set('mapped_category_{iso}'.format(iso_code), getattr(default_category, "name_" + iso_code))

            self.initRichtext(ctx)
            ctx.skip_dialog()

        elif ctx.mode == 'now':
            create_new_args = {k: getattr(ctx.dialog, k) for k in ctx.dialog.get_attribute_names() if k not in ['cdb_object_id', 'color', 'is_group', 'target_value', 'act_value']}
            try:
                rte.environ['rqm_skip_desc_empty_check'] = '1'
                qry = (
                    """UPDATE %s
                    SET position = position+1
                    WHERE specification_object_id='%s'
                    AND parent_object_id='%s'""" % (self.__maps_to__,
                                                    self.specification_object_id,
                                                    self.cdb_object_id))
                sqlapi.SQL(qry)
                rte.environ['rqm_position_overwrite'] = '1'
                new_obj = operations.operation(
                    "CDB_Create",
                    self.GetClassDef(),
                    operations.form_input(
                        self.GetClassDef(),
                        **create_new_args
                    )
                )
                self.Specification.update_sortorder(ctx)
                new_obj.Reload()
                ctx.set_object_result(new_obj)
            except ElementsError as e:
                LOG.exception(e)
                raise ue.Exception('just_a_replacement', e)
            finally:
                if 'rqm_skip_desc_empty_check' in rte.environ:
                    del rte.environ['rqm_skip_desc_empty_check']
                if 'rqm_position_overwrite' in rte.environ:
                    del rte.environ['rqm_position_overwrite']

    def _handle_new_neighbor_req(self, ctx):
        if ctx.mode == 'pre_mask':
            for fname in ctx.dialog.get_attribute_names():
                if fname not in ['specification_object_id', 'fulfillment_kpi_active', 'parent_object_id']:
                    ctx.set(fname, '')
            # default values:
            self.fillAuthorField(ctx)
            specobject_id, _ = self.makeNumber()
            ctx.set('specobject_id', specobject_id)
            ctx.set('is_defined', 0)
            ctx.set('weight', 1)
            ctx.set('position', 0)
            if ctx.dialog.category == "":
                default_category = RequirementCategory.getDefaultCategory()
            else:
                default_category = RequirementCategory.ByKeys(ctx.dialog.category)
            if default_category:
                cat_name = default_category.name
                ctx.set('category', cat_name)
                for iso_code in i18n.Languages():
                    if hasattr(default_category, iso_code):
                        ctx.set('mapped_category_{iso}'.format(iso_code), getattr(default_category, "name_" + iso_code))
            self.initRichtext(ctx)
            ctx.skip_dialog()

        elif ctx.mode == 'now':
            create_new_args = {k: getattr(ctx.dialog, k) for k in ctx.dialog.get_attribute_names() if k not in ['cdb_object_id', 'color', 'is_group', 'target_value', 'act_value']}
            try:
                rte.environ['rqm_skip_desc_empty_check'] = '1'
                qry = ("""UPDATE %s
                  SET position = position+1
                  WHERE specification_object_id='%s'
                  AND parent_object_id='%s'
                  AND position > %d""") % (self.__maps_to__,
                                           self.specification_object_id,
                                           self.parent_object_id,
                                           self.position)
                sqlapi.SQL(qry)
                rte.environ['rqm_position_overwrite'] = "{}".format(self.position + 1)
                new_obj = operations.operation(
                    "CDB_Create",
                    self.GetClassDef(),
                    operations.form_input(
                        self.GetClassDef(),
                        **create_new_args
                    )
                )
                self.Specification.update_sortorder(ctx)
                new_obj.Reload()
                ctx.set_object_result(new_obj)
            except ElementsError as e:
                LOG.exception(e)
                raise ue.Exception('just_a_replacement', e)
            finally:
                if 'rqm_skip_desc_empty_check' in rte.environ:
                    del rte.environ['rqm_skip_desc_empty_check']
                if 'rqm_position_overwrite' in rte.environ:
                    del rte.environ['rqm_position_overwrite']

    def switch_to_detail(self, ctx):
        ctx.url("/info/spec_object/%s" % self.cdb_object_id)

    def handle_move_left(self, ctx):
        if ctx.mode == 'pre_mask':
            ctx.skip_dialog()
        if ctx.mode == 'now':
            if self.parent_object_id:
                old_parent_position = self.ParentRequirement.position
                old_parent_id = self.parent_object_id
                old_position = self.position
                self.parent_object_id = self.ParentRequirement.parent_object_id

                # for the old level do a normal re-numbering of positions - so filling the gap
                self._resetPositions(
                    specification_object_id=self.specification_object_id,
                    parent_object_id=old_parent_id
                )
                # for the new level do a re-numbering with insertion of the new object in that level
                self._resetPositions(
                    specification_object_id=self.specification_object_id,
                    parent_object_id=self.parent_object_id,
                    inserted_object=self,
                    inserted_object_position=old_parent_position + 1
                )
                self.update_sortorder(ctx)
                old_parent = RQMSpecObject.ByKeys(old_parent_id)
                if old_parent:
                    old_parent.Reload()
                    if not old_parent.SubRequirements:
                        tf_kpi = old_parent.FulfillmentQualityCharacteristic
                        if tf_kpi:
                            tf_kpi.set_actual_value(None, guetegrad=u"manuell")
                    WithRQMBase.aggregate_qc(old_parent, True)
                self.Reload()
                WithRQMBase.aggregate_qc(self, True)
                at = self.createAuditTrail("modify")
                self.createAuditTrailDetail(
                    at.audittrail_object_id,
                    self.GetClassname(),
                    "parent_object_id",
                    old_parent_id,
                    self.parent_object_id
                )
                if old_position != self.position:
                    self.createAuditTrailDetail(
                        at.audittrail_object_id,
                        self.GetClassname(),
                        "position",
                        old_position,
                        self.position
                    )

    def handle_move_right(self, ctx):
        if ctx.mode == 'pre_mask':
            ctx.skip_dialog()
        elif ctx.mode == 'now':
            same_level_reqs_before = RQMSpecObject.KeywordQuery(
                parent_object_id=self.parent_object_id,
                specification_object_id=self.specification_object_id
            ).Query("position < {}".format(self.position), order_by="position").Execute()
            if same_level_reqs_before:
                req_before = same_level_reqs_before[-1]
                if not req_before.TargetValues:
                    old_parent_id = self.parent_object_id
                    old_position = self.position

                    new_level_requirement_max_positions = RQMSpecObject.KeywordQuery(
                        specification_object_id=self.specification_object_id,
                        parent_object_id=req_before.cdb_object_id
                    ).position
                    new_level_requirement_max_position = (
                        max(
                            new_level_requirement_max_positions
                        ) if len(new_level_requirement_max_positions) > 0 else 0)
                    self.parent_object_id = req_before.cdb_object_id
                    self._resetPositions(
                        specification_object_id=self.specification_object_id,
                        parent_object_id=old_parent_id
                    )
                    self._resetPositions(
                        specification_object_id=self.specification_object_id,
                        parent_object_id=self.parent_object_id,
                        inserted_object=self,
                        inserted_object_position=new_level_requirement_max_position + 1
                    )
                    self.update_sortorder(ctx)
                    old_parent = RQMSpecObject.ByKeys(old_parent_id)
                    if old_parent:
                        old_parent.Reload()
                        if not old_parent.SubRequirements:
                            tf_kpi = old_parent.FulfillmentQualityCharacteristic
                            if tf_kpi:
                                tf_kpi.set_actual_value(None, guetegrad=u"manuell")
                        WithRQMBase.aggregate_qc(old_parent, True)
                    self.Reload()
                    WithRQMBase.aggregate_qc(self, True)
                    at = self.createAuditTrail("modify")
                    self.createAuditTrailDetail(at.audittrail_object_id,
                                                self.GetClassname(),
                                                "parent_object_id",
                                                old_parent_id,
                                                self.parent_object_id)
                    if old_position != self.position:
                        self.createAuditTrailDetail(
                            at.audittrail_object_id,
                            self.GetClassname(),
                            "position",
                            old_position,
                            self.position
                        )

    def handle_move_up(self, ctx):
        if ctx.mode == 'pre_mask':
            ctx.skip_dialog()
        elif ctx.mode == 'now':
            same_level_reqs_before = RQMSpecObject.KeywordQuery(
                parent_object_id=self.parent_object_id,
                specification_object_id=self.specification_object_id
            ).Query("position < {}".format(self.position), order_by="position").Execute()
            if same_level_reqs_before:
                req_before = same_level_reqs_before[-1]
                reg_before_pos = req_before.position
                req_before.position = self.position
                self.position = reg_before_pos
                self._resetPositions(
                    specification_object_id=self.specification_object_id,
                    parent_object_id=self.parent_object_id
                )
                self.update_sortorder(ctx)

    def handle_move_down(self, ctx):
        if ctx.mode == 'pre_mask':
            ctx.skip_dialog()
        elif ctx.mode == 'now':
            same_level_reqs_after = RQMSpecObject.KeywordQuery(
                parent_object_id=self.parent_object_id,
                specification_object_id=self.specification_object_id
            ).Query("position > {}".format(self.position), order_by="position").Execute()
            if same_level_reqs_after:
                req_after = same_level_reqs_after[0]
                self._move_req_positions(
                    specification_object_id=self.specification_object_id,
                    selected_req=req_after,
                    reqs_to_move=[self]
                )
                self._resetPositions(
                    specification_object_id=self.specification_object_id,
                    parent_object_id=self.parent_object_id
                )
                self.update_sortorder(ctx)

    def update_position_after_delete(self, ctx):
        qry = "UPDATE %s" \
              " SET position = position-%d" \
              " WHERE specification_object_id='%s'" \
              " AND parent_object_id='%s'" \
              " AND position > %d" % (self.__maps_to__,
                                      1,
                                      self.specification_object_id,
                                      self.parent_object_id,
                                      self.position)
        sqlapi.SQL(qry)

    def delete_sub_elements(self, ctx):
        tree_down_context = RQMHierarchicals.get_tree_down_context(
            specification=self.Specification,
            parent_object=self,
            return_objects=False
        )
        with transactions.Transaction():
            total_ids = tree_down_context["spec_object_cache"]
            tv_ids = TargetValue.KeywordQuery(
                # ensure also the direct acceptance criterions of self are deleted
                # as tree_down_context only contains the ones of deeper requirements (sub or subsub or ...)
                requirement_object_id=list(tree_down_context["target_value_cache"]) + [self.cdb_object_id]
            ).cdb_object_id
            total_ids += tv_ids
            total_ids.append(self.cdb_object_id)
            self.Specification._delete_elements_by_ids(
                total_ids, ce_baseline_id=''
            )

    def update_sortorder(self, ctx=None):
        self.Specification.update_sortorder(ctx)

    def check_concurrent_modification(self, ctx):
        if ctx.interactive == 0 and not ctx.uses_webui and 'cdb_mdate' in ctx.dialog.get_attribute_names() and RQMSpecObject.KeywordQuery(cdb_object_id=self.cdb_object_id).Execute()[0].cdb_mdate != from_legacy_date_format(ctx.dialog.cdb_mdate):
            raise ue.Exception(
                'just_a_replacement',
                json.dumps(
                    {
                        'type': 'refetch',
                        'msg': str(ue.Exception('obj_changed', Person.ByKeys(personalnummer=self.cdb_mpersno).name))
                    }, ensure_ascii=False
                )
            )

    @classmethod
    def switch_to_spec(cls, ctx):
        ctx.url("/info/specification")

    def enhance_search_condition(self, ctx):
        BaselineTools.enhance_search_condition(self, ctx)
        # If present, retrieve checkbox value
        ckb_my_req = int(ctx.dialog.my_requirements) if 'my_requirements' in ctx.dialog.get_attribute_names() and ctx.dialog.my_requirements else None
        if ckb_my_req:
            # Get current users id
            search_target = Person.ByKeys(personalnummer=auth.persno)
            evaluator_id = search_target.cdb_object_id
            create_new = False
            # Check if the web control is not empty
            if "classification_web_ctrl" in ctx.sys_args.get_attribute_names() and ctx.sys_args['classification_web_ctrl'] != '':
                # Retrieve web control and converto to string
                web_ctrl_json = json.loads(ctx.sys_args['classification_web_ctrl'])
                # If control is present but its completely empty (click) or with the class linked but empty values (click, assign class)
                if (
                    web_ctrl_json['assigned_classes'] == [] or
                    (
                        web_ctrl_json['assigned_classes'] == ['RQM_RATING'] and web_ctrl_json['values'] == {}
                    )
                ):
                    create_new = True
                # Check if control if the classes were assigned but the values are empty
                elif ('RQM_RATING' in web_ctrl_json['assigned_classes'] and web_ctrl_json['values'] != {}):
                    # Check if the Evaluator field is there and substitute if for current user
                    if 'RQM_RATING_RQM_RATING' in web_ctrl_json['values']:
                        web_ctrl_json['values']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_EVALUATOR'][0]['value'] = evaluator_id
                        web_ctrl_json['values']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_EVALUATOR'][0]['addtl_value'] = get_addtl_objref_value(
                            evaluator_id,
                            None
                        )
                    # In case the rating class is there but there are no RQM_RATING_RQM_RATING field
                    else:
                        new_classification = classification_api.get_new_classification(["RQM_RATING"], with_defaults=False)
                        rqm_rating = new_classification['properties']['RQM_RATING_RQM_RATING']
                        rqm_rating[0]['value']['child_props']['RQM_EVALUATOR'][0]['value'] = evaluator_id
                        rqm_rating[0]['value']['child_props']['RQM_EVALUATOR'][0]['addtl_value'] = get_addtl_objref_value(
                                                                                                evaluator_id,
                                                                                                None
                                                                                            )
                        web_ctrl_json['values']['RQM_RATING_RQM_RATING'] = rqm_rating
                    # Turn back to string
                    web_ctrl_str = json.dumps(web_ctrl_json, default=rqm_utils.date_to_str)
                    # Reassign web control value
                    ctx.set('cdb::argument.classification_web_ctrl', web_ctrl_str)
            else:
                create_new = True
            # If there was no information in the web control, create a classification object from scratch
            if create_new:
                # New classification
                classification_data = classification_api.get_new_classification(['RQM_RATING'], with_defaults=False, narrowed=False)
                # Set current user as Evaluator on this classification
                classification_data['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_EVALUATOR'][0]['value'] = evaluator_id
                classification_data['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_EVALUATOR'][0]['addtl_value'] = get_addtl_objref_value(
                    evaluator_id,
                    None
                )
                # Adapt fields to how the web search is done
                classification_data['values'] = classification_data['properties']
                del classification_data['properties']
                if 'metadata' in classification_data:
                    del classification_data['metadata']
                classification_data_str = json.dumps(classification_data, default=rqm_utils.date_to_str)
                # Set created classification as search parameter
                ctx.set('cdb::argument.classification_web_ctrl', classification_data_str)

    event_map = {
        ('modify', 'pre'): 'check_concurrent_modification',
        ('create', 'pre_mask'): ('deletemoveTargetValue', 'presetCategory', 'preset_rating_class'),
        ('create', 'post'): 'moveTargetValue',
        ('create', 'pre'): 'preset_rating_class',
        (('create', 'copy'), 'pre'): ('setParentID'),
        (('modify', 'info'), 'pre_mask'): ('setSpecificationReadOnly'),
        (('create', 'copy'), 'post'): ('make_sortorder', 'set_chapter'),
        ('delete', 'post'): ('update_position_after_delete', 'delete_sub_elements'),
        ('delete', 'final'): 'update_sortorder',
        ('copy', 'post_mask'): 'ensureNoTargetValues',
        (('create', 'modify', 'copy', 'info'), 'pre_mask'): ('presetValues'),
        (('create', 'modify', 'copy'), 'pre'): ('validateRankedDown',
                                                'ensure_no_cycle'),
        (('create', 'modify', 'copy'), 'post'): ('aggregateRankedUp', 'setDefined'),
        ('cdbrqm_batch_modification', 'pre_mask'): 'preset_bm',
        ('cdbrqm_batch_modification', 'now'): 'execute_bm',
        (('cdbrqm_easy_fulfilled', 'cdbrqm_easy_not_fulfilled'), 'now'): 'change_fulfillment',
        ('cdbrqm_create_from_template', 'now'): "create_from_template",
        ('cdbrqm_reset_fulfillment', 'now'): 'reset_fulfillment',
        (('cdbrqm_easy_fulfilled', 'cdbrqm_easy_not_fulfilled', 'cdbrqm_reset_fulfillment'), 'post'): 'setEvaluationDate',
        ('cdbrqm_spec_object_create_below', '*'): '_handle_new_sub_req',
        ('cdbrqm_spec_object_create_beside', '*'): '_handle_new_neighbor_req',
        ('cdbrqm_spec_object_detail', 'now'): "switch_to_detail",
        ('cdbrqm_spec_object_move_left', '*'): "handle_move_left",
        ('cdbrqm_spec_object_move_right', '*'): "handle_move_right",
        ('cdbrqm_spec_object_move_up', '*'): "handle_move_up",
        ('cdbrqm_spec_object_move_down', '*'): "handle_move_down",
        ('cdbrqm_switch_web_to_spec', 'now'): "switch_to_spec",
        ('copy', 'final'): "update_sortorder",
        (('query', 'requery', 'query_catalog'), 'pre'): "enhance_search_condition"
    }


@sig.connect(RQMSpecObject, "classification_update", "pre_commit")
def classification_pre_update(classified_object,
                              classification_data,
                              classification_diff_data
                              ):
    if 'RQM_RATING' in classification_data["assigned_classes"]:
        # ShouldI query for languages everytime?
        languages = get_active_classification_languages()
        autom_checkbox = classification_data['properties']['RQM_RATING_RQM_RATING_CALCULATED'][0]['value']
        # If autom_checkbox is set to True, the automatic calculation will run,
        # if not, the value will be hard set by the user.
        # Checking for changes in RQM_RATING classification only to avoid updating timestamps if no changes were made.
        rating_classification = {key: classification_data['properties'][key]
                                 for key in classification_data['properties'] if "RQM_RATING" in key}
        rating_classification_diff = {key: classification_diff_data['properties'][key]
                                      for key in classification_diff_data['properties'] if "RQM_RATING" in key}
        if autom_checkbox and rating_classification != rating_classification_diff:
            rating.Rating.update_overall_rating(classification_data)
            classification_data['properties']['RQM_RATING_RQM_RATING_SET_BY'][0]['value'] = None
            classification_data['properties']['RQM_RATING_RQM_RATING_MDATE'][0]['value'] = datetime.datetime.now()
        else:
            # Check if there were no changes done
            if 'old_value' in classification_diff_data['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value'][languages[0]]:
                if (
                    classification_diff_data['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value'][languages[0]]['old_value'] !=
                    classification_diff_data['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value'][languages[0]]['text_value']
                ):
                    # If it is not the automatic process, check if user is allowed
                    is_allowed = False
                    # Recover information from context
                    changed_by = Person.ByKeys(personalnummer=auth.persno)  # Current users as a Person object
                    personal_number = auth.persno                       # Current users personal number
                    responsible_type = classified_object.subject_type   # Could be Person, Common Role or Project Role
                    resp_or_role = classified_object.subject_id         # Person Name, Role in general or in a project
                    if (responsible_type == "Person"):
                        if (resp_or_role == personal_number):
                            is_allowed = True
                    elif (responsible_type == "Common Role"):
                        # Get role
                        roles = util.get_roles("GlobalContext", "", personal_number)
                        if resp_or_role in roles:
                            is_allowed = True
                    elif (responsible_type == "PCS Role"):
                        # Get project id
                        project_id = classified_object.cdb_project_id
                        if project_id:
                            # Get Project role
                            roles = util.get_roles("ProjectContext", project_id, personal_number)
                            if resp_or_role in roles:
                                is_allowed = True
                    if is_allowed:
                        classification_data['properties']['RQM_RATING_RQM_RATING_SET_BY'][0]['value'] = changed_by.cdb_object_id
                        classification_data['properties']['RQM_RATING_RQM_RATING_MDATE'][0]['value'] = datetime.datetime.now()
                    else:
                        LOG.warning("This user is not allowed to change the overall rating")
                        raise ue.Exception('cdbrqm_rating_no_override_per')


class RQMSpecification(WithSubject, WithSemanticLinks, BriefcaseContent, WithPowerReports, WithSharing,
                       WithQualityCharacteristic, WithRQMBase, WithAuditTrail):
    __classname__ = "cdbrqm_specification"
    __maps_to__ = "cdbrqm_specification"
    __maps_to_view__ = "cdbrqm_specification_v"
    __number_format__ = "S%09d"
    __number_key__ = "RQM_SPEC_NR_SEQ"
    __objektart__ = "cdbrqm_specification"
    __readable_id_field__ = "spec_id"
    __reference_field__ = "spec_object_id"

    class DRAFT(State):
        status = 0

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(RQMSpecification.REVISION.status)
            super(RQMSpecification.DRAFT, state).pre_mask(self, ctx)

    class REVIEW(State):
        status = 100

    class BLOCKED(State):
        status = 170

        def post(state, self, ctx):  # @NoSel
            self.setLinksObsolete(1)

    class OBSOLETE(State):
        status = 180

        def post(state, self, ctx):  # @NoSel
            self.setLinksObsolete(1)

    class REVISION(State):
        status = 190

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(RQMSpecification.RELEASED.status)
                ctx.excl_state(RQMSpecification.OBSOLETE.status)
                ctx.excl_state(RQMSpecification.DRAFT.status)
            super(RQMSpecification.REVISION, state).pre_mask(self, ctx)

    class RELEASED(State):
        status = 200

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(RQMSpecification.REVISION.status)
            super(RQMSpecification.RELEASED, state).pre_mask(self, ctx)

        def post(state, self, ctx):  # @NoSel
            self.setLinksObsolete(0)

    class DRAFT_TO_REVIEW(Transition):
        transition = (0, 100)

        def post(transition, self, ctx):  # @NoSelf
            LOG.debug("DRAFT_TO_REVIEW: post")
            WithRQMBase.aggregate_qc(self, False)

    class REVIEW_TO_DRAFT(Transition):
        transition = (100, 0)

        def post(transition, self, ctx):  # @NoSelf
            LOG.debug("REVIEW_TO_DRAFT: post")
            WithRQMBase.aggregate_qc(self, False)

    class REVIEW_TO_RELEASED(Transition):
        transition = (100, 200)

        def post(transition, self, ctx):  # @NoSelf
            LOG.debug("REVIEW_TO_RELEASED: post")
            if len(self.PreviousVersions):
                if self.PreviousVersions[-1].status == RQMSpecification.REVISION.status:
                    self.PreviousVersions[-1].ChangeState(RQMSpecification.OBSOLETE.status)
            self.Requirements.Update(is_defined=1)

    class REVISION_TO_RELEASED(Transition):
        transition = (190, 200)

        def post(transition, self, ctx):  # @NoSelf
            LOG.debug("REVISION_TO_RELEASED: post")
            self.enqueueObjects()

    class RELEASED_TO_REVISION(Transition):
        transition = (200, 190)

        def post(transition, self, ctx):  # @NoSelf
            LOG.debug("RELEASED_TO_REVISION: post")
            self.enqueueObjects()

    class RELEASED_TO_BLOCKED(Transition):
        transition = (200, 170)

        def post(transition, self, ctx):  # @NoSelf
            LOG.debug("RELEASE_TO_BLOCKED: post")
            self.enqueueObjects()

    class REVISION_TO_DRAFT(Transition):
        transition = (190, 0)

        def post(transition, self, ctx):  # @NoSelf
            LOG.debug("REVISION_TO_DRAFT: post")
            self.enqueueObjects()

    Requirements = SpecObjects = references.Reference_N(fRQMSpecObject,
                                                        fRQMSpecObject.specification_object_id == fRQMSpecification.cdb_object_id)

    TargetValues = references.Reference_N(fTargetValue,
                                          fTargetValue.specification_object_id == fTargetValue.cdb_object_id)

    TopRequirements = TopSpecObjects = references.Reference_N(fRQMSpecObject,
                                                              fRQMSpecObject.specification_object_id == fRQMSpecification.cdb_object_id,
                                                              fRQMSpecObject.parent_object_id == '',
                                                              order_by=fRQMSpecObject.position)

    LastStateProtocolEntry = references.ReferenceMethods_N(fRQMSpecificationStateProtocol,
                                                           lambda self: rqm_utils.get_last_state_protocol_entry(cdb_object_id=self.cdb_object_id,
                                                                                                                state_protocol_type=fRQMSpecificationStateProtocol))

    PreviousVersions = references.Reference_N(fRQMSpecification,
                                              fRQMSpecification.spec_id == fRQMSpecification.spec_id,
                                              fRQMSpecification.revision < fRQMSpecification.revision,
                                              order_by=fRQMSpecification.revision)

    OtherVersions = references.Reference_N(fRQMSpecification,
                                           fRQMSpecification.spec_id == fRQMSpecification.spec_id,
                                           fRQMSpecification.revision != fRQMSpecification.revision
                                           )
    Baselines = references.ReferenceMethods_N(fRQMSpecification,
                                              lambda self: BaselineTools.get_baselines(self))

    BaselineDetails = references.Reference_1(
        Baseline,
        Baseline.cdb_object_id == fRQMSpecification.ce_baseline_id
    )

    AllVersions = references.Reference_N(
        fRQMSpecification,
        fRQMSpecification.ce_baseline_origin_id == fRQMSpecification.ce_baseline_origin_id,
        fRQMSpecification.cdb_object_id != fRQMSpecification.cdb_object_id  # all other but self
    )

    AllVersionsInIndex = references.Reference_N(
        fRQMSpecification,
        fRQMSpecification.ce_baseline_object_id == fRQMSpecification.ce_baseline_object_id,
        fRQMSpecification.cdb_object_id != fRQMSpecification.cdb_object_id  # all other but self
    )

    Files = references.Reference_N(CDB_File, CDB_File.cdbf_object_id == fRQMSpecification.cdb_object_id)

    def setLinksObsolete(self, obsolete):
        args = dict(
            cdb_obsolete=obsolete,
            specification_object_id_literal=RQMSpecObject.specification_object_id.make_literal(self.cdb_object_id),
            specification_object_id_condition=str(RQMSpecObject.specification_object_id==self.cdb_object_id)
        )
        # update semantic links of spec, requirements and acceptance criterions
        # in both directions
        subject_object_id_query = """
            cdb_semantic_link SET subject_cdb_obsolete = {cdb_obsolete} 
                WHERE subject_object_id={specification_object_id_literal}
                OR subject_object_id IN (
                    SELECT cdb_object_id FROM cdbrqm_spec_object WHERE 1=1 AND {specification_object_id_condition}
                ) OR subject_object_id IN (
                    SELECT cdb_object_id FROM cdbrqm_target_value WHERE 1=1 AND {specification_object_id_condition}
                )
        """.format(**args)
        object_object_id_query = """
            cdb_semantic_link SET object_cdb_obsolete = {cdb_obsolete} 
                WHERE object_object_id={specification_object_id_literal}
                OR object_object_id IN (
                    SELECT cdb_object_id FROM cdbrqm_spec_object WHERE 1=1 AND {specification_object_id_condition}
                ) OR object_object_id IN (
                    SELECT cdb_object_id FROM cdbrqm_target_value WHERE 1=1 AND {specification_object_id_condition}
                )
        """.format(**args)
        sqlapi.SQLupdate(subject_object_id_query)
        sqlapi.SQLupdate(object_object_id_query)

    def _get_Documents(self):
        return [x.Document for x in fRQMSpecificationDocumentReference.KeywordQuery(spec_object_id=self.cdb_object_id)]

    Documents = references.ReferenceMethods_N(Document, _get_Documents)
    DocumentRefs = references.Reference_N(fRQMSpecificationDocumentReference, fRQMSpecificationDocumentReference.spec_object_id == fRQMSpecification.cdb_object_id)

    Project = references.Reference_1(fProject, fProject.cdb_project_id == fRQMSpecification.cdb_project_id)

    Product = references.Reference_1(fProduct, fProduct.cdb_object_id == fRQMSpecification.product_object_id)

    ImportRuns = references.Reference_N(fRQMImportProcessRun, fRQMImportProcessRun.specification_object_id == fRQMSpecification.cdb_object_id)

    ExportRuns = references.Reference_N(
        fRQMExportProcessRun,
        fRQMExportProcessRun.specification_object_id == fRQMSpecification.cdb_object_id
    )

    def enqueueObjects(self):
        if self.Requirements:
            tablename = self.Requirements[0].GetTableName()
            for req in self.Requirements:
                TESJobQueue.enqueue(req.cdb_object_id,
                                    tablename,
                                    None,
                                    None)
        if self.TargetValues:
            tablename = self.TargetValues[0].GetTableName()
            for tv in self.TargetValues:
                TESJobQueue.enqueue(tv.cdb_object_id,
                                    tablename,
                                    None,
                                    None)

    def statechangeAuditTrailEntry(self, ctx=None):
        label = Label.ByKeys(ausgabe_label='cdbrqm_spec_state_comment')
        audittrail = super(RQMSpecification, self).statechangeAuditTrailEntry(ctx)
        if audittrail:
            AuditTrailDetail.Create(
                detail_object_id=cdbuuid.create_uuid(),
                audittrail_object_id=audittrail.audittrail_object_id,
                attribute_name="cdbprot_remark",
                old_value="",
                new_value=ctx.dialog.cdbprot_remark,
                label_de=label.d,
                label_en=label.uk
            )

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the project, product the object itself.
        In case of being a template additional channel for status change to approved and invalid.
        """
        channels = [self]
        if self.Project:
            channels.append(self.Project)
        if self.Product:
            channels.append(self.Product)
        if isinstance(posting, SystemPosting):
            if self._is_template() and posting.context_object_status in (RQMSpecification.RELEASED.status,
                                                                         RQMSpecification.OBSOLETE.status):
                posting.addTopic(Channel.KeywordQuery(title_de=u"Anforderungsmanagement")[0])
        return channels

    def adjust_fulfillment_kpi_active(self, ctx=None):
        """
        Activate the kpi control attributes if not already set.
        Specification templates and its contained elements can not be fulfilled therefore its values are forced to be -2.

        fulfillment_kpi_active possible values: 0 (default), 1 (active), -2 (inactive)
        """
        # fulfillment_kpi_active: 0 (default), 1 active, 2 inactive
        if not self.is_template:
            active = 1
        else:
            # spec templates and its content can not be fulfilled
            active = -2
        if active == -2 or self.fulfillment_kpi_active in [0, None]:
            self.Update(fulfillment_kpi_active=active)
        if active == -2:
            # forces deactivation of all
            sqlapi.SQLupdate("cdbrqm_spec_object SET fulfillment_kpi_active = %d WHERE specification_object_id='%s'" % (active, self.cdb_object_id))
            sqlapi.SQLupdate("cdbrqm_target_value SET fulfillment_kpi_active = %d WHERE specification_object_id='%s'" % (active, self.cdb_object_id))
        else:
            sqlapi.SQLupdate("cdbrqm_spec_object SET fulfillment_kpi_active = %d WHERE specification_object_id='%s' AND (fulfillment_kpi_active=0 OR fulfillment_kpi_active IS NULL) " % (active, self.cdb_object_id))
            sqlapi.SQLupdate("cdbrqm_target_value SET fulfillment_kpi_active = %d WHERE specification_object_id='%s' AND (fulfillment_kpi_active=0 OR fulfillment_kpi_active IS NULL)" % (active, self.cdb_object_id))

    def _init_RQMTreeLogic(self):
        if not hasattr(self, '_rqm_tree_logic_initialized'):
            self._rqm_tree_logic_initialized = True

    def _get_RQMTreeLogic_base_var(self):
        return RQMSpecObject.__classname__

    def _tree_depth_first_next(self, tree_context, parent=None, with_target_values=True):
        cache = tree_context.get('spec_object_cache')
        target_value_cache = tree_context.get('target_value_cache')
        ids = tree_context.get('ids')
        if parent is None:
            parent = self
        parent_object_id = ('' if parent == self else parent.cdb_object_id)
        childs = [x for x in ids if x.get('parent_object_id') == parent_object_id]
        if childs:
            res = [cache.get(x.get('cdb_object_id')) for x in childs]
        elif parent_object_id in target_value_cache and with_target_values:
            res = target_value_cache.get(parent_object_id)
        else:
            res = []
        return res

    def _tree_down_reference(self):
        return self.TopSpecObjects.Execute()

    def get_reqif_description(self):
        return self.name

    def get_reqif_long_name(self):
        return self.GetDescription()

    def _is_template(self):
        return self.is_template

    @classmethod
    def makeNumber(cls):
        return WithRQMBase.makeNumber(cls)

    def setNumber(self, ctx=None):
        if "followup_cdbrqm_new_revision" in \
                ctx.ue_args.get_attribute_names():
            return
        self.spec_id, self.maxno = RQMSpecification.makeNumber()
        if not self.ext_spec_id:
            self.ext_spec_id = self.spec_id
        self.cdb_object_id = cdbuuid.create_uuid()
        self.ce_baseline_object_id = self.cdb_object_id
        self.ce_baseline_origin_id = cdbuuid.create_uuid()

    def on_link_matrix_now(self, ctx):
        config = semanticlinks.LinkMatrixConfig.KeywordQuery(name="SpecificationLinkMatrix")[0]
        ctx.url("powerscript/cs.tools.semanticlinks.linkmatrix?context_object_id=%s&config_object_id=%s" %
                (self.cdb_object_id, config.cdb_object_id))

    def reset_external_fields(self, ctx, source_obj=None):
        source = rqm_utils._get_source_object(self, ctx, RQMSpecification, source_obj)
        if (
            source is not None and
            "followup_cdbrqm_new_revision" not in ctx.ue_args.get_attribute_names()
        ):
            self.ext_spec_id = ""
            self.reqif_id = ""
            self.ce_baseline_origin_id = cdbuuid.create_uuid()

    @classmethod
    def create_from_template(cls, ctx):
        """
        Create a specification by selecting an template and copying it
        """

        def _uniquote(s):
            if isinstance(s, str):
                v = s.encode('utf-8')
            else:
                v = s
            return urllib.parse.quote(v)

        if misc.CDBApplicationInfo().rootIsa(misc.kAppl_HTTPServer):
            from cs.requirements.web.template_create_app.main import TemplateCreateApp
            url = TemplateCreateApp.MOUNT_PATH + "/specification"
            if ctx.relationship_name:
                # We have to provide information about the relationship and the
                # parent
                rs = relships.Relship.ByKeys(ctx.relationship_name)
                cdef = entities.CDBClassDef(rs.referer)
                o = support._RestKeyObj(cdef, ctx.parent)
                key = support.rest_key(o)
                url += u"?classname=%s&rs_name=%s&keys=%s" % \
                       (_uniquote(rs.referer),
                        _uniquote(rs.rolename),
                        _uniquote(key))

            ctx.url(url)

        if not ctx.catalog_selection:
            state = StateDefinition.ByKeys(objektart=u"cdbrqm_specification",
                                           statusnummer=200)
            browser_attr = {
                "joined_status_name": state.StateText['']
            }
            ctx.start_selection(catalog_name="cdbrqm_specification_template", **browser_attr)
        else:
            cdb_object_id = ctx.catalog_selection[0]["cdb_object_id"]
            template = cls.ByKeys(cdb_object_id=cdb_object_id)
            ctx.set_followUpOperation("CDB_Copy", keep_rship_context=True,
                                      predefined=[("is_template", 0)],
                                      op_object=template)

    def update_sortorder(self, ctx=None):
        RQMHierarchicals.update_sortorder(obj=self)
        if ctx is not None:
            ctx.refresh_tables(["cdbrqm_spec_object"])

    def recalculate_positions(self, ctx=None):
        rqm_utils.RQMHierarchicals.update_positions(RQMSpecObject, self)
        rqm_utils.RQMHierarchicals.update_positions(
            TargetValue, self,
            parent_attribute_field_name='requirement_object_id',
            position_attribute_field_name='pos'
        )
        if ctx is not None:
            ctx.refresh_tables(["cdbrqm_spec_object"])
            ctx.refresh_tables(["cdbrqm_target_value"])

    @classmethod
    def tree_copy_pre_cb_func(cls, source_obj, static_properties, **kwargs):
        attrs = WithRQMBase.tree_copy_pre_cb_func(source_obj, static_properties, **kwargs)
        attrs.update(
            {'ext_spec_id': '',
             'cdb_objektart': source_obj.cdb_objektart,
             'cdb_status_txt': rqm_utils.get_state_txt(RQMSpecification.DRAFT.status,
                                                       objektart=RQMSpecification.__objektart__),
             'template_oid': source_obj.cdb_object_id,
             }
        )
        return attrs

    def _createMissingSubQCs(self, source, req_ids, tv_ids, already_existent_ids):
        # needed for creating QC objects for reqs, tvs when copying a spec from a spec template
        if source and source.is_template:
            for req_id in req_ids:
                if req_id in already_existent_ids:
                    continue
                args = {
                    'cdbf_object_id': req_id,
                    'classname': RQMSpecObject.__classname__,
                    '__force_creation__': 1
                }
                rqm_utils.createQC(**args)
            for tv_id in tv_ids:
                if tv_id in already_existent_ids:
                    continue
                args = {
                    'cdbf_object_id': tv_id,
                    'classname': TargetValue.__classname__,
                    '__force_creation__': 1
                }
                rqm_utils.createQC(**args)

    def remove_all_baseline_elements(self, ce_baseline_id):
        # we have to make sure that already released specifications cannot be altered by resetting
        # to an old baseline
        if self.CheckAccess("save") and self.ce_baseline_id == ce_baseline_id:
            with transactions.Transaction():
                context = RQMHierarchicals.get_tree_down_context(self, return_objects=False)
                total_ids = context["spec_object_cache"]
                total_ids += self.TargetValues.cdb_object_id
                total_ids.append(self.cdb_object_id)
                self._delete_elements_by_ids(total_ids, ce_baseline_id)
        else:
            raise ue.Exception("cdbrqm_baseline_restore_no_permission", self.GetDescription())

    def _delete_elements_by_ids(self, ids, ce_baseline_id=None):
        total_ids = ids
        context_sls = SemanticLink.KeywordQuery(
            subject_object_id=total_ids)
        context_sls += SemanticLink.KeywordQuery(
            object_object_id=total_ids)
        for sl in context_sls:
            total_ids.append(sl.cdb_object_id)

        # objects itself
        args = dict(cdb_object_id=total_ids)
        if ce_baseline_id is not None:
            args['ce_baseline_id'] = ce_baseline_id
        SemanticLink.KeywordQuery(cdb_object_id=total_ids).Delete()
        TargetValue.KeywordQuery(**args).Delete()
        RQMSpecObject.KeywordQuery(**args).Delete()
        RQMSpecification.KeywordQuery(**args).Delete()
        # audit trail
        AuditTrailObjects.KeywordQuery(object_id=total_ids).Delete()
        # object kpis
        ObjectQualityCharacteristic.KeywordQuery(cdbf_object_id=total_ids).Delete()
        # file attachments
        CDB_File.KeywordQuery(cdbf_object_id=total_ids).Delete()
        # doc refs
        fRQMSpecObjectDocumentReference.KeywordQuery(specobject_object_id=total_ids).Delete()
        fRQMSpecificationDocumentReference.KeywordQuery(spec_object_id=total_ids).Delete()
        # long text fields
        specification_text_fields = RQMSpecification.GetTextFieldNames()
        spec_object_text_fields = RQMSpecObject.GetTextFieldNames()
        target_value_text_fields = TargetValue.GetTextFieldNames()
        for text_field in specification_text_fields:
            sqlapi.SQLdelete("FROM %s WHERE %s" % (
                text_field,
                RQMSpecification.cdb_object_id.one_of(*total_ids))
            )
        for text_field in spec_object_text_fields:
            sqlapi.SQLdelete("FROM %s WHERE %s" % (
                text_field,
                RQMSpecObject.cdb_object_id.one_of(*total_ids))
            )
        for text_field in target_value_text_fields:
            sqlapi.SQLdelete("FROM %s WHERE %s" % (
                text_field,
                TargetValue.cdb_object_id.one_of(*total_ids))
            )
        # classification deletes
        sqlapi.SQLdelete("FROM %s WHERE %s" % (
            ObjectClassification.__maps_to__,
            ObjectClassification.ref_object_id.one_of(*total_ids)
        ))
        sqlapi.SQLdelete("FROM %s WHERE %s" % (
            ClassificationChecksum.__maps_to__,
            ClassificationChecksum.ref_object_id.one_of(*total_ids)
        ))

        sqlapi.SQLdelete("FROM %s WHERE %s" % (
            ObjectPropertyValue.__maps_to__,
            ObjectPropertyValue.ref_object_id.one_of(*total_ids)
        ))

        # issue references
        sqlapi.SQLdelete("FROM %s WHERE %s" % (
            RQMSpecObjectIssueReference.__maps_to__,
            RQMSpecObjectIssueReference.specobject_object_id.one_of(*total_ids)
        ))

    def copy_baseline_elements(self, ce_baseline_id, restore=False):
        highest_revision = self.get_highest_revision()
        if not restore and not self.revision == highest_revision:
            raise ValueError('Baselines can only be created from the highest revision')
        if restore and not self.revision == highest_revision:
            raise ValueError('Only baselines from the highest revision can be restored')
        kwargs = dict(ce_baseline_id=ce_baseline_id)
        if restore and ce_baseline_id == '':
            kwargs.update(dict(cdb_object_id=self.ce_baseline_object_id))
        new_spec_obj = self.Copy(**kwargs)
        for name in self.GetTextFieldNames():
            new_spec_obj.SetText(name, self.GetText(name))
        new_spec_obj.copy_subobjects(
            ctx=None, source_obj=self, baseline_copy=True,
            ce_baseline_id=ce_baseline_id,
            restore=restore
        )
        return new_spec_obj

    def copy_subobjects(self, ctx=None, source_obj=None, processed_objs=None,
                        semlinks_to_create=None, baseline_copy=False, restore=False,
                        **kwargs):
        copyDocuments = True
        copyTargetValues = True
        ce_baseline_id = kwargs.get('ce_baseline_id', None)
        depth = -1
        if ctx and "depth" in ctx.ue_args.get_attribute_names():
            depth = int(ctx.ue_args.depth)
            copyDocuments = True if (ctx.ue_args.copy_documents == "1") else False
            copyTargetValues = True if (ctx.ue_args.copy_target_values == "1") else False

        source = rqm_utils._get_source_object(self, ctx, RQMSpecification, source_obj)
        if source:
            new_context_copy = self.spec_id != source.spec_id
            if depth == -1 or "followup_cdbrqm_new_revision" in ctx.ue_args.get_attribute_names():
                context = RQMHierarchicals.get_tree_down_context(source, return_objects=False)
                if ce_baseline_id and context['missing_ce_baseline_object_ids']:
                    raise ValueError('Cannot baseline old unmigrated data')
                total_ids = context["spec_object_cache"]
                if source.TargetValues and copyTargetValues:
                    total_ids += source.TargetValues.cdb_object_id
                total_ids.append(source.cdb_object_id)
                qcs_ids = list(set(total_ids))
                context_sls = SemanticLink.KeywordQuery(
                    subject_object_id=total_ids)
                context_sls += SemanticLink.KeywordQuery(
                    object_object_id=total_ids)
                context_sl_ids = []
                indexing = True

                if (
                    baseline_copy or
                    (
                        ctx and "followup_cdbrqm_new_revision" in
                        ctx.ue_args.get_attribute_names()
                    )
                ):
                    for sl in context_sls:
                        context_sl_ids.append(sl.cdb_object_id)
                else:
                    indexing = False
                    for sl in context_sls:
                        if sl.subject_object_id in total_ids and sl.object_object_id in total_ids:
                            context_sl_ids.append(sl.cdb_object_id)
                total_ids += context_sl_ids
                total_ids = list(set(total_ids))

                def get_id(old_id):
                    if restore:
                        ce_baseline_object_id_cache = context["ce_baseline_object_id_cache"]
                        if old_id in ce_baseline_object_id_cache:
                            return ce_baseline_object_id_cache[old_id]
                        else:
                            return cdbuuid.create_uuid()
                    else:
                        return cdbuuid.create_uuid()

                old_id_new_id = {i: get_id(i) for i in total_ids}
                old_id_new_id[source.cdb_object_id] = self.ce_baseline_object_id if restore else self.cdb_object_id

                def reset_reqif_id(obj):
                    if indexing:
                        return obj.reqif_id
                    else:
                        return rqm_utils.createUniqueIdentifier()

                def reset_baseline_origin_id(obj):
                    if new_context_copy:
                        return cdbuuid.create_uuid()
                    else:
                        return obj.ce_baseline_origin_id

                with transactions.Transaction():
                    # copy requirements
                    new_spec_object_ids = []
                    spec_text_fields = RQMSpecObject.GetTextFieldNames()
                    rs = sqlapi.RecordSet2("cdbrqm_spec_object",
                                           "specification_object_id = '%s'"
                                           % source.cdb_object_id)
                    spec_copy_id = util.nextval(RQMSpecObject.__number_key__, len(rs)) - len(rs)
                    static_kwargs = {}
                    if ce_baseline_id is not None:
                        static_kwargs['ce_baseline_id'] = ce_baseline_id
                    for r in rs:
                        if indexing:
                            args = dict(
                                cdb_object_id=old_id_new_id[r.cdb_object_id],
                                specification_object_id=self.cdb_object_id,
                                parent_object_id=old_id_new_id[r.parent_object_id] if r.parent_object_id else "",
                                template_oid=r.cdb_object_id,
                                reqif_id=reset_reqif_id(r),
                                ce_baseline_origin_id=reset_baseline_origin_id(r),
                                **static_kwargs
                            )
                            if not ce_baseline_id:
                                args['ce_baseline_object_id'] = old_id_new_id[r.cdb_object_id]
                            r.copy(**args)
                        else:
                            spec_copy_id += 1
                            r.copy(cdb_object_id=old_id_new_id[r.cdb_object_id],
                                   ce_baseline_object_id=old_id_new_id[r.cdb_object_id],
                                   specification_object_id=self.cdb_object_id,
                                   parent_object_id=old_id_new_id[
                                       r.parent_object_id] if r.parent_object_id else "",
                                   template_oid=r.cdb_object_id,
                                   reqif_id=reset_reqif_id(r),
                                   ce_baseline_origin_id=reset_baseline_origin_id(r),
                                   specobject_id=RQMSpecObject.__number_format__ % (spec_copy_id))
                        for iso_lang in i18n.Languages():
                            description_attr_name = RQMSpecObject.__description_attrname_format__.format(iso=iso_lang)
                            if description_attr_name in spec_text_fields:
                                for t in sqlapi.RecordSet2(description_attr_name,
                                                           "cdb_object_id = '%s'" % r.cdb_object_id):
                                    t.copy(cdb_object_id=old_id_new_id[r.cdb_object_id])
                        new_spec_object_ids.append(old_id_new_id[r.cdb_object_id])
                    # copy acceptance criterions
                    new_target_value_object_ids = []
                    if copyTargetValues:
                        targetv_text_fields = TargetValue.GetTextFieldNames()
                        tvrs = sqlapi.RecordSet2(
                            "cdbrqm_target_value",
                            "specification_object_id = '%s'" % source.cdb_object_id)
                        tv_copy_id = util.nextval(TargetValue.__number_key__, len(tvrs)) - len(tvrs)
                        for r in tvrs:
                            if indexing:
                                args = dict(
                                    cdb_object_id=old_id_new_id[r.cdb_object_id],
                                    specification_object_id=self.cdb_object_id,
                                    requirement_object_id=old_id_new_id[r.requirement_object_id] if r.requirement_object_id else "",
                                    template_oid=r.cdb_object_id,
                                    reqif_id=reset_reqif_id(r),
                                    ce_baseline_origin_id=reset_baseline_origin_id(r),
                                    **static_kwargs
                                )
                                if not ce_baseline_id:
                                    args['ce_baseline_object_id'] = old_id_new_id[r.cdb_object_id]
                                r.copy(**args)
                            else:
                                tv_copy_id += 1
                                r.copy(cdb_object_id=old_id_new_id[r.cdb_object_id],
                                       ce_baseline_object_id=old_id_new_id[r.cdb_object_id],
                                       specification_object_id=self.cdb_object_id,
                                       requirement_object_id=old_id_new_id[
                                           r.requirement_object_id] if r.requirement_object_id else "",
                                       template_oid=r.cdb_object_id,
                                       reqif_id=reset_reqif_id(r),
                                       ce_baseline_origin_id=reset_baseline_origin_id(r),
                                       targetvalue_id=TargetValue.__number_format__ % (tv_copy_id))
                            for iso_lang in i18n.Languages():
                                description_attr_name = TargetValue.__description_attrname_format__.format(
                                    iso=iso_lang)
                                if description_attr_name in targetv_text_fields:
                                    for t in sqlapi.RecordSet2(description_attr_name,
                                                               "cdb_object_id = '%s'" % r.cdb_object_id):
                                        t.copy(cdb_object_id=old_id_new_id[r.cdb_object_id])
                            new_target_value_object_ids.append(old_id_new_id[r.cdb_object_id])
                    # copy semantic links
                    for sl_obj_id in list(set(context_sl_ids)):
                        for r in sqlapi.RecordSet2("cdb_semantic_link",
                                                   "cdb_object_id = '%s'"
                                                   % sl_obj_id):
                            new_object_object_id = r.object_object_id
                            new_subject_object_id = r.subject_object_id
                            object_cdb_obsolete = r.object_cdb_obsolete
                            subject_cdb_obsolete = r.subject_cdb_obsolete
                            if r.object_object_id in total_ids:
                                new_object_object_id = old_id_new_id[new_object_object_id]
                                object_cdb_obsolete = 0
                            if r.subject_object_id in total_ids:
                                new_subject_object_id = old_id_new_id[new_subject_object_id]
                                subject_cdb_obsolete = 0
                            mirror_id = ""
                            if r.mirror_link_object_id in old_id_new_id:
                                mirror_id = old_id_new_id[r.mirror_link_object_id]
                            r.copy(cdb_object_id=old_id_new_id[r.cdb_object_id],
                                   mirror_link_object_id=mirror_id,
                                   subject_object_id=new_subject_object_id,
                                   object_object_id=new_object_object_id,
                                   object_cdb_obsolete=object_cdb_obsolete,
                                   subject_cdb_obsolete=subject_cdb_obsolete)
                    # copy classification
                    update_solr_index_ids = []
                    for cl_obj_id in context["classification_cache"]:
                        if cl_obj_id == source.cdb_object_id and not baseline_copy:
                            # spec classification is copied by classification sig handler
                            # due to copy operation
                            continue
                        # copy assigned classes
                        if (
                            cl_obj_id in total_ids and
                            old_id_new_id[cl_obj_id] not in update_solr_index_ids
                        ):
                            rset = sqlapi.RecordSet2(
                                ClassificationChecksum.__maps_to__, "ref_object_id='%s'"
                                % cl_obj_id
                            )
                            if rset:
                                checksum = rset[0]
                                checksum.copy(ref_object_id=old_id_new_id[cl_obj_id])
                            rset = sqlapi.RecordSet2(
                                ObjectClassification.__maps_to__, "ref_object_id='%s'" % cl_obj_id
                            )
                            if len(rset) > 0:
                                update_solr_index_ids.append(old_id_new_id[cl_obj_id])
                            for r in rset:
                                r.copy(
                                    id=cdbuuid.create_uuid(),
                                    ref_object_id=old_id_new_id[cl_obj_id]
                                )

                            # copy property values
                            rset = sqlapi.RecordSet2(
                                ObjectPropertyValue.__maps_to__, "ref_object_id='%s'" % cl_obj_id
                            )
                            if len(rset) > 0:
                                update_solr_index_ids.append(old_id_new_id[cl_obj_id])
                            for r in rset:
                                r.copy(id=cdbuuid.create_uuid(),
                                       ref_object_id=old_id_new_id[cl_obj_id])
                    qcs = ObjectQualityCharacteristic.KeywordQuery(cdbf_object_id=qcs_ids)

                    if indexing:
                        for qc in qcs:
                            qc.Copy(cdbf_object_id=old_id_new_id[qc.cdbf_object_id])
                    else:
                        created_qc_object_ids = set()
                        for qc in qcs:
                            qc.Copy(cdbf_object_id=old_id_new_id[qc.cdbf_object_id],
                                    act_value=None)
                            created_qc_object_ids.add(old_id_new_id[qc.cdbf_object_id])
                        self._createMissingSubQCs(
                            source=source,
                            req_ids=new_spec_object_ids,
                            tv_ids=new_target_value_object_ids,
                            already_existent_ids=created_qc_object_ids
                        )
                        change_control_values = SemanticLink.MakeChangeControlAttributes()

                        def createCopyLink(obj):
                            source_classname = dest_classname = obj.GetClassname()
                            copy_link_type = SemanticLinkType.getValidLinkTypes(
                                subject_object_classname=dest_classname,
                                object_object_classname=source_classname,
                                is_copy_link_type=1)
                            copy_link_type = copy_link_type[0] if copy_link_type else None
                            if copy_link_type:
                                sem_link = SemanticLink.Create(
                                    link_type_object_id=copy_link_type.cdb_object_id,
                                    subject_object_id=old_id_new_id[obj.cdb_object_id],
                                    object_object_id=obj.cdb_object_id,
                                    subject_object_classname=dest_classname,
                                    object_object_classname=source_classname,
                                    **change_control_values)
                                sem_link.generateMirrorLink()

                        createCopyLink(source)
                        for r in source.Requirements:
                            createCopyLink(r)
                        if copyTargetValues:
                            for t in source.TargetValues:
                                createCopyLink(t)

                    def partition(l, n):
                        for i in range(0, len(l), n):
                            yield l[i:i + n]

                    if copyDocuments:
                        for r in sqlapi.RecordSet2("cdbrqm_specification2doc",
                                                   "spec_object_id = '%s'" % source.cdb_object_id):
                            r.copy(spec_object_id=self.cdb_object_id)
                        if len(context["spec_object_cache"]) > 500:
                            for parts in partition(context["spec_object_cache"], 500):
                                for r in sqlapi.RecordSet2("cdbrqm_specobject2doc",
                                                           "specobject_object_id in ('%s')" % "','".join(parts)):
                                    r.copy(specobject_object_id=old_id_new_id[r.specobject_object_id])
                        else:
                            for r in sqlapi.RecordSet2("cdbrqm_specobject2doc",
                                                       "specobject_object_id in ('%s')" % "','".join(context["spec_object_cache"])):
                                r.copy(specobject_object_id=old_id_new_id[r.specobject_object_id])

                    # copy Files
                    if baseline_copy:
                        old_pfiles = list(old_id_new_id)
                    else:
                        # in copy cases the root element is copied by the kernel
                        # which copies files also
                        old_pfiles = [x for x in old_id_new_id.keys() if x != source.cdb_object_id]
                    if len(old_pfiles) > 500:
                        for parts in partition(old_pfiles, 500):
                            for r in sqlapi.RecordSet2(
                                "cdb_file",
                                "%s" % CDB_File.cdbf_object_id.one_of(*parts)
                            ):
                                r.copy(cdbf_object_id=old_id_new_id[r.cdbf_object_id])
                    else:
                        for r in sqlapi.RecordSet2(
                            "cdb_file",
                            "%s" % CDB_File.cdbf_object_id.one_of(*old_pfiles)
                        ):
                            r.copy(cdbf_object_id=old_id_new_id[r.cdbf_object_id])

                    # copy issues
                    if len(context["spec_object_cache"]) > 500:
                        for parts in partition(context["spec_object_cache"], 500):
                            for r in sqlapi.RecordSet2("cdbrqm_specobject2issue",
                                                       "specobject_object_id in ('%s')" % "','".join(
                                                           parts)):
                                r.copy(specobject_object_id=old_id_new_id[r.specobject_object_id])
                    else:
                        for r in sqlapi.RecordSet2("cdbrqm_specobject2issue",
                                                   "specobject_object_id in ('%s')" % "','".join(
                                                       context["spec_object_cache"])):
                            r.copy(specobject_object_id=old_id_new_id[r.specobject_object_id])

                    if indexing:
                        auos = AuditTrailObjects.KeywordQuery(object_id=source.cdb_object_id)
                        for au in auos:
                            au.Copy(object_id=self.cdb_object_id)

                if update_solr_index_ids:
                    from cs.classification import solr
                    for obj_id in update_solr_index_ids:
                        solr.index_object(objects.ByID(obj_id))
            else:
                kwargs.update(dict(cdb_classname=self.GetClassname(),
                                   root_dst_obj=self,
                                   specification_object_id=self.cdb_object_id))
                if source_obj is not None:
                    return super(RQMSpecification, self).copy_subobjects(ctx, source, processed_objs, semlinks_to_create, **kwargs)
                else:
                    super(RQMSpecification, self).copy_subobjects(ctx, source, processed_objs, semlinks_to_create, **kwargs)

    def presetCategory(self, ctx):
        if not self.category:
            name = ""
            default_category = RQMSpecificationCategory.get_default_category()
            if default_category:
                name = default_category.name
            ctx.set('category', name)

    def presetProductProject(self, ctx):
        if ctx.relationship_name == 'cdbrqm_project2specifications':
            ctx.set("cdb_project_id", ctx.parent.cdb_project_id)
            from cs.pcs.projects import Project
            ctx.set("project_name", Project.ByKeys(ctx.parent.cdb_project_id).project_name)
        elif ctx.relationship_name == 'cdbrqm_product2specifications':
            ctx.set("product_object_id", ctx.parent.cdb_object_id)
            from cs.vp.products import Product
            ctx.set("product_code", Product.ByKeys(ctx.parent.cdb_object_id).code)

    def get_highest_revision(self):
        sql = ("select max(revision) maxno from cdbrqm_specification where "
               "spec_id = '%s'" %
               (self.spec_id))
        r = sqlapi.RecordSet2(sql=sql)
        # default value: 1
        rno = 1
        try:
            # try to increase the number
            rno = int(r[0].maxno)
        except (IndexError, AttributeError, ValueError, TypeError):
            return None
        return rno

    def gen_revision(self):
        """
        Generate the revision number of the Specificaiton object.
        """
        # find out the max value in database
        highest_revision = self.get_highest_revision()
        if highest_revision is None:
            return 1
        return highest_revision + 1

    def create_new_revision(self, ctx):
        opargs = [("followup_cdbrqm_new_revision", 1)]
        predefined = []
        ctx.set_followUpOperation("CDB_Copy",
                                  opargs=opargs,
                                  predefined=predefined)

    def setRevision(self, ctx):
        if "followup_cdbrqm_new_revision" not in \
                ctx.ue_args.get_attribute_names():
            return
        if len(self.PreviousVersions):
            if self.PreviousVersions[-1].status in [RQMSpecification.RELEASED.status, RQMSpecification.DRAFT.status]:
                self.PreviousVersions[-1].ChangeState(RQMSpecification.REVISION.status, check_access=0)

    def resetRevision(self, ctx):
        prev = len(self.PreviousVersions)
        if prev and prev == len(self.OtherVersions):
            last_one = self.PreviousVersions[-1]
            if last_one.status == RQMSpecification.REVISION.status and last_one.LastStateProtocolEntry is not None:
                last_one.ChangeState(last_one.LastStateProtocolEntry.cdbprot_oldstate)

    def disableMaskonIndex(self, ctx):
        if "followup_cdbrqm_new_revision" in \
                ctx.ue_args.get_attribute_names():
            ctx.skip_dialog()

    def presetRevision(self, ctx):
        if "followup_cdbrqm_new_revision" not in \
                ctx.ue_args.get_attribute_names():
            ctx.set("revision", 0)
        else:
            ctx.set("revision", self.gen_revision())

    def getAuditTrailEntries(self):
        object_ids = {self.cdb_object_id: self.GetClassname()}
        for spec in RQMSpecification.Query("spec_id='%s'" % self.spec_id):
            object_ids[spec.cdb_object_id] = RQMSpecification.__classname__
            if spec.Requirements:
                for obj_id in spec.Requirements.cdb_object_id:
                    object_ids[obj_id] = RQMSpecObject.__classname__
            if spec.TargetValues:
                for obj_id in spec.TargetValues.cdb_object_id:
                    object_ids[obj_id] = TargetValue.__classname__
        return object_ids

    def createAuditTrailEntry(self, ctx=None):
        if ctx is not None and "followup_cdbrqm_new_revision" in \
                ctx.ue_args.get_attribute_names():
            self.createAuditTrail('create_index')
        else:
            super(RQMSpecification, self).createAuditTrailEntry(ctx)

    def open_specification_editor(self, ctx):
        ctx.url("/info/specification/%s" % self.cdb_object_id, view_extern=1, icon="")

    @classmethod
    def switch_to_spec_object(cls, ctx):
        ctx.url("/info/spec_object")

    @classmethod
    def _disable_classification_web_registers(cls, ctx):
        if not ctx.uses_webui:
            ctx.disable_registers(['cs_classification_tab_web', 'cs_classification_tab_c_web', 'cs_classification_tab_s_web'])

    def on_cdbrqm_rating_import_now(self, ctx):
        rqm_rating_cls = ClassificationClass.ByKeys(code='RQM_RATING')
        # Block processing if the system does not contain the rating class
        if rqm_rating_cls is not None:
            # Process for logging
            process_run = operations.operation(
                "CDB_Create", RQMImportProcessRun,
                specification_object_id=self.cdb_object_id,
                import_type="Excel Import"
            )
            # Save process id
            process_run_id = process_run.cdb_object_id
            # Create a protocol using said process id
            protocol = operations.operation(
                "CDB_Create", RQMProtocol,
                cdbf_object_id=process_run.cdb_object_id,
                protocol_id=1,
                action="Preparation"
            )
            # Logger creation
            logger_extra_args = dict(
                tags=['rqm_protocol'],
                specification_object_id=self.cdb_object_id
            )
            with RQMProtocolLogging(protocol) as logger:
                # Save Specification id from self object
                ctx.keep('spec_id_context', self.spec_id)
                # Retrieve rated by from dialog
                rated_by_id = ctx.dialog.bewerter
                ctx.keep('rated_by', rated_by_id)
                # Retrieve Excel file path
                client_path = ctx.dialog.import_excel
                if client_path is None or client_path == '':
                    logger.info('The provided file is empty: %s', client_path, extra=logger_extra_args)
                    raise ue.Exception("cdbrqm_not_excel", client_path)
                # Save file name for storing
                source_filename = os.path.basename(client_path)
                ctx.keep('source_filename', source_filename)
                # Validate that the path exists and it contains a valid xlsx file
                allowed_ext = ['.xlsx', 'xlsm', 'xltx', 'xltm']
                if not client_path.endswith(tuple(allowed_ext)):
                    logger.info('The provided file is not a valid Excel file', extra=logger_extra_args)
                    raise ue.Exception("cdbrqm_not_excel", client_path)
                # Temporary file
                f_temp = tempfile.NamedTemporaryFile(
                    prefix='rating_import_f',
                    delete=False
                )
                # Append extension since openpyxl requires it
                temp_name_with_excel_extension = "{}.xlsx".format(f_temp.name)
                # Save the clients file to the server
                logger.info('Downloading file from client to server: %s to %s', client_path, f_temp.name, extra=logger_extra_args)
                ctx.download_from_client(client_path,
                                         temp_name_with_excel_extension,
                                         delete_file_after_download=0
                                         )
                # Keep important ids.
                ctx.keep('importpath', temp_name_with_excel_extension)
                ctx.keep('process_run_id', process_run_id)
                ctx.keep('protocol_id', protocol.protocol_id)
        else:
            ctx.keep('invalid_system', True)
            raise ue.Exception("cdbrqm_unsupported_operation")

    def on_cdbrqm_rating_import_post(self, ctx):
        # Guard from final to post again:
        if (
            'end_of_import' not in ctx.dialog.get_attribute_names() and
            'invalid_system' not in ctx.dialog.get_attribute_names()
        ):
            # Recover path to file, spec_id, file and rated by
            process_run_id = ctx.ue_args['process_run_id']
            path_to_file = ctx.ue_args['importpath']
            spec_id_context = ctx.ue_args['spec_id_context']
            index_context = self.revision
            rated_by = ctx.ue_args['rated_by']
            # Recover process
            process_run = RQMImportProcessRun.ByKeys(cdb_object_id=process_run_id)
            # Create a protocol using said process id
            protocol = operations.operation(
                "CDB_Create", RQMProtocol,
                cdbf_object_id=process_run.cdb_object_id,
                protocol_id=2,
                action="Execution"
            )
            logger_extra_args = dict(
                tags=['rqm_protocol'],
                specification_object_id=self.cdb_object_id
            )
            success = False
            with RQMProtocolLogging(protocol) as logger:
                try:
                    importPath = ctx.ue_args['importpath']
                    source_filename = ctx.ue_args['source_filename']
                    ftype = getFileTypeByFilename(source_filename)
                    CDB_File.NewFromFile(process_run_id,
                                         importPath,
                                         primary=True,
                                         additional_args=dict(cdbf_name=source_filename,
                                                              cdbf_type=ftype.getName()))
                    success = False
                    # Create Rating object and trigger round trip functios
                    req_update = rating.Rating(path_to_file, rated_by, spec_id_context, index_context)
                    req_update.trigger(logger, logger_extra_args)
                    process_run.import_status = RQMImportProcessRun.FINISHED
                    success = True
                except ExcelImportError as e:
                    logger.exception(e)
                    raise e
                finally:
                    if not success:
                        ctx.keep('failure_on_exit', "failure")
                        process_run.import_status = RQMImportProcessRun.FAILED

    def on_cdbrqm_rating_import_final(self, ctx):
        if (
            "failure_on_exit" not in ctx.ue_args.get_attribute_names() and
            'end_of_import' not in ctx.dialog.get_attribute_names() and
            'invalid_system' not in ctx.dialog.get_attribute_names()
        ):
            msgbox = ctx.MessageBox("cdbrqm_excel_import_success",
                                    "",
                                    "end_of_import",
                                    ctx.MessageBox.kMsgBoxIconInformation)
            msgbox.addButton(ctx.MessageBoxButton("button_cad_bind",
                                                  ctx.MessageBox.kMsgBoxResultYes,
                                                  is_dflt=1))
            ctx.show_message(msgbox)

    def enhance_search_condition(self, ctx):
        BaselineTools.enhance_search_condition(self, ctx)

    def open_diff_app(self, ctx):
        if BaselineTools.is_baseline(self):
            left_object_id = self.cdb_object_id
            current_object = BaselineTools.get_current_obj(self)
            right_object_id = current_object.cdb_object_id if current_object else ''
        else:
            left_object_id = ''
            right_object_id = self.cdb_object_id
        from cs.requirements.web.diff.main import MOUNT_PATH
        ctx.url("{mount_path}/{left_object_id}/{right_object_id}".format(
            left_object_id=left_object_id,
            right_object_id=right_object_id,
            mount_path=MOUNT_PATH
        ))

    def delete_sub_elements(self, ctx):
        self.remove_all_baseline_elements(ce_baseline_id='')

    event_map = {
        ('cdbrqm_create_from_template', 'now'): "create_from_template",
        ('create', ('pre_mask', 'pre')): ("presetCategory", "presetRevision"),
        ('copy', ('pre_mask', 'pre')): ("presetRevision", "presetProductProject", "disableMaskonIndex"),
        ('copy', 'post'): ("update_sortorder", "adjust_fulfillment_kpi_active", "setRevision"),
        ('cdbrqm_update_sortorder', 'now'): ("recalculate_positions", "update_sortorder"),
        ('cdbrqm_new_revision', 'now'): "create_new_revision",
        ('delete', 'post'): ("resetRevision", "delete_sub_elements"),
        ('cdbrqm_open_specification_editor', 'now'): 'open_specification_editor',
        ('cdbrqm_switch_web_to_spec_object', 'now'): 'switch_to_spec_object',
        (('create', 'copy', 'modify', 'query', 'requery'), 'pre_mask'): '_disable_classification_web_registers',
        ('cdbrqm_diff', 'now'): 'open_diff_app',
        (('query', 'requery', 'query_catalog'), 'pre'): "enhance_search_condition"
    }


class TargetValue(Object, WithSemanticLinks, WithQualityCharacteristic, WithRQMBase, WithAuditTrail):

    __classname__ = "cdbrqm_target_value"
    __maps_to__ = "cdbrqm_target_value"
    __maps_to_view__ = "cdbrqm_target_value_v"
    __parent_object_id_field__ = "requirement_object_id"
    __context_object_id_field__ = "specification_object_id"
    __description_attrname_format__ = "cdbrqm_target_value_desc_{iso}"
    __short_description_attrname_format__ = "name_{iso}"
    __number_format__ = "A%09d"
    __readable_id_field__ = "targetvalue_id"
    __number_key__ = "RQM_TV_NR_SEQ"

    Requirement = RQMSpecObject = references.Reference_1(
        fRQMSpecObject, fRQMSpecObject.cdb_object_id == fTargetValue.requirement_object_id
    )
    Specification = references.Reference_1(
        fRQMSpecification,
        fRQMSpecification.cdb_object_id == fTargetValue.specification_object_id
    )
    Baselines = references.ReferenceMethods_N(fTargetValue,
                                              lambda self: BaselineTools.get_baselines(self))
    BaselineDetails = references.Reference_1(
        Baseline,
        Baseline.ce_baseline_id == fTargetValue.ce_baseline_id
    )

    AllVersions = references.Reference_N(
        fTargetValue,
        fTargetValue.ce_baseline_origin_id == fTargetValue.ce_baseline_origin_id,
        fTargetValue.cdb_object_id != fTargetValue.cdb_object_id  # all other but self
    )

    AllVersionsInIndex = references.Reference_N(
        fTargetValue,
        fTargetValue.ce_baseline_object_id == fTargetValue.ce_baseline_object_id,
        fTargetValue.cdb_object_id != fTargetValue.cdb_object_id  # all other but self
    )

    Files = references.Reference_N(CDB_File, CDB_File.cdbf_object_id == fTargetValue.cdb_object_id)

    def referencedAuditTrailObjects(self):
        refs = [self, self.Specification]
        if self.Requirement:
            refs.append(self.Requirement)
            parent = self.Requirement
            while parent:
                parent = parent.ParentRequirement
                if parent:
                    refs.append(parent)
        return refs

    def on_preview_now(self, ctx):
        preview_url = "/cs-requirements-web-richtext?cdb_object_id=%s&restname=target_value&preview=1&readonly=1&fieldname=cdbrqm_target_value_desc_"
        ctx.setPreviewURL(preview_url % self.cdb_object_id)

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the requirements, specifications, project, product the object itself.
        """
        channels = [self, self.Requirement, self.Specification]
        if self.Specification.Project:
            channels.append(self.Specification.Project)
        if self.Specification.Product:
            channels.append(self.Specification.Product)
        return channels

    def _tree_up_reference(self):
        return self.RQMSpecObject

    def _is_template(self):
        return self.Specification.is_template

    def _isValidTargetValue(self, target_value):
        try:
            TargetProcessor(target_value)
            return True
        except InvalidTargetValue:
            return False

    def ensureLeafReq(self, _):
        if self.Requirement and not self.Requirement.isLeafReq():
            raise ue.Exception("cdbrqm_invalid_parent_req")

    def _set_ctx_id(self, _):
        if self.Requirement:
            self.specification_object_id = self.Requirement.specification_object_id

    def reset_external_fields(self, ctx, source_obj=None):
        source = rqm_utils._get_source_object(self, ctx, TargetValue, source_obj)
        if (
            source is not None and
            "followup_cdbrqm_new_revision" not in ctx.ue_args.get_attribute_names()
        ):
            self.reqif_id = ""
            self.ce_baseline_origin_id = cdbuuid.create_uuid()

    def setQualityType(self, ctx):
        if 'value_type' in ctx.dialog.get_attribute_names() and \
            'value_unit' in ctx.dialog.get_attribute_names() and \
                'target_value_mask' in ctx.dialog.get_attribute_names():
            if ctx.dialog["value_type"] == '1':
                ctx.set("target_value_mask", ">=100")
                ctx.set_readonly("target_value_mask")
                ctx.set("value_unit", "%")
                ctx.set_readonly("mapped_unit")
            else:
                if (ctx.action != "info"):
                    ctx.set_writeable("target_value_mask")
                    ctx.set_writeable("mapped_unit")

    def set_act_value(self, act_value, guetegrad=None):
        fls.allocate_license('RQM_035')
        self.Reload()
        if act_value is not None and self._isValidActValue(act_value=act_value)[0]:
            if guetegrad is None:
                guetegrad = 'manuell'
            old_value = self.act_value
            qcd = rqm_utils.getQCFulfillmentDef()
            qc = self.ObjectQualityCharacteristics.KeywordQuery(cdbqc_def_object_id=qcd.cdb_object_id)[0]
            qc.set_actual_value(act_value, guetegrad=guetegrad)

            if old_value != act_value:
                audittrail = self.createAuditTrail('modify')
                if audittrail:
                    self.createAuditTrailDetail(
                        audittrail_object_id=audittrail.audittrail_object_id,
                        clsname=self.GetClassname(),
                        attribute="act_value",
                        old_value=old_value,
                        new_value=act_value
                    )

    def set_target_value(self, target_value, with_audittrail=True):
        fls.allocate_license('RQM_035')
        old_target_value = self.target_value
        qcd = rqm_utils.getQCFulfillmentDef()
        try:
            qc = self.ObjectQualityCharacteristics.KeywordQuery(cdbqc_def_object_id=qcd.cdb_object_id)[0]
            qc.set_target_value(target_value)
        except IndexError:
            rqm_utils.createQC(**{
                'cdbf_object_id': self.cdb_object_id,
                'classname': self.GetClassname(),
                'target_value': target_value
            })
        if with_audittrail and old_target_value != target_value:
            audittrail = self.createAuditTrail('modify')
            if audittrail:
                self.createAuditTrailDetail(
                    audittrail_object_id=audittrail.audittrail_object_id,
                    clsname=self.GetClassname(),
                    attribute="target_value",
                    old_value=old_target_value,
                    new_value=target_value
                )

    def _set_target_value(self, ctx):
        if 'target_value_mask' in ctx.ue_args.get_attribute_names():
            target_value = ctx.ue_args.target_value_mask
            self.set_target_value(target_value)

    def _isValidActValue(self, ctx=None, act_value=None):
        if (ctx and 'act_value_mask' in ctx.dialog.get_attribute_names()) or act_value is not None:
            if ctx:
                act_val = ctx.dialog['act_value_mask']
            else:
                act_val = act_value
            # qualitative/numeric target value
            if act_val == "":
                return (True, None)
            else:
                if self.value_type == 1:
                    if rqm_utils.isValidFloat(act_val, (0.0, 100.0)):
                        return (True, None)
                    else:
                        return(False, "cdbrqm_invalid_act_value")
                else:
                    if rqm_utils.isValidFloat(act_val):
                        return (True, None)
                    else:
                        return (False, "cdbrqm_invalid_act_value_float")

    def validateActValue(self, ctx=None):
        valid, err = self._isValidActValue(ctx)
        if not valid:
            raise ue.Exception(err)

    def isFulfilled(self, act_value, target_value):
        if self.value_type == 1:
            return 100.0 == act_value
        else:
            tp = TargetProcessor(target_value)
            if rqm_utils.isValidFloat(act_value) and \
               tp(act_value):
                return True
            else:
                return False

    def fillVirtualAttributes(self, ctx=None):
        if ctx:
            ctx.set("target_value_mask", self.target_value)

    def keepArgs(self, ctx=None):
        if ctx and 'target_value_mask' in ctx.dialog.get_attribute_names():
            ctx.keep("target_value_mask", ctx.dialog["target_value_mask"])

    def validateTargetValue(self, ctx):
        if ctx and 'target_value_mask' in ctx.dialog.get_attribute_names():
            if not self._isValidTargetValue(ctx.dialog["target_value_mask"]):
                raise ue.Exception("cdbrqm_invalid_target_value")

    def check_qcd_active(self, ctx):
        qcd = rqm_utils.getQCFulfillmentDef()
        if qcd and not rqm_utils.isValidFulfillmentDef(qcd):
            if (self.target_value != ctx.dialog['target_value_mask']):
                if (ctx.dialog["target_value_mask"] is not None and
                    ctx.dialog["target_value_mask"] != '' and
                        ctx.dialog['value_type'] != '1'):
                    raise ue.Exception("cdbrqm_qcd_not_active")

    def setSpecification(self, ctx):
        if self.Requirement and self.Requirement.specification_object_id:
            ctx.set('specification_object_id', self.Requirement.specification_object_id)

    def check_rights_evaluate(self, ctx):
        failed = []
        failed_objs = []
        value_type = None
        value_unit = None
        target_value = None
        act_value = None
        target_value_differs = False
        act_value_differs = False

        for obj in self.PersistentObjectsFromContext(ctx):
            if value_type is None:
                value_type = obj.value_type
                value_unit = obj.value_unit
            elif value_type != obj.value_type:
                raise ue.Exception("cdbrqm_value_type_differs")
            elif value_unit != obj.value_unit:
                raise ue.Exception("cdbrqm_value_unit_differs")
            if target_value is None:
                target_value = obj.target_value
            elif target_value != obj.target_value:
                target_value_differs = True
            if act_value is None:
                act_value = obj.act_value
            elif act_value != obj.act_value:
                act_value_differs = True

        # may not edit any object
        if len(ctx.objects) == len(failed):
            raise ue.Exception('cdbrqm_evaluate_all_failed')
        if failed and 'question_bm_ask_continue' not in ctx.dialog.get_attribute_names():
            if len(failed) > 5:
                failed = failed[:5]
                failed.append("...")
            msgbox = ctx.MessageBox('cdbrqm_evaluate_ask_continue', ['\n'.join(failed)],
                                    'question_evaluate_ask_continue', ctx.MessageBox.kMsgBoxIconQuestion)
            msgbox.addButton(ctx.MessageBoxButton('button_skip', 'skip'))
            msgbox.addCancelButton()
            ctx.keep('failed_objs', ';'.join(failed_objs))
            ctx.show_message(msgbox)
        ctx.set("value_unit", value_unit)
        ctx.set("value_type", value_type)
        if not target_value_differs:
            ctx.set("target_value_mask", target_value)
        if not act_value_differs:
            ctx.set("act_value_mask", act_value)

    def execute_evaluate(self, ctx):
        if self.cdb_object_id == ctx.objects[0].cdb_object_id:
            with transactions.Transaction():
                for obj in self.PersistentObjectsFromContext(ctx):
                    self.validateActValue(ctx)
                    if 'failed_objs' in ctx.ue_args.get_attribute_names() and \
                       obj.cdb_object_id in ctx.ue_args.failed_objs:
                        continue
                    obj.set_act_value(act_value=ctx.dialog.act_value_mask)

    def setEvaluationDate(self, ctx):
        if self.cdb_object_id == ctx.objects[0].cdb_object_id:
            for obj in self.PersistentObjectsFromContext(ctx):
                if 'failed_objs' in ctx.ue_args.get_attribute_names() and \
                   obj.cdb_object_id in ctx.ue_args.failed_objs:
                    continue
                obj.Update(cdbrqm_edate=datetime.datetime.now(),
                           cdbrqm_epersno=auth.persno)

    @classmethod
    def _tv_item_set_position_pre_mask(cls, ctx):
        if ctx.uses_webui:
            specification_object_id, requirement_object_id, _ = rqm_utils.get_objects_to_move_data(
                cls, ctx, 'requirement_object_id'
            )
            ctx.set('requirement_object_id', requirement_object_id)
            ctx.set('specification_object_id', specification_object_id)

    @classmethod
    def _tv_item_set_position_now(cls, ctx):
        specification_object_id, requirement_object_id, objs_to_move = rqm_utils.get_objects_to_move_data(
            cls, ctx, 'requirement_object_id'
        )

        if not ctx.uses_webui and not ctx.catalog_selection:
            browser_attr = {
                "requirement_object_id": requirement_object_id,
                "specification_object_id": specification_object_id
            }
            ctx.start_selection(catalog_name="cdbrqm_target_value_brows", **browser_attr)
        else:
            if ctx.uses_webui:
                if ctx.dialog.new_predecessor:
                    selected_target = TargetValue.ByKeys(ctx.dialog.new_predecessor)
                else:
                    raise ue.Exception("cdbrqm_no_pos")
            else:
                selected_target = TargetValue.ByKeys(ctx.catalog_selection[0]["cdb_object_id"])
            cls._move_target_positions(specification_object_id, selected_target, objs_to_move)
            cls._resetPositions(selected_target)
            util.refresh_structure_node(selected_target.requirement_object_id, 'cdbrqm_spec_object_overview')
            util.refresh_structure_node(selected_target.requirement_object_id, 'cdbrqm_specification_overview')

    @classmethod
    def _resetPositions(cls, selected_target):
        spec_objs = TargetValue.KeywordQuery(specification_object_id=selected_target.specification_object_id,
                                             requirement_object_id=selected_target.requirement_object_id, order_by='pos')
        i = 1
        # TODO: Perfomance
        for spec_obj in spec_objs:
            spec_obj.position = i
            i += 1

    @classmethod
    def _move_target_positions(cls, specification_object_id, selected_target, targets_to_move):
        if selected_target is not None:
            target_field = int(selected_target.pos)
            positions_to_move = len(targets_to_move)
            qry = "UPDATE %s" \
                  " SET pos = pos+%d" \
                  " WHERE specification_object_id='%s'" \
                  " AND requirement_object_id='%s'" \
                  " AND pos > %d" % (cls.__maps_to__,
                                     positions_to_move,
                                     specification_object_id,
                                     selected_target.requirement_object_id,
                                     target_field)
            sqlapi.SQL(qry)
            for target in targets_to_move:
                target_field += 1
                target.pos = target_field

    def makePosition(self, ctx=None):
        return TargetValue.lookupPosition(self.requirement_object_id,
                                          specification_object_id=self.specification_object_id)

    @classmethod
    def lookupPosition(cls, requirement_object_id, specification=None, specification_object_id=None):
        position = 1
        if specification is None and specification_object_id is not None:
            specification = RQMSpecification.ByKeys(cdb_object_id=specification_object_id)
            specification = specification if specification is None or specification.CheckAccess("read") else None
        if specification:
            position = 1
            mymax = sqlapi.RecordSet2(cls.__maps_to__,
                                      (TargetValue.specification_object_id == specification.cdb_object_id) &
                                      (TargetValue.requirement_object_id == requirement_object_id),
                                      columns=["MAX(pos) p"])
            if mymax and mymax[0].p:
                position = int(mymax[0].p) + 1
        return position

    @classmethod
    def makeNumber(cls):
        return WithRQMBase.makeNumber(cls)

    def setNumber(self, ctx=None):
        self.targetvalue_id, _ = TargetValue.makeNumber()
        self.cdb_object_id = cdbuuid.create_uuid()
        self.ce_baseline_object_id = self.cdb_object_id
        self.ce_baseline_origin_id = cdbuuid.create_uuid()

    def get_reqif_long_name(self):
        return self.targetvalue_id

    def get_reqif_description(self):
        return self.name

    @classmethod
    def tree_copy_pre_cb_func(cls, source_obj, static_properties, **kwargs):
        attrs = WithRQMBase.tree_copy_pre_cb_func(source_obj, static_properties, **kwargs)
        level = kwargs.get('level', 0)
        followup_cdbrqm_new_revision = kwargs.get("followup_cdbrqm_new_revision", 0)
        if level != 0 and followup_cdbrqm_new_revision == 0:
            new_tv_id, new_req_maxno = TargetValue.makeNumber()
            attrs.update(dict(
                targetvalue_id=new_tv_id,
                maxno=new_req_maxno
            ))
        return attrs

    def initialize_fulfillment_kpi_active(self, ctx=None):
        self.fulfillment_kpi_active = 1

    def readonlyRichtext(self, ctx):
        if (
            not self.CheckAccess("rqm_richtext_save") or
            not self.CheckAccess("save") or
            ctx.action == 'info'
        ):
            readonly_url = '/cs-requirements-web-richtext?readonly=1&restname=target_value&cdb_object_id={}'.format(
                self.cdb_object_id
            )
            ctx.set_elink_url(
                "richtext_desc", readonly_url
            )
            ctx.set_readonly(".richtext_desc")

    def ask_user_fulfillment(self, ctx):
        # Create a message box
        msgbox = ctx.MessageBox(
            "cdbrqm_ask_user_fulfillment",
            [],
            "question_fulfillment",
            ctx.MessageBox.kMsgBoxIconQuestion
        )
        msgbox.addYesButton(1)
        msgbox.addNoButton()
        msgbox.addCancelButton()
        ctx.show_message(msgbox)

    def check_fulfillment_modify(self, ctx):
        if "question_fulfillment" not in ctx.dialog.get_attribute_names():
            if self.act_value:
                self.ask_user_fulfillment(ctx)
        else:
            result = ctx.dialog["question_fulfillment"]
            if result == ctx.MessageBox.kMsgBoxResultYes:
                tf_kpi = self.FulfillmentQualityCharacteristic
                if tf_kpi:
                    tf_kpi.set_actual_value(None, guetegrad=u"manuell")

    def addQCArguments(self, args, ctx=None):
        target_value = None
        if ctx and 'target_value_mask' in ctx.ue_args.get_attribute_names():
            target_value = ctx.ue_args['target_value_mask']
        if target_value:
            args.update({
                'target_value': target_value
            })
            audittrail = self.createAuditTrail('modify')
            if audittrail:
                self.createAuditTrailDetail(
                    audittrail_object_id=audittrail.audittrail_object_id,
                    clsname=self.GetClassname(),
                    attribute="target_value",
                    old_value=">=100",
                    new_value=target_value
                )

    event_map = {(('copy', 'create', 'modify'), ('dialogitem_change', 'pre_mask')): 'setQualityType',
                 (('create', 'modify', 'copy'), 'post_mask'): ('validateTargetValue'),
                 ('modify', 'post_mask'): 'check_qcd_active',
                 (('modify', 'info'), 'pre_mask'): 'readonlyRichtext',
                 ('create', 'pre_mask'): 'ensureLeafReq',
                 ('modify', 'post_mask'): ('ensureLeafReq', 'check_fulfillment_modify'),
                 (('copy', 'create', 'modify'), 'pre'): '_set_ctx_id',
                 (('modify'), 'post'): '_set_target_value',
                 (('create', 'copy'), 'pre_mask'): 'setSpecification',
                 ('cdbrqm_evaluate', 'pre_mask'): 'check_rights_evaluate',
                 ('cdbrqm_evaluate', 'post_mask'): 'validateActValue',
                 ('cdbrqm_evaluate', 'now'): 'execute_evaluate',
                 ('cdbrqm_evaluate', 'post'): 'setEvaluationDate',
                 }
