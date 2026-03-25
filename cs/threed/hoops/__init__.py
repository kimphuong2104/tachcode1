# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


import logging

from cdb import classbody
from cdb import constants
from cdb import dberrors
from cdb import sig
from cdb import sqlapi
from cdb import ue
from cdb import util as cdb_util

from cdb.objects import ByID
from cdb.objects import Reference_N
from cdb.objects import Rule
from cdb.objects import operations as objects_operations
from cdb.objects.cdb_file import CDB_File
from cdb.objects.expressions import Forward
from cdb.objects.pdd import Sandbox

from cs.activitystream.objects import Topic2Posting

from cs.web.components.generic_ui.class_view import CLASS_VIEW_SETUP
from cs.web.components.generic_ui.detail_view import DETAIL_VIEW_SETUP

from cs.documents import Document
from cs.documents import DocumentReference
from cs.sharing import SHARING_CREATED

from cs.vp.bom import AssemblyComponent
from cs.vp.cad import Model
from cs.vp.items import Item
from cs.vp.products import Product

from cs.threed.hoops import utils
from cs.threed.hoops.converter import create_threed_batch_job
from cs.threed.hoops.converter import convert_document
from cs.threed.hoops.converter import configurations
from cs.threed.hoops.converter import SCZ_FILE_FORMAT


LOG = logging.getLogger(__name__)

fMeasurement = Forward("cs.threed.hoops.markup.Measurement")
fViewerSnapshot = Forward("cs.threed.hoops.markup.ViewerSnapshot")
fView = Forward("cs.threed.hoops.markup.View")

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

BLACKLIST_RULE = "3DConnect: Blacklist"

_MODEL_RULE = "3D Models"

MSSSQL_MAXIMUM_RECURSION_DEPTH = 530
ORACLE_MAXIMUM_RECURSION_DEPTH = -32044


class EmptyModelError(ValueError):
    pass


class ModelTypeNotSupportedError(ValueError):
    pass


@sig.connect(SHARING_CREATED)
def sharing_created(sharing):
    from cs.threed.hoops.markup import View

    for attached_object in sharing.AttachedObjects:
        if isinstance(attached_object, View):
            snapshot = attached_object.SnapshotFile
            posting = sharing.Posting

            if snapshot:
                objects_operations.operation(constants.kOperationCopy, snapshot,
                                            cdbf_object_id=posting.cdb_object_id)

            Topic2Posting.createMapping(posting_id=posting.cdb_object_id,
                                        topic_id=attached_object.context_object_id)


@sig.connect(Document, list, "wsmcommit", "post")
def create_hoops_conversion_jobs_with_dependencies(lst, ctx):
    """Assure file types required by the hoops web viewer."""
    blacklist = Rule.ByKeys(BLACKLIST_RULE)

    docs = []
    for doc in lst:
        # the wsmcommit event gets emitted with a list of object id strings
        doc = ByID(doc) if isinstance(doc, str) else doc

        if blacklist is None or not blacklist.match(doc):
            docs.append(doc)

    create_threed_batch_job(docs, target="threed_viewing", reconvert_dependencies=True)


@sig.connect(Document, list, "threed_hoops_covert_select", "now")
def create_selected_hoops_conversion_jobs(docs, ctx):

    if any([(attr in ["viewing_format", "auto_formats"] and ctx.dialog[attr] == "1") or (attr == "ft_name" and ctx.dialog[attr]) for attr in ctx.dialog.get_attribute_names()]):

        selected_filetypes_set = set()

        if ctx.dialog["auto_formats"] == "1":
            auto_filetypes = [conf.ft_name for conf in configurations.get_configurations() if conf.auto_convert]
            selected_filetypes_set.update(auto_filetypes)

        if ctx.dialog["viewing_format"] == "1":
            selected_filetypes_set.add(SCZ_FILE_FORMAT)

        if ctx.dialog["ft_name"]:
            selected_filetypes_set.update(ctx.dialog["ft_name"].split(','))

        success = False

        if len(docs) == 1:
            try:
                success = convert_document(docs[0], target="threed_viewing", params={"filetypes": list(selected_filetypes_set)})
            except Exception as e:
                LOG.exception(e)
        elif len(docs) > 1:
            success = create_threed_batch_job(docs, target="threed_viewing", filetypes=list(selected_filetypes_set)) is not None

        if not success:
            message_box = ctx.MessageBox("threed_hoops_convert_select_convert_not_possible", [], "",
                                        ctx.MessageBox.kMsgBoxIconAlert)
            message_box.addButton(ctx.MessageBoxButton(
                "button_close",
                ctx.MessageBox.kMsgBoxResultCancel,
                ctx.MessageBoxButton.kButtonActionCancel,
                is_dflt=True)
            )

            ctx.show_message(message_box)


