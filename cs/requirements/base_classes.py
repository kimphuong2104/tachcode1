# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import collections
import datetime
import json
import logging
import re
from os import environ

import lxml.etree
from cdb import auth, cdbuuid, transactions, ue, util
from cdb.objects import ByID, ObjectCollection, references
from cs.baselining.support import BaselineTools
from cs.classification import api as classification_api
from cs.metrics.qualitycharacteristics import QualityCharacteristic
from cs.platform.web import uisupport
from cs.requirements import rqm_utils
from cs.requirements.classes import AuditTrailDetailRichText
from cs.tools import semanticlinks
from cs.requirements.richtext import RichTextModifications

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

LOG = logging.getLogger(__name__)


class WithReqIFBase(object):
    # objects with this class should be cdb.objects.Object instances and
    # should have at least the following attributes
    # cdb_mdate, reqif_id, cdb_object_id
    # and should also be an instance of WithSemanticLinks

    def _tree_up_reference(self):
        raise NotImplementedError()

    def _tree_down_reference(self):
        raise NotImplementedError()

    def get_reqif_long_name(self):
        raise NotImplementedError()

    def get_reqif_description(self):
        raise NotImplementedError()


class WithRQMTreeLogic(WithReqIFBase):

    def _tree_up_reference(self):
        return None

    def _tree_down_reference(self):
        return None

    def _walk(self, obj, func, parent=None, level=0, depth=-1, post=False, up=False,
              with_context_update=False, context_keys_to_reset_after_siblings=None,
              **context_data):
        """walks the tree up or down and executes func on elements of it.
        tree reference methods _tree_up_reference and _tree_down_reference
        to walk up/down the tree must be available

        :param func: function to be executed on elements in the walked tree
        must have the following signature :
        (parent, obj, next_elems, level, **context_data)
        :type func: callable
        :param post: indicates whether the children of an element are processed
        after the element itself (True) or before the element (False).
        :type post: bool
        :param with_context_update: indicate whether the given context_data
        should be updated by func output while walking the tree
        :type with_context_update: bool
        :param context_keys_to_reset_after_siblings:
        keys within the context data which should not be modified between siblings
        :type context_keys_to_reset_after_siblings: list
        :returns: dict -- the updated or not updated context_data
        """
        return self._walk_inner(parent=parent,
                                obj=obj,
                                func=func,
                                level=level,
                                depth=depth,
                                post=post,
                                up=up,
                                with_context_update=with_context_update,
                                context_keys_to_reset_after_siblings=context_keys_to_reset_after_siblings,
                                **context_data)

    def _walk_inner(self, obj, func, parent=None, level=0, depth=-1, post=False, up=False,
                    with_context_update=False, context_keys_to_reset_after_siblings=None,
                    **context_data):
        next_elems = getattr(obj, '_tree_up_reference')() if up else getattr(obj, '_tree_down_reference')()

        if next_elems is None:
            next_elems = []
        elif not isinstance(next_elems, ObjectCollection) and not isinstance(next_elems, collections.Iterable):
            next_elems = [next_elems]
        if post:
            res = func(parent, obj, next_elems, level, **context_data)
            if with_context_update and res is not None:
                context_data.update(res)

        from cs.requirements import TargetValue
        for next_elem in next_elems:
            if level == depth and not isinstance(next_elem, TargetValue):
                continue
            res = self._walk_inner(obj=next_elem,
                                   func=func,
                                   parent=obj,
                                   level=level + 1,
                                   depth=depth,
                                   post=post,
                                   up=up,
                                   with_context_update=with_context_update,
                                   context_keys_to_reset_after_siblings=context_keys_to_reset_after_siblings,
                                   **context_data)

            if context_keys_to_reset_after_siblings is not None:
                for key in context_keys_to_reset_after_siblings:
                    if key in res:
                        del res[key]
            if with_context_update and res is not None:
                context_data.update(res)

        if not post:
            res = func(parent, obj, next_elems, level, **context_data)
            if with_context_update and res is not None:
                context_data.update(res)
        return context_data

    def _get_context_data_value(self, key, **context_data):
        assert key in context_data, ue.Exception("just_a_replacement",
                                                 "missing %s in tree context_data" % key)
        return context_data[key]

    def _get_RQMTreeLogic_base_var(self):
        if hasattr(self, 'GetClassname'):
            return self.GetClassname()
        else:
            return "rqm_"

    def _get_environ_val(self, val, default=None):
        return environ.get(val, default)

    def _set_environ_val(self, key, val):
        environ[key] = val

    def _reset_environ_val(self, key):
        if key in environ:
            del(environ[key])


