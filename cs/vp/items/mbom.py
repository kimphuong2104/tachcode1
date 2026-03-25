#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-
# $Id$
# CDB:Browse
# Copyright (C) 1990 - 2006 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     mbom.py
# Author:   aki
# Creation: 05.03.2014
# Purpose:

# pylint: disable-msg=E0102,W0142,W0212,W0201

import cdbwrapc

from cdb import constants
from cdb import sig
from cdb import ue
from cdb.classbody import classbody
from cdb.objects import ByID, Object
from cdb.objects import ReferenceMethods_1
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import operations
from cdb.objects.org import Organization
from cdb.platform import mom, gui
from cdb.platform.gui import Label
from cdb.platform.olc import StateChangeDefinition

from cs.vp.bom import get_mbom_bom_type, get_sbom_bom_type, BomType, RBOM_COPY_ARG_NAME
from cs.vp.items import Item
from cs.web.components.ui_support.frontend_dialog import FrontendDialog

CREATE_MBOM_OP_NAME = "cdb_create_mbom"

MBOM_DEPENDENT_FIELDS = ['cdb_depends_on', 'site_object_id']

DERIVED_BOM_CREATED = sig.signal()


def _run(operation, cls_or_obj, **args):
    if isinstance(cls_or_obj, Object):
        cls_or_obj = cls_or_obj.ToObjectHandle()

    op = cdbwrapc.Operation(operation,
                            cls_or_obj,
                            mom.SimpleArguments(**args))
    op.run()

    result = op.getObjectResult()
    return result