@classbody.classbody
class Document(object):
    ViewerMeasurements = Reference_N(fMeasurement,
                                     fMeasurement.context_object_id == Document.cdb_object_id)
    ViewerSnapshots = Reference_N(fViewerSnapshot,
                                  fViewerSnapshot.context_object_id == Document.cdb_object_id)
    ViewerViews = Reference_N(fView,
                              fView.context_object_id == Document.cdb_object_id)

    def on_threed_cockpit_now(self, ctx):
        url = "/cs-threed-hoops-web-cockpit/%s" % self.cdb_object_id
        return ue.Url4Context(url)

    def on_threed_cockpit_model_comparison_pre_mask(self, ctx):
        docs = [x for x in [Document.ByKeys(z_nummer=obj.z_nummer, z_index=obj.z_index)
                       for obj in ctx.objects] if x is not None]
        for i, doc in enumerate(docs[:2]):
            ctx.set("doc%s" % (i + 1), docs[i].cdb_object_id)

    def on_threed_cockpit_model_comparison_now(self, ctx):
        doc2 = Document.ByKeys(cdb_object_id=ctx.dialog.doc2)
        doc2_title = doc2.getExternalFilename()
        url = "/cs-threed-hoops-web-cockpit/%s?modelComparison=%s&title=%s" % (
            ctx.dialog.doc1, ctx.dialog.doc2, doc2_title)
        return ue.Url4Context(url)

    def _get_derived_file(self, file_format):
        result = None
        primary_file_ids = set()

        #required to ensure that self.Files is up to date
        self.Reload()

        for f in self.Files:
            if f.cdbf_primary == "1":
                primary_file_ids.add(f.cdb_object_id)

        for f in self.Files:
            if f.cdbf_type == file_format and f.cdbf_derived_from in primary_file_ids:
                result = f
                break

        return result

    def get_scz_file(self):
        from cs.threed.hoops.converter import SCZ_FILE_FORMAT
        return self._get_derived_file(SCZ_FILE_FORMAT)

    def get_json_mapping_file(self):
        from cs.threed.hoops.converter import JSON_FILE_FORMAT
        return self._get_derived_file(JSON_FILE_FORMAT)

    def getModelDependencies(self):

        # as we currently can't check for a maximum recursion depth
        # postgres will fallback to the "slow" dependency search. see: E076226
        if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
            return self.getModelDependenciesSlow() # noqa

        try:
            dependencies = self.getModelDependenciesFast()
        except dberrors.DBError as err:
            if err.code in [MSSSQL_MAXIMUM_RECURSION_DEPTH, ORACLE_MAXIMUM_RECURSION_DEPTH]:
                # MSSQL may have done a rollback already by this point
                dependencies = self.getModelDependenciesSlow()
            else:
                LOG.exception("check cyclicity run into a db error")
                raise
        return dependencies

    def getModelDependenciesFast(self):
        doc_keys = ", ".join(["zeichnung." + key.name for key in set(Document.GetTableKeys())])

        operator="UNION ALL"

        # E076226: the query works under postgres. However cyclic structures wont
        # throw errors. Therefore this is unsued for now.
        postgres_addition = "RECURSIVE" if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES else ""

        if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
            # this also prevents endless recursion in cycles but does not work in Oracle or MSSQL
            operator="UNION"

        QUERYSTR = """
                WITH {postgres}
                docs (z_nummer, z_index, z_nummer2, z_index2)
                AS
                (
                    SELECT cdb_doc_rel.z_nummer, cdb_doc_rel.z_index, cdb_doc_rel.z_nummer2, cdb_doc_rel.z_index2
                        FROM cdb_doc_rel
                        WHERE cdb_doc_rel.z_nummer2='{z_nummer}' AND cdb_doc_rel.z_index2='{z_index}' AND cdb_doc_rel.cdb_link='0'
                    {operator}
                        SELECT cdb_doc_rel.z_nummer, cdb_doc_rel.z_index, cdb_doc_rel.z_nummer2, cdb_doc_rel.z_index2
                        FROM cdb_doc_rel
                            INNER JOIN docs
                            ON docs.z_nummer=cdb_doc_rel.z_nummer2 AND docs.z_index=cdb_doc_rel.z_index2
                )
                SELECT DISTINCT {doc_keys} FROM docs
                LEFT JOIN zeichnung
                    ON docs.z_nummer=zeichnung.z_nummer AND docs.z_index=zeichnung.z_index
        """

        query = QUERYSTR.format(
            postgres=postgres_addition,
            z_nummer=self.z_nummer,
            z_index=self.z_index,
            operator=operator,
            doc_keys=doc_keys
        )
        return Document.SQL(query)

    def getModelDependenciesSlow(self):
        dependencies = []
        return set(self._getModelDependenciesSlow(dependencies))

    def _getModelDependenciesSlow(self, dependencies):
        doc_refs = DocumentReference.KeywordQuery(z_nummer2=self.z_nummer, z_index2=self.z_index, cdb_link=0)
        for ref in doc_refs:
            dep = Document.ByKeys(z_nummer=ref.z_nummer, z_index=ref.z_index)

            if dep not in dependencies:
                dependencies.append(dep)
                dep._getModelDependenciesSlow(dependencies)

        return dependencies


