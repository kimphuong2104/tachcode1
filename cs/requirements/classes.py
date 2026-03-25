# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals
from cdb import util, ue
from cdb.lru_cache import lru_cache
from cdb.objects import references
from cdb.objects.cdb_file import CDB_File
from cdb.objects.core import Object
from cdb.objects.expressions import Forward
import logging
from cdb.platform import gui
from cs.classification import ObjectClassification
from cs.audittrail import AuditTrailDetailLongText
from cs.documents import Document
import json
from cdb.tools import load_callable

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

LOG = logging.getLogger(__name__)

fRQMSpecObjectDocumentReference = Forward(__name__ + ".RQMSpecObjectDocumentReference")
fRQMSpecObjectIssueReference = Forward(__name__ + ".RQMSpecObjectIssueReference")
fRQMSpecificationDocumentReference = Forward(__name__ + ".RQMSpecificationDocumentReference")
fRQMSpecificationStateProtocol = Forward(__name__ + ".RQMSpecificationStateProtocol")
fRQMExportProcessRun = Forward(__name__ + ".RQMExportProcessRun")
fRQMImportProcessRun = Forward(__name__ + ".RQMImportProcessRun")
fRQMProtocol = Forward(__name__ + ".RQMProtocol")
fRQMProtocolEntry = Forward(__name__ + ".RQMProtocolEntry")
fRQMSpecification = Forward("cs.requirements.RQMSpecification")
fRQMSpecObject = Forward("cs.requirements.RQMSpecObject")
fDocumentExportProfile = Forward(__name__ + ".DocumentExportProfile")


class RQMUnit(Object):
    __classname__ = "cdbrqm_unit"
    __maps_to__ = "cdbrqm_unit"


class RQMSpecObjectWeight(Object):
    __classname__ = "cdbrqm_req_weight"
    __maps_to__ = "cdbrqm_req_weight"


class RQMSpecObjectDiscipline(Object):
    __classname__ = "cdbrqm_req_discipline"
    __maps_to__ = "cdbrqm_req_discipline"


class RQMSpecObjectDocumentReference(Object):
    __classname__ = "cdbrqm_specobject2doc"
    __maps_to__ = "cdbrqm_specobject2doc"
    Document = references.Reference_1(Document,
                                      Document.cdb_object_id == fRQMSpecObjectDocumentReference.document_object_id)
    SpecObject = references.Reference_1(fRQMSpecObject,
                                        fRQMSpecObject.cdb_object_id == fRQMSpecObjectDocumentReference.specobject_object_id)


class RQMSpecObjectIssueReference(Object):
    __classname__ = "cdbrqm_specobject2issue"
    __maps_to__ = "cdbrqm_specobject2issue"

    SpecObject = references.Reference_1(fRQMSpecObject,
                                        fRQMSpecObject.cdb_object_id == fRQMSpecObjectIssueReference.specobject_object_id)

    def on_create_pre_mask(self, ctx):
        if self.SpecObject and self.SpecObject.Specification.cdb_project_id:
            ctx.set("cdb_project_id", self.SpecObject.Specification.cdb_project_id)


class RQMSpecificationDocumentReference(Object):
    __classname__ = "cdbrqm_specification2doc"
    __maps_to__ = "cdbrqm_specification2doc"
    Document = references.Reference_1(Document,
                                      Document.cdb_object_id == fRQMSpecificationDocumentReference.document_object_id)
    Specification = references.Reference_1(fRQMSpecification,
                                           fRQMSpecification.cdb_object_id == fRQMSpecificationDocumentReference.spec_object_id)


class RQMSpecificationStateProtocol(Object):
    __classname__ = "cdbrqm_spec_statiprot"
    __maps_to__ = "cdbrqm_spec_statiprot"


class RQMSpecificationCategory(Object):
    __classname__ = "cdbrqm_specification_category"
    __maps_to__ = "cdbrqm_specification_category"

    @classmethod
    @lru_cache()
    def get_default_category(cls=None):
        default = None
        defaultCategories = RQMSpecificationCategory.KeywordQuery(is_default_value=1)
        if len(defaultCategories):
            default = defaultCategories[0]
        return default


