#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# vim: set fileencoding=latin1 :
# -*- Python -*-
# $Id$
# CDB:Browse
# Copyright (C) 1990 - 2006 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     BatchOperations.py
# Author:   aki
# Creation: 15.08.06
# Purpose:

# pylint: disable-msg=E0102,W0232,W0201,W0142

from __future__ import absolute_import
import datetime
import traceback

import six

from cdb.objects import Object, Reference, N, Forward, LocalizedField
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import CDBCatalogContent
from cdb.platform.gui import Message
from cdb.platform.olc import StateDefinition
from cdb.platform.mom.entities import Class
from cdb import sqlapi, util, misc, auth, tools, decomp, typeconversion, ElementsError
from cdbwrapc import CDBClassDef

from cdb import transaction

# Forward declarations
TypeDefinition = Forward(__name__ + ".TypeDefinition")
OperationDefinition = Forward(__name__ + ".OperationDefinition")
BatchOperation = Forward(__name__ + ".BatchOperation")
ExecSession = Forward(__name__ + ".ExecSession")

# Constants
kExecStateNotExecuted = 0
kExecStateError = 1
kExecStateOk = 2


class _LoadMessage(object):
    def __init__(self, nr):
        self._nr = nr
        self._msg = None

    def __get__(self, source, mytype=None):
        if self._msg is None:
            self._msg = Message.GetMessage(self._nr)
        return self._msg


class _Messages:
    kErr = _LoadMessage(4952)
    kOk = _LoadMessage(4953)
    kErrCDB = _LoadMessage(4950)
    kPost = _LoadMessage(4951)
    kState = _LoadMessage(4954)


class TypeDefinition(Object):
    __maps_to__ = "cdbbop_typedef"

    OperationsByID = Reference(1, OperationDefinition, OperationDefinition.type_id == TypeDefinition.type_id,
                               indexed_by=OperationDefinition.operation)

    Operations = Reference(N, OperationDefinition, OperationDefinition.type_id == TypeDefinition.type_id)

    def ObjectType(self):
        return tools.getObjectByName(self.obj_type)

    def AssignType(self):
        return tools.getObjectByName(self.asgn_type)

    def get_param_masks(self):
        """ Liefert Liste mit Namen der Paramterregister aller konfigurierten Operationen """
        result = []
        for op in self.Operations:
            register_name = op.param_register
            if register_name not in result:
                result.append(register_name)
        return result

    def get_param_mask(self, operation):
        """ Liefert den Namen des Parameterregisters fuer die Operation """
        if self.OperationsByID[operation].param_register:
            return self.OperationsByID[operation].param_register
        return None

    def get_registers_to_disable(self, operation):
        """ Liefert Liste mit Maskenregistern, die fuer die Operation ausgeblendet werden koennen """
        result = self.get_param_masks()
        if result:
            del result[result.index(self.OperationsByID[operation].param_register)]
        return result

    def on_create_post_mask(self, ctx):
        self.type_id = self.ObjectType().GetTableName()


