#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=too-many-locals,too-many-instance-attributes
# pylint: disable=too-many-lines,too-many-nested-blocks,consider-using-f-string

"""
The module contains functionality for creating and updating time schedules that
have been processed with |tm.project|.

The data is transferred based on the XML schema of |tm.project|.
The XML schema has been extended by |cs.pcs|.
"""

import time
from collections import OrderedDict
from datetime import datetime

from cdb import auth, cdbuuid, dberrors, misc, sig, sqlapi, ue, util
from cdb.constants import kOperationDelete
from cdb.objects import Object
from cdb.objects.pdd.Files import Sandbox
from cdb.sig import emit, signal
from cdb.storage.index.tesjobqueue_utils import Job
from cdb.transactions import Transaction
from cs.documents import Document
from cs.workflow.briefcases import BriefcaseContent
from lxml import objectify  # nosec
from lxml.etree import XMLSyntaxError  # nosec

from cs.pcs.msp import misc as msp_misc
from cs.pcs.msp.import_results import DiffType, ImportException, ImportResult
from cs.pcs.msp.internal import ProjectConsistency
from cs.pcs.msp.misc import logger
from cs.pcs.projects import Project, tasks_changes
from cs.pcs.projects.common import partition
from cs.pcs.projects.tasks import Task, TaskRelation
from cs.pcs.helpers import get_dbms_split_count

CAN_PUBLISH_PROJECT = signal()