class RequirementPriority(Object):
    __classname__ = "cdbrqm_req_prio"
    __maps_to__ = "cdbrqm_req_prio"

    @classmethod
    @lru_cache()
    def get_priorities_by_priority(cls=None):
        priorities = RequirementPriority.Query()
        priority_by_priority = {}
        for priority in priorities:
            priority_by_priority[priority.priority] = priority
        return priority_by_priority


class RequirementCategory(Object):
    __classname__ = "cdbrqm_requirement_category"
    __maps_to__ = "cdbrqm_requirement_category"

    @classmethod
    @lru_cache()
    def getDefaultCategory(cls=None):
        default = None
        defaultCategories = RequirementCategory.KeywordQuery(is_default_value=1)
        if len(defaultCategories):
            default = defaultCategories[0]
        return default


class RQMExportProcessRun(Object):
    __classname__ = "cdbrqm_export_process_run"
    __maps_to__ = "cdbrqm_export_process_run"

    Protocols = references.Reference_N(
        fRQMProtocol, fRQMProtocol.cdbf_object_id == fRQMExportProcessRun.cdb_object_id,
        order_by="protocol_id DESC"
    )
    Files = references.Reference_N(
        CDB_File, CDB_File.cdbf_object_id == fRQMExportProcessRun.cdb_object_id
    )
    Specification = references.Reference_1(
        fRQMSpecification,
        fRQMSpecification.cdb_object_id == fRQMExportProcessRun.specification_object_id
    )
    Profile = references.Reference_1(
        fDocumentExportProfile,
        fDocumentExportProfile.cdb_object_id == fRQMExportProcessRun.profile_object_id
    )

    # all ucs
    CREATED = -2
    WAITING = 0
    RUNNING = 1
    # all ucs
    FINISHED = 100
    FAILED = -1


class RQMImportProcessRun(Object):
    __classname__ = "cdbrqm_import_process_run"
    __maps_to__ = "cdbrqm_import_process_run"

    Protocols = references.Reference_N(fRQMProtocol, fRQMProtocol.cdbf_object_id == fRQMImportProcessRun.cdb_object_id, order_by="protocol_id DESC")
    Files = references.Reference_N(CDB_File, CDB_File.cdbf_object_id == fRQMImportProcessRun.cdb_object_id)
    Specification = references.Reference_1(fRQMSpecification,
                                           fRQMSpecification.cdb_object_id == fRQMImportProcessRun.specification_object_id)

    # all ucs
    CREATED = 0
    CLIENT_UPLOAD_STARTED = 10
    # all ucs
    FINISHED = 100
    FAILED = -1

    def get_title(self):
        title = util.get_label('cdbrqm_jobstatus_import')
        return title % (self.source, self.Specification.GetDescription())


class RQMProtocolEntry(Object):
    __classname__ = "cdbrqm_protocol_entry"
    __maps_to__ = "cdbrqm_protocol_entry"
    Protocol = references.Reference_1(fRQMProtocol,
                                      fRQMProtocol.cdbf_object_id == fRQMProtocolEntry.cdbf_object_id,
                                      fRQMProtocol.protocol_id == fRQMProtocolEntry.protocol_id)
    ImportRun = references.Reference_1(fRQMImportProcessRun,
                                       fRQMImportProcessRun.cdb_object_id == fRQMProtocol.cdbf_object_id)
    ExportRun = references.Reference_1(fRQMExportProcessRun,
                                       fRQMExportProcessRun.cdb_object_id == fRQMProtocol.cdbf_object_id)