class ObjectAssignment(Object):
    operation = None
    log_buffer = ""
    _exec_state = None
    _exec_info = None

    @classmethod
    def Reset(cls, operation):
        sqlapi.SQLupdate("%s set infotext = '', exec_state = %s where id = '%s'" %
                         (cls.GetTableName(), kExecStateNotExecuted, operation.id))
        if operation.TypeDefinition.log_rel:
            sqlapi.SQLdelete("from %s where id = '%s'" %
                             (operation.TypeDefinition.log_rel, operation.id))

    @classmethod
    def getPendingObjects(cls, operation):
        assignments = operation.TypeDefinition.AssignType().Query(
            "id = '%s' and exec_state != %s" % (operation.id, kExecStateOk))
        for a in assignments:
            a.operation = operation
        return assignments

    @classmethod
    def getObjects(cls, operation):
        assignments = operation.TypeDefinition.AssignType().KeywordQuery(id=operation.id)
        for a in assignments:
            a.operation = operation
        return assignments

    def getObjectKeys(self):
        keys = {}
        for key in self.operation.TypeDefinition.ObjectType().KeyNames():
            keys[key] = self[key]
        return keys

    def getObject(self):
        return self.operation.TypeDefinition.ObjectType().ByKeys(**self.getObjectKeys())

    def log(self, msg):
        if not msg:
            return
        self.log_buffer += "%s\n" % msg

    def _writeLog(self):
        log_rel = self.operation.TypeDefinition.log_rel

        if log_rel:
            self.SetText(log_rel, self.log_buffer + self.GetText(log_rel))
        logs = self.log_buffer
        self.log_buffer = ""
        return logs

    def finalize(self, session=None):
        self.Update(infotext=self._exec_info.replace("\n", " "),
                    exec_state=self._exec_state)

        state_txt = ""
        if self.exec_state == kExecStateOk:
            state_txt = _Messages.kOk
        elif self.exec_state == kExecStateError:
            state_txt = _Messages.kErr
        self.log(_Messages.kState + " " + state_txt)  # "Status: "
        self.log(('=' * 40) + "\n")
        logs = self._writeLog()

        # write session log
        if session:
            obj = self.getObject()
            if obj:
                session.log(obj.GetDescription() + "\n")
            else:
                # object may be deleted during operation. log object keys instead of description tag.
                session.log(
                    "/".join(["%s = %s" % (v[0], v[1]) for v in list(six.iteritems(self.getObjectKeys()))]) + "\n")
            session.log(logs.replace(session.exec_info, ""))

    def setExecutionState(self, info_str):
        if info_str == _Messages.kOk:
            if self._exec_state != kExecStateError:
                self._exec_state = kExecStateOk
                self._exec_info = _Messages.kOk
        else:
            self._exec_state = kExecStateError
            self._exec_info = info_str
        return self._exec_state


class OperationDefinition(Object):
    __maps_to__ = "cdbbop_opdef"

    Name = LocalizedField('name')


