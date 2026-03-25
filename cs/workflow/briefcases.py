#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module briefcases

This is the documentation for the briefcases module.
"""

import enum
import logging

from cdbwrapc import CDBClassDef
from cdb import auth
from cdb import rte
from cdb import sig
from cdb import ue
from cdb import util

from cdb.classbody import classbody
from cdb.constants import kOperationNew
from cdb.lru_cache import lru_cache

from cdb.platform import gui
from cdb.platform import FolderContent
from cdb.platform.gui import PythonColumnProvider
from cdb.platform.mom import entities
from cdb.platform.mom.operations import OperationConfig
from cdb.platform.mom.relships import Relship

from cdb.objects import ByID
from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.objects.operations import operation

from cs.activitystream import create_system_posting
from cs.platform.web.uisupport import get_webui_link
from cs.workflow import protocols
from cs.workflow.misc import is_csweb
from cs.workflow.process_template import _cdbwf_ahwf_new_from_template

__all__ = ['Briefcase',
           'BriefcaseContent',
           'BriefcaseLink',
           'check_rights_for_object',
           'FolderContent',
           'IOTypeCatalog',
           'rights_to_check',
           'WithBriefcase']

fFolderContent = Forward("cdb.platform.FolderContent")

fProcess = Forward("cs.workflow.processes.Process")
fTask = Forward("cs.workflow.tasks.Task")

fBriefcase = Forward(__name__ + ".Briefcase")
fBriefcaseLink = Forward(__name__ + ".BriefcaseLink")
fBriefcaseReference = Forward(__name__ + ".BriefcaseReference")


class IOType(enum.Enum):
    info = 0
    edit = 1


WFACCESSPROFILE = "cdbwf_assign_rights"
BRIEFCASE_COUNT = 0


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def set_briefcase_count():
    global BRIEFCASE_COUNT
    BRIEFCASE_COUNT = len(Briefcase.Query())


class IOTypeCatalog(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        return [gui.I18nCatalogEntry("", "")] + \
            [gui.I18nCatalogEntry("%d" % iotype.value, iotype.name) for iotype in IOType]


class Briefcase(Object):
    __maps_to__ = "cdbwf_briefcase"
    __classname__ = "cdbwf_briefcase"

    Process = Reference_1(fProcess,
                          fProcess.cdb_process_id == fBriefcaseLink.cdb_process_id)

    FolderContents = Reference_N(fFolderContent,
                                 fFolderContent.cdb_folder_id == fBriefcase.cdb_object_id)

    def getContent(self):
        for content in FolderContent.getContent(self.cdb_object_id):
            if content.CheckAccess("read"):
                yield content

    Content = ReferenceMethods_N(Object,
                                 lambda self: list(self.getContent()))

    Links = Reference_N(fBriefcaseLink,
                        fBriefcaseLink.cdb_process_id == fBriefcase.cdb_process_id,
                        fBriefcaseLink.briefcase_id == fBriefcase.briefcase_id,)

    event_map = {
        ("create", "pre"): "make_id",
        ("create", "post"): "init_briefcase_count",
    }

    @classmethod
    def ByContent(cls, obj_or_obj_id):
        """Return all briefcases which contain given
        object or objects with given cdb_object_id"""
        if isinstance(obj_or_obj_id, Object):
            obj_or_obj_id = getattr(obj_or_obj_id, "cdb_object_id")

        return cls.SQL(
            "SELECT {briefcase}.* FROM {briefcase} "
            "JOIN {content} "
            "ON {content}.cdb_content_id='{oid}' "
            "AND {content}.cdb_folder_id={briefcase}.cdb_object_id".format(
                briefcase=cls.GetTableName(),
                content=FolderContent.GetTableName(),
                oid=obj_or_obj_id))

    @classmethod
    def new_briefcase_id(cls):
        briefcase_id = 0

        # 0 is reserved for the attachments map
        while briefcase_id == 0:
            briefcase_id = util.nextval("cdbwf_briefcase_id")
        return briefcase_id

    def make_id(self, ctx):
        if not self.briefcase_id:
            self.briefcase_id = self.new_briefcase_id()

    def notify_content_change(self):
        create_system_posting(self, "cdbwf_briefcase_content_modified")

    def GetActivityStreamTopics(self, posting):
        """Topics for Postings"""
        from cs.workflow.tasks import InteractiveTask

        return [self, self.Process] + \
            InteractiveTask.get_running_tasks_by_briefcase(self)

    def init_briefcase_count(self, ctx):
        if ctx.error:
            return
        if not BRIEFCASE_COUNT:
            set_briefcase_count()


class BriefcaseLink(Object):
    __maps_to__ = "cdbwf_briefcase_link"
    __classname__ = "cdbwf_briefcase_link"

    Process = Reference_1(fProcess,
                          fProcess.cdb_process_id == fBriefcaseLink.cdb_process_id)

    Task = Reference_1(fTask,
                       fTask.cdb_process_id == fBriefcaseLink.cdb_process_id,
                       fTask.task_id == fBriefcaseLink.task_id,)

    Briefcase = Reference_1(fBriefcase,
                            fBriefcase.cdb_process_id == fBriefcaseLink.cdb_process_id,
                            fBriefcase.briefcase_id == fBriefcaseLink.briefcase_id,)

    event_map = {("create", "pre_mask"): "set_briefcase_name",
                 (('create', 'copy', 'modify'), 'pre'): ("check_obj_rights"),
                 (('create', 'copy', 'modify'), ('pre_mask', 'pre')): ("set_extends_rights"),
                 (('create', 'copy', 'modify'), 'post'): ("add_briefcase_to_cycle", "check_extends_rights"),
                 (("create", "copy", "modify"), "post_mask"): "verify_linkage"}

    def set_briefcase_name(self, ctx):
        if self.Briefcase and not self.briefcase_name:
            ctx.set("briefcase_name", self.Briefcase.name)

    def check_obj_rights_with_updated_iotype(self, ctx, new_iotype, persno):
        iotypes = {self.cdb_object_id: new_iotype}

        if self.Briefcase:
            for content in self.Briefcase.FolderContents:
                content.check_foldercontent_rights(
                    ctx, iotypes=iotypes, persno=persno)

    def check_obj_rights(self, ctx, persno=None):
        self.check_obj_rights_with_updated_iotype(ctx, self.iotype, persno)

    def set_extends_rights(self, ctx):
        if self.Task and self.Task.isSystemTask():
            self.extends_rights = 0
            ctx.set_readonly("extends_rights")

    def check_extends_rights(self, ctx):
        if not self.extends_rights:
            raise ue.Exception("cdbwf_system_task_must_extend_rights")

    def verify_linkage(self, ctx):
        # all links with this link's briefcase except of
        # self (include self when copying)
        links = [l for l in self.Briefcase.Links
                 if ctx.action == "copy" or
                 l.cdb_object_id != self.cdb_object_id]
        num_global_links = len([l for l in links if not l.task_id])
        num_non_global_links = len(links) - num_global_links
        if (not self.task_id and (num_non_global_links > 0)) or \
           (self.task_id and (num_global_links > 0)):
            # don't allow linking a briefcase globally and
            # simultaneously directly to one or more tasks
            raise ue.Exception("cdbwf_incorrect_briefcase_linkage")

    def add_briefcase_to_cycle(self, ctx):
        if self.Task:
            self.Task.add_briefcase_to_cycle(self.Briefcase)


# ===============================================================================
# Access rights and briefcase content
# ===============================================================================

def log_no_access(briefcase, access_denied):
    msg = util.CDBMsg(util.CDBMsg.kNone, "cdbwf_briefcase_access_denied")
    text = "{}\n  - {}".format(
        str(msg) % briefcase.name,
        "\n  - ".join(access_denied)
    )
    briefcase.Process.addProtocol(text, protocols.MSGSYSTEM)


class WithBriefcase(object):
    """ Decorator for classes which have briefcases. The classes which inherit
        from this decorator should implement the ReferenceMapping_N
        'BriefcaseLinksByType'.
    """
    __briefcase_sorting_key__ = lambda self, briefcase: briefcase.name

    def getBriefcases(self, iotype, reference="BriefcaseLinksByType", check_rights=False):
        result = set()
        if iotype == "all":
            result.update(self.getBriefcases("info", reference, check_rights))
            result.update(self.getBriefcases("edit", reference, check_rights))
        else:
            briefcases_mapping = getattr(self, reference)

            condition = lambda lnk: (lnk.extends_rights if check_rights else True)

            result.update([lnk.Briefcase
                           for lnk in
                           briefcases_mapping[IOType[iotype].value]
                           if lnk.Briefcase and condition(lnk)])
        return sorted(list(result), key=self.__briefcase_sorting_key__)

    InfoBriefcases = ReferenceMethods_N(fBriefcase,
                                        lambda self: self.getBriefcases("info"))

    EditBriefcases = ReferenceMethods_N(fBriefcase,
                                        lambda self: self.getBriefcases("edit"))

    # get all directly-linked briefcases
    Briefcases = ReferenceMethods_N(fBriefcase,
                                    lambda self: self.getBriefcases("all"))

    # References to content

    def getContent(self, iotype, reference="BriefcaseLinksByType", check_rights=False):
        objs = []
        for briefcase in self.getBriefcases(iotype, reference, check_rights):
            objs += briefcase.getContent()
        return list(set(objs))

    InfoContent = ReferenceMethods_N(Object, lambda self: self.getContent("info"))
    EditContent = ReferenceMethods_N(Object, lambda self: self.getContent("edit"))
    # get contents of all directly-linked briefcases
    Content = ReferenceMethods_N(Object, lambda self: self.getContent("all"))

    # Access rights
    def set_briefcase_rights(self, reference="BriefcaseLinks"):
        """ Set the flag 'extends_rights' of the briefcases associated to
            the object.

            If the user responsible for the process has the access rights on
            the content of the briefcase, the flag is set to true, otherwise it
            is set to false.

            The responsible user is either the user referenced by the process's
            "started_by" attribute or - if no user is referenced yet - the user
            currently logged in.
        """
        if hasattr(self, "Process"):
            persno = self.Process.started_by
        else:
            persno = self.started_by

        persno = persno or auth.persno

        for briefcase_link in getattr(self, reference):
            mode = IOType(briefcase_link.iotype).name

            access_denied = [obj.GetDescription()
                             for obj in briefcase_link.Briefcase.Content
                             if not check_rights_for_object(obj, mode, persno)]

            if access_denied:
                briefcase_link.extends_rights = 0
                log_no_access(briefcase_link.Briefcase, access_denied)
            else:
                briefcase_link.extends_rights = 1


class BriefcaseContent(object):
    """
    Decorator for classes whose instances can be put in a briefcase.
    Responsible for adding default values and checks for briefcase content.
    """
    AHWF_DEFAULTS = {"title": "Ad Hoc Workflow"}


    @classmethod
    def on_cdbwf_ahwf_new_now(cls, ctx):
        """
        Adds default values to the new workflow object.
        """
        # use event handler instead of event map to handle multiselect only once

        from cs.workflow.processes import Process
        args = dict(
            cls.AHWF_DEFAULTS,
            subject_id=auth.persno,
            subject_type="Person",
            is_template="0",
        )

        # cs.web: Create WF, attach objects and open info page
        if is_csweb():
            new_process = operation(kOperationNew, Process, **args)
            cls.setup_ahwf(
                new_process,
                cls.PersistentObjectsFromContext(ctx),
                False
            )
            process_url = get_webui_link(
                None,
                new_process
            )

            ctx.url(process_url)

        # cdbpc: Legacy mechanism - use CDB_Create
        else:
            objects = ";".join([
                obj.cdb_object_id
                for obj in cls.PersistentObjectsFromContext(ctx)
            ])

            msg = Process.MakeCdbcmsg("CDB_Create", interactive=True)
            for key in args:
                msg.add_item(key, Process.__maps_to__, args[key])

            classdef = cls._getClassDef()
            for classname in [classdef.getClassname()] + list(
                classdef.getBaseClassNames()
            ):
                ent = entities.Entity.ByKeys(classname=classname)
                if ent and ent.fqpyname:
                    msg.add_sys_item("ahwf_classpath", ent.fqpyname)
                    break

            msg.add_sys_item("ahwf_content", objects)

            ctx.url(msg.eLink_url())

    @classmethod
    def on_cdbwf_ahwf_new_from_template_now(cls, ctx):
        _cdbwf_ahwf_new_from_template(cls, ctx)

    @staticmethod
    def setup_ahwf(process, objects, check_whitelist=True):
        # assign the current objects to the process
        from cs.workflow.process_template import content_in_whitelist
        for obj in objects:
            if check_whitelist:
                try:
                    content_in_whitelist(obj.cdb_object_id)
                except Exception as error:
                    raise util.ErrorMessage("just_a_replacement", error)
            process.AddAttachment(obj.cdb_object_id)

        # eventually set cdb_project_id
        project_ids = set([
            obj.cdb_project_id
            for obj in objects
            if getattr(obj, "cdb_project_id", "")
        ])
        if len(project_ids) == 1:
            process.cdb_project_id = project_ids.pop()
            process.update_cdb_project_id()

    def notify_briefcases(self, ctx):
        """
        If the content object is changed, briefcase content is notified
        to make the necessary changes.
        """
        sig.emit("wf_briefcase_content_change")(self, ctx)

    def check_briefcase_usage(self, ctx):
        """
        Checks if the object to be deleted is already in use.
        If so, the object cannot be deleted unless it is removed from
        briefcase content.
        """
        if Briefcase.ByContent(self):
            raise util.ErrorMessage("cdbwf_obj_used_in_briefcase")

    event_map = {
        ('modify', 'post'): 'notify_briefcases',
        ('delete', 'pre'): 'check_briefcase_usage',
    }


class BriefcaseContentWhitelist(Object):
    __maps_to__ = "cdbwf_briefcase_whitelist"
    __classname__ = "cdbwf_briefcase_whitelist"
    OPERATION_NAMES = set(["cdbwf_ahwf_new", "cdbwf_ahwf_new_from_template"])

    @classmethod
    def Classnames(cls):
        """
        :returns: Whitelisted classnames for briefcase use.
            Includes classnames directly configured and their subclasses.
        :rtype: set
        """
        result = set()

        for root in cls.Query().classname:
            cdef = CDBClassDef(root)
            if cdef:
                result.add(root)
                result.update(cdef.getSubClassNames(True))

        return result


@sig.connect(OperationConfig, "create", "post")
@sig.connect(OperationConfig, "copy", "post")
@sig.connect(OperationConfig, "modify", "post")
def create_whitelist_entry(self, ctx):
    if (
        not ctx.error and
        self.name in BriefcaseContentWhitelist.OPERATION_NAMES and
        self.classname not in BriefcaseContentWhitelist.Classnames()
    ):
        BriefcaseContentWhitelist.Create(
            classname=self.classname,
            cdb_module_id=self.cdb_module_id,
        )


@classbody
class FolderContent(object):
    Briefcase = Reference_1(fBriefcase,
                            fBriefcase.cdb_object_id == fFolderContent.cdb_folder_id)

    @sig.connect(FolderContent, "create", "pre")
    @sig.connect(FolderContent, "copy", "pre")
    def check_valid_content(self, ctx, iotypes=None, persno=None):
        if self.Briefcase:
            content = ByID(self.cdb_content_id)
            if not content:
                raise ue.Exception(
                    "cdbwf_briefcase_unknown_obj",
                    self.cdb_content_id,
                )

    @sig.connect(FolderContent, "create", "pre")
    @sig.connect(FolderContent, "copy", "pre")
    def check_process_status(self, ctx):
        """Check that the briefcase process is not closed"""
        if self.Briefcase:
            from cs.workflow.processes import Process

            if self.Briefcase.Process and\
                    self.Briefcase.Process.status in [Process.COMPLETED.status,
                                                      Process.FAILED.status]:
                raise ue.Exception("cdbwf_process_already_closed")

    @sig.connect(FolderContent, "create", "pre")
    @sig.connect(FolderContent, "copy", "pre")
    @sig.connect(FolderContent, "delete", "pre")
    def check_briefcase_rights(self, ctx, persno=None):
        """
        Check that user is allowed to add contents to this briefcase.
        This is never the case if the workflow / template
        """
        if not persno:
            persno = ""

        if self.Briefcase:
            from cs.workflow.processes import Process

            wf_status = self.Briefcase.Process.status
            access_granted = False

            if wf_status in [Process.NEW.status, Process.PAUSED.status]:
                access_granted = self.Briefcase.CheckAccess("edit schema", persno=persno)

            elif wf_status == Process.EXECUTION.status:
                access_granted = (
                    self.Briefcase.CheckAccess("edit schema", persno=persno) or
                    self.Briefcase.CheckAccess("cdbwf_task_active", persno=persno)
                )

            # don't allow for final statuses:
            #     workflow: COMPLETED, FAILED, DISCARDED
            #     template: REVIEW, RELEASED, INVALID
            if not access_granted:
                raise ue.Exception("cdbwf_add_to_briefcase_not_allowed")

    @sig.connect(FolderContent, "create", "pre")
    @sig.connect(FolderContent, "copy", "pre")
    def check_briefcase_content(self, ctx):
        """Check that the object to be added has object ID"""
        if self.Briefcase:
            content = ByID(self.cdb_content_id)
            if content and not content.GetObjectID():
                raise ue.Exception("cdbwf_briefcase_content_not_allowed",
                                   content.GetDescription())

    @sig.connect(FolderContent, "create", "pre")
    @sig.connect(FolderContent, "copy", "pre")
    def check_foldercontent_rights(self, ctx, iotypes=None, persno=None):
        """Check the access rights on the object to be added to the briefcase."""
        iotypes = {} if iotypes is None else iotypes
        briefcase = Briefcase.ByKeys(self.cdb_folder_id)
        persno = persno or auth.persno

        if briefcase:
            modes = set([])
            for briefcase_link in briefcase.Links:
                # iotypes may contain newer iotype for link id
                modes.add(iotypes.get(briefcase_link.cdb_object_id,
                                      briefcase_link.iotype))

            # iotypes key None means a link is being created right now
            if None in iotypes:
                modes.add(iotypes[None])

            obj = ByID(self.cdb_content_id)
            if obj:
                for int_mode in modes:
                    if not check_rights_for_object(obj, IOType(int_mode).name,
                                                   persno):
                        raise ue.Exception("cdbwf_no_briefcase_rights",
                                           briefcase.GetDescription(),
                                           obj.GetDescription())

    @sig.connect(FolderContent, "create", "post")
    @sig.connect(FolderContent, "delete", "post")
    def check_foldercontent_change(self, ctx):
        """
        Check whether briefcase content gets added or removed (for
        protocol/notification purposes only)
        """
        content_obj = ByID(self.cdb_content_id)
        briefcase = Briefcase.ByKeys(cdb_object_id=self.cdb_folder_id)
        sig.emit("wf_briefcase_content_change")(content_obj, ctx, briefcase)


class BriefcaseReference(Object):
    __classname__ = "cdbwf_process_content"
    __maps_to__ = "cdbwf_process_content"

    Process = Reference_1(fProcess, fBriefcaseReference.cdb_process_id)
    Briefcase = Reference_1(fBriefcase,
                            fBriefcase.cdb_process_id == fBriefcaseReference.cdb_process_id,
                            fBriefcase.briefcase_id == fBriefcaseReference.briefcase_id)

    def _getReferencedObject(self):
        return ByID(self.cdb_content_id)

    ReferencedObject = ReferenceMethods_1(Object, _getReferencedObject)


# Help functions

WF_MODE_RIGHT = {"info": "cdbwf_obj_info", "edit": "cdbwf_obj_edit"}
NEVER_CHECK = set()
CHECK_IF_HAS_FILES = set(["read_file", "write_file"])


def get_access_rs_profiles(obj):
    classes = [obj.GetClassname()]
    classes.extend(obj.GetClassDef().getBaseClassNames())
    query = (
        "referer='{referer}' "
        "AND reference IN ('{reference}') "
        "AND rs_acc_prof > '' "
    )
    query = query.format(referer=Briefcase.__classname__, reference="', '".join(classes))
    return Relship.Query(query)


@lru_cache(maxsize=None, clear_after_ue=False)
def rights_to_check(mode, obj):
    """ Find out the rights, which are automatically assigned from
        the workflow engine
    """
    obj_access_rights = set()
    file_access_rights = set()
    from cdb.platform import acs

    def update_access_rights(profile_name):
        access_profile = acs.RelshipAccessProfile.ByKeys(profile_name)
        local_result = access_profile.AccessMapping \
            .KeywordQuery(referer_allow=WF_MODE_RIGHT[mode]).reference_allow
        if not obj.GetClassDef().hasFiles():
            obj_access_rights.update(local_result)
        else:
            file_access_rights.update(local_result)
    profiles = get_access_rs_profiles(obj)

    if not profiles:
        update_access_rights(WFACCESSPROFILE)
    else:
        for profile in get_access_rs_profiles(obj):
            profile_name = profile.rs_acc_prof
            update_access_rights(profile_name)

    result = obj_access_rights.difference(CHECK_IF_HAS_FILES) \
                .union(file_access_rights).difference(NEVER_CHECK)
    return result


def check_rights_for_object(obj, mode, persno):
    for right in rights_to_check(mode, obj):
        if not obj.CheckAccess(right, persno=persno):
            logging.error(
                "access right '%s' not granted for user '%s' on object '%s'",
                right,
                persno,
                obj,
            )
            return False
    return True


class IOTypeColumn(PythonColumnProvider):
    @staticmethod
    def getColumnDefinitions(classname, query_args):
        return [{
            "column_id": "mapped_iotype",
            "label": util.get_label("cdbwf_iotype"),
            "data_type": "text"}]

    @staticmethod
    @lru_cache(maxsize=5, clear_after_ue=False)
    def getIOType(iotype):
        try:
            int_iotype = int(iotype)
            return IOType(int_iotype).name
        except (ValueError, TypeError):
            return ""

    @staticmethod
    def getColumnData(classname, table_data):
        return [{
            "mapped_iotype": IOTypeColumn.getIOType(link["iotype"]),
        } for link in table_data]

    @staticmethod
    def getRequiredColumns(classname, available_columns):
        return ["iotype"]
