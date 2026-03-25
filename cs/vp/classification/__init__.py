#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import ue
from cdb import sqlapi
from cdb import util
from cdb import misc
from cdb import cad
from cdb.transactions import Transaction
from cdb.classbody import classbody

from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import LocalizedField
from cdb.objects import ReferenceMethods_1
from cdb.objects import Reference_1
from cdb.objects import Reference_N

from cs.vp.items import Item
from cs.vp.classification import sml
from cs.documents import Document

from cdb.platform.mom import fields


fClassificationCategory = Forward(__name__ + ".ClassificationCategory")
fProperty = Forward(__name__ + ".Property")
fPropertySet = Forward(__name__ + ".PropertySet")
fPropertyValue = Forward(__name__ + ".PropertyValue")
fPropertyReference = Forward(__name__ + ".PropertyReference")
fCGCategoryReference = Forward(__name__ + ".CGCategoryReference")
fCGPropertySetReference = Forward(__name__ + ".CGPropertySetReference")


class CGDocumentReference(Object):
    __maps_to__ = "cdbsml_cg_docs"
    Document = Reference_1(Document, Document.z_nummer, Document.z_index)


class CGCategoryReference(Object):
    __maps_to__ = "cdbsml_cg_hier"

    Parent = Reference_1(fClassificationCategory, fCGCategoryReference.cgroup_id)
    Child = Reference_1(fClassificationCategory, fCGCategoryReference.child_id)


class CGPropertySetReference(Object):
    __maps_to__ = "cdbsml_cg_pset"

    PropertySet = Reference_1(fPropertySet, fCGPropertySetReference.pset_id)


class ClassificationCategory(Object):
    __maps_to__ = "cdbsml_cgroup"
    __classname__ = "cdbsml_cgroup"

    DocumentReferences = Reference_N(CGDocumentReference,
                                     CGDocumentReference.cgroup_id == fClassificationCategory.cgroup_id)

    Subcategories = Reference_N(CGCategoryReference,
                                CGCategoryReference.cgroup_id == fClassificationCategory.cgroup_id)

    PropertySetReferences = Reference_N(fCGPropertySetReference,
                                        fCGPropertySetReference.cgroup_id == fClassificationCategory.cgroup_id)

    @classmethod
    def getRoot(cls):
        return cls.ByKeys('root')

    @classmethod
    def on_preview_available_now(cls, ctx):
        ctx.enablePreview()

    def on_preview_now(self, ctx):
        # Import module here late, to avoid initialization of cdb.pdd.objects
        from cs.vp.classification.oplan.sml import getCGroupInfoURL
        ctx.setPreviewURL(getCGroupInfoURL(ctx.object))

    def CheckPsetID(self, ctx):
        if "cgroup_id" in ctx.dialog.get_attribute_names():
            sml.check_pset_id(ctx.dialog.cgroup_id)

    event_map = {
        (('copy', 'create'), 'post_mask'): ('CheckPsetID')
    }


class PropSetDocumentReference(Object):
    __maps_to__ = "cdbsml_pset_doc"

    Document = Reference_1(Document, Document.z_nummer, Document.z_index)