class BatchOperation(Object):
    __maps_to__ = "cdbbop_operation"

    TypeDefinition = Reference(1, TypeDefinition, BatchOperation.type_id)

    def assignObject(self, obj):
        """ Ordnet ein Objekt der Sammeloperation zu.
        obj ist ein Dictionary, das mindestens die Schluessel des zuzuordnenden
        Objekt enthaelt."""

        d = {"id": self.id,
             "exec_state": 0
             }
        keys = self.TypeDefinition.AssignType().GetTablePKeys()
        for key in keys:
            if key.name != "id":
                try:
                    d[key.name] = obj[key.name]
                except KeyError:
                    # Fix for einzelteile.auswahlmenge, which is unused in
                    # many installations:
                    # If keys are missing we assume that they
                    # are empty for char fields and
                    # 0 for float and integer fields.
                    if key.type in [sqlapi.SQL_FLOAT, sqlapi.SQL_INTEGER]:
                        d[key.name] = 0
                    else:
                        d[key.name] = ""
                    misc.cdblogv(misc.kLogMsg, 5, "BatchOperation.assignObject: Missing key %s. "
                                                  "Setting value to '%s' " % (key.name, d[key.name]))
        try:
            self.TypeDefinition.AssignType()._Create(**d)
        except Exception:
            # war schon zugeordnet
            pass

    def resetExecutionState(self):
        self.Update(exec_state=kExecStateNotExecuted,
                    failures=0,
                    successes=0)

    def newSession(self):
        session = ExecSession.Create(id=ExecSession.makeID(),
                                     folder_id=self.id,
                                     persno=auth.persno,
                                     exec_date=datetime.datetime.now())
        session.init(self)
        return session

    def getOperationParameters(self):
        # Operationsparameter ermitteln
        op_params = {}
        for i in six.moves.range(10):
            param_key = "param%d" % (i + 1)
            op_params[param_key] = self[param_key]
        return op_params

    @classmethod
    def CreateFromContext(cls, ctx):
        # Sammeloperation anlegen
        attrs = ["id", "type_id", "operation", "exec_state", "param1", "param2", "param3", "param4", "param5",
                 "param6", "param7", "param8", "param9", "param10", "description", "failures", "successes"]
        values = {}
        values["cdb_cdate"] = datetime.datetime.now()
        values["cdb_mdate"] = datetime.datetime.now()
        values["cdb_cpersno"] = auth.persno
        values["cdb_mpersno"] = auth.persno
        for attr in attrs:
            if attr in ctx.dialog.get_attribute_names():
                values[attr] = ctx.dialog[attr]
            else:
                values[attr] = ""
        op = BatchOperation.Create(**values)
        # Objekte zuordnen
        with transaction.Transaction():
            for obj in ctx.objects:
                op.assignObject(obj)
        # ggf. Operation sofort ausfuehren
        if ctx.dialog.execute_now == '1':
            op.execute()
            ctx.refresh_tables([op.type_id])
        ctx.refresh_tables(["cdbbop_operation"])

        # anzeigen
        ctx.url(op.MakeURL("CDB_ShowObject"))

    def setNextMaskExpected(self, ctx):
        if ctx.get_current_mask() == "initial::predicate_mask":
            # Flag fuer Folgemaske setzen, da es auf jeden Fall ein operationsspezifisches Register gibt
            ctx.next_mask_expected(1)

    def setFollowUpOperation(self, ctx):
        if not ctx.error:
            ctx.set_followUpOperation("CDB_ShowObject", 1)

    def on_copy_post(self, ctx):
        if not ctx.error:
            self.resetExecutionState()

    def on_create_pre_mask(self, ctx):
        if self.TypeDefinition and len(self.TypeDefinition.Operations) == 1:
            ctx.set("operation", self.TypeDefinition.Operations[0].operation)
            ctx.set("mapped_op_name", self.TypeDefinition.Operations[0].Name[''])

    def on_relship_copy_post(self, ctx):
        # Ausfuehrungsstatus und Protokoll der zugeordneten Objekte zuruecksetzen
        self.TypeDefinition.AssignType().Reset(self)

    def on_cdbbop_operation_exec_now(self, ctx):
        op = BatchOperation.ByKeys(ctx.object.id)
        op.execute()
        ctx.refresh_tables(["cdbbop_operation", op.type_id])

    @classmethod
    def run(cls, myid):
        return BatchOperation.ByKeys(myid).execute()

    event_map = {
        (('create', 'copy'), 'pre_mask'): 'setNextMaskExpected',
        (('create', 'copy'), 'post'): 'setFollowUpOperation',
    }

    def _call(self, m, *args):
        info_str = _Messages.kOk
        msg = ""
        op = getattr(self, m, None)
        if op:
            try:
                err_msg = op(*args)
                if err_msg:
                    info_str = (_Messages.kErr + ": " + err_msg)[:255]
                    msg += err_msg + "\n"
            except RuntimeError as e:
                cdb_err = misc.unescape_string(six.text_type(e))
                info_str = (_Messages.kErr + ": " + cdb_err)[:255]
                msg += _Messages.kErrCDB + "\n" + cdb_err + "\n"
            except:
                memfile = six.StringIO()
                traceback.print_exc(file=memfile)
                info_str = _Messages.kErr + ": *** PowerScript-Error ***"
                msg += "*** PowerScript-Error ***:\n%s" % memfile.getvalue()
        return info_str, msg

    # Ausfuehren der Sammeloperation
    def execute(self):
        session = self.newSession()
        # zugeordnete Objekte ermitteln, die noch nicht erfolgreich ausgefuehrt wurden
        asgn_objects = self.TypeDefinition.AssignType().getPendingObjects(self)
        if asgn_objects:
            # Initialisierung der Operation
            info_str, msg = self._call("init", self.getOperationParameters())
            if msg:
                msg = _Messages.kErr + ":\n" + msg
                session._failures = len(asgn_objects)
                session.log(msg)
                # Initialisierungsfehler fuer alle zugeordneten Objekte setzen
                for asgn_obj in asgn_objects:
                    asgn_obj.log(session.exec_info)
                    asgn_obj.log(msg)
                    asgn_obj.setExecutionState(info_str)
                    asgn_obj.finalize()
            else:
                # Ausfuehren der Operation fuer jedes zugeordnete Objekt

                for asgn_obj in asgn_objects:
                    asgn_obj.log(session.exec_info)
                    info_str, msg = self._call("perform_action", asgn_obj.getObject(), session)
                    if msg:
                        msg = _Messages.kErr + ":\n" + msg
                    # set execution states and info string
                    asgn_obj.setExecutionState(info_str)
                    # append log entry
                    asgn_obj.log(msg)

                # Ausfuehren der Post Aktionen fuer jedes zugeordnete Objekt
                for asgn_obj in asgn_objects:
                    info_str, msg = self._call("perform_post_actions", asgn_obj.getObject(), session)
                    if msg:
                        msg = _Messages.kErr + ":\n" + msg
                    if asgn_obj.setExecutionState(info_str) == kExecStateOk:
                        session._successes += 1
                    else:
                        session._failures += 1
                    # log
                    if msg != "":
                        asgn_obj.log(_Messages.kPost)  # "Ausfuehrung von abschliessenden Aktionen ...\n"
                        asgn_obj.log(msg)
                    asgn_obj.finalize(session)

        return session.finalize()

    @classmethod
    def on_cdbbop_decomp_now(cls, ctx):
        cls.GenerateDecomposition()

    @classmethod
    def GenerateDecomposition(cls):
        decompsource = decomp.DecompSource(source_id=None,
                                           relation="cdbbop_typedef",
                                           key_attr="type_id",
                                           parent_key_attr=None,
                                           attribute_mappings={"type_id": "type_id"},
                                           c_conditions={},
                                           s_conditions={},
                                           label_attribute="name_<language>",
                                           position_attr="",
                                           icon_attr="",
                                           leaf_attr="",
                                           default_icon="Folder",
                                           leaf_icon="Folder",
                                           root_id="",
                                           order_by="name_d",
                                           py_generator=__name__ + ".BatchOperation.GenerateDecomposition")

        # remove decompositions based on the source object
        decompsource.delete_decompositions()
        # create decomposition
        decompsource.generate_decomposition("CDBBOP_OPERATION_TYPES")