@classbody.classbody
class Item(object):
    ViewerMeasurements = Reference_N(fMeasurement,
                                     fMeasurement.context_object_id == Item.cdb_object_id)
    ViewerSnapshots = Reference_N(fMeasurement,
                                  fMeasurement.context_object_id == Item.cdb_object_id)
    ViewerViews = Reference_N(fView,
                              fView.context_object_id == Item.cdb_object_id)

    def on_threed_cockpit_now(self, ctx):
        doc = self.get_3d_model_document()
        if not doc:
            raise ue.Exception("threed_hoops_conversion_failed", self.teilenummer, self.t_index)
        url = "/cs-threed-hoops-web-cockpit/%s?part=%s" % (doc.cdb_object_id, self.cdb_object_id)
        return ue.Url4Context(url)

    def get_3d_model_document(self, use_max_index=True):
        result = self.get_3d_model_documents([self], use_max_index=use_max_index)

        if self.cdb_object_id in result:
            return result[self.cdb_object_id]
        return None


    @staticmethod
    def __get_documents(items):
        result = []
        for chunked_items in utils.chunks(items, max_size=500):
            stmnt = utils.make_item_pk_statement(chunked_items)
            result.extend(Document.Query(stmnt))
        return result


    @classmethod
    def get_3d_model_documents(cls, items, use_max_index=False):
        result = {}

        if not items:
            return result

        documents = cls.__get_documents(items)
        rule = Rule.ByKeys(_MODEL_RULE)
        filtered_model = [doc for doc in documents if rule.match(doc)]

        prio_prop = cdb_util.get_prop("3dpr")
        prio_list = prio_prop.split(',') if prio_prop else []

        for item in items:
            item_documents = [model for model in filtered_model if model.teilenummer == item.teilenummer and model.t_index == item.t_index]
            result[item.cdb_object_id] = cls._get_prioritized_document(item_documents, prio_list=prio_list, use_max_index=use_max_index)

        return result

    @classmethod
    def _find_erzeug_prio(cls, prio_list, model):
        prefix = model.erzeug_system.split(':')[0]
        return prio_list.index(prefix) if prefix in prio_list else 1000

    @classmethod
    def _get_max_index_doc(cls, docs):
        # all docs should have the same z_nummer, teilenummer and t_index
        # so take the first one as a representative
        rep_doc = docs[0]

        sort_criteria = cdb_util.get_prop("ixsm")
        if not sort_criteria:
            sort_criteria = "z_index"

        stmt_str = """
            z_index FROM zeichnung 
            WHERE z_nummer='{z_nummer}' 
                AND teilenummer='{teilenummer}' 
                AND t_index='{t_index}' 
            ORDER BY {sort_criteria} DESC
        """
        stmt = stmt_str.format(
            z_nummer=rep_doc.z_nummer,
            teilenummer=rep_doc.teilenummer,
            t_index=rep_doc.t_index,
            sort_criteria=sort_criteria
        )

        t = sqlapi.SQLselect(stmt)
        max_index = sqlapi.SQLstring(t, 0, 0) if sqlapi.SQLrows(t) else None

        # there should only be one matching doc
        max_index_docs = [d for d in docs if d.z_index == max_index] if max_index else None
        return max_index_docs[0] if max_index_docs else None


    @classmethod
    def _get_prioritized_document(cls, docs, prio_list=None, use_max_index=False):
        if not docs:
            return None

        # if no better matching model is found
        # we will return the first found result.
        best_prio_model = docs[0]

        if len(docs) > 1:
            if not prio_list:
                prio_prop = cdb_util.get_prop("3dpr")
                prio_list = prio_prop.split(',') if prio_prop else []

            best_prio_position = 1000
            best_prio_candidates = []

            for doc in docs:
                current_prio_position = cls._find_erzeug_prio(prio_list, doc)
                if current_prio_position < best_prio_position:
                    best_prio_candidates = [doc]
                    best_prio_position = current_prio_position
                elif current_prio_position == best_prio_position:
                    best_prio_candidates.append(doc)

            best_prio_model = best_prio_candidates[0]

            if len(best_prio_candidates) > 1:

                if not all([m.z_nummer == best_prio_candidates[0].z_nummer for m in best_prio_candidates]):
                    LOG.warn("Multiple documents with different 'z_nummer' found. Guessing the right one.")
                    return best_prio_model

                # If there is still more than one model/document,
                # we assume different indexes for the same document
                # if use_max_index is set, the highest doc index in the item context is used
                # otherwise the z_index is random, so make sure it is not needed
                if use_max_index:
                    max_index_doc = cls._get_max_index_doc(best_prio_candidates)

                    if max_index_doc:
                        best_prio_model = max_index_doc

        return best_prio_model