class PropertyReference(Object):
    __maps_to__ = "cdbsml_pset_prop"
    __classname__ = "cdbsml_pset_prop"

    Property = Reference_1(fProperty, fPropertyReference.prop_id)
    PropertySet = Reference_1(fPropertySet, fPropertyReference.pset_id)
    DDField = ReferenceMethods_1(fields.DDField, lambda self: self._getDDField())

    def _getDDField(self):
        """
        """
        flds = fields.DDField.KeywordQuery(cdb_object_id=self.dd_attr_uuid)
        try:
            result = flds[0]
        except:
            result = None
        return result

    def on_delete_post(self, ctx):
        if ctx.error == 0:
            # Die Merkmalwertein-/ausschlussrelation von Hand loeschen, da der zugehoerige View
            # via outer join funktioniert und nicht wirklich alle Werte da sind
            sqlapi.SQLdelete("FROM cdbsml_pval_subset WHERE pset_id = '%s' and prop_mk = '%s'" % (sqlapi.quote(self.pset_id), sqlapi.quote(self.prop_mk)))

    def _refreshDataDictionary(self, sml_class, previous_attrdef):
        """
        Creates the data dictionary attribute or if previous_attrdef is None
        refreshes previous_attrdef
        """
        clss = None
        values = {"classname": sml_class.classname,
                  "is_mandatory": 0,
                  "not_replicated": 0,
                  "position": self.prop_nr,
                  "gui_autodefined": 1
                  }
        if not previous_attrdef:
            values["field_name"] = sml_class.makeFieldName(self.prop_mk)

        if self.Property:
            if self.Property.din4001_mm_me and int(self.Property.din4001_mm_me) >= 1000:
                clss = fields.DDPhysicalQuantity
                values["pq_type"] = self.Property.din4001_mm_me
            elif self.Property.din4001_mm_me and int(self.Property.din4001_mm_me) == 999:
                # Spezialfall: Sennheiser Mixed Felder
                clss = fields.DDSHMixed
            elif self.Property.din4001_mm_dt in ("T", "B"):
                clss = fields.DDCharField
                values["data_length"] = self.Property.din4001_mm_v1
            elif self.Property.din4001_mm_dt == "Z":
                if not self.Property.din4001_mm_n1 or not int(self.Property.din4001_mm_n1):
                    clss = fields.DDIntegerField
                else:
                    clss = fields.DDFloatField
                    if int(self.Property.din4001_mm_n1) > 0:
                        values["float_post_decimal"] = self.Property.din4001_mm_n1

            if clss:
                # Setting the labels
                for field in clss.GetFields():
                    if field.name[0:6] == "label_":
                        lang = field.name[6:]
                        if "name_" + lang in self.Property:
                            values[field.name] = sml.trimLabel(self.Property["name_" + lang], field.length)

                values["cdb_classname"] = clss.__classname__
                if not previous_attrdef:
                    values["ranking_fac"] = clss.__ranking_fac__

            if previous_attrdef:
                previous_attrdef.Update(**values)
            else:
                ddfield = clss.Create(**values)
                if ddfield:
                    self.dd_attr_uuid = ddfield.cdb_object_id

    def adaptTabConfiguration(self, values):
        """
        Adapt an Value set used for generating a field in a projection tab.
        """
        if self.Property:
            from cdb import i18n
            from cdb.platform import gui
            languages = [x[13:] for x in gui.TableAttribute.GetFieldNames() if x.startswith("beschriftung_")]
            for lang in languages:
                iso_lang = i18n.iso(lang)
                label = sml.get_label("ptld", self, self.Property, iso_lang, 'name_$(CADDOK_ISOLANG) + "\\n" + prop_mk + "\\n" + prop_unit')
                if label:
                    fieldname = "beschriftung_" + lang
                    field = gui.TableAttribute.GetFieldByName(fieldname)
                    if field:
                        values[fieldname] = sml.trimLabel(label, field.length)
            if self.Property.din4001_mm_dt == "B":
                # Use Checkbox for Bool-Field
                values["itemtype"] = "Checkbox"

    def _handleMaskCatalog(self, values):
        """
        Fills values["katalog"] with the configured catalog or
        with ``cdbsml_pval`` if this is appropriate.
        """
        if self.prop_browser:
            values["katalog"] = self.prop_browser
        elif self.Property:
            if self.Property.mask_browser:
                values["katalog"] = self.Property.mask_browser
            elif self.Property.use_pval == '1':
                values["katalog"] = "cdbsml_pval"
                values["itemtyp"] = 4

        # If there is a catalog, we have to set the editability
        if values.get("katalog", None) and \
                self.Property and self.Property.use_pval_excl == '1':
            values["read_only"] = 2

    def adaptMaskConfiguration(self, values):
        """
        Adapt an Value set used for generating a field in a mask.
        e.g. the SML-Property-Value-Catalogs will be added
        """
        self._handleMaskCatalog(values)
        if self.Property:
            from cdb import i18n
            from cdb.platform import gui

            if self.Property.din4001_mm_dt == "B":
                # Use Checkbox for Bool-Field
                values["itemtyp"] = 2

            languages = [x[13:] for x in gui.MaskAttribute.GetFieldNames() if x.startswith("beschriftung_")]
            for lang in languages:
                iso_lang = i18n.iso(lang)
                label = sml.get_label("pmld", self, self.Property, iso_lang, 'name_$(CADDOK_ISOLANG) + [" ("+prop_mk+")"]+[" \\["+prop_unit+"\\]"]')
                if label:
                    fieldname = "beschriftung_" + lang
                    field = gui.MaskAttribute.GetFieldByName(fieldname)
                    if len(label) > field.length:
                        misc.cdblogv(misc.kLogMsg, 6, "Determined projection label is too long. Stripped-down to %d charcters" % (field.length))
                        label = label[:field.length]
                    values[fieldname] = label

    def presetPropertyNumber(self, ctx):
        """
        Used to set prop_nr to a proper value
        """
        if self.PropertySet:
            self.prop_nr = self.PropertySet.nextPropertyNumber()
        else:
            self.prop_nr = 10

    def clearDataDictionaryFieldLink(self, ctx):
        """
        Reset self.dd_attr_uuid
        """
        self.dd_attr_uuid = ''

    def set_fields_readonly(self, ctx):
        ctx.set_readonly('prop_id')

    event_map = {(('create', 'copy'), 'pre_mask'): 'presetPropertyNumber',
                 (('create', 'copy'), ('pre', 'pre_mask')): 'clearDataDictionaryFieldLink',
                 ('modify', 'pre_mask'): 'set_fields_readonly'
                 }