class ExecSession(Object):
    __maps_to__ = "cdbbop_prot"

    def init(self, op):
        self.op = op
        self.exec_info = "%s, %s\n" % (auth.persno, typeconversion.to_legacy_date_format(datetime.datetime.now()))
        self._failures = 0
        self._successes = 0
        self._log_buffer = ""

    def log(self, msg):
        self._log_buffer += msg

    def finalize(self):
        self.Update(exec_state=kExecStateError if self._failures else kExecStateOk,
                    failures=self._failures,
                    successes=self._successes)

        # Status auch fuer die Operation setzen
        self.op.Update(exec_state=self.exec_state,
                       failures=self.failures,
                       successes=self.successes)
        if len(self._log_buffer) > 2000:
            for part in partition(self._log_buffer, 2000):
                sql_query = "into cdbbop_prot_txt (id, zeile, text) VALUES ({id}, (SELECT CASE WHEN max(zeile) is NULL " \
                            "THEN 0 ELSE max(zeile)+1 END AS zeile FROM cdbbop_prot_txt WHERE id={id}),'{text}')".format(
                    id=self.id, text=sqlapi.quote(part))
                sqlapi.SQLinsert(sql_query)
        else:
            sql_query = "into cdbbop_prot_txt (id, zeile, text) VALUES ({id}, (SELECT CASE WHEN max(zeile) is NULL " \
                        "THEN 0 ELSE max(zeile)+1 END AS zeile FROM cdbbop_prot_txt WHERE id={id}),'{text}')".format(
                        id=self.id, text=sqlapi.quote(self._log_buffer))
            sqlapi.SQLinsert(sql_query)

        self._log_buffer = ""
        return self.exec_state, self.failures, self.successes

    @classmethod
    def makeID(cls):
        return util.nextval("cdbbop_prot")


