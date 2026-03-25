#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Default state conditions below can be customized by inheritance:

class MyCompleteBomImpl(CompleteBomImpl):

    def init(self, params):
        self.Super(CompleteBomImpl).init(params)
        self.modifyAssemblyStateList = [10,20]
        self.newComponentStateList = [30, 40]


Assemblies indexed during operation will be released
finally and the old assembly index will be declared as invalid by
state change. This behavior can be customized also by inheritance:

class MyCompleteBomImpl(CompleteBomImpl):

    def perform_post_actions(self, assembly_component, session):
        # do not call Super(...) and implement your own behavior here.
        pass

"""

import traceback
from io import StringIO

from cdb import transaction

from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import Forward

from cs.tools.batchoperations import BatchOperation
from cs.tools.batchoperations import ObjectAssignment
from cs.vp.bom import AssemblyComponent
from cs.vp.items import Item

from cdb.platform.gui import Message

CompleteBomItemAssignment = Forward(__name__ + ".CompleteBomItemAssignment")
CompleteBomImpl = Forward(__name__ + ".CompleteBomImpl")

kNewComponentStateList = [200]  # Default state conditions for items to be used in assemblies by batch operations.
kModifyAssemblyStateList = [200]  # Default state conditions for assembly modifications by batch operations.


class BOMItemBatchOperation(BatchOperation):
    __match__ = BatchOperation.type_id == 'einzelteile'

    def checkAssemblyState(self, assembly):
        if hasattr(self, "_indexed_assemblies") and assembly.teilenummer in self._indexed_assemblies:
            return

        if not hasattr(self, "modifyAssemblyStateList"):
            self.modifyAssemblyStateList = kModifyAssemblyStateList
        if assembly.status not in self.modifyAssemblyStateList:
            return Message.GetMessage(4957, assembly.teilenummer, assembly.t_index,
                                      ','.join(map(str, self.modifyAssemblyStateList)))

    def checkNewComponentState(self, item):
        if not hasattr(self, "newComponentStateList"):
            self.newComponentStateList = kNewComponentStateList
        if item.status not in self.newComponentStateList:
            return Message.GetMessage(4956, item.teilenummer, item.t_index,
                                      ','.join(map(str, self.newComponentStateList)))

    def checkComponent(self, assembly_component, item):
        if (
            assembly_component.teilenummer != item.teilenummer and
            assembly_component.t_index != item.t_index
        ):
            return Message.GetMessage(4955, item.teilenummer, item.t_index,
                                      assembly_component.baugruppe, assembly_component.b_index,
                                      assembly_component.position)

    def createAssemblyComponent(self, assembly, item, position, quantity):
        AssemblyComponent.Create(baugruppe=assembly.teilenummer,
                                 b_index=assembly.t_index,
                                 teilenummer=item.teilenummer,
                                 t_index=item.t_index,
                                 position=position,
                                 variante="",
                                 auswahlmenge=0,
                                 menge=quantity,
                                 is_imprecise=0)

    def deleteAssemblyComponent(self, assembly, item, position):
        comp = AssemblyComponent.ByKeys(baugruppe=assembly.teilenummer,
                                        b_index = assembly.t_index,
                                        teilenummer = item.teilenummer,
                                        t_index = item.t_index,
                                        position = position)
        if comp is None:
            return Message.GetMessage(
                "cdb_batchop_06",
                item.teilenummer,
                item.t_index,
                assembly.teilenummer,
                assembly.t_index,
                position
            )
        comp.Delete()

    def replaceAssemblyComponent(self, assembly, item_old, item_new, position):
        comp = AssemblyComponent.ByKeys(baugruppe=assembly.teilenummer,
                                        b_index=assembly.t_index,
                                        teilenummer=item_old.teilenummer,
                                        t_index=item_old.t_index,
                                        position=position)
        if comp is None:
            return Message.GetMessage(
                "cdb_batchop_06",
                item_old.teilenummer,
                item_old.t_index,
                assembly.teilenummer,
                assembly.t_index,
                position
            )
        comp.teilenummer = item_new.teilenummer
        comp.t_index = item_new.t_index

    def createAssemblyIndex(self, assembly):
        if not hasattr(self, "_indexed_assemblies"):
            self._indexed_assemblies = {}

        if assembly.teilenummer not in self._indexed_assemblies:
            indexed_assembly = assembly.CreateIndex()
            self._indexed_assemblies[assembly.teilenummer] = indexed_assembly
        else:
            indexed_assembly = self._indexed_assemblies[assembly.teilenummer]
        return indexed_assembly

    def _assemblyStateChange(self, assembly, target_state):
        return_msg = ""
        err_msg = Message.GetMessage(4958, assembly.teilenummer, assembly.t_index, target_state)
        try:
            assembly.ChangeState(target_state)
        except RuntimeError as e:
            return_msg = err_msg + Message.GetMessage(4952) + ":\n  " + Message.GetMessage(4950) + str(e) + "\n"
        except:
            memfile = StringIO()
            traceback.print_exc(file=memfile)
            return_msg = err_msg + Message.GetMessage(4952) + ":\n"
            return_msg += "  *** PowerScript-Error ***:\n%s\n" % memfile.getvalue()
        return return_msg

    def _releaseIndexedAssembly(self, assembly_component):
        """
        Freigabe einer während der Ausführung indizierten Baugruppe.
        Bei erfolgreichem Statuswechsel wird der Vorgängerindex in den Status 'ungültig'
        Konnte der neue Index nicht freigegeben werden, wird der Vorgängerindex in den Status
        'in Änderung' gebracht.
        Wurde die Baugruppe während der Operationsausführung nicht indiziert,
        werden keine Änderungen vorgenommen.
        Im Fehlerfall wird eine entsprechende Fehlermeldung zurückgeliefert, sonst ein Leerstring.
        """
        return_msg = ""
        bnr = assembly_component.baugruppe
        if not hasattr(self, "_indexed_assemblies") or bnr not in self._indexed_assemblies:
            return return_msg  # nothing to do
        if not hasattr(self, "_post_handled_assemblies"):
            self._post_handled_assemblies = {}

        if bnr not in self._post_handled_assemblies:
            # Indizierte Baugruppe freigeben und den Vorgängerindex in den Status 'ungültig' bringen
            indexed_assembly = self._indexed_assemblies[bnr]
            return_msg = self._assemblyStateChange(indexed_assembly, 200)
            if return_msg == "":
                # Wenn der Statuswechsel nach 'freigegeben' erfolgreich war,
                # Statuswechsel für Vorgängerindex nach 'ungültig' durchführen.
                items = Item.KeywordQuery(teilenummer=bnr, status=190)
                for prev_assembly_index in items:
                    return_msg = self._assemblyStateChange(prev_assembly_index, 180)
            self._post_handled_assemblies[bnr] = return_msg
        else:
            # Baugruppe wurde bereits im Kontext einer anderen Stücklistenposition behandelt.
            return_msg = self._post_handled_assemblies[bnr]
        return return_msg

    def perform_post_actions(self, assembly_component, session):
        """ ggf. indizierte Baugruppe freigeben """
        if assembly_component is None:
            return Message.GetMessage("cdb_batchop_13")

        return self._releaseIndexedAssembly(assembly_component)

    def assignObject(self, obj):
        d = {"id": self.id,
             "exec_state": 0
             }

        keynames = ['baugruppe', 'b_index', 'teilenummer', 't_index', 'position']
        obj_keys =  {}
        for key in keynames:
            try:
                obj_keys[key] = obj[key]
            except KeyError:
                obj_keys.clear()
                break
        if not obj_keys:
            # construct by oid
            bom_item = AssemblyComponent.ByKeys(cdb_object_id=obj.cdb_object_id)
            obj_keys = {key: bom_item[key] for key in keynames}
            obj_keys["auswahlmenge"] = 0
            obj_keys["variante"] = ""
        d.update(obj_keys)
        try:
            self.TypeDefinition.AssignType()._Create(**d)
        except Exception:
            # already assigned
            pass


class BatchOperationBOMItemAssignment(ObjectAssignment):
    __maps_to__ = "cdbbop_bomitem_asgn"

    def setItem(self, ctx):
        # In param1/param2 wird immer der Artikel erwartet,
        # dessen Verwendungen durch die Sammeloperation bearbeitet werden.
        # Für Sammeloperationen auf beliebigen Stücklistenpositionen
        # (also nicht auf Basis der Verwendung eines bestimmten Artikels)
        # können param1/param2 auch leer bleiben.
        if not self.teilenummer:
            op = BatchOperation.ByKeys(self.id)
            self.teilenummer = op.param1
            self.t_index = op.param2

    def getObjectKeys(self):
        # old bom_items keys instead of cdb_object_id is used here
        keynames = ['baugruppe', 'b_index', 'teilenummer', 't_index', 'position']
        keys = {key: self[key] for key in keynames}
        return keys

    event_map = {
        (('create', 'copy'), 'pre_mask'): 'setItem'
        }


class CompleteBomItemAssignment(Object):
    __maps_to__ = "cdbbop_bomitem_para"

    Item = Reference_1(Item, CompleteBomItemAssignment.teilenummer, CompleteBomItemAssignment.t_index)


class CompleteBomImpl(BOMItemBatchOperation):

    __match__ = BatchOperation.type_id == 'einzelteile' and BatchOperation.operation == 'CompletePartsList'

    ItemAssignments = Reference_N(CompleteBomItemAssignment, CompleteBomItemAssignment.id == CompleteBomImpl.id)

    def init(self, params):
        # Erweiterunskriterium der Stückliste
        self.item = Item.ByKeys(params["param1"], params["param2"])
        if not self.item:
            return Message.GetMessage(4961, params["param1"], params["param2"])
        # Status der einzufügenden Komponenten prüfen: Die neue Komponente muss freigegeben sein.
        for item_asgn in self.ItemAssignments:
            err_msg = self.checkNewComponentState(item_asgn.Item)
            if err_msg:
                return err_msg

    def perform_action(self, assembly_component, session):
        if len(self.ItemAssignments) == 0:
            return

        if assembly_component is None:
            return Message.GetMessage("cdb_batchop_13")

        assembly = assembly_component.Assembly
        # Erweiterungskriterium prüfen.
        # Der als Operationsparameter übergebene Artikel muss in der Verwendung verbaut sein
        err_msg = self.checkComponent(assembly_component, self.item)
        if err_msg:
            return err_msg
        err_msg = self.checkAssemblyState(assembly)
        if err_msg:
            return err_msg
        indexed_assembly = self.createAssemblyIndex(assembly)
        # Hinzufügen der Stücklistenpositionen
        with transaction.Transaction():
            curr_pos = indexed_assembly.maxPosition()
            for new_comp in self.ItemAssignments:
                curr_pos += 10
                self.createAssemblyComponent(indexed_assembly, new_comp, curr_pos, new_comp.menge)


class CompleteBomVariantImpl(BOMItemBatchOperation):

    __match__ = BatchOperation.type_id == 'einzelteile' and BatchOperation.operation == 'CompletePartsListVar'

    def init(self, params):
        # Erweiterunskriterium der Stückliste
        self.item = Item.ByKeys(params["param1"], params["param2"])
        if not self.item:
            return Message.GetMessage(4961, params["param1"], params["param2"])
        # einzufügende Variante
        self.variant = Item.ByKeys(params["param3"], params["param4"])
        if not self.variant:
            return Message.GetMessage(4961, params["param3"], params["param4"])
        err_msg = self.checkNewComponentState(self.variant)
        if err_msg:
            return err_msg

    def perform_action(self, assembly_component, session):
        if assembly_component is None:
            return Message.GetMessage("cdb_batchop_13")

        assembly = assembly_component.Assembly
        # Erweiterungskriterium prüfen.
        # Der als Operationsparameter übergebene Artikel muss in der Verwendung verbaut sein
        err_msg = self.checkComponent(assembly_component, self.item)
        if err_msg:
            return err_msg
        err_msg = self.checkAssemblyState(assembly)
        if err_msg:
            return err_msg
        indexed_assembly = self.createAssemblyIndex(assembly)
        self.createAssemblyComponent(indexed_assembly, self.variant, assembly_component.position, assembly_component.menge)


class RemoveBomItemImpl(BOMItemBatchOperation):

    __match__ = BatchOperation.type_id == 'einzelteile' and BatchOperation.operation == 'DeleteComponent'

    def init(self, params):
        # zu löschende Komponente
        self.item = Item.ByKeys(params["param1"], params["param2"])
        if not self.item:
            return Message.GetMessage(4961, params["param1"], params["param2"])

    def perform_action(self, assembly_component, session):
        if assembly_component is None:
            return Message.GetMessage("cdb_batchop_13")

        assembly = assembly_component.Assembly
        # Die zu löschende Komponente muss in der ausgewählten Verwendung verbaut sein
        err_msg = self.checkComponent(assembly_component, self.item)
        if err_msg:
            return err_msg
        err_msg = self.checkAssemblyState(assembly)
        if err_msg:
            return err_msg
        indexed_assembly = self.createAssemblyIndex(assembly)
        err_msg = self.deleteAssemblyComponent(indexed_assembly,
                                     self.item,
                                     assembly_component.position)
        if err_msg:
            return err_msg


class PartReplacementImpl(BOMItemBatchOperation):

    __match__ = BatchOperation.type_id == 'einzelteile' and BatchOperation.operation == 'Replace Part'

    def init(self, params):
        # zu ersetzende Komponente
        self.item_old = Item.ByKeys(params["param1"], params["param2"])
        if not self.item_old:
            return Message.GetMessage(4961, params["param1"], params["param2"])
        # neue Komponente
        self.item_new = Item.ByKeys(params["param3"], params["param4"])
        if not self.item_new:
            return Message.GetMessage(4961, params["param3"], params["param4"])
        err_msg = self.checkNewComponentState(self.item_new)
        if err_msg:
            return err_msg

    def perform_action(self, assembly_component, session):
        if assembly_component is None:
            return Message.GetMessage("cdb_batchop_13")

        assembly = assembly_component.Assembly
        # Die zu ersetzende Komponente muss in der ausgewählten Verwendung verbaut sein
        err_msg = self.checkComponent(assembly_component, self.item_old)
        if err_msg:
            return err_msg
        err_msg = self.checkAssemblyState(assembly)
        if err_msg:
            return err_msg
        indexed_assembly = self.createAssemblyIndex(assembly)
        err_msg = self.replaceAssemblyComponent(indexed_assembly,
                                      self.item_old,
                                      self.item_new,
                                      assembly_component.position)
        if err_msg:
            return err_msg