class RQMProtocolLogHandler(logging.Handler):

    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self._queue = []

    def flush(self):
        queue = self._queue
        self._queue = []  # prevent that another invocation of flush leads to unique errors
        for record in queue:
            # only handle log messages which are for rqm_protocol
            if hasattr(record, 'tags') and 'rqm_protocol' in record.tags:
                try:
                    message = self.format(record)
                except TypeError as e:
                    LOG.exception(e)
                    LOG.error(record)
                args = dict(
                    cdbf_object_id=self.cdbf_object_id,
                    protocol_id=self.protocol_id,
                    entry_id=self.entry_id,
                    entry_text=message[0:254],
                    level=record.levelno,
                    level_name=record.levelname,
                    parent_entry_id='-1'
                )
                args.update(RQMProtocolEntry.MakeChangeControlAttributes())
                pe = RQMProtocolEntry.Create(**args)
                pe.SetText('cdbrqm_protocol_entry_detail', message)
                self.entry_id += 1

    def emit(self, record):
        self._queue.append(record)


class RQMProtocol(Object):
    __classname__ = "cdbrqm_protocol"
    __maps_to__ = "cdbrqm_protocol"

    ProtocolEntries = references.Reference_N(fRQMProtocolEntry,
                                             fRQMProtocolEntry.cdbf_object_id == fRQMProtocol.cdbf_object_id,
                                             fRQMProtocolEntry.protocol_id == fRQMProtocol.protocol_id,
                                             order_by="entry_id DESC")
    ImportRun = references.Reference_1(fRQMImportProcessRun,
                                       fRQMImportProcessRun.cdb_object_id == fRQMProtocol.cdbf_object_id)
    ExportRun = references.Reference_1(fRQMExportProcessRun,
                                       fRQMExportProcessRun.cdb_object_id == fRQMProtocol.cdbf_object_id)

    def __init__(self, *args, **kwargs):
        super(RQMProtocol, self).__init__(*args, **kwargs)
        self._handler = RQMProtocolLogHandler()

    def _get_logger(self):
        return logging.getLogger(__name__ + ".{cls}@{context_id}@{p_id}".format(
            cls="RQMProtocol",
            context_id=self.cdbf_object_id,
            p_id=self.protocol_id)
        )

    def getLogger(self, level=None):
        if level is None:
            level = logging.INFO
        logger = self._get_logger()
        logger.setLevel(level)
        self._handler.cdbf_object_id = self.cdbf_object_id
        self._handler.protocol_id = self.protocol_id
        self._handler.entry_id = self.ProtocolEntries[0].entry_id + 1 if self.ProtocolEntries else 0
        self._handler.setLevel(level)
        logger.addHandler(self._handler)
        return logger

    def flush_and_exit(self):
        self._handler.flush()
        logger = self._get_logger()
        logger.removeHandler(self._handler)

    @classmethod
    def get_max_id(cls, cdbf_object_id):
        from cdb import sqlapi
        rs = sqlapi.RecordSet2(sql="SELECT MAX(protocol_id) protocol_id FROM {table} WHERE cdbf_object_id='{cdbf_object_id}'".format(table=cls.__maps_to__,
                                                                                                                                     cdbf_object_id=sqlapi.quote(cdbf_object_id)))
        rs = rs[0]
        rs = rs['protocol_id']
        if rs:
            return int(rs)
        else:
            return 0


class RQMProtocolLogging(object):

    def __init__(self, protocol, level=None, extra=None, **kwargs):
        self.protocol = protocol

        if level is not None:
            self.level = level
        elif (
            util.get_prop('rmil') and
            util.get_prop('rmil').upper() in [
                "CRITICAL",
                "ERROR",
                "WARNING",
                "INFO",
                "DEBUG"
            ]
        ):
            self.level = getattr(logging, util.get_prop('rmil').upper())

        self.logger = None
        self.extra = extra

    def __extra_wrapper(self, attr):

        def wrapper_func(*args, **kwargs):
            if 'extra' not in kwargs:
                return getattr(self.logger, attr)(*args, extra=self.extra, **kwargs)
            else:
                return getattr(self.logger, attr)(*args, **kwargs)

        return wrapper_func

    def __getattribute__(self, name):
        if name not in ['critical', 'debug', 'disabled', 'error', 'exception', 'fatal', 'info', 'warning']:
            return object.__getattribute__(self, name)
        return self.__extra_wrapper(name)

    def __enter__(self):
        self.logger = self.protocol.getLogger(self.level)
        return self

    def __exit__(self, *args):
        self.protocol.flush_and_exit()