class WithBatchOperations(object):
    @classmethod
    def on_cdbbop_operation_create_pre_mask(cls, ctx):
        if ctx.get_current_mask() == "initial":
            type_id = cls.setOperationType(ctx)
            cls.presetOperation(type_id, ctx)
            ctx.next_mask_expected(1)

    @classmethod
    def on_cdbbop_operation_create_post_mask(cls, ctx):
        if ctx.get_current_mask() == "initial":
            mask = TypeDefinition.ByKeys(ctx.dialog.type_id).get_param_mask(ctx.dialog.operation)
            if mask:
                ctx.next_mask(mask)

    @classmethod
    def on_cdbbop_operation_create_now(cls, ctx):
        BatchOperation.CreateFromContext(ctx)

    @classmethod
    def setOperationType(cls, ctx):
        type_id = ""
        if hasattr(cls, "GetTableName"):
            type_id = cls.GetTableName()
            ctx.set("type_id", type_id)
        return type_id

    @classmethod
    def presetOperation(cls, type_id, ctx):
        # Wenn es nur eine Operation fuer den Typ gibt, diese schon vorbelegen
        typedef = TypeDefinition.ByKeys(type_id)
        if len(typedef.Operations) == 1:
            ctx.set("operation", typedef.Operations[0].operation)
            ctx.set("mapped_op_name", typedef.Operations[0].Name[''])

    @classmethod
    def mandatoryMaskParametersFilled(cls, ctx):
        param_mask = TypeDefinition.ByKeys(ctx.dialog.type_id).get_param_mask(ctx.dialog.operation)
        if param_mask:
            from cdb.platform import gui
            masks = gui.Mask.ByName(param_mask)
            if len(masks) > 0:
                mandatory_attrs = masks[0].MandatoryAttributes()
                for attr in mandatory_attrs:
                    if attr not in ctx.dialog.get_attribute_names() or ctx.dialog[attr.attribut] == "":
                        return False
        return True


class TargetStateCatalogData(CDBCatalogContent):
    def __init__(self, bop_objects, relation, catalog):
        """
        Initializes the catalog. `bop_objects` are the objects
        assigned to the batch operation as an iterable of
        `cdb.mom.CDBObjectHandle` objects. The catalog will
        look for common states of `bop_objects` which means
        `status` and `cdb_status_txt` have the same value.
        """
        self.cdef = catalog.getClassDefSearchedOn()
        tabdefname = catalog.getTabularDataDefName()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        life_cycles = []
        if bop_objects:
            for obj in bop_objects:
                olc = obj.getOLC()
                if olc and olc not in life_cycles:
                    life_cycles.append(olc)
        else:
            if relation:
                for olc in Class.ByRelation(relation).getWorkflowClass().Workflows:
                    life_cycles.append(olc.objektart)

        all_states = StateDefinition.KeywordQuery(objektart=life_cycles, order_by="statusnummer")
        # Only states that are available for all olcs and who have the same label for a state number are
        # part of the result
        self._data = []
        candidate = None
        count = 0
        nr_of_lcs = len(life_cycles)
        for state in sorted(set(all_states), key=lambda state: state.statusnummer):
            if not candidate or candidate.statusnummer != state.statusnummer:
                candidate = state
                count = 1
            elif candidate.statusbezeich == state.statusbezeich:
                count += 1

            if count == nr_of_lcs:
                self._data.append(candidate)

    def getNumberOfRows(self):
        return len(self._data)

    def getRowObject(self, row):
        return self._data[row].ToObjectHandle()


class TargetStateCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        """
        Called by the framework to initialize the catalog.
        """
        batch_op_objects = []
        relation = ""
        cdef = self.getInvokingOpClassDef()
        if cdef:
            if cdef.getClassname() == "cdbbop_operation":
                # The batch operation already exists - we have to find out
                # which objects are involved
                ol = self.getInvokingOpObjects()
                if ol:
                    bop = BatchOperation.ByKeys(ol[0].getValue("id", False))
                    bop_objects = [obj.getObject() for obj in
                                   bop.TypeDefinition.AssignType().getPendingObjects(bop)]
                    # When copying batch operations there are no PendingObjects
                    # so get all
                    if not bop_objects:
                        bop_objects = [obj.getObject() for obj in
                                       bop.TypeDefinition.AssignType().getObjects(bop)]
                    batch_op_objects = [obj.ToObjectHandle() for obj in bop_objects if obj]
                else:
                    # No batch_op_objects available
                    try:
                        relation = self.getInvokingDlgValue("type_id")
                    except ElementsError as e:
                        pass
            else:
                batch_op_objects = [obj for obj in self.getInvokingOpObjects()]

        self.setResultData(TargetStateCatalogData(batch_op_objects, relation, self))


def partition(l, n):
    for i in six.moves.range(0, len(l), n):
        yield l[i:i + n]