@classbody
class Item(object):
    def getEngineeringView(self):
        if self.cdb_depends_on != '' and self.cdb_depends_on is not None:
            return Item.ByKeys(cdb_object_id=self.cdb_depends_on)

    EngineeringView = ReferenceMethods_1(Item, getEngineeringView)

    ManufacturingViews = Reference_N(Item, Item.cdb_depends_on == Item.cdb_object_id)
    ManufacturingSite = Reference_1(Organization, Organization.cdb_object_id == Item.site_object_id)

    BomType = Reference_1(BomType, BomType.cdb_object_id == Item.type_object_id)

    def get_filter_dict(self, ctx):
        filter_text = ""
        filter_arguments = {}
        if "site_object_id" in ctx.dialog.get_attribute_names():
            if ctx.dialog.site_object_id:
                label = mom.fields.DDField.ByKeys("part", "site_object_id").Label['']
                value = ByID(ctx.dialog.site_object_id).GetDescription()
                filter_text = label + ": " + value
                filter_arguments["site_object_id"] = ctx.dialog.site_object_id

        return filter_arguments, filter_text

    def bom_type_changed(self, ctx):
        """
        Called if the type_object_id field has been changed interactively.
        Sets dependent fields readonly/writeable and clears/restores the
        values of these fields.
        """
        if self.IsDerived():
            if ctx.action == "modify":
                ebom = Item.ByKeys(cdb_object_id=ctx.object.cdb_depends_on)
                if ebom:
                    self.materialnr_erp = ebom.materialnr_erp
            ctx.set_fields_writeable(MBOM_DEPENDENT_FIELDS)
            for field_name in MBOM_DEPENDENT_FIELDS:
                if field_name in ctx.object.get_attribute_names():
                    self[field_name] = ctx.object[field_name]
        else:
            for field_name in MBOM_DEPENDENT_FIELDS:
                self[field_name] = ""
            ctx.set_fields_readonly(MBOM_DEPENDENT_FIELDS)
            if ctx.action == "modify":
                self.materialnr_erp = self.calc_erp_number()

    def ebom_changed(self, ctx):
        if self.cdb_depends_on:
            item = Item.ByKeys(cdb_object_id=self.cdb_depends_on)
            if item:
                self.materialnr_erp = item.materialnr_erp

    @sig.connect(Item, 'modify', 'dialogitem_change')
    @sig.connect(Item, 'create', 'dialogitem_change')
    @sig.connect(Item, 'copy', 'dialogitem_change')
    def _mbom_attr_changed(self, ctx):
        if ctx.changed_item == 'type_object_id':
            self.bom_type_changed(ctx)
        elif ctx.changed_item == 'cdb_depends_on':
            self.ebom_changed(ctx)

    def validate_changed_ebom(self, ctx):
        if self.IsDerived() and self.cdb_depends_on != ctx.object.cdb_depends_on:
            # For the first mBOM Version the eBOM assignment can be changed freely.
            # If more than one mBOM Index exists, all Versions must belong to the same eBOM.
            num_indexes = len(Item.KeywordQuery(teilenummer=self.teilenummer))
            old_ebom = Item.ByKeys(cdb_object_id=ctx.object.cdb_depends_on)
            if num_indexes > 1 and old_ebom:
                new_ebom = Item.ByKeys(cdb_object_id=self.cdb_depends_on)
                if not new_ebom or old_ebom.teilenummer != new_ebom.teilenummer:
                    raise ue.Exception('cdb_invalid_ebom_for_mbom', old_ebom.teilenummer)

    @sig.connect(Item, 'modify', 'pre')
    def _validate_changed_ebom(self, ctx):
        self.validate_changed_ebom(ctx)

    def validate_matching_bom_type(self, ctx):
        """
        When deriving a BOM as an index of an existing derived BOM, ensure that the BOM type stays the same,
        as it should not be possible that two indices of the same BOM have different BOM types.

        This validation is necessary because:
            - the user can select any BOM from the catalog in the Web UI, independent of the active BOM type /
              active master BOM selected in the BOM manager.
            - invalid combinations of parameters might be passed when using the powerscript operation API.
        """

        # BOM type currently selected in the BOM manager.
        selected_bom_type = getattr(ctx.dialog, "type_object_id", None)

        # BOM type of the BOM selected (from the catalog) for indexing.
        bom_type_of_source = self.type_object_id

        # If the BOM types differ, the indexing should not be possible, so raise an appropriate error.
        if selected_bom_type != bom_type_of_source:
            selected_bom_type_name = BomType.GetBomTypeForID(selected_bom_type).name
            bom_type_of_source_name = BomType.GetBomTypeForID(bom_type_of_source).name
            raise ue.Exception(
                "cdb_deriving_index_with_changed_bom_type",
                selected_bom_type_name,
                bom_type_of_source_name
            )

    def validate_same_master(self, ctx):
        """
        When deriving a BOM as an index of an existing derived BOM, ensure that the BOM selected for indexing
        is derived from the same master, or one of its indices, as the currently selected master in the BOM
        manager.

        This validation ensures that the newly derived index cannot be derived from a completely different
        master BOM than the selected derived BOM. However, deriving from a different index of the master BOM
        is still possible. This is necessary because:
            - the user can select any BOM from the catalog in the Web UI, independent of the active BOM type /
              active master BOM selected in the BOM manager.
            - invalid combinations of parameters might be passed when using the powerscript operation API.
        """

        # Get the master BOM that the index should derive from (the one selected in the BOM manager). Note
        # that cdb_depends_on is filled by the generate_derived_bom() function.
        cdb_depends_on = getattr(ctx.dialog, "cdb_depends_on", None)

        # Handle case that the master of the BOM selected for indexing differs.
        if cdb_depends_on and cdb_depends_on != self.cdb_depends_on:
            master_of_selected = Item.ByKeys(cdb_object_id=self.cdb_depends_on)
            current_master = Item.ByKeys(cdb_object_id=cdb_depends_on)

            # Edge case: selected BOM is itself not derived; indexing should not be possible.
            if not master_of_selected:
                raise ue.Exception(
                    "cdb_deriving_index_from_underived_master",
                    current_master.teilenummer,
                    self.teilenummer
                )

            # Prevent the indexing if the new index's master would differ from the one of the BOM selected for
            # indexing.
            if master_of_selected.teilenummer != current_master.teilenummer:
                raise ue.Exception(
                    "cdb_deriving_index_from_invalid_master",
                    current_master.teilenummer,
                    self.teilenummer,
                    master_of_selected.teilenummer)

    @sig.connect(Item, 'index', 'pre')
    def _validate_selected_bom_for_deriving_index(self, ctx):
        """
        Validate whether creating an index based on the selected BOM is possible in the context of the active
        BOM type and active master BOM in the BOM manager. All indices of a derived BOM must be assigned to
        exactly one master BOM or its indices.
        """

        # Check whether this indexing operation was triggered by the BOM manager operation "Create New Index
        # from Derivation".
        if self.is_create_mbom_op(ctx):
            self.validate_matching_bom_type(ctx)
            self.validate_same_master(ctx)

    def setup_mbom_fields_on_copy(self, ctx):
        """
        Called on pre_mask to setup mbom related fields.
        """
        if not self.IsDerived():
            ctx.set_fields_readonly(MBOM_DEPENDENT_FIELDS)

    @sig.connect(Item, 'copy', 'pre_mask')
    def _setup_mbom_fields_on_copy(self, ctx):
        self.setup_mbom_fields_on_copy(ctx)

    def copy_bom_relship(self, ctx):
        if self.is_create_mbom_op(ctx):
            item = Item.ByKeys(cdb_object_id=ctx.sys_args.item_object_id)
            if 'question_copy_stl_relship_1st_level' in ctx.sys_args.get_attribute_names() and\
                    ctx.sys_args.question_copy_stl_relship_1st_level == ctx.MessageBox.kMsgBoxResultYes:

                args = {
                    "baugruppe": self.teilenummer,
                    "b_index": self.t_index,
                    # Pass flag so that AssemblyComponent.skip_relships_for_rbom_copy() does not copy
                    # certain relships (see cs.vp.bom.RELSHIPS_TO_SKIP_FOR_RBOM_COPY).
                    RBOM_COPY_ARG_NAME: True
                }

                for comp in item.Components:
                    if comp.Item:
                        args["position"] = comp.position
                        _run(constants.kOperationCopy, comp, **args)

    @sig.connect(Item, 'create', 'post')
    def _copy_bom_relship(self, ctx):
        self.copy_bom_relship(ctx)

    def setup_mbom_fields_on_create(self, ctx):
        if self.is_create_mbom_op(ctx):
            blacklist = [
                'cdb_object_id',
                'teilenummer',
                't_index',
                'status',
                'cdb_status_txt',
                't_ersatz_fuer',
                't_ersatz_durch',
                't_pruefer',
                't_pruef_datum'
            ]

            item = Item.ByKeys(cdb_object_id=ctx.sys_args.item_object_id)
            cldef = self.GetClassDef()
            args = {}
            for attr in cldef.getAttributeDefs():
                attr_name = attr.getName()
                if attr_name not in blacklist:
                    if not attr.is_text():
                        args[attr_name] = getattr(item, attr_name)
                    elif attr_name in ctx.dialog.get_attribute_names():
                        ctx.set(attr_name, item.GetText(attr_name))

            args.update(teilenummer='#',
                        t_index='',
                        cdb_depends_on=item.cdb_object_id,
                        cdb_copy_of_item_id=item.cdb_object_id,
                        type_object_id=get_mbom_bom_type().cdb_object_id,
                        materialnr_erp=item.materialnr_erp)
            self.Update(**args)
            ctx.set_fields_readonly(['cdb_depends_on', 'type_object_id'])
        if not self.IsDerived():
            ctx.set_fields_readonly(MBOM_DEPENDENT_FIELDS)

    @sig.connect(Item, 'create', 'pre_mask')
    def _setup_mbom_fields_on_create(self, ctx):
        self.setup_mbom_fields_on_create(ctx)

    def setup_mbom_fields_on_modify(self, ctx):
        readonly_attrs = set()
        num_indexes = len(Item.KeywordQuery(teilenummer=self.teilenummer))
        if num_indexes > 1:
            readonly_attrs.update(['type_object_id'])

        if not self.IsDerived():
            readonly_attrs.update(MBOM_DEPENDENT_FIELDS)
            if 'type_object_id' not in readonly_attrs and self.ManufacturingViews:
                readonly_attrs.add('type_object_id')
        ctx.set_fields_readonly(readonly_attrs)

    @sig.connect(Item, 'modify', 'pre_mask')
    def _setup_mbom_fields_on_modify(self, ctx):
        self.setup_mbom_fields_on_modify(ctx)

    @staticmethod
    def is_create_mbom_op(ctx):
        """
        Returns true, if the operation context is a cdb_create_mbom operation.
        """
        return CREATE_MBOM_OP_NAME in ctx.sys_args.get_attribute_names()


    @staticmethod
    def get_released_mboms(materialnr_erp, site_object_id, bom_type_id=None):
        """
        If no bom_type_id is given it is searched for mbom types, otherwise for the given bom_type_id.
        """
        type_id = bom_type_id if bom_type_id else get_mbom_bom_type().cdb_object_id
        return Item.KeywordQuery(
            materialnr_erp=materialnr_erp,
            type_object_id=type_id,
            site_object_id=site_object_id,
            status=[200, 300]
        )

    @sig.connect(Item, 'state_change', 'pre')
    def _check_released_mboms(self, ctx):
        """
        Released items are checked depending on the bom type of the item.
        """
        self.check_released_mboms(ctx)

    def check_released_mboms(self, ctx):
        """
        Released items are checked depending on the bom type of the item.
        """
        if not self.IsDerived() or not self.materialnr_erp or self.status != 200:
            return
        released_mboms = self.get_released_mboms(
            self.materialnr_erp, self.site_object_id, self.type_object_id
        )
        msite_name = self.ManufacturingSite.name if self.ManufacturingSite else ""
        if len(released_mboms) > 0:
            bom_type = BomType.GetBomTypeForID(self.type_object_id)
            raise ue.Exception("cdb_release_mbom_err",
                               self.materialnr_erp, msite_name, bom_type.name,
                               released_mboms[0].GetDescription(), bom_type.name)

    @sig.connect(Item, 'wf_step', 'post_mask')
    def _handle_release_mbom(self, ctx):
        """
        Released items are handled depending on the bom type of the item.
        """
        self.handle_release_mbom(ctx)

    def handle_release_mbom(self, ctx):
        """
        Released items are handled depending on the bom type of the item.
        """
        if not self.IsDerived() or self.status != 200 or not self.cdb_depends_on:
            return

        # ebom must be released first
        ebom = Item.ByKeys(cdb_object_id=self.cdb_depends_on)
        if ebom.status in (0, 100):
            raise ue.Exception("cdb_release_mbom_err2")
        # ebom cannot be obsolete
        if ebom.status in (170, 180):
            raise ue.Exception("cdb_release_mbom_err3")

        if self.materialnr_erp:
            # Ensure that only one derived BOM per materialnr_erp and manufacturing site and bom type is released
            released_mboms = self.get_released_mboms(
                self.materialnr_erp, self.site_object_id, self.type_object_id
            )
            if released_mboms:
                if not "question_release_derived_bom" in ctx.dialog.get_attribute_names():
                    other_ebom = Item.ByKeys(cdb_object_id=released_mboms[0].cdb_depends_on)
                    bom_type = BomType.GetBomTypeForID(self.type_object_id)
                    replacements = [self.materialnr_erp,
                                    self.ManufacturingSite.name if self.ManufacturingSite else "",
                                    bom_type.name,
                                    released_mboms[0].teilenummer, released_mboms[0].t_index,
                                    other_ebom.teilenummer, other_ebom.t_index,
                                    bom_type.name,
                                    bom_type.name,
                                    self.teilenummer, self.t_index,
                                    ebom.teilenummer, ebom.t_index,
                                    ]

                    msgbox = ctx.MessageBox("cdb_release_mbom_question",
                                            replacements,
                                            "question_release_derived_bom",
                                            ctx.MessageBox.kMsgBoxIconQuestion)
                    msgbox.addYesButton(1)
                    msgbox.addCancelButton()
                    ctx.show_message(msgbox)
                else:
                    # bisher freigegebene mBOM ungültig setzen
                    released_mboms[0].ChangeState(180)

    @staticmethod
    def _getLocalizedLabelText(ausgabe_label):
        """Returns the localized label text for the given label id, according to the current session language.

        :param ausgabe_label: The label id to retrieve.
        :return: The localized label text for the given label id."""

        lab = Label.ByKeys(ausgabe_label)
        return lab.Text['']

    @staticmethod
    def _get_state_int_by_label_str(objektart, status, state_as_label):
        """Maps the status name to the corresponding status number.
        This reflects the mechanism also used in the kernel, see
        int Workflow::getStateIntByLabelStr(const std::string& state_as_label) in olc.cc

        :param objektart: The name of the object life cycle
        :param status: The current status of the object (from_status)
        :param state_as_label: The status label which was retrieved from the dialog
        :return: The status number which corresponds to the given label

        :throws: ue.Exception if no matching status was found
        """

        label2state = dict()
        str2state = dict()
        for state_change_def in StateChangeDefinition.KeywordQuery(objektart=objektart, iststatus=status):
            to_state = state_change_def.ToState
            label2state[to_state.statusbez] = state_change_def.zielstatus
            str2state[to_state.statusbezeich] = state_change_def.zielstatus

        part_dest_status = label2state.get(state_as_label)
        if part_dest_status is None:
            part_dest_status = str2state.get(state_as_label)
        if part_dest_status is None:
            raise ue.Exception('invalid_state', state_as_label)

        return part_dest_status

    @staticmethod
    def check_released_mbom_hook(hook):
        """
        Web UI equivalent for the handle_release_mbom() post mask userexit.

        :param hook: The hook context
        """

        # Re-query the current item from the keys in the mask
        part_id = hook.get_new_value('teile_stamm.teilenummer')
        part_index = hook.get_new_value('teile_stamm.t_index')
        myself = Item.ByKeys(teilenummer=part_id, t_index=part_index)

        if not myself.IsDerived():
            # hook is only needed for derived parts ... no need to determine the destination status
            return

        # Map the destination status name to the status number
        part_dest_status_name = hook.get_new_value('.zielstatus')
        part_dest_status = Item._get_state_int_by_label_str(myself.cdb_objektart,
                                                            myself.status,
                                                            part_dest_status_name)

        if part_dest_status != 200 or not myself.cdb_depends_on:
            return

        # Get the eBOM for the mBOM
        ebom = Item.ByKeys(cdb_object_id=myself.cdb_depends_on)
        if ebom.status in (0, 100):
            raise ue.Exception("cdb_release_mbom_err2")
        # ebom cannot be obsolete
        if ebom.status in (170, 180):
            raise ue.Exception("cdb_release_mbom_err3")

        if myself.materialnr_erp:
            # Ensure that only one derived BOM per materialnr_erp and manufacturing site and bom type is released
            released_mboms = myself.get_released_mboms(
                myself.materialnr_erp, myself.site_object_id, myself.type_object_id
            )

            # If there is at least one already released mBOM, ask the user if this mBOM
            # shall be set to obsolete
            if released_mboms:
                # On submit, show the message box to the user if they did not already confirm it.
                # choice_result will be None for the first hook call, or 'abort' if the user aborted the
                # message box in a previous run.
                choice_result = hook.get_new_values().get(".choiceResult")
                if choice_result != 'confirm':
                    other_ebom = Item.ByKeys(cdb_object_id=released_mboms[0].cdb_depends_on)
                    bom_type = BomType.GetBomTypeForID(myself.type_object_id)
                    replacements = [myself.materialnr_erp,
                                    myself.ManufacturingSite.name if myself.ManufacturingSite else "",
                                    bom_type.name,
                                    released_mboms[0].teilenummer, released_mboms[0].t_index,
                                    other_ebom.teilenummer, other_ebom.t_index,
                                    bom_type.name,
                                    bom_type.name,
                                    myself.teilenummer, myself.t_index,
                                    ebom.teilenummer, ebom.t_index,
                                    ]

                    # Get all localized texts for the dialog
                    msg = gui.Message.GetMessage("cdb_release_mbom_question", *replacements)
                    msgTitle = Item._getLocalizedLabelText('pccl_cap_quest')
                    yesText = Item._getLocalizedLabelText('web.base.dialog_yes')
                    noText = Item._getLocalizedLabelText('web.base.dialog_no')

                    # Show the frontend dialog (will be shown after the hook terminates)
                    fe = FrontendDialog(msgTitle, msg, '.choiceResult')
                    fe.add_button(yesText, 'confirm', FrontendDialog.ActionCallServer, is_default=True)
                    fe.add_button(noText,  'abort',  FrontendDialog.ActionBackToDialog, is_cancel=True)
                    hook.set_dialog(fe)
                else:
                    # Hook was called again after the Frontend dialog was confirmed with "Yes"
                    # Then set the previously released mBOM to Obsolete
                    released_mboms[0].ChangeState(180)

    def generate_mbom(self, site_object_id=None, **sysargs):
        return self.generate_derived_bom(get_mbom_bom_type().cdb_object_id, site_object_id, **sysargs)

    def generate_sbom(self, site_object_id=None, **sysargs):
        return self.generate_derived_bom(get_sbom_bom_type().cdb_object_id, site_object_id, **sysargs)

    def generate_derived_bom(self, type_object_id, site_object_id=None, depends_on=None, create_index=False, **sysargs):
        blacklist = [
            'cdb_object_id',
            'teilenummer',
            't_index',
            'status',
            'cdb_status_txt',
            't_ersatz_fuer',
            't_ersatz_durch',
            't_pruefer',
            't_pruef_datum',
            'cdb_cdate',
            'cdb_mdate',
            'ce_valid_from',
            'ce_valid_to'
        ]

        cldef = self.GetClassDef()
        args = {}
        if create_index is False:
            for attr in cldef.getAttributeDefs():
                attr_name = attr.getName()
                if attr_name not in blacklist:
                    if not attr.is_text() and not attr.is_virtual() and not attr.is_mapped():
                        args[attr_name] = getattr(self, attr_name)

        # we are generating for example an sbom from an mbom
        # then we will associate the new sbom to the mbom
        if depends_on is None:
            cdb_depends_on = self.cdb_object_id
        else:
            cdb_depends_on = depends_on

        # Ensure that the newly derived bom receives the materialnr_erp from the correct (current) master.
        if self.cdb_depends_on == cdb_depends_on:
            # No need for query if source and new BOM derive from same BOM.
            materialnr_erp = self.materialnr_erp
        else:
            materialnr_erp = Item.ByKeys(cdb_object_id=cdb_depends_on).materialnr_erp

        args.update(
            cdb_depends_on=cdb_depends_on,
            cdb_copy_of_item_id=self.cdb_object_id,
            type_object_id=type_object_id,
            materialnr_erp=materialnr_erp,
            site_object_id=site_object_id
        )

        context = self if create_index else self.GetClassname()
        operation_name = constants.kOperationIndex if create_index else constants.kOperationNew

        mbom = operations.operation(
            operation_name,
            context,
            operations.system_args(
                cdb_create_mbom=1,
                item_object_id=self.cdb_object_id,
                **sysargs
            ),
            **args
        )
        return mbom