class PropertySet(Object):
    __maps_to__ = "cdbsml_propset"
    __classname__ = "cdbsml_propset"

    Name = LocalizedField("name")

    DocumentReferences = Reference_N(PropSetDocumentReference,
                                     PropSetDocumentReference.pset_id == fPropertySet.pset_id)

    PropertyReferences = Reference_N(fPropertyReference,
                                     fPropertyReference.pset_id == fPropertySet.pset_id,
                                     order_by=fPropertyReference.prop_nr)

    Items = Reference_N(Item, Item.sachgruppe == fPropertySet.pset_id)

    def nextPropertyNumber(self):
        """
        Retrieving the next property number
        """
        rset = sqlapi.RecordSet2(sql="select max(prop_nr) maxpos "
                                 "from cdbsml_pset_prop where pset_id = '%s'"
                                 % sqlapi.quote(self.pset_id))
        maxpos = rset[0].maxpos
        if maxpos != sqlapi.NULL:
            return maxpos + 10
        else:
            return 10

    def _get_label_dict(self):
        """Retrieving the label for all languages configured in the database
           as a dictionary
        """
        from cdb.platform import gui
        from cdb import i18n

        result = {}
        msg = gui.Message.ByName("cdbsml_label_desc")

        languages = i18n.Languages()
        for lang in languages:
            cdb_lang = i18n._to_cdb(lang)
            if not cdb_lang:
                cdb_lang = lang

            langattrs = [cdb_lang + "_beschriftung",
                         cdb_lang + "_ueberschrift"]
            label = ""
            pattern = msg[cdb_lang]
            if not pattern:
                pattern = "name_" + lang

            label = self.ApplyDescriptionPattern(pattern)

            # If cdbsml_label_desc is not configured for some languages it ist better
            # to leave the fields empty, because this enables the Fallback-Language-Mechanism
            if label:
                for lattr in langattrs:
                    result[lattr] = label

        return result

    def generate_facet(self):
        """
        Generate or update the facet definition of self.
        Returns a tuple (success, errmsg) to indicate the
        success of the operation.
        """
        sml_facet_module_name = "cs.vp.classification:generated"

        def _generate_dialogs(sml_class, initial):
            """
            Generates the facet's dialog. If `initial` is ``True`` a
            search and create dialog will be generated and assigned
            to the specific operations if there are specific base masks.
            If the property ``srmt`` is ``True`` the dialogs will be
            (re-)generated.
            """
            def _handle_dialog(operations, base_mask_name, std_dialog_name, initial):
                """
                If the mask given in `base_mask_name` a dialog will be (re-)created
                that bases on this mask and will be assigned to the operation configurations
                given in operations. If the base_mask does not exist the function
                ensures that every op in `operations` uses the `std_dialog_name`.
                """
                from cdb.platform import gui
                base_mask = gui.Dialog.ByKeys(base_mask_name, "public")
                if base_mask:
                    # Use the _n or _s ending from the base mask
                    std_op_dialog_name = std_dialog_name + base_mask_name[-2:]
                else:
                    std_op_dialog_name = std_dialog_name

                if initial and base_mask:
                    # Create special search and creation-masks if there is a base_mask
                    sml_class.autodefineDialog(std_op_dialog_name,
                                               "public",
                                               recreate=False,
                                               template_mask=base_mask_name)
                    for op in operations:
                        op.Update(mask_name=std_op_dialog_name)

                elif not initial:
                    if not base_mask:
                        # if there is no base mask we have to revert the operations
                        # configuration to the standard mask
                        for op in operations:
                            if op.mask_name != std_dialog_name:
                                # Think about: We should delete the old dialog if it is
                                #              not used elsewhere.
                                op.Update(mask_name=std_dialog_name)
                    else:
                        recreated_dialogs = set()
                        for op in operations:
                            dlgname = op.mask_name
                            if dlgname == std_dialog_name:
                                dlgname = std_op_dialog_name
                            if dlgname not in recreated_dialogs:
                                recreated_dialogs.add(dlgname)
                                sml_class.autodefineDialog(dlgname, "public", recreate=True, template_mask=base_mask_name)
                            if op.mask_name != dlgname:
                                op.Update(mask_name=dlgname)

            replace_gui_config = cad.isTrue(util.get_prop("srmt"))
            if not initial and not replace_gui_config:
                misc.cdblogv(misc.kLogMsg, 6, "Do not generate any further dialogs for '%s' because the facet class already exsists and the property srmt is False" % (sml_class.classname))
                return

            # This operations will be accessed from the code
            # so initialize them to avoid existence checks
            op_dict = {"CDB_Create": None,
                       "CDB_Search": None,
                       "CDB_SearchAgain": None,
                       "CDB_Modify": None,
                       "CDB_Copy": None}

            for op in sml_class.OperationConfigurations:
                op_dict[op.name] = op

            std_dialog = None
            if op_dict["CDB_Modify"]:
                std_dialog = op_dict["CDB_Modify"].mask_name

            # If initial is True the dialog has been created during the classes
            # compilation so recreate it only if it is an update
            if std_dialog and \
                    not initial and replace_gui_config:
                sml_class.autodefineDialog(std_dialog, "public", recreate=True)

            search_ops = []
            for opname in ["CDB_Search", "CDB_SearchAgain"]:
                if op_dict[opname]:
                    search_ops.append(op_dict[opname])
            if search_ops:
                _handle_dialog(search_ops, "sml_base_mask_s", std_dialog, initial)

            create_ops = []
            for opname in ["CDB_Create", "CDB_Copy"]:
                if op_dict[opname]:
                    create_ops.append(op_dict[opname])
            if create_ops:
                _handle_dialog(create_ops, "sml_base_mask_n", std_dialog, initial)

        def _generate_table(sml_class):
            """
            (Re-)generates the table if ``srmt`` is ``True``.
            """
            if sml_class and sml_class.tabelle and cad.isTrue(util.get_prop("srmt")):
                sml_class.autodefineTable(sml_class.tabelle, "public", recreate=True)

        def _tag_facet(sml_class):
            """
            Calls the module content resolver to tag all elements that belongs to
            the facet with ``sml_class.cdb_module_id``.
            """
            from cdb.comparch import resolver

            if not sml_class.cdb_module_id:
                sml_class.cdb_module_id = sml_facet_module_name

            pseudo_module = resolver.PseudoModule(sml_class.cdb_module_id, [sml_class])
            res = resolver.ModuleContentResolver(pseudo_module,
                                                 check_non_empty_module_ids=False)
            res._resolve()

        from cdb.platform.mom import constraints, entities, operations
        result = (True, "")
        values = {"classname": self.pset_id,
                  "is_abstract": 0,
                  "base_cls": "",
                  "sorting": 0,
                  "has_files": 0,
                  "filename_tmpl": "",
                  "is_indexed": 0,
                  "recent_obj_flag": 0,
                  "cdb_dflt_action": "",
                  "cdb_icon_id": self.icon_id,
                  "cdb_objektart": "cdb_class",
                  "cdb_classname": "cdb_facet",
                  "cdb_module_id": sml_facet_module_name
                  }

        label_attrs = self._get_label_dict()
        for key, val in label_attrs.items():
            values[key] = val

        error_label = "sml no create"
        # Try to locate the class
        sml_class = entities.Class.ByKeys(classname=self.pset_id)
        if sml_class:
            initial_create = False
            misc.cdblogv(misc.kLogMsg, 3, "Updating facet class definition for '%s'" % self.pset_id)
            error_label = "sml no modify"
            sml_class.Update(**values)
        else:
            sml_class = entities.Class.Create(**values)
            initial_create = True

        # Create am Primary Key
        new_pk_info = False
        pk = sml_class.PrimaryKey
        if not pk:
            pk = constraints.DDPrimaryKey.Create(classname=sml_class.classname)
            new_pk_info = True

        # Alle Attribute, die nicht mehr referenziert werden, loeschen
        attrdef_ids = [prop.dd_attr_uuid for prop in self.PropertyReferences]
        attrdef = {}
        old_attributes = sml_class.DDFields
        tnr = None
        tidx = None
        for field in old_attributes:
            if field.cdb_object_id not in attrdef_ids:
                if field.field_name == "teilenummer":
                    tnr = field
                elif field.field_name == "t_index":
                    tidx = field
                else:
                    misc.cdblogv(misc.kLogMsg, 3, "Removing field '%s' because it is no longer part of the SML definition" % (field.GetDescription()))
                    field.Delete()
            else:
                attrdef[field.cdb_object_id] = field

        # Create predefined fields
        if not tnr:
            f = fields.DDPredefinedField.Create(classname=sml_class.classname,
                                                field_name="teilenummer",
                                                is_mandatory=1,
                                                predefined_field_name="teilenummer",
                                                predefined_field_clsname="",
                                                position=-20,  # To avoid conflicts with prop_nr
                                                not_replicated=0,
                                                gui_autodefined=0,
                                                ranking_fac="identifying")
            try:
                constraints.DDConstraintField.Create(constraint_oid=pk.cdb_object_id,
                                                     field_classname=f.classname,
                                                     classname=f.classname,
                                                     field_name=f.field_name,
                                                     position=10)
                new_pk_info = True
            except Exception:
                # War wohl schon da
                pass

        if not tidx:
            f = fields.DDPredefinedField.Create(classname=sml_class.classname,
                                                field_name="t_index",
                                                is_mandatory=1,
                                                predefined_field_name="t_index",
                                                predefined_field_clsname="",
                                                position=-10,  # To avoid conflicts with prop_nr
                                                not_replicated=0,
                                                gui_autodefined=0,
                                                ranking_fac="identifying")
        try:
            constraints.DDConstraintField.Create(constraint_oid=pk.cdb_object_id,
                                                 field_classname=f.classname,
                                                 classname=f.classname,
                                                 field_name=f.field_name,
                                                 position=20)
            new_pk_info = True
        except Exception:
            # War wohl schon da
            pass

        if new_pk_info:
            pk.updateInfo()

        for prop in self.PropertyReferences:
            previous_attrdef = None
            if prop.dd_attr_uuid in attrdef:
                previous_attrdef = attrdef[prop.dd_attr_uuid]
            prop._refreshDataDictionary(sml_class, previous_attrdef)

        # if srmt ist set, the mask and table have to be recreated
        old_dialog = ""
        replace_gui_config = cad.isTrue(util.get_prop("srmt"))
        if replace_gui_config:
            modify_op = operations.OperationConfig.ByKeys("CDB_Modify", sml_class.classname)
            if modify_op:
                old_dialog = modify_op.mask_name

        sml_class.compile(force=True)
        if sml_class.isValid():
            sml_class.setupSystemOperations()
            sml_class.setupBaseProjection()
            _generate_dialogs(sml_class, initial_create)
            if not initial_create:
                _generate_table(sml_class)
            if replace_gui_config and old_dialog:
                sml_class.autodefineDialog(old_dialog, "public", recreate=True)
            _tag_facet(sml_class)

        else:
            errmsg = util.ErrorMessage(error_label)
            comp_log = sml_class.GetText("cdbdd_compilation_log_txt")
            misc.cdblogv(misc.kLogErr, 0, "Compiling facet class '%s' failed" % self.pset_id)
            result = (False, str(errmsg) + " ==> " + comp_log)

        return result

    def set_default_icon(self):
        if self.PropertyReferences:
            if not self.icon_id:
                self.icon_id = "cdbsml_propset"
        else:
            # Wenn keine Merkmale, anderes Icon
            if not self.icon_id or self.icon_id == "cdbsml_propset":
                self.icon_id = "cdbsml_propset2"

    def on_cdbsml_mkpset1_now(self, ctx):
        self.set_default_icon()
        (success, errmsg) = self.generate_facet()
        if not success:
            raise ue.Exception(1024, errmsg)

    @classmethod
    def on_cdbsml_mkpset_now(cls, ctx):
        psets = cls.Query()
        failed = []
        for pset in psets:
            pset.set_default_icon()
            (success, errmsg) = pset.generate_facet()
            if not success:
                failed.append(pset.pset_id)

        if failed:
            # We generate our own message, cause the standard message contains the
            # compilation log. This is too much if several errors occure.
            errmsg = str(util.ErrorMessage("sml no create")) + "\n(" + ",\n".join(failed) + ")"
            raise ue.Exception(1024, errmsg)

    def on_relship_copy_post(self, ctx):
        if ctx.relationship_name == "cdbsml_pset_prop":
            # Cleanup dd_attr_uuid in copied properties
            for prop in self.PropertyReferences:
                prop.dd_attr_uuid = ""

    @classmethod
    def on_preview_available_now(cls, ctx):
        ctx.enablePreview()

    def on_preview_now(self, ctx):
        # Import module here, cause oplan includes sandbox, which tries to initialize cdb.pdd.objects
        from cs.vp.classification.oplan.sml import getPSetInfoURL
        ctx.setPreviewURL(getPSetInfoURL(ctx.object, preview=True))

    def CheckPsetID(self, ctx):
        if "pset_id" in ctx.dialog.get_attribute_names():
            sml.check_pset_id(ctx.dialog.pset_id)

    event_map = {
        (('copy', 'create'), 'post_mask'): ('CheckPsetID')
    }