@classbody.classbody
class Product(object):
    ViewerMeasurements = Reference_N(fMeasurement,
                                     fMeasurement.context_object_id == Product.cdb_object_id)
    ViewerSnapshots = Reference_N(fViewerSnapshot,
                                  fViewerSnapshot.context_object_id == Product.cdb_object_id)
    ViewerViews = Reference_N(fView,
                              fView.context_object_id == Product.cdb_object_id)

    def on_threed_cockpit_now(self, ctx):
        maxbom = self._get_max_bom_item(ctx)
        doc = maxbom.get_3d_model_document()
        if not doc:
            raise ue.Exception("threed_hoops_conversion_failed", self.teilenummer, self.t_index)
        url = "/cs-threed-hoops-web-cockpit/%s?item=%s&product=%s" % \
              (doc.cdb_object_id, maxbom.cdb_object_id, self.cdb_object_id)
        return ue.Url4Context(url)

    def select_maxbom_for_3d(self, ctx):
        ctx.set("product_object_id", self.cdb_object_id)
        self.set_max_bom(ctx)

    event_map = {
        (("threed_cockpit", "threed_cockpit_extern"), "pre_mask"): "select_maxbom_for_3d",
    }


@classbody.classbody
class AssemblyComponent(object):

    @staticmethod
    def __get_items(bom_items):
        result = []
        for chunked_bom_items in utils.chunks(bom_items, max_size=500):
            result.extend(Item.Query(utils.make_item_pk_statement(chunked_bom_items)))
        return result

    @staticmethod
    def __get_item_key(item):
        return item.teilenummer, item.t_index

    @classmethod
    def get_items_for_bom_items(cls, bom_items):
        result = {}

        itms = cls.__get_items(bom_items)
        items_by_key = {cls.__get_item_key(i): i for i in itms}

        for bom_item in bom_items:
            result[bom_item.cdb_object_id] = items_by_key[(bom_item.teilenummer, bom_item.t_index)]

        return result


# -- utils --------------------------------------------------------------------

SNAPSHOT_DOC_DEFAULTS = {
    "z_categ1": "144",
    "z_categ2": "298"
}


def _checkout_and_store_files_in_wsp(file_oids, title):
    if isinstance(file_oids, str):
        file_oids = [file_oids]
    files = [CDB_File.GetFilesForObject(oid, primary_only=False) for oid in file_oids]
    file_objs = [val for sublist in files for val in sublist]

    with Sandbox() as sb:
        source_files = sb.checkout(*file_objs)

        # create document to store the result
        doc = objects_operations.operation(constants.kOperationNew, Document, titel=title,
                                           **SNAPSHOT_DOC_DEFAULTS)
        if not doc:
            raise ue.Exception("threed_hoops_cant_create_wsp")  # necessary?

        # attach all source files as primary
        for i in range(0, len(source_files)):
            CDB_File.NewFromFile(doc.cdb_object_id, source_files[i], primary=True)

        return doc