class AuditTrailDetailRichText(AuditTrailDetailLongText):
    __classname__ = "cdb_audittrail_detail_richtext"


class DocumentExportProfile(Object):
    __classname__ = "cdbrqm_doc_export_profile"
    __maps_to__ = "cdbrqm_doc_export_profile"

    Files = references.Reference_N(
        CDB_File, CDB_File.cdbf_object_id == fDocumentExportProfile.cdb_object_id
    )

    @lru_cache()
    def get_settings(self):
        """
            Get the configured profile settings.

            :rtype: dict
            :return: The profile settings.
        """
        settings = self.GetText('cdbrqm_doc_export_profile_cfg')
        try:
            settings = json.loads(settings)
        except BaseException:
            settings = {}
        return settings

    def export(self, *args, **kwargs):
        export_func = self._check_fqpyname(
            logger=kwargs.get('logger'),
            extra=kwargs.get('extra')
        )
        kwargs['profile'] = self
        return export_func(*args, **kwargs)

    def _check_fqpy_change(self, ctx=None):
        if not self.CheckAccess('rqm_fqpy_edit'):
            fqpyname_before = self.fqpyname
            if fqpyname_before != ctx.dialog.fqpyname:
                raise ue.Exception("just_a_replacement", "You are not allowed to change the fqpyname")

    def _prevent_fqpy_change(self, ctx=None):
        if not self.CheckAccess('rqm_fqpy_edit'):
            ctx.set_readonly('fqpyname')

    def _check_fqpyname(self, ctx=None, logger=None, extra=None):
        logger = logger if logger is not None else LOG
        f = None
        try:
            f = load_callable(self.fqpyname)
        except (ImportError, ValueError):
            logger.error("%s is not a valid callable", self.fqpyname, extra=extra)
            raise ue.Exception("just_a_replacement", "%s is not a valid callable" % self.fqpyname)
        return f

    event_map = {
        (('create', 'copy', 'modify'), 'pre'): ('_check_fqpyname', '_check_fqpy_change'),
        (('create', 'copy', 'modify'), 'pre_mask'): ('_prevent_fqpy_change'),
    }


class ClassPropertiesCatalog(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):
        cdb_object_id = self.getInvokingDlgValue("cdb_object_id")
        specification_object_id = self.getInvokingDlgValue("specification_object_id")
        self.setResultData(
            ClassPropertiesCatalogContent(
                self, cdb_object_id, specification_object_id
            )
        )


class ClassPropertiesCatalogContent(gui.CDBCatalogContent):

    def __init__(self, catalog, cdb_object_id, specification_object_id):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        gui.CDBCatalogContent.__init__(self, tabdef)
        self._data = []
        self.specification_object_id = specification_object_id
        self.cdb_object_id = cdb_object_id
        self.code = None
        self.init_data(True)

    def init_data(self, refresh=False):
        if refresh:
            self._set_search_args()
            self._search_data()

    def _search_data(self):
        self._data = []
        args = dict(
            ref_object_id=[self.cdb_object_id, self.specification_object_id]
        )
        object_classifications = ObjectClassification.KeywordQuery(**args)
        for object_classification in object_classifications:
            clazz = object_classification.Class
            if clazz:
                properties = clazz.Properties
                if self.code:
                    filtered_properties = [p for p in properties if self.code in p.code]
                else:
                    filtered_properties = properties
                self._data.extend(filtered_properties)

    def _set_search_args(self):
        for arg in self.getSearchArgs():
            for name in ["code"]:
                if arg.name == name:
                    setattr(self, name, arg.value.replace('*', ''))

    def onSearchChanged(self):
        self.init_data(True)

    def refresh(self):
        self.init_data(True)

    def getNumberOfRows(self):
        return len(self._data)

    def getRowObject(self, row):
        return self._data[row].ToObjectHandle()