class PropDocumentReference(Object):
    __maps_to__ = "cdbsml_propdoc"
    Document = Reference_1(Document, Document.z_nummer, Document.z_index)


class Property(Object):
    __maps_to__ = "cdbsml_property"
    Name = LocalizedField("name")

    DocumentReferences = Reference_N(PropDocumentReference,
                                     PropDocumentReference.prop_id == fProperty.prop_id)

    PropertyReferences = Reference_N(fPropertyReference,
                                     fPropertyReference.prop_id == fProperty.prop_id)


class PropertyValue(Object):
    __maps_to__ = "cdbsml_propvalue"
    __classname__ = "cdbsml_propvalue"

    Property = Reference_1(fProperty, fPropertyValue.prop_id)

    @classmethod
    def _handle_prop_value_search(cls, ctx):
        """
        Calculates additional search conditions for the property
        value catalog ``cdbsml_prop_value_search``.
        """
        if ctx.catalog_name == "cdbsml_prop_value_search":
            prop_id = ""
            if ctx.catalog_invoking_field[:8] == "propval_":
                prop_attr = "propid_" + ctx.catalog_invoking_field[8:]
                prop_id = getattr(ctx.catalog_invoking_dialog, prop_attr, "")
                ctx.set("prop_id", prop_id)

    @classmethod
    def handle_global_action(cls, ctx, exclude_val):
        # Sort the values to groups - each for every property
        prop_dict = {}
        for obj in ctx.objects:
            if not obj.prop_id in prop_dict:
                prop_dict[obj.prop_id] = [obj]
            else:
                prop_dict[obj.prop_id].append(obj)

        for prop_id, objs in prop_dict.items():
            the_property = Property.ByKeys(prop_id)
            if the_property:
                with Transaction():
                    prop_uses = the_property.PropertyReferences
                    for prop_use in prop_uses:
                        for obj in objs:
                            sqlapi.SQLdelete("from cdbsml_pval_subset where "
                                             "pset_id='%s' and prop_mk='%s' and pval_value='%s'"
                                             % (sqlapi.quote(prop_use.pset_id),
                                                sqlapi.quote(prop_use.prop_mk),
                                                sqlapi.quote(obj.pval_value)))
                    if exclude_val:
                        value = 1
                    else:
                        value = 0

                    for prop_use in prop_uses:
                        for obj in objs:
                            ins = util.DBInserter("cdbsml_pval_subset")
                            ins.add("pset_id", prop_use.pset_id)
                            ins.add("prop_mk", prop_use.prop_mk)
                            ins.add("pval_value", obj.pval_value)
                            ins.add("pval_exclude", value)
                            ins.insert()

        ctx.refresh_tables(['cdbsml_pval_subset', 'cdbsml_pval_subset_v'])

    @classmethod
    def on_cdbsml_pval_global_exclude_now(cls, ctx):
        cls.handle_global_action(ctx, exclude_val=True)

    @classmethod
    def on_cdbsml_pval_global_include_now(cls, ctx):
        cls.handle_global_action(ctx, exclude_val=False)

    event_map = {('query_catalog', 'pre'): '_handle_prop_value_search'}


class PropertyCategory(Object):
    __classname__ = "cdbsml_propcat"
    __maps_to__ = "cdbsml_propcat"


@classbody
class Item(object):

    PropertySet = Reference_1(fPropertySet, Item.sachgruppe)

    def _get_props(self):
        return sml.LoadProperties(self)

    Properties = property(_get_props)

    @classmethod
    def smlPremaskImages(cls, ctx):
        sml.PremaskImages(ctx)