class WithRQMBase(WithRQMTreeLogic):
    EMPTY_DIV = '<xhtml:div></xhtml:div>'

    def add_volatile_richtext_modifications(self, ctx):
        richtext_attribute_values = RichTextModifications.get_richtext_attribute_values(obj=self)
        patched_fields = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
            objs=self, attribute_values=richtext_attribute_values, from_db=True
        )
        patched_richtext_attribute_values = richtext_attribute_values.copy()
        patched_richtext_attribute_values.update(patched_fields)
        # needed for REST API
        for field, value in patched_fields.items():
            # only temporary change - need to be replaced the other way around in PRE
            ctx.set(field, value)
            LOG.debug('replaced %s by %s', richtext_attribute_values[field], value)

        # needed for pc client/elements UI operation
        # JSON string representation of dict iso code -> richtext
        richtexts = RichTextModifications.get_richtexts_by_iso_code(
            obj=self, patched_attribute_values=patched_richtext_attribute_values, as_json=True
        )
        ctx.set("richtext_desc", richtexts)
    
    def get_richtext_attribute_values_from_ctx(self, ctx):
        richtext_attribute_values = {}
        rest_api = False
        if (
            ctx and ctx.dialog and hasattr(self, '__description_attrname_format__') and
            self.__description_attrname_format__
        ):
            dialog_attribute_names = ctx.dialog.get_attribute_names()
            if "richtext_desc" in dialog_attribute_names:
                # pc client/elements UI operation
                richtext_attribute_values = {
                    self.__description_attrname_format__.format(iso=iso): v
                    for (iso, v) in json.loads(ctx.dialog.richtext_desc).items()
                }
            else:
                # REST API
                desc_attr_prefix = self.__description_attrname_format__.format(iso='')
                richtext_attribute_values = {
                    attr: ctx.dialog[attr] for
                    attr in dialog_attribute_names if attr.startswith(desc_attr_prefix)
                }
                rest_api = True
        return richtext_attribute_values, rest_api

    def process_volatile_richtext_modifications(self, ctx):
        obj = ByID(ctx.dragged_obj.cdb_object_id) if ctx.dragged_obj else self
        try:
            richtext_attribute_values, rest_api = self.get_richtext_attribute_values_from_ctx(ctx)
            patched_fields = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
                objs=obj, attribute_values=richtext_attribute_values, from_db=False
            )
            patched_richtext_attribute_values = richtext_attribute_values.copy()
            patched_richtext_attribute_values.update(patched_fields)
            # we need to have a common serialization within db to ensure that quick diff indicator is correct
            serialization_patched_fields = RichTextModifications.force_serializations(
                attribute_values=patched_richtext_attribute_values
            )
            patched_richtext_attribute_values.update(serialization_patched_fields)
            old_richtext_attribute_values = (
                RichTextModifications.get_richtext_attribute_values(obj=self)
            )

            # check only the permission if richtexts are part of this change
            if patched_richtext_attribute_values and not self.CheckAccess('rqm_richtext_save'):
                changed = not(
                    patched_richtext_attribute_values == old_richtext_attribute_values
                )
                if changed:
                    raise ue.Exception('cdbrqm_desc_change_perm_miss')

            # set short titles
            short_title_attribute_values = RichTextModifications.get_short_title_attribute_values(
                obj=obj, richtext_attribute_values=patched_richtext_attribute_values
            )
            for attr, value in short_title_attribute_values.items():
                ctx.set(attr, value)
            # set descriptions
            update_long_text_in_db = True if not rest_api else False

            for attr, new_value in patched_richtext_attribute_values.items():
                if ctx.action not in ("create", "copy"):
                    old_text = old_richtext_attribute_values.get(attr)
                    if old_text != new_value:
                        ctx.keep(
                            "auditrich_%s" % attr,
                            old_text
                        )
                        ctx.set('cdb_mdate', datetime.datetime.now())
                        if update_long_text_in_db:
                            self.SetText(attr, new_value)
                ctx.set(attr, new_value)
                unpatched_new_value = richtext_attribute_values.get(attr)
                if unpatched_new_value != new_value:
                    LOG.debug('replaced back %s by %s', unpatched_new_value, new_value)
        except lxml.etree.XMLSyntaxError as _:
            raise ue.Exception('cdbrqm_xml_syntax_error')

    def _get_fulfillment_qc(self):
        qcd = rqm_utils.getQCFulfillmentDef()
        if qcd:
            qc = self.ObjectQualityCharacteristics.KeywordQuery(cdbqc_def_object_id=qcd.cdb_object_id)
            if qc:
                return qc[0]

    FulfillmentQualityCharacteristic = references.ReferenceMethods_1(QualityCharacteristic, _get_fulfillment_qc)

    @classmethod
    def aggregate_qc(cls, obj, up_structure=True):
        if obj._is_template() is not None and not obj._is_template():
            aggr_obj = None
            if up_structure:
                aggr_obj = obj._tree_up_reference()
            else:
                aggr_obj = obj
            if aggr_obj is not None:
                qc = rqm_utils.getFulfillmentQC(aggr_obj)
                if qc is not None:
                    qc.aggregate()
                else:
                    LOG.warn('aggregation failed - qc does not exist')
            else:
                LOG.debug('aggregation not needed - no parent found')

    @classmethod
    def makeNumber(cls, delegatedClass):
        maxno = util.nextval(delegatedClass.__number_key__)
        formatted_number = delegatedClass.__number_format__ % (maxno)
        return formatted_number, maxno

    def makePosition(self, ctx=None):
        pass

    def _is_template(self):
        # workaround for not existing virtual attributes within some ctx
        return None

    def ensure_parent_qcs(self, ctx=None):
        pass

    def on_link_graph_now(self, ctx):
        ctx.url(rqm_utils.get_rqm_linkgraph_url(self.cdb_object_id))

    def fillAuthorField(self, ctx=None):
        if ctx:
            name = auth.get_attribute("name")
            ctx.set("authors", name)

    def _copy_obj_within_tree(self, parent, obj, next_elems, level, **context_data):
        # src_parent = parent
        dst_parent = self._get_context_data_value("parent_dst", **context_data)
        dst_parent_object_id = dst_parent.cdb_object_id if dst_parent else ""
        static_properties = self._get_context_data_value("static_properties", **context_data)
        processed_objs = self._get_context_data_value("processed_objs", **context_data)
        semlinks_to_create = self._get_context_data_value("semlinks_to_create", **context_data)
        pre_cb_func = self._get_context_data_value("pre_callback_func", **context_data)
        post_cb_func = self._get_context_data_value("post_callback_func", **context_data)
        sl_cb_func = self._get_context_data_value("semanticlinks_callback_func", **context_data)
        copyRootLevelAttachments = self._get_context_data_value("copyRootLevelAttachments", **context_data)
        copyRootLevelDocuments = self._get_context_data_value("copyRootLevelDocuments", **context_data)
        copyDocuments = self._get_context_data_value("copyDocuments", **context_data)
        copyTargetValues = self._get_context_data_value("copyTargetValues", **context_data)
        copyClassification = self._get_context_data_value("copyClassification", **context_data)
        followup_cdbrqm_new_revision = self._get_context_data_value("followup_cdbrqm_new_revision", **context_data)

        from cs.requirements import TargetValue
        if isinstance(obj, TargetValue) and not copyTargetValues:
            processed_objs.update({obj.cdb_object_id: {"dest": None,
                                                       "dest_clsn": None}})
            result = dict(processed_objs=processed_objs,
                          semlinks_to_create=semlinks_to_create)
            return result

        if pre_cb_func is not None:
            pre_cb_res = pre_cb_func(source_obj=obj,
                                     static_properties=static_properties,
                                     level=level,
                                     followup_cdbrqm_new_revision=followup_cdbrqm_new_revision)
            if pre_cb_res is not None:
                static_properties.update(pre_cb_res)
        # if root element of tree is already copied and given use it
        # this is used for kernel copy operations on the first element
        if 'root_dst_obj' in static_properties and level == 0:
            dst_obj = static_properties.get('root_dst_obj')
            upd_keys = [x for x in static_properties.keys() if hasattr(dst_obj, x)]
            upd_args = {}
            for k in upd_keys:
                upd_args[k] = static_properties[k]
            if upd_args:
                dst_obj.Update(**upd_args)
        else:
            args = {}
            if hasattr(obj, "__parent_object_id_field__"):
                args = {obj.__parent_object_id_field__: dst_parent_object_id}
            args.update(static_properties)
            # copy obj to new_elem
            dst_obj = obj.Copy(**args)
            # copy long text fields
            for text_field in obj.GetTextFieldNames():
                dst_obj.SetText(text_field, obj.GetText(text_field))
            LOG.debug("_copy_obj_within_tree: copied (%s) %s to %s", type(obj), obj.cdb_object_id, dst_obj.cdb_object_id)

        # add copied dst_obj to processed_objs
        processed_objs.update({obj.cdb_object_id: {"dest": dst_obj.cdb_object_id,
                                                   "dest_clsn": dst_obj.GetClassname()}})

        # copy attachments only on level below root or when it is forced explicitly
        if hasattr(obj, 'Files') and (copyRootLevelAttachments or level > 0):
            derived_files_dict = {}
            for file_obj in obj.Files.Query(condition="1=1", order_by="cdbf_derived_from"):
                new_file_object_id = file_obj.Copy(cdbf_object_id=dst_obj.cdb_object_id,
                                                   cdbf_derived_from=derived_files_dict[file_obj.cdb_object_id] if file_obj.cdb_object_id in derived_files_dict else None)
                derived_files_dict[file_obj.cdb_object_id] = new_file_object_id

        # copy documents only on level below root or when it is forced explicitly
        if hasattr(obj, 'DocumentRefs') and (copyRootLevelDocuments or level > 0) and copyDocuments:
            for doc_obj_ref in obj.DocumentRefs:
                args = {obj.__reference_field__: dst_obj.cdb_object_id}
                doc_obj_ref.Copy(**args)

        # copy classification when it is forced
        if copyClassification and level > 0:
            dest_classification = classification_api.get_classification(obj)
            del dest_classification['values_checksum']
            classification_api.update_classification(
                dst_obj,
                dest_classification
            )

        # call callback if configured
        if post_cb_func is not None:
            post_cb_func(source_obj=obj,
                         dest_obj=dst_obj,
                         processed_objs=processed_objs,
                         static_properties=static_properties,
                         level=level,
                         copyRootLevelAttachments=copyRootLevelAttachments,
                         copyRootLevelDocuments=copyRootLevelDocuments,
                         followup_cdbrqm_new_revision=followup_cdbrqm_new_revision)

        # create semantic links and add semantic links to a list which can not actually be created
        if sl_cb_func is not None:
            sl_cb_func(source_obj=obj,
                       dest_obj=dst_obj,
                       semlinks_to_create=semlinks_to_create,
                       processed_objs=processed_objs,
                       followup_cdbrqm_new_revision=followup_cdbrqm_new_revision)

        result = dict(processed_objs=processed_objs,
                      semlinks_to_create=semlinks_to_create)
        # set new dst_parent for elements below if given
        result.update(dict(parent_dst=dst_obj))
        return result

    def _create_external_semlinks(self, tree_result):
        if 'semlinks_to_create' in tree_result and 'processed_objs' in tree_result:
            for object_object_id, semlinks_to_create in tree_result["semlinks_to_create"].items():
                if object_object_id not in tree_result["processed_objs"]:
                    external_obj = ByID(object_object_id)
                    if external_obj:
                        for semlink_to_create in semlinks_to_create:
                            external_obj_subj_sl = semanticlinks.SemanticLink.KeywordQuery(subject_object_id=external_obj.cdb_object_id,
                                                                                           object_object_id=semlink_to_create["source"])
                            external_obj_obj_sl = semanticlinks.SemanticLink.KeywordQuery(object_object_id=external_obj.cdb_object_id,
                                                                                          subject_object_id=semlink_to_create["source"])
                            sl_old_new = {}
                            sl_created = []
                            for sl in external_obj_subj_sl:  # copy all sl's where external_obj is subject of the link
                                sl_new = sl.Copy(**dict(object_object_id=semlink_to_create["subject"]))
                                sl_old_new[sl.cdb_object_id] = sl_new.cdb_object_id
                                sl_created.append(sl_new)
                            for sl in external_obj_obj_sl:  # copy all sl's where external_obj is object of the link
                                sl_new = sl.Copy(**dict(subject_object_id=semlink_to_create["subject"]))
                                sl_old_new[sl.cdb_object_id] = sl_new.cdb_object_id
                                sl_created.append(sl_new)
                            for sl in sl_created:  # update mirror link references
                                new_mirror_object_id = sl_old_new[sl.mirror_link_object_id]
                                sl.Update(**{"mirror_link_object_id": new_mirror_object_id})

    @classmethod
    def _filter_attribute_values_by_object(cls, obj, values):
        attrs = {}
        for k, v in values.items():
            if hasattr(obj, k):
                attrs[k] = v
            else:
                LOG.warn('unable to set %s on %s', k, obj.GetClassname())
        return attrs

    @classmethod
    def tree_copy_post_cb_func(cls, source_obj, dest_obj, processed_objs, static_properties, **kwargs):
        followup_cdbrqm_new_revision = kwargs.get("followup_cdbrqm_new_revision", 0)
        # generate new empty qc for requirement which was copied source_obj->dest_obj
        # or in case of index creation copy the old_values
        if followup_cdbrqm_new_revision == 1:
            source_qc = rqm_utils.getFulfillmentQC(source_obj)
            if source_qc:
                source_qc.Copy(cdbf_object_id=dest_obj.cdb_object_id)
        else:
            dest_classname = dest_obj.GetClassname()
            args = {"cdbf_object_id": dest_obj.cdb_object_id,
                    "classname": dest_classname}
            rqm_utils.createQC(**args)

    def _copy_post_cb_func(self, source_obj, dest_obj, processed_objs, static_properties, **kwargs):
        return source_obj.tree_copy_post_cb_func(source_obj, dest_obj, processed_objs, static_properties, **kwargs)

    @classmethod
    def tree_copy_pre_cb_func(cls, source_obj, static_properties, **kwargs):
        followup_cdbrqm_new_revision = kwargs.get("followup_cdbrqm_new_revision", 0)
        attrs = {}
        if followup_cdbrqm_new_revision == 0:
            if kwargs.get('level', 0) > 0:
                new_object_id = cdbuuid.create_uuid()
                new_attrs = {
                    'ce_baseline_id': '',
                    'cdb_object_id': new_object_id,
                    'ce_baseline_object_id': new_object_id,
                    'ce_baseline_origin_id': cdbuuid.create_uuid(),
                }
                attrs.update(new_attrs)
            attrs['reqif_id'] = ''
        change_control_values = source_obj.MakeChangeControlAttributes()
        attrs.update(change_control_values)
        return attrs

    def _copy_pre_cb_func(self, source_obj, static_properties, **kwargs):
        return source_obj.tree_copy_pre_cb_func(source_obj, static_properties, **kwargs)

    def _copy_sl_cb_func(self, source_obj, dest_obj, semlinks_to_create,
                         processed_objs, **kwargs):
        if hasattr(source_obj, "SemanticLinks"):
            # add semlinks which cannot actually be added (not both ends in processed_objs)
            rqm_utils._add_semlinks(
                source=source_obj,
                semlinks_to_create=semlinks_to_create,
                processed_objs=processed_objs,
                dest=dest_obj
            )
            # create semlinks which can actually be created (both ends in processed_objs)
            rqm_utils._create_semlinks(
                source=source_obj,
                dest=dest_obj,
                semlinks_to_create=semlinks_to_create,
                processed_objs=processed_objs
            )

            if not kwargs["followup_cdbrqm_new_revision"]:
                if (
                    hasattr(source_obj, "specification_object_id") and
                    hasattr(dest_obj, "specification_object_id") and
                    source_obj.specification_object_id != dest_obj.specification_object_id
                ) or (
                    not hasattr(source_obj, "specification_object_id") and
                    not hasattr(dest_obj, "specification_object_id")
                ):
                    semanticlinks.SemanticLink.createCopyLink(source_obj=source_obj,
                                                              dest_obj=dest_obj)

    def setTemplateOID(self, ctx):
        if ctx and ctx.cdbtemplate[u"cdb_object_id"]:
            self.template_oid = ctx.cdbtemplate[u"cdb_object_id"]

    def copy_subobjects(self, ctx=None, source_obj=None, processed_objs=None, semlinks_to_create=None, **kwargs):
        if processed_objs is None:
            processed_objs = {}
        if semlinks_to_create is None:
            semlinks_to_create = {}

        if source_obj is not None and kwargs.get('specification_object_id') is not None and source_obj._tree_down_reference() is not None:
            with transactions.Transaction():
                copyRootLevelDocuments = kwargs.get('copyRootLevelDocuments', False)
                copyRootLevelAttachments = kwargs.get('copyRootLevelAttachments', False)
                depth = -1
                copyDocuments = True
                copyTargetValues = True
                copyClassification = True  # actually per default also copy the classification as the kernel does it
                if "depth" in ctx.ue_args.get_attribute_names():
                    depth = int(ctx.ue_args.depth)
                    copyDocuments = True if (ctx.ue_args.copy_documents == "1") else False
                    copyTargetValues = True if (ctx.ue_args.copy_target_values == "1") else False

                kwargs = kwargs.copy()
                context_data = {
                    "parent_dst": "",
                    "processed_objs": processed_objs,
                    "semlinks_to_create": semlinks_to_create,
                    "static_properties": kwargs,
                    "post_callback_func": self._copy_post_cb_func,
                    "pre_callback_func": self._copy_pre_cb_func,
                    "followup_cdbrqm_new_revision": 0,
                    "semanticlinks_callback_func": self._copy_sl_cb_func,
                    # copy documents/attachments only in case of drag & drop as otherwise this is done by kernel copy
                    "copyRootLevelDocuments": True if (ctx and ctx.dragged_obj) or copyRootLevelDocuments else False,
                    "copyRootLevelAttachments": True if (ctx and ctx.dragged_obj) or copyRootLevelAttachments else False,
                    "copyDocuments": copyDocuments,
                    "copyTargetValues": copyTargetValues,
                    "copyClassification": copyClassification
                }
                if "followup_cdbrqm_new_revision" in \
                        ctx.ue_args.get_attribute_names():
                    context_data["followup_cdbrqm_new_revision"] = 1
                # walk down the tree beginning at self
                context_data = self._walk(parent=source_obj._tree_up_reference(),
                                          obj=source_obj,
                                          func=self._copy_obj_within_tree,
                                          depth=depth,
                                          post=True,  # first process element then children as children need parent_object_id of newly created elements
                                          with_context_update=True,
                                          context_keys_to_reset_after_siblings=["parent_dst"],
                                          **context_data)
                sls_to_create = context_data.get("semlinks_to_create")
                if "followup_cdbrqm_new_revision" in \
                        ctx.ue_args.get_attribute_names():
                    for _obj_id, sls_to_c in sls_to_create.items():
                        for sl_to_c in sls_to_c:
                            args = {"subject_object_id": sl_to_c["subject"],
                                    "link_type_object_id": sl_to_c["link_type"],
                                    "object_object_id": sl_to_c["object"],
                                    "object_object_classname": sl_to_c["object_clsn"],
                                    "subject_object_classname": sl_to_c["subject_clsn"]}
                            change_control_values = semanticlinks.SemanticLink.MakeChangeControlAttributes()
                            args.update(change_control_values)
                            created_sem_link = semanticlinks.SemanticLink.Create(**args)
                            created_sem_link.generateMirrorLink(sl_to_c["subject_clsn"], sl_to_c["object_clsn"])
                return context_data.get("processed_objs"), sls_to_create

    def get_long_description(self):
        if not hasattr(self, "__readable_id_field__"):
            return None
        else:
            readable_id = self[self.__readable_id_field__]
            return "%s/%d" % (readable_id, self.revision)

    def setPosition(self, ctx=None):
        if (hasattr(self, 'specification_object_id') and
            hasattr(self, 'parent_object_id') and
            (self.specification_object_id is not None and
             hasattr(self, 'position'))):
            self.position = self.makePosition(ctx)
        elif (hasattr(self, 'specification_object_id') and
              hasattr(self, 'requirement_object_id') and
              hasattr(self, 'pos')):
                self.pos = self.makePosition(ctx)

    def setNumber(self, ctx=None):
        raise NotImplementedError

    def setReqIfId(self, ctx=None):
        if not self.reqif_id:
            self.reqif_id = rqm_utils.createUniqueIdentifier()

    def reset_external_fields(self, ctx, source_obj=None):
        raise NotImplementedError

    def reset_baseline_fields(self, ctx):
        # ce_baseline_object_id has to be reset in case of index, ce_baseline_origin_id not
        self.getPersistentObject().ce_baseline_object_id = self.cdb_object_id

    def fillVirtualAttributes(self, ctx=None):
        pass

    def keepArgs(self, ctx=None):
        pass

    def set_copy_mask(self, ctx):
        if ctx.get_current_mask() == "initial":
            if ctx.classname == "cdbrqm_spec_object":
                ctx.next_mask("cdbrqm_spec_object_comp_c")
            elif ctx.classname == "cdbrqm_specification":
                ctx.next_mask("cdbrqm_specification_comp_c")

    def keepCopyArgs(self, ctx):
        if ctx and "depth" in ctx.dialog.get_attribute_names():
            ctx.keep("depth", ctx.dialog.depth)
            ctx.keep("copy_documents", ctx.dialog.copy_documents)
            ctx.keep("copy_target_values", ctx.dialog.copy_target_values)

    def handle_copy_mask(self, ctx):
        if ctx and ctx.changed_item in ["copy_all_levels", "copy_first_level"]:
            if ctx.changed_item == "copy_all_levels":
                if ctx.dialog.copy_all_levels == "1":
                    ctx.set_readonly("depth")
                    ctx.set("depth", "-1")
                    ctx.set("copy_first_level", "0")
                else:
                    ctx.set_writeable("depth")
                    ctx.set("depth", "")
            elif ctx.changed_item == "copy_first_level":
                if ctx.dialog.copy_first_level == "1":
                    ctx.set_readonly("depth")
                    ctx.set("depth", "0")
                    ctx.set("copy_all_levels", "0")
                else:
                    ctx.set_writeable("depth")
                    ctx.set("depth", "")

    def setFocus(self, ctx):
        if hasattr(self, '__description_attrname_format__') and self.__description_attrname_format__ and \
           hasattr(self, '__short_description_attrname_format__') and self.__short_description_attrname_format__:
            ctx.set_focus(self.__description_attrname_format__.format(iso='de'))

    def get_initial_richtext(self, ctx):
        richtexts = RichTextModifications.get_empty_richtexts_by_iso_codes(obj=self)
        if ctx.dragged_obj:
            dragged_obj = ByID(ctx.dragged_obj.cdb_object_id)
            richtexts.update(
                RichTextModifications.get_richtexts_by_iso_code(obj=dragged_obj)
            )
        return json.dumps(richtexts, ensure_ascii=False)

    def initRichtext(self, ctx):
        if (
            ctx and ctx.dialog and
            hasattr(self, '__description_attrname_format__') and
            self.__description_attrname_format__ and
            hasattr(ctx.dialog, 'richtext_desc') and
            not ctx.dialog.richtext_desc
        ):
                initial_rich_text = self.get_initial_richtext(ctx)
                ctx.set("richtext_desc", initial_rich_text)

    def initialize_fulfillment_kpi_active(self, ctx=None):
        if self.fulfillment_kpi_active in [0, None]:
            if not hasattr(self, 'Specification'):
                self.fulfillment_kpi_active = 1 if not self.is_template else 0
            else:
                self.fulfillment_kpi_active = 1 if not self.Specification.is_template else 0

    def keepAuditTrailAttributes(self, ctx):
        pass

    def createAuditTrailRichText(self, audittrail_object_id, clsname, longtext, old_text, new_text):
        from cs.audittrail import config, shortenText
        attr_length = getattr(AuditTrailDetailRichText, "old_value").length
        ot = rqm_utils.strip_tags(old_text).strip()
        nt = rqm_utils.strip_tags(new_text).strip()
        longdetail = AuditTrailDetailRichText.Create(detail_object_id=cdbuuid.create_uuid(),
                                                     audittrail_object_id=audittrail_object_id,
                                                     attribute_name=longtext,
                                                     old_value=shortenText(ot, attr_length),
                                                     new_value=shortenText(nt, attr_length),
                                                     label_de=config[clsname]["fields"][longtext]["de"],
                                                     label_en=config[clsname]["fields"][longtext]["en"]
                                                     )
        longdetail.SetText("cdb_audittrail_longtext_old", old_text)
        longdetail.SetText("cdb_audittrail_longtext_new", new_text)

    def specialkeepAuditTrailAttributes(self, ctx):
        if ctx and ctx.dialog:
            if ctx.action == "modify":
                old_values = ""
                for attribute in ctx.ue_args.get_attribute_names():
                    if attribute.startswith("audit"):
                        old_values += "%s;" % re.sub('^audi[^_]+_', '', attribute)
                if old_values:
                    ctx.keep("old_audit_values", old_values)

                obj_attributes = ctx.object.get_attribute_names()
                obj_longtext = self.GetTextFieldNames()
                for attribute in ctx.dialog.get_attribute_names():
                    if attribute in obj_attributes:
                        if attribute in obj_longtext and not hasattr(self, '__description_attrname_format__'):
                            longtext = self.GetText(attribute)
                            if ctx.dialog[attribute] != longtext:
                                ctx.keep("auditlong_%s" % attribute, longtext)
                        elif attribute not in obj_longtext and ctx.dialog[attribute] != ctx.object[attribute]:
                            ctx.keep("audit_%s" % attribute, ctx.object[attribute])

    def createAuditTrailEntry(self, ctx=None):
        audittrail = self.createAuditTrail('create')
        if audittrail:
            from cs.audittrail import config, is_object_id
            long_text_names = self.GetTextFieldNames()
            for attribute in ctx.object.get_attribute_names():
                if attribute in long_text_names:
                    # will be handled separately
                    continue
                if attribute in config[self.GetClassname()]["fields"]:
                    if ctx.object[attribute]:
                        nv = ctx.object[attribute]
                        if is_object_id(nv):
                            nv = ByID(nv)
                            if nv:
                                nv = nv.GetDescription()
                            else:
                                nv = ""
                        self.createAuditTrailDetail(audittrail.audittrail_object_id,
                                                    self.GetClassname(),
                                                    attribute,
                                                    "",
                                                    nv)

            for longtext in long_text_names:
                if longtext in config[self.GetClassname()]["fields"]:
                    new_text = self.GetText(longtext)
                    if new_text:
                        if not hasattr(self, '__description_attrname_format__'):
                            self.createAuditTrailLongText(audittrail.audittrail_object_id,
                                                          self.GetClassname(),
                                                          longtext,
                                                          "",
                                                          new_text)
                        else:
                            if new_text != self.EMPTY_DIV:
                                self.createAuditTrailRichText(
                                    audittrail.audittrail_object_id,
                                    self.GetClassname(),
                                    longtext,
                                    "",
                                    new_text
                                )

    def createSemanticLinks(self, ctx):
        if 'uses_web_ui' not in ctx.sys_args.get_attribute_names() or not ctx.sys_args.uses_web_ui:
            if self.cdb_object_id == ctx.objects[0].cdb_object_id:
                obj_ids = []
                for obj in self.PersistentObjectsFromContext(ctx):
                    if obj.GetClassname() != self.GetClassname():
                        raise ue.Exception("cdbrqm_create_semanticlinks_failed")
                    else:
                        obj_ids.append(obj.cdb_object_id)

                link = '/cs-tools-semanticlinks-createLinksApp?restname=%s&cdb_object_ids=%s' % (
                    self.GetClassDef().getRESTName(), ";".join(obj_ids))
                ctx.url(link)

    def modifyAuditTrailEntry(self, ctx):
        audittrail = super(WithRQMBase, self).modifyAuditTrailEntry(ctx)
        from cs.audittrail import config
        if self.GetClassname() in config:
            audittrail_richtext = [re.sub('^auditrich_', '', attribute) for attribute in
                                   ctx.ue_args.get_attribute_names()
                                   if attribute.startswith("auditrich_")]

            if audittrail_richtext:
                if not audittrail:
                    audittrail = self.createAuditTrail('modify')
                for richtext in audittrail_richtext:
                    if richtext not in config[self.GetClassname()]["fields"]:
                        continue
                    old_text = ctx.ue_args["auditrich_%s" % richtext]
                    new_text = self.GetText(richtext)
                    self.createAuditTrailRichText(audittrail.audittrail_object_id,
                                                  self.GetClassname(),
                                                  richtext,
                                                  old_text,
                                                  new_text)

    def create_baseline(self, ctx):
        _, baselined_obj = BaselineTools.create_baseline(
            obj=self, name=ctx.dialog.ce_baseline_name, comment=ctx.dialog.ce_baseline_comment)
        if baselined_obj:
            ctx.set_object_result(baselined_obj)

    def restore_baseline(self, ctx):
        current_obj = BaselineTools.restore_baseline(baseline_obj=self)
        if current_obj and ctx.interactive:
            if rqm_utils.is_ctx_from_web(ctx):
                web_url = uisupport.get_ui_link(request=None, target_obj=current_obj)
                ctx.url(web_url)
            else:
                ctx.url(current_obj.MakeURL())
        else:
            ctx.set_object_result(current_obj)

    event_map = {
        ('create', 'pre_mask'): ('setFocus', 'initRichtext'),
        (('create', 'copy'), 'pre_mask'): ('setPosition', 'fillAuthorField', 'reset_external_fields'),
        (('create', 'modify', 'copy'), 'pre'): (
            'process_volatile_richtext_modifications',
            'specialkeepAuditTrailAttributes', 'keepArgs', 'keepCopyArgs'),
        (('create', 'copy'), 'pre'): (
            'reset_external_fields',
            'setPosition',
            'setNumber',
            'setReqIfId',
            'initialize_fulfillment_kpi_active'),
        ('copy', 'post_mask'): "set_copy_mask",
        ('copy', 'pre'): "setTemplateOID",
        ('copy', 'post'): ('reset_baseline_fields', 'copy_subobjects'),
        ('create', 'final'): ('reset_baseline_fields', 'copy_subobjects'),
        ('copy', 'dialogitem_change'): 'handle_copy_mask',
        (('info', 'modify', 'copy'), 'pre_mask'): ('fillVirtualAttributes', 'add_volatile_richtext_modifications'),
        ('cdbrqm_create_semanticlinks', 'now'): 'createSemanticLinks',
        ('ce_baseline_create', 'now'): 'create_baseline',
        ('ce_baseline_restore', 'now'): 'restore_baseline'
    }