class XmlMergeImport:

    ID_COUNT = 0

    def __init__(self):
        self.pcs_project = None
        self.msp_project = None
        self.xml_document = None
        self.called_from_officelink = False
        self.db_type = sqlapi.SQLdbms()
        self.split_count = get_dbms_split_count()

        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            self.split_count_post_actions = 1000
        else:
            self.split_count_post_actions = self.split_count

    def get_next_task_id(self):
        if self.dry_run:
            self.ID_COUNT += 1
            return "TMP_T%06d" % self.ID_COUNT
        return Task.makeTaskID()

    @classmethod
    def add_system_attribute(cls, attr):
        cls().SYSTEM_ATTRIBUTES.append(attr)

    @classmethod
    def remove_system_attribute(cls, attr):
        cls().SYSTEM_ATTRIBUTES.remove(attr)

    @classmethod
    def get_readonly_task_fields(cls):
        return cls().TASK_READONLY_FIELDS

    def enqueue_objects(self, objs, is_deleted):
        if is_deleted:
            for objects in partition(list(set(objs)), self.split_count):
                try:
                    stmt = (
                        "INSERT INTO cdbes_jobs "
                        "(job_id, enqueued, cdb_jobject_id, relation_name, obj_deleted,"
                        " job_state, initial_phase, prevent_associated_obj_update)"
                    )
                    if self.db_type == sqlapi.DBMS_ORACLE:
                        stmt += " "
                        for obj in objects:
                            stmt += (
                                "SELECT '%s' %s '-%s', %s, '%s', 'cdbpcs_task', "
                                "1, '%s', 0, 0 FROM dual UNION ALL "
                            ) % (
                                obj["cdb_object_id"],
                                sqlapi.SQLstrcat(),
                                hex(int(time.time()))[2:],
                                sqlapi.SQLdbms_date(datetime.now()),
                                obj["cdb_object_id"],
                                Job.waiting,
                            )
                        stmt = stmt[:-10]
                    else:
                        stmt += " VALUES "
                        for obj in objects:
                            stmt += (
                                "('%s' %s '-%s', %s, '%s', 'cdbpcs_task', 1, '%s', 0, 0 ),"
                                % (
                                    obj["cdb_object_id"],
                                    sqlapi.SQLstrcat(),
                                    hex(int(time.time()))[2:],
                                    sqlapi.SQLdbms_date(datetime.now()),
                                    obj["cdb_object_id"],
                                    Job.waiting,
                                )
                            )
                        stmt = stmt[:-1]
                    sqlapi.SQL(stmt)
                except dberrors.DBConstraintViolation:
                    pass
        else:
            for objects in partition(objs, self.split_count):
                try:
                    stmt = (
                        "INSERT INTO cdbes_jobs "
                        "(job_id, enqueued, cdb_jobject_id, relation_name, obj_deleted,"
                        " job_state, initial_phase, prevent_associated_obj_update)"
                        " SELECT"
                        " cdb_object_id %s '-%s', %s, cdb_object_id, 'cdbpcs_task', 0, '%s', 0, 0"
                        " FROM cdbpcs_task"
                        % (
                            sqlapi.SQLstrcat(),
                            hex(int(time.time()))[2:],
                            sqlapi.SQLdbms_date(datetime.now()),
                            Job.waiting,
                        )
                    )
                    if isinstance(objects[0], tuple):
                        stmt += " WHERE cdb_object_id in ('%s')" % "','".join(
                            (obj[2]["cdb_object_id"] for obj in objects)
                        )
                    else:
                        stmt += " WHERE cdb_object_id in ('%s')" % "','".join(
                            (obj["cdb_object_id"] for obj in objects)
                        )
                    sqlapi.SQL(stmt)
                except dberrors.DBConstraintViolation:
                    pass

    @classmethod
    def import_project_from_xml(
        cls,
        pcs_project_object_or_id,
        xml_doc,
        dry_run=False,
        called_from_officelink=False,
    ):
        """
        Performs a full import of given Document into given PCS project and returns the import
        result. The Document must contain an MSP XML file.
        """
        logger.info(
            "pcs_project_object_or_id=%s, xml_doc=%s, dry_run=%s, called_from_officelink=%s",
            pcs_project_object_or_id,
            xml_doc,
            dry_run,
            called_from_officelink,
        )
        merge_import = cls()
        merge_import.called_from_officelink = called_from_officelink
        try:
            if dry_run:
                merge_import.set_pcs_project(pcs_project_object_or_id)
                merge_import.pcs_project.set_msp_default_times()
                merge_import.load_msp_project_from_document(
                    xml_doc, called_from_officelink
                )
                merge_import.execute(dry_run)
            else:
                with Transaction():
                    merge_import.set_pcs_project(pcs_project_object_or_id)
                    merge_import.pcs_project.set_msp_default_times()
                    merge_import.load_msp_project_from_document(
                        xml_doc, called_from_officelink
                    )
                    merge_import.execute(dry_run)
        except ImportException:
            misc.log_traceback("")
        return merge_import.result

    @classmethod
    def check_import_right(
        cls, pcs_project, xml_doc=None, called_from_officelink=False
    ):
        """
        This method is called from msp projectlink implementation.
        """
        logger.info(
            "pcs_project=%s, xml_doc=%s, called_from_officelink=%s",
            pcs_project,
            xml_doc,
            called_from_officelink,
        )
        if not pcs_project.msp_active:
            raise ue.Exception("cdbpcs_msp_msp_not_set_as_project_editor_short")
        if called_from_officelink:
            if xml_doc != pcs_project.getLastPrimaryMSPDocument():
                raise ue.Exception("cdbpcs_msp_document_not_primary_msp_document")
        if not pcs_project.CheckAccess("save"):
            raise ue.Exception("cdbpcs_msp_missing_project_save_right")
        if pcs_project.locked_by and pcs_project.locked_by != auth.persno:
            raise ue.Exception("pcs_tbd_locked", pcs_project.mapped_locked_by_name)
        can_sync = all(emit(CAN_PUBLISH_PROJECT)(pcs_project))
        # the returned bool value decides the enabled/disabled property of "publish" button
        # in MSP officelink implementation
        return can_sync

    @classmethod
    def check_msp_edition(cls, pcs_project, msp_edition):
        """
        This method is called from msp officelink implementation and is used
        to verify that the right MS Project edition is used for the given project.
        `msp_edition` might currently be `pjEditionStandard` or `pjEditionProfessional`.
        """

        def is_standard_but_needed_professional():
            return msp_edition == "pjEditionStandard" and pcs_project.msp_active == 1

        if is_standard_but_needed_professional():
            raise ue.Exception("cdbpcs_msp_edition_conflict")

    def set_pcs_project(self, pcs_project_object_or_id):
        logger.info("Start")
        if isinstance(pcs_project_object_or_id, Project):
            self.pcs_project = pcs_project_object_or_id
        else:
            self.pcs_project = Project.ByKeys(cdb_project_id=pcs_project_object_or_id)
        tasks_changes.set_project_id(self.pcs_project.cdb_project_id)

        self.pcs_old_tasks = Task.KeywordQuery(
            cdb_project_id=self.pcs_project.cdb_project_id,
            ce_baseline_id=self.pcs_project.ce_baseline_id,
        ).Execute()  # prevent lazy evaluation
        logger.info("PCS task count: %s", len(self.pcs_old_tasks))

        self.pcs_old_task_links = TaskRelation.KeywordQuery(
            cdb_project_id=self.pcs_project.cdb_project_id,
            cdb_project_id2=self.pcs_project.cdb_project_id,
        ).Execute()  # prevent lazy evaluation
        logger.info("PCS task link count: %s", len(self.pcs_old_task_links))

        self.pcs_old_external_task_links = TaskRelation.Query(
            "cdb_project_id='%(pid)s' AND cdb_project_id2!='%(pid)s' OR "
            "cdb_project_id!='%(pid)s' AND cdb_project_id2='%(pid)s'"
            % {"pid": self.pcs_project.cdb_project_id}
        )
        logger.info(
            "PCS external task link count: %s", len(self.pcs_old_external_task_links)
        )

        self.reset_results()
        logger.info("End")

        self.consistency = ProjectConsistency(
            self.pcs_project,
            self.pcs_old_tasks,
            self.pcs_old_task_links,
            self.pcs_old_external_task_links,
        )

    def _get_xml_file_object_from_document(self, keys):
        # get the only non-primary xml file derived from the document's
        # only primary mpp file
        self.xml_document = Document.ByKeys(
            z_nummer=keys["z_nummer"], z_index=keys["z_index"]
        )
        if not self.xml_document:
            raise ue.Exception(
                "cdbpcs_no_msp_document", keys["z_nummer"], keys["z_index"]
            )
        all_files = self.xml_document.Files
        # Get Primary MSP file from Document
        primary_mpp_files_iterator = filter(
            lambda f: (f.cdbf_type == "MS-Project" and f.cdbf_primary == "1"), all_files
        )
        primary_mpp_files = list(primary_mpp_files_iterator)
        if len(primary_mpp_files) != 1:
            raise ue.Exception(
                "cdbpcs_not_exactly_one_primary_msp_file_in_document",
                self.xml_document.GetDescription(),
            )
        primary_mpp_fobj = primary_mpp_files[0]

        # Get non primary files of type xml derived from found mpp
        derived_xml_files_iterator = filter(
            lambda f: (
                f.cdbf_type == "XML"
                and f.cdbf_primary == "0"
                and f.cdbf_derived_from == primary_mpp_fobj.cdb_object_id
            ),
            all_files,
        )
        derived_xml_files = list(derived_xml_files_iterator)
        if not derived_xml_files:
            raise ue.Exception(
                "cdbpcs_xml_file_not_found_in_document",
                self.xml_document.GetDescription(),
            )
        if len(derived_xml_files) > 1:
            raise ue.Exception(
                "cdbpcs_multiple_xml_files_in_document",
                self.xml_document.GetDescription(),
            )
        return derived_xml_files[0]

    def _get_xml_file_object_from_document_for_import(self, keys):
        # TODO: Refactor file determination in case of importing from xml
        # This method is purposely redundant to _get_xml_file_object_from_document
        # which will be fixed in the future

        # get only xml file on document
        self.xml_document = Document.ByKeys(
            z_nummer=keys["z_nummer"], z_index=keys["z_index"]
        )
        if not self.xml_document:
            raise ue.Exception(
                "cdbpcs_no_msp_document", keys["z_nummer"], keys["z_index"]
            )
        all_files = self.xml_document.Files
        # Get files of type xml
        xml_files_iterator = filter(lambda f: f.cdbf_type == "XML", all_files)
        xml_files = list(xml_files_iterator)
        if not xml_files:
            raise ue.Exception(
                "cdbpcs_xml_file_not_found_in_document",
                self.xml_document.GetDescription(),
            )
        if len(xml_files) > 1:
            raise ue.Exception(
                "cdbpcs_multiple_xml_files_in_document",
                self.xml_document.GetDescription(),
            )
        return xml_files[0]

    def load_msp_project_from_document(self, keys, called_from_officelink):
        """
        Takes a key dictionary (Document), and in case it's called for import:
            retrieves the only xml file
        and in case it's called from officelink:
            retrieves the only primary mpp file
            and reads the only non-primary xml derived from that mpp file

        Raises ue.Exception if `called_from_officelink`, when there is:
            - not exactly one primary mpp file
            - not exactly one non-primary xml file derived from the primary mpp file
        """
        logger.info("Start importing msp project from document")
        if called_from_officelink:
            fobj = self._get_xml_file_object_from_document(keys)
        else:
            fobj = self._get_xml_file_object_from_document_for_import(keys)
        logger.info("Checking out xml file..")
        try:
            with Sandbox() as sb:
                sb.checkout(fobj)
                tree = objectify.parse(sb.pathname(fobj))
            self.msp_project = tree.getroot()
        except XMLSyntaxError as ex:
            logger.error(ex)
            raise ue.Exception("cdbpcs_msp_document_syntax_error")

        logger.info("Removing project summary task from XML..")
        # exclude the project summary task since there's no such thing in PCS
        project_summary_task = self.msp_project.Tasks.xpath(
            "xmlns:Task/xmlns:OutlineLevel[text()='0']/..",
            namespaces={"xmlns": msp_misc.MSP_XML_SCHEMA},
        )
        if project_summary_task:
            self.msp_project.Tasks.remove(project_summary_task[0])

        logger.info("Adding Text* fields to XML..")
        # for easier access later on add extended task attributes ("Text*") as regular attributes
        ext_attr_defs = self.msp_project.xpath(
            "xmlns:ExtendedAttributes/xmlns:ExtendedAttribute",
            namespaces={"xmlns": msp_misc.MSP_XML_SCHEMA},
        )
        for ext_attr_def in ext_attr_defs:
            ext_attrs = self.msp_project.xpath(
                "xmlns:Tasks/xmlns:Task/xmlns:ExtendedAttribute/"
                "xmlns:FieldID[text()='%s']/.." % ext_attr_def.FieldID,
                namespaces={"xmlns": msp_misc.MSP_XML_SCHEMA},
            )
            for ext_attr in ext_attrs:
                msp_task = ext_attr.xpath("..")[0]
                msp_task.addattr("%s" % ext_attr_def.FieldName, "%s" % ext_attr.Value)

        self.build_msp_task_tree()

        self.reset_results()
        logger.info("End importing msp project from document")

    def reset_results(self):
        self.mapped_tasks = OrderedDict()
        self.result = ImportResult(self.pcs_project)
        self.result.num_old_tasks = len(getattr(self, "pcs_old_tasks", []))

    def execute(self, dry_run=False):
        self.dry_run = dry_run
        start_time = datetime.now()

        logger.info("Checking import right..")
        try:
            self.check_import_right(
                self.pcs_project, self.xml_document, self.called_from_officelink
            )
        except Exception as ex:
            misc.log_traceback("")
            self.result.add_diff_object(
                DiffType.MODIFIED, self.pcs_project, exception=ex
            )
            logger.info("Aborting import..")
            return

        logger.info("Importing project attributes..")
        pcs_project_attrs, exceptions = self.get_mapped_pcs_attrs(
            self.PROJECT_MAPPING,
            self.PROJECT_DEFAULTS,
            self.msp_project,
            self.pcs_project,
        )
        if not exceptions:
            self.modify_pcs_object(
                self.pcs_project,
                pcs_project_attrs,
                attr_display_order=self.PROJECT_ATTR_ORDER,
            )
        else:
            for ex in exceptions:
                self.result.add_diff_object(
                    DiffType.MODIFIED, self.pcs_project, exception=ex
                )

        logger.info("Importing tasks..")
        m, c = self.update_pcs_task_tree("", self.msp_task_tree)
        cl, ml = self.update_pcs_task_links()
        logger.info("Removing unmapped task objects..")
        d, dls = self.delete_unmapped_task_objects()

        logger.info("Emitting pre_signal...")
        self.consistency.pre_project(self.result)
        self.consistency.pre_tasks(self.result)
        sig.emit("cs.pcs.msp.pre_import")(self.result)
        num_exceptions = self.result.exceptions_occurred()

        logger.info("Update DB...")
        if not self.dry_run and not num_exceptions:
            tasks_changes.update_modified_tasks(m)
            self.insert_new_tasks(c)
            self.remove_task_objects(d, dls)
            self.create_task_links(cl)
            self.modify_task_links(ml)

            for proc_new, task in self.result.workflow_content:
                try:
                    BriefcaseContent.setup_ahwf(proc_new, [task])
                except util.ErrorMessage as ex:
                    self.result.add_diff_object(DiffType.MODIFIED, task, exception=ex)
                    num_exceptions += 1

        logger.info("Finalizing import..")
        result_clone = self.result.clone()
        if not self.dry_run and not num_exceptions:
            self.consistency.refresh()
            self.consistency.post_tasks(result_clone, self.split_count_post_actions)
            self.consistency.post_project(result_clone, self.split_count_post_actions)

        if not self.dry_run and not num_exceptions:
            logger.info("Indexing objects...")
            self.enqueue_objects(m, 0)
            self.enqueue_objects(c, 0)
            self.enqueue_objects(d, 1)

        logger.info("Emitting post signal...")
        if not self.dry_run and not num_exceptions:
            sig.emit("cs.pcs.msp.post_import")(result_clone)

        logger.info(
            "Import finished in %s second(s)", (datetime.now() - start_time).seconds
        )
        self.result.log_count()

        if not dry_run and num_exceptions:
            raise ImportException("Number of import exceptions: %s" % num_exceptions)

    def build_msp_task_tree(self):
        """
        Traverses the flat structured MSP XML project and builds a hierarchical task structure via
        ordered dictionary.
        """
        self.msp_task_tree = OrderedDict()
        self.msp_task_links = OrderedDict()
        parent_path = []
        for msp_task in self.msp_project.Tasks.getchildren():
            if getattr(msp_task, "IsNull", 0):
                continue  # empty MSP task
            while parent_path:
                if parent_path[-1].OutlineLevel < msp_task.OutlineLevel:
                    break
                parent_path.pop()
            _msp_task_tree = self.msp_task_tree
            for parent in parent_path:
                _msp_task_tree = _msp_task_tree[parent]
            _msp_task_tree[msp_task] = OrderedDict()
            parent_path.append(msp_task)

    def update_pcs_task_tree(self, parent_pcs_task_id, msp_task_tree):
        """Maps an MSP XML task tree and recursively updates the regarding PCS task tree."""
        guid_map = {}
        uid_map = {}
        tuid_map = {}

        for old_task in self.pcs_old_tasks:
            if old_task.msp_guid:
                guid_map[old_task.msp_guid] = old_task
            if old_task.msp_uid:
                uid_map[old_task.msp_uid] = old_task
            if old_task.tuid and not old_task.msp_guid and not old_task.msp_uid:
                tuid_map[old_task.tuid] = old_task
        # Possible signal point (pre change)
        m, c = self.construct_pcs_task_data(
            parent_pcs_task_id, msp_task_tree, guid_map, uid_map, tuid_map
        )
        # Possible signal point (post change)
        return m, c

    def insert_new_tasks(self, tasks_to_insert):
        logger.info("Start")
        # do not process empty list
        if not tasks_to_insert:
            return
        logger.info("Number of tasks to insert=%d", len(tasks_to_insert))

        # create list of keys
        keys_to_sql = set(["cdb_cdate", "cdb_cpersno", "cdb_mdate", "cdb_mpersno"])
        keys_to_sql = list(keys_to_sql.union(*(t.keys() for t in tasks_to_insert)))
        keys_to_sql.sort()
        keys_to_insert = ", ".join(keys_to_sql)
        logger.info("keys_to_insert='%s'", keys_to_insert)

        # create list of value tuples
        cca = Task.MakeChangeControlAttributes()
        oids_to_remove = []
        values_to_insert = []
        table_info = util.tables["cdbpcs_task"]
        for task_to_create in tasks_to_insert:
            values_to_sql = []
            task_to_create = OrderedDict(**task_to_create)
            task_to_create.update(**cca)
            for k in keys_to_sql:
                if k in task_to_create:
                    v = sqlapi.make_literal(table_info, k, task_to_create[k])
                    values_to_sql.append(v)
                    if k == "cdb_object_id":
                        oids_to_remove.append(v)
                else:
                    values_to_sql.append("NULL")
            values_to_insert.append(", ".join(values_to_sql))
        logger.info("num of oids_to_remove=%d", len(oids_to_remove))
        logger.info("num of values_to_insert=%d", len(values_to_insert))

        # insert values and adjust table cdb_object
        for oids in partition(oids_to_remove, self.split_count):
            logger.info("Deleting %d tasks..", len(oids))
            sqlapi.SQLdelete(
                "FROM cdbpcs_task WHERE cdb_object_id IN (%s)" % ", ".join(oids)
            )
        for values in partition(values_to_insert, self.split_count):
            logger.info("Inserting %d tasks..", len(values))
            stmt = "INTO cdbpcs_task (%s)" % keys_to_insert
            if self.db_type == sqlapi.DBMS_ORACLE:
                stmt += " "
                for value_to_insert in values:
                    stmt += "SELECT %s FROM dual UNION ALL " % value_to_insert
                stmt = stmt[:-10]
            else:
                stmt += " VALUES "
                stmt += "(%s)" % "), (".join(values)
            sqlapi.SQLinsert(stmt)
        logger.info("Inserting tasks into cdb_object table..")
        sqlapi.SQLinsert(
            """INTO cdb_object (id, relation)
                SELECT cdb_object_id, 'cdbpcs_task' FROM cdbpcs_task
                WHERE cdb_object_id NOT IN (SELECT id FROM cdb_object
                                            WHERE relation = 'cdbpcs_task')"""
        )
        logger.info("End")

    def construct_pcs_task_data(
        self,
        parent_pcs_task_id,
        msp_task_tree,
        guid_map,
        uid_map,
        tuid_map,
        m=None,
        c=None,
    ):
        if m is None:
            m = []
        if c is None:
            c = []
        pcs_task_position = 10
        modified_tasks_result = []
        created_tasks_result = []
        for msp_task, msp_sub_task_tree in list(msp_task_tree.items()):
            # prefer the more reliable GUID if it exists (instead of UID):
            # 1) the UID changes when moving tasks in MSP via cut/paste
            # 2) the UID gets re-used when deleting tasks and re-opening the plan afterwards
            pcs_task = None
            if (
                hasattr(msp_task, "GUID")
                and msp_task.GUID
                and msp_task.GUID in guid_map
            ):
                pcs_task = guid_map[msp_task.GUID]
            if not pcs_task and msp_task.UID and msp_task.UID in uid_map:
                pcs_task = uid_map[msp_task.UID]

            # legacy: support importing MSP files formerly managed by the old interface
            # where the task id (UUID) mapping was msp_task.Text18 <-> pcs_task.tuid
            if (
                not pcs_task
                and hasattr(msp_task, "Text18")
                and (len("%s" % msp_task.Text18) == 36)
                and msp_task.Text18 in tuid_map
            ):
                pcs_task = tuid_map[msp_task.Text18]

            pcs_task_attrs, exceptions = self.get_mapped_pcs_attrs(
                self.TASK_MAPPING,
                self.TASK_DEFAULTS,
                msp_task,
                pcs_task or Task,
                attribute_order=self.TASK_ATTR_IMPORT_ORDER,
            )
            pcs_task_attrs["parent_task"] = parent_pcs_task_id

            pcs_task_attrs["position"] = pcs_task_position
            pcs_task_position += 10

            if pcs_task:
                if not exceptions:
                    modified_tasks_result.append(
                        (
                            pcs_task.task_id,
                            self.modify_pcs_object(
                                pcs_task,
                                pcs_task_attrs,
                                attr_display_order=self.TASK_ATTR_ORDER,
                            ),
                            pcs_task,
                        )
                    )
                else:
                    for ex in exceptions:
                        self.result.add_diff_object(
                            DiffType.MODIFIED, pcs_task, exception=ex
                        )
                for t in self.pcs_old_tasks:
                    # self.old_tasks.remove(pcs_task) is not reliable
                    if t.cdb_object_id == pcs_task.cdb_object_id:
                        self.pcs_old_tasks.remove(t)
                        break
            else:
                pcs_task_attrs["cdb_project_id"] = self.pcs_project.cdb_project_id
                pcs_task_attrs["ce_baseline_id"] = self.pcs_project.ce_baseline_id
                pcs_task = pcs_task_attrs.copy()
                pcs_task["task_id"] = self.get_next_task_id()
                pcs_task["cdb_object_id"] = cdbuuid.create_uuid()
                if not exceptions:
                    exception = None
                    if not self.dry_run:
                        created_tasks_result.append(pcs_task)
                    self.result.add_diff_object(
                        DiffType.ADDED, pcs_task, Task, exception=exception
                    )
                else:
                    for ex in exceptions:
                        self.result.add_diff_object(
                            DiffType.ADDED, pcs_task, Task, exception=ex
                        )

            self.mapped_tasks[msp_task.UID] = {
                "msp_task": msp_task,
                "pcs_task": pcs_task,
            }

            links = msp_task.xpath(
                "xmlns:PredecessorLink", namespaces={"xmlns": msp_misc.MSP_XML_SCHEMA}
            )
            for link in links:
                self.msp_task_links.setdefault(msp_task.UID, [])
                self.msp_task_links[msp_task.UID].append(link)

            self.update_pcs_task_references(msp_task, pcs_task)

            mn, cn = self.construct_pcs_task_data(
                pcs_task["task_id"],
                msp_sub_task_tree,
                guid_map,
                uid_map,
                tuid_map,
                m,
                c,
            )
            modified_tasks_result += mn
            created_tasks_result += cn
        return modified_tasks_result, created_tasks_result

    def update_pcs_task_references(self, msp_task, pcs_task):
        for msp_attr, function in list(self.TASK_REFERENCE_MAPPING.items()):
            function = getattr(self, function)
            function(msp_task, msp_attr, pcs_task)

    def update_pcs_task_links(self):
        """Maps MSP XML task links and updates the regarding PCS task links."""
        logger.info("Start")
        c = []
        m = []
        for successor_uid, links in list(self.msp_task_links.items()):
            for link in links:
                predecessor = self.mapped_tasks[link.PredecessorUID]["pcs_task"]
                successor = self.mapped_tasks[successor_uid]["pcs_task"]

                # workaround to see a descriptive task link name in the import preview
                task_id2 = predecessor["task_id"] or "@%s" % predecessor["task_name"]

                pcs_link_keys = {
                    "cdb_project_id": successor["cdb_project_id"],
                    "task_id": successor["task_id"],
                    "cdb_project_id2": predecessor["cdb_project_id"],
                    "task_id2": task_id2,
                    "rel_type": msp_misc.MspToPcs.TaskLinkType[link.Type],
                }
                pcs_link_attrs = {
                    # PredecessorLink.LinkLag: The amount of lag in tenths of a minute
                    "minimal_gap": int(link.LinkLag)
                    / 60
                    / 10
                    / 8,  # days in PCS
                }
                pcs_link = self.pcs_old_task_links.KeywordQuery(**pcs_link_keys)
                if pcs_link:
                    pcs_link = pcs_link[0]
                    self.modify_pcs_object(pcs_link, pcs_link_attrs, successor)
                    for link in self.pcs_old_task_links:
                        # self.pcs_old_task_links.remove(pcs_link) is not reliable
                        for key, value in pcs_link_keys.items():
                            if link[key] != value:
                                break
                        else:
                            self.pcs_old_task_links.remove(link)
                            break
                    if pcs_link_attrs["minimal_gap"] != pcs_link["minimal_gap"]:
                        pcs_link_attrs.update(pcs_link_keys)
                        exception = None
                        if not self.dry_run:
                            try:
                                m.append(pcs_link_attrs)
                            except Exception:
                                misc.log_traceback("")
                else:
                    pcs_link_attrs.update(pcs_link_keys)
                    # much too slow: pcs_link = TaskRelation.createRelation(**pcs_link_attrs)
                    exception = None
                    if not self.dry_run:
                        try:
                            c.append(pcs_link_attrs)
                        except Exception:
                            misc.log_traceback("")
                    pcs_link = pcs_link_attrs.copy()
                    self.result.add_diff_object(
                        DiffType.ADDED,
                        pcs_link,
                        TaskRelation,
                        parent=successor,
                        exception=exception,
                    )
        still_used_links = []
        for pcs_link in self.pcs_old_external_task_links:
            link_points_outside = (
                pcs_link.cdb_project_id == self.pcs_project.cdb_project_id
            )
            linked_task_id = (
                pcs_link.task_id if link_points_outside else pcs_link.task_id2
            )
            for mapped_task in self.mapped_tasks.values():
                if mapped_task["pcs_task"]["task_id"] == linked_task_id:
                    still_used_links.append(pcs_link)
                    break
        for pcs_link in still_used_links:
            self.pcs_old_external_task_links.remove(pcs_link)
        logger.info("End")
        return c, m

    def create_task_links(self, c):
        logger.info("Start")
        if not self.dry_run:
            keys_to_insert = []
            values_to_insert = []
            keys_to_sql = []
            table_info = util.tables["cdbpcs_taskrel"]
            for links_to_create in c:
                values_to_sql = []
                keys_to_sql = []
                for k, v in links_to_create.items():
                    try:
                        vt = sqlapi.make_literal(table_info, k, v)
                    except ValueError as e:
                        if isinstance(v, float):
                            vt = sqlapi.make_literal(table_info, k, int(float(v)))
                        else:
                            raise e
                    values_to_sql.append(vt)
                    keys_to_sql.append(k)
                keys_to_insert = ", ".join(keys_to_sql)
                values_to_insert.append(", ".join(values_to_sql))
            if keys_to_sql:
                for values in partition(values_to_insert, self.split_count):
                    stmt = "INTO cdbpcs_taskrel (%s)" % keys_to_insert
                    if self.db_type == sqlapi.DBMS_ORACLE:
                        stmt += " "
                        for value_to_insert in values:
                            stmt += "SELECT %s FROM dual UNION ALL " % value_to_insert
                        stmt = stmt[:-10]
                    else:
                        stmt += " VALUES "
                        stmt += "(%s)" % "), (".join(values)
                    sqlapi.SQLinsert(stmt)
        logger.info("End")

    def modify_task_links(self, m):
        logger.info("Start")
        if not self.dry_run:
            for link in m:
                stmt = """cdbpcs_taskrel SET minimal_gap = {minimal_gap},
                                             gap = {minimal_gap},
                                             cross_project = 0,
                                             violation = 0
                           WHERE cdb_project_id = '{cdb_project_id}'
                           AND task_id = '{task_id}'
                           AND cdb_project_id2 = '{cdb_project_id2}'
                           AND task_id2 = '{task_id2}'
                       """.format(
                    **link
                )
                sqlapi.SQLupdate(stmt)
        logger.info("End")

    def delete_unmapped_task_objects(self):
        def del_pcs_obj(pcs_object, d):
            exception = None
            if not self.dry_run:
                try:
                    d.append(pcs_object)
                except Exception:
                    misc.logging.exception("%s" % pcs_object)
            self.result.add_diff_object(
                DiffType.DELETED, pcs_object, exception=exception
            )
            return d

        def del_pcs_task_rel(pcs_object, dl):
            exception = None
            if not self.dry_run:
                try:
                    dl.append(
                        {
                            "cdb_project_id": pcs_object.cdb_project_id,
                            "task_id": pcs_object.task_id,
                            "cdb_project_id2": pcs_object.cdb_project_id2,
                            "task_id2": pcs_object.task_id2,
                            "rel_type": pcs_object.rel_type,
                        }
                    )
                except Exception:
                    misc.logging.exception("%s" % pcs_object)
            self.result.add_diff_object(
                DiffType.DELETED, pcs_object, exception=exception
            )
            return dl

        d = []
        dls = []
        if self.pcs_old_tasks:
            tasks = self.result.tasks.all
            self.result.tasks.all = OrderedDict()
            for pcs_task in self.pcs_old_tasks:
                del_pcs_obj(pcs_task, d)
            for key, diff_object in list(tasks.items()):
                self.result.tasks.all[key] = diff_object
        for pcs_link in self.pcs_old_task_links + self.pcs_old_external_task_links:
            del_pcs_task_rel(pcs_link, dls)
        return d, dls

    def remove_task_objects(self, d, dls):
        def del_pcs_task(pcs_task):
            try:
                msp_misc.operation_ex(
                    kOperationDelete, pcs_task, called_from_officelink=True
                )
            except Exception:
                misc.logging.exception("%s" % pcs_task)

        logger.info("Start")
        if not self.dry_run:
            for pcs_task in d:
                del_pcs_task(pcs_task)
            for dl_p in partition(dls, self.split_count):
                stmt = "FROM cdbpcs_taskrel WHERE "
                for dl in dl_p:
                    wc = []
                    for k, v in dl.items():
                        wc.append("%s='%s'" % (k, v))
                    where = " AND ".join(wc)
                    stmt += "(%s) OR " % where
                stmt = stmt[:-4]
                sqlapi.SQLdelete(stmt)
        logger.info("End")

    def get_mapped_pcs_attrs(
        self,
        attr_mapping,
        attr_defaults,
        msp_object,
        pcs_obj_or_cls,
        attribute_order=None,
    ):
        """
        Maps an MSP XML object (project or task) and returns a filled PCS attribute dictionary.
        """
        pcs_object_attrs = {}
        exceptions = []
        attr_mapping_checks = {}

        # determine order of synchronization
        sync_order = []
        if attribute_order:
            sync_order = list(attribute_order)
        for msp_attr in list(attr_mapping):
            if msp_attr not in sync_order:
                sync_order.append(msp_attr)

        # perform synchronization
        for msp_attr in sync_order:
            pcs_attr = attr_mapping[msp_attr]
            try:
                if isinstance(pcs_attr, tuple):
                    function, pcs_attrs = pcs_attr
                    function = getattr(self, function)
                    if not isinstance(pcs_attrs, list):
                        pcs_attrs = [pcs_attrs]
                    for pcs_attr in pcs_attrs:
                        function(
                            msp_object,
                            msp_attr,
                            pcs_object_attrs,
                            pcs_attr,
                            pcs_obj_or_cls,
                        )
                        attr_mapping_checks[pcs_attr] = msp_attr
                else:
                    msp_value = "%s" % getattr(msp_object, msp_attr, "")
                    pcs_object_attrs[pcs_attr] = msp_misc.MspToPcs.convert_value(
                        pcs_obj_or_cls, pcs_attr, msp_value
                    )
                    attr_mapping_checks[pcs_attr] = msp_attr
            except Exception as ex:
                misc.log_traceback("")
                exceptions.append("%s" % ex)
        for pcs_attr, default_value in attr_defaults.items():
            value_is_set_in_msp = pcs_object_attrs.get(pcs_attr)
            object_exists_in_db = isinstance(pcs_obj_or_cls, Object)
            value_is_set_in_db = getattr(pcs_obj_or_cls, pcs_attr, None) not in [
                None,
                "",
            ]
            if (not value_is_set_in_msp) and (
                not object_exists_in_db or not value_is_set_in_db
            ):
                pcs_object_attrs[pcs_attr] = default_value
        try:
            tmpl_start = self.DEFAULT_START_TIME
            tmpl_end = self.DEFAULT_FINISH_TIME
            if pcs_object_attrs.get("milestone", 0):
                msp_misc.MspToPcs.check_milestone_value(
                    [tmpl_start, tmpl_end], msp_object
                )
            else:
                msp_misc.MspToPcs.check_start_value(tmpl_start, msp_object)
                msp_misc.MspToPcs.check_end_value(tmpl_end, msp_object)
        except Exception as ex:
            misc.log_traceback("")
            exceptions.append("%s" % ex)
        return pcs_object_attrs, exceptions

    def modify_pcs_object(
        self, pcs_object, pcs_object_attrs, parent=None, attr_display_order=None
    ):
        """Skips running the 'modify' operation when values don't differ anyway."""
        diffs = OrderedDict()
        classname = msp_misc.get_classname(pcs_object)

        _pcs_object_attrs_ordered = OrderedDict()
        if attr_display_order:
            for attr in attr_display_order:
                if attr in pcs_object_attrs:
                    _pcs_object_attrs_ordered[attr] = pcs_object_attrs.pop(attr)
        _pcs_object_attrs_ordered.update(pcs_object_attrs)
        pcs_object_attrs = _pcs_object_attrs_ordered
        only_system_attributes = True
        for pcs_attr, new_value in list(pcs_object_attrs.items()):
            value_diff = msp_misc.get_value_diff(pcs_object, pcs_attr, new_value)
            if value_diff:
                logger.info(
                    "%s.%s: '%s' -> '%s'",
                    classname,
                    pcs_attr,
                    value_diff["old_value"],
                    value_diff["new_value"],
                )
                if pcs_attr not in self.SYSTEM_ATTRIBUTES:
                    only_system_attributes = False
                    diffs[pcs_attr] = self.modify_value_diff_display(
                        pcs_object, pcs_attr, value_diff
                    )

        if diffs:
            self.result.add_diff_object(
                DiffType.MODIFIED, pcs_object, classname, diffs=diffs, parent=parent
            )
        self.result.only_system_attributes.append(only_system_attributes)
        if not self.dry_run:
            pcs_object_attrs.update({"only_system_attributes": only_system_attributes})
            return pcs_object_attrs
        return None

    def modify_value_diff_display(self, pcs_object, pcs_attr, value_diff):
        """Convert internal values (unreadable/non-descriptive for the user) into readable ones"""
        if isinstance(pcs_object, Task):
            if pcs_attr == "constraint_type":
                _old_value = value_diff["old_value"]
                value_diff["old_value"] = pcs_object.mapped_constraint_type_name
                setattr(pcs_object, pcs_attr, value_diff["new_value"])
                value_diff["new_value"] = pcs_object.mapped_constraint_type_name
                setattr(pcs_object, pcs_attr, _old_value)
        return value_diff
