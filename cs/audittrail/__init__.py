# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import absolute_import
import datetime
import uuid
import six
from pytz import utc as utc_tz

from cdb import auth, rte, constants
from cdb import sqlapi
from cdb import cdbuuid
from cdb import util
from cdb import sig
from cdb import ElementsError

from cdb.objects import Object, ViewObject, ClassRegistry, ByID, Forward, references
from cdb.objects.cdb_file import FILE_EVENT
from cdb.objects.iconcache import IconCache, _LabelValueAccessor
from cdb.platform import mom
from cdb.platform.mom import entities, fields
from cdb.platform.mom.relships import Relship
from cs.platform.web.rest.relship.main import UnaryRelshipResolver, NaryRelshipResolver

from cdb.platform.olc import StateDefinition

config = {}


def is_object_id(object_id):
    try:
        uuid.UUID(object_id)
    except ValueError:
        return False
    except AttributeError:
        return False
    except TypeError:
        return False
    return True


def partition(l, n):
    for i in six.moves.range(0, len(l), n):
        yield l[i:i + n]


def setConfig():
    """
    if 'config' is not populated it will set initial values to it and call it 'cdb_file_base'.
    Config is dictionary contains class names with the following paramters

    :param is_indexed: mandatory
    :param ident_field: mandatory
    :param index_fields: mandatory
    :param fields: have various variables, depending on the variables on the class which is extracted from DB

    if The classname got from SQL query is the rootclass than a signal is sent to inform about the changes.
    Write the data of the cdb_audittrail_config relation to memory for faster access during AuditTrail entry creation.
    """
    global config
    if not config:
        config["cdb_file_base"] = {"is_indexed": 0,
                                   "create_details": 1,
                                   "ident_field": "",
                                   "index_field": "",
                                   "fields": {"cdbf_name": {"de": "Dateiname",
                                                            "en": "File Name"}}}
        for atc in sqlapi.RecordSet2("cdb_audittrail_config"):
            cdef = entities.CDBClassDef(atc.classname)
            config[atc.classname] = {"is_indexed": atc.is_indexed,
                                     "create_details": atc.create_details,
                                     "ident_field": atc.ident_field,
                                     "index_field": atc.index_field}
            config[atc.classname]["fields"] = {}
            langs = []
            if atc.multilang_dlg_languages:
                from cdb.platform import mom
                obj = mom.getObjectHandleFromObjectID(atc.multilang_dlg_languages)
                if obj and obj.is_valid():
                    langs = obj.iso_languages.split(",")
            config[atc.classname]["status_langs"] = langs
            for field in sqlapi.RecordSet2("cdb_audittrail_config_field", "classname = '%s'" % atc.classname):
                f = fields.DDField.ByKeys(atc.classname, field.field_name)
                if not f:
                    rootClassname = cdef.getRootClass().getClassname()
                    f = fields.DDField.ByKeys(rootClassname, field.field_name)
                if f:
                    if f.cdb_classname.startswith("cdbdd_multilang_field"):
                        langs = []
                        restricted_to_langs = False
                        if field.multilang_dlg_languages:
                            restricted_to_langs = True
                            from cdb.platform import mom
                            obj = mom.getObjectHandleFromObjectID(field.multilang_dlg_languages)
                            if obj and obj.is_valid():
                                langs = obj.iso_languages.split(",")
                        for mlf in f.LangFields:
                            if (langs and mlf.cdb_iso_language_code in langs) or not restricted_to_langs:
                                config[atc.classname]["fields"][mlf.field_name] = {"en": mlf.getLabel("en"),
                                                                                   "de": mlf.getLabel("de"),
                                                                                   "attr_type": sqlapi.SQL_CHAR}
                    else:
                        try:
                            attr_type = cdef.getAttributeDefinition(field.field_name).getSQLType()
                        except ElementsError:
                            attr_type = sqlapi.SQL_CHAR
                        if field.labelname_en or field.labelname_de:
                            config[atc.classname]["fields"][field.field_name] = {"en": field.labelname_en,
                                                                             "de": field.labelname_de,
                                                                             "attr_type":attr_type}
                        else:
                            config[atc.classname]["fields"][field.field_name] = {"en": f.getLabel("en"),
                                                                                 "de": f.getLabel("de"),
                                                                                 "attr_type": attr_type}

        for atc in sqlapi.RecordSet2("cdb_audittrail_config"):
            cdef = entities.CDBClassDef(atc.classname)
            subclasses = cdef.getSubClassNames(True)
            rootClassname = cdef.getRootClass().getClassname()
            addSignal = True
            if rootClassname != atc.classname:
                if rootClassname in config:
                    addSignal = False
            if addSignal:
                pycls = ClassRegistry().find(cdef.getPrimaryTable())
                if pycls:
                    sig.connect(pycls, "classification_update", "post")(ClassificationEvent)
                    sig.connect(FILE_EVENT, pycls.__maps_to__, any)(FileEvents)
            for subclass in subclasses:
                if subclass not in config:
                    config[subclass] = config[atc.classname]
                else:
                    subclass_fields = config[subclass]["fields"].copy()
                    subclass_fields.update(config[atc.classname]["fields"])
                    config[subclass]["fields"] = subclass_fields


def shortenText(text, maxlength):
    if len(text.encode("utf-8")) <= maxlength:
        return text
    else:
        encode_text = text.encode("utf-8")[:maxlength-3]
        return "{}...".format(encode_text.decode("utf-8", errors="ignore"))


fAuditTrailView = Forward(__name__ + ".AuditTrailView")
fAuditTrailObjects = Forward(__name__ + ".AuditTrailObjects")


class AuditTrail(Object):
    __classname__ = "cdb_audittrail"
    __maps_to__ = "cdb_audittrail"

    def GetObjectIcon(self, base_uri=None, **kwargs):
        return IconCache.getIcon(
            sqlapi.RecordSet2(
                "cdb_audittrail_type",
                "type='%s'" % sqlapi.quote(self.type)
            )[0].cdb_icon_id,
            accessor=_LabelValueAccessor(self, True)
        )


class AuditTrailDetail(Object):
    __classname__ = "cdb_audittrail_detail"
    __maps_to__ = "cdb_audittrail_detail"


class AuditTrailObjects(Object):
    __classname__ = "cdb_audittrail_objects"
    __maps_to__ = "cdb_audittrail_objects"

    Entries = references.Reference_N(fAuditTrailView,
                                     fAuditTrailView.audittrail_object_id == fAuditTrailObjects.audittrail_id,
                                     order_by="cdb_cdate DESC")


class AuditTrailDetailLongText(AuditTrailDetail):
    __classname__ = "cdb_audittrail_detail_longtext"


class AuditTrailView(ViewObject):
    __classname__ = "cdb_audittrail_view"
    __maps_to__ = "cdb_audittrail_view"


class AuditTrailConfig(Object):
    __classname__ = "cdb_audittrail_config"
    __maps_to__ = "cdb_audittrail_config"

    event_map = {(('create', 'copy', 'modify'), 'pre_mask'): 'setDefaults',
                 (('create', 'copy', 'modify'), 'dialogitem_change'): 'changeDialog'}

    def setDefaults(self, ctx):
        if self.is_indexed:
            ctx.set_fields_mandatory(["ident_field", "index_field"])
        else:
            ctx.set_fields_readonly(["ident_field", "index_field"])

    def changeDialog(self, ctx):
        if ctx.changed_item == "is_indexed":
            if ctx.dialog.is_indexed == "1":
                ctx.set_fields_writeable(["ident_field", "index_field"])
                ctx.set_mandatory("ident_field")
                ctx.set_mandatory("index_field")
            else:
                ctx.set_fields_readonly(["ident_field", "index_field"])
                ctx.set_optional("ident_field")
                ctx.set_optional("index_field")
                ctx.set("ident_field", "")
                ctx.set("index_field", "")


class AuditTrailConfigField(Object):
    __classname__ = "cdb_audittrail_config_field"
    __maps_to__ = "cdb_audittrail_config_field"

    event_map = {(('create', 'copy', 'modify'), 'dialogitem_change'): 'changefieldDialog'}

    def changefieldDialog(self, ctx):
        if ctx.changed_item == "field_name":
            clsname = ctx.dialog.classname
            field_name2 = ctx.dialog.field_name
            if field_name2:
                chosen_field = fields.DDField.ByKeys(clsname, field_name2)
                type_chosen_field = chosen_field._name if chosen_field else None
                if type_chosen_field and type_chosen_field.find('MultiLang') >= 0:
                    ctx.set_fields_writeable(["multilang_dlg_languages"])
                else:
                    ctx.set_fields_readonly(["multilang_dlg_languages"])
                    ctx.set("multilang_dlg_languages", "")


def ClassificationEvent(obj, update_data):
    # Created Classes
    if update_data["new_classes"]:
        at = obj.createAuditTrail("create_classification")
        for nc in update_data["new_classes"]:
            AuditTrailDetail.CreateNoResult(detail_object_id=cdbuuid.create_sortable_id(),
                                            audittrail_object_id=at.audittrail_object_id,
                                            attribute_name="classification",
                                            old_value="",
                                            new_value=nc,
                                            label_de="Klassifizierung",
                                            label_en="Classification")

    # Deleted Classes
    if update_data["deleted_classes"]:
        at = obj.createAuditTrail("delete_classification")
        for dc in update_data["deleted_classes"]:
            AuditTrailDetail.CreateNoResult(detail_object_id=cdbuuid.create_sortable_id(),
                                            audittrail_object_id=at.audittrail_object_id,
                                            attribute_name="classification",
                                            old_value=dc,
                                            new_value="",
                                            label_de="Klassifizierung",
                                            label_en="Classification")
    # Deleted Properties
    if update_data["deleted_properties"]:
        at = obj.createAuditTrail("delete_classification_props")
        for dp in update_data["deleted_properties"]:
            old_value = "%s"
            if dp.float_value:
                old_value = old_value % dp.float_value
            elif dp.boolean_value:
                old_value = old_value % "True" if dp.boolean_value else "False"
            elif dp.integer_value:
                old_value = old_value % dp.integer_value
            elif dp.datetime_value:
                old_value = old_value % dp.datetime_value
            elif dp.text_value:
                old_value = old_value % dp.text_value
            elif dp.value:
                try:
                    prop = ByID(dp.value)
                except TypeError:
                    prop = None
                if prop:
                    old_value = old_value % prop.GetDescription()
                else:
                    old_value = ""
            if dp.unit_object_id:
                old_value += " %s" % ByID(dp.unit_object_id).symbol
            AuditTrailDetail.CreateNoResult(detail_object_id=cdbuuid.create_sortable_id(),
                                            audittrail_object_id=at.audittrail_object_id,
                                            attribute_name="classification",
                                            old_value=old_value,
                                            new_value="",
                                            label_de=dp.property_path,
                                            label_en=dp.property_path)
    # Modified Properties
    to_modify = []
    for props, elements in six.iteritems(update_data["properties"]):
        for e in elements:
            old_value = ""
            new_value = ""
            add = False
            if "old_value" in e:
                add = True
                if type(e["old_value"]) is dict:
                    if e["old_value"].get("float_value"):
                        old_value = "%s %s" % (e["old_value"]["float_value"], e["old_value"].get("unit_label", ""))
                    elif e["old_value"] is not None:
                        old_value = "%s" % e["old_value"] if e["old_value"] is not None else ""
                else:
                    old_value = "%s" % e["old_value"] if e["old_value"] is not None else ""
            if "value" in e:
                if type(e["value"]) is dict:
                    if e["value"].get("float_value"):
                        new_value = "%s %s" % (e["value"]["float_value"], e["value"].get("unit_label", ""))
                    elif e["value"].get("child_props"):
                        for asc in e["value"].get("child_props"):
                            current_prop = e["value"].get("child_props")[asc]
                            if len(current_prop) > 0:
                                if type(current_prop[0]["value"]) is dict and len(current_prop[0]["value"]) > 1:
                                    if "de" in current_prop[0]["value"] and "old_value" in current_prop[0]["value"][
                                        "de"]:
                                        old_value_de = "%s %s" % (
                                        current_prop[0]["value"]["de"]["old_value"] if current_prop[0]["value"]["de"][
                                            "old_value"] else "",
                                        e["value"].get("unit_label", ""))
                                        new_value_de = "%s %s" % (
                                        current_prop[0]["value"]["de"]["text_value"] if current_prop[0]["value"]["de"][
                                            "text_value"] else "",
                                        e["value"].get("unit_label", ""))
                                        old_value_en = "%s %s" % (
                                        current_prop[0]["value"]["en"]["old_value"] if current_prop[0]["value"]["en"][
                                            "old_value"] else "",
                                        e["value"].get("unit_label", ""))
                                        new_value_en = "%s %s" % (
                                        current_prop[0]["value"]["en"]["text_value"] if current_prop[0]["value"]["en"][
                                            "text_value"] else "",
                                        e["value"].get("unit_label", ""))
                                        if old_value_de != new_value_de:
                                            to_modify.append([old_value_de,
                                                              new_value_de,
                                                              current_prop[0]["value_path"]])
                                            to_modify.append([old_value_en,
                                                              new_value_en,
                                                              current_prop[0]["value_path"]])
                                    elif (current_prop[0]["value"].get("float_value")) and "old_value" in current_prop[
                                        0]:
                                        nv = "%s %s" % (current_prop[0]["value"]["float_value"],
                                                        current_prop[0]["value"].get("unit_label", ""))
                                        ov = "%s %s" % (
                                        current_prop[0]["old_value"]["float_value"] if "old_value" in current_prop[
                                            0] and current_prop[0]["old_value"] is not None else "",
                                        current_prop[0]["value"].get("unit_label", ""))
                                        to_modify.append([ov, nv, current_prop[0]["value_path"]])
                                elif current_prop[0]['property_type'] == 'objectref' and "old_value" in current_prop[0]:
                                    new_value_evaluator = None
                                    if "value" in current_prop[0] and current_prop[0]["value"]:
                                        value_obj_new = ByID(current_prop[0]["value"])
                                        if value_obj_new:
                                            got_name = getattr(value_obj_new, "name", False)
                                            new_value_evaluator = "%s %s" % (
                                                value_obj_new.name if got_name else
                                                value_obj_new.GetDescription() if current_prop[0]["value"]
                                                else "",
                                                e["value"].get("unit_label", ""))
                                    old_value_evaluator = None
                                    if "old_value" in current_prop[0] and current_prop[0][
                                        "old_value"]:
                                        value_obj_old = ByID(current_prop[0]["old_value"])
                                        if value_obj_old:
                                            got_name = getattr(value_obj_old, "name", False)
                                            old_value_evaluator = "%s %s" % (
                                                value_obj_old.name if got_name else
                                                value_obj_old.GetDescription() if current_prop[0]["old_value"] else "",
                                                e["value"].get("unit_label", ""))
                                    if new_value_evaluator != old_value_evaluator:
                                        to_modify.append([old_value_evaluator,
                                                          new_value_evaluator,
                                                          current_prop[0]["value_path"]])
                                elif "old_value" in current_prop[0]:
                                    add = True
                                    old_value = "%s %s" % (
                                    current_prop[0]["old_value"] if current_prop[0]["old_value"] else "",
                                    e["value"].get("unit_label", ""))
                                    new_value = "%s %s" % (current_prop[0]["value"] if current_prop[0]["value"] else "",
                                                           e["value"].get("unit_label", ""))
                                if add and (new_value or old_value):
                                    if new_value != old_value:
                                        to_modify.append([old_value, new_value, current_prop[0]["value_path"]])
                                add = False
                elif e["value"] is not None:
                    new_value = "%s" % e["value"] if e["value"] is not None else ""
            if add and (new_value is not None or old_value is not None):
                if new_value == old_value:
                    new_value = ""
                if e['property_type'] == "objectref":
                    if old_value:
                        old_ref = ByID(old_value)
                        if old_ref:
                            old_value = old_ref.GetDescription()
                        else:
                            old_value = old_value
                    if new_value:
                        new_ref = ByID(new_value)
                        if new_ref:
                            new_value = new_ref.GetDescription()
                        else:
                            new_value = new_value
                to_modify.append([old_value, new_value, e["value_path"]])
    if to_modify:
        at = obj.createAuditTrail("modify_classification")
        for tm in to_modify:
            AuditTrailDetail.CreateNoResult(detail_object_id=cdbuuid.create_sortable_id(),
                                    audittrail_object_id=at.audittrail_object_id,
                                    attribute_name="classification",
                                    old_value=tm[0],
                                    new_value=tm[1],
                                    label_de=tm[2],
                                    label_en=tm[2])


def FileEvents(the_file, obj_hndl, ctx):
    obj = ByID(obj_hndl.getValue('cdb_object_id', False))

    if obj:
        clsname = obj.GetClassname()
        if clsname in config:
            type = ""
            if ctx.action == 'create':
                type = "create_file"
            elif ctx.action == 'modify':
                type = "modify_file"
            elif ctx.action == 'delete':
                type = "delete_file"

            if type:
                at = obj.createAuditTrail(type)
                if at:
                    obj.createAuditTrailDetail(audittrail_object_id=at.audittrail_object_id,
                                               clsname="cdb_file_base",
                                               attribute="cdbf_name",
                                               old_value="",
                                               new_value=the_file.cdbf_name)


class WithAuditTrail(object):
    """
    Mixin which enables objects to automatically create AuditTrail entries.
    """

    event_map = {(('create', 'copy'), 'post'): 'createAuditTrailEntry',
                 ('relship_copy', 'post'): 'copyrelshipAuditTrailEntry',
                 ('state_change', 'post'): 'statechangeAuditTrailEntry',
                 ('delete', 'post'): 'deleteAuditTrailEntry',
                 ('modify', 'post'): "modifyAuditTrailEntry",
                 (('create', 'copy', 'relship_copy', 'state_change', 'modify'), 'pre_mask'): "initAuditTrail"}

    def initAuditTrail(self, ctx=None):
        global config
        if not config:
            setConfig()

    def referencedAuditTrailObjects(self):
        return [self]

    def getObjectDescription(self, iso_lang):
        try:
            return self.GetDescription(iso_lang=iso_lang)
        except KeyError:
            return self.ToObjectHandle().getDesignation(iso_lang=iso_lang)

    def createAuditTrail(self, category):
        """
        Creates a new AuditTrail entry.

        :param category: Which type of entry is generated e.g. create, modify, etc.
        :return: The AuditTrail entry
        """
        self.initAuditTrail()

        clsname = self.GetClassname()
        idx = ""
        audittrail = None
        if clsname in config:
            if config[clsname]["is_indexed"] == 1 and config[clsname]["index_field"]:
                idx = self[config[clsname]["index_field"]]
            desc_de = self.getObjectDescription("de")
            desc_en = self.getObjectDescription("en")
            audittrail = AuditTrail.Create(audittrail_object_id=cdbuuid.create_sortable_id(),
                                           object_id=self.cdb_object_id,
                                           object_description=desc_de if desc_de else desc_en,
                                           object_description_ml_en=desc_en if desc_en else desc_de,
                                           idx=idx,
                                           cdb_cpersno=auth.persno,
                                           cdb_cdate=datetime.datetime.now(utc_tz),
                                           type=category)
            for obj in self.referencedAuditTrailObjects():
                if category == 'delete' and obj == self:
                    continue
                if hasattr(obj, "cdb_object_id"):
                    AuditTrailObjects.CreateNoResult(object_id=obj.cdb_object_id,
                                             audittrail_id=audittrail.audittrail_object_id)
        return audittrail

    def createAuditTrailDetail(self, audittrail_object_id, clsname, attribute, old_value, new_value):
        """
        Creates a new AuditTrailDetail entry

        :param audittrail_object_id: cdb_object_id of the encompassing AuditTrail entry
        :param attribute: Attribute name of the changed attribute
        :param old_value: Old value of the attribute
        :param new_value: New value of the attribute
        """
        self.initAuditTrail()
        if attribute in config[clsname]["fields"] or attribute.startswith("Status ("):
            ov = old_value
            if ov and is_object_id(ov):
                ov = ByID(ov)
                if ov:
                    ov = ov.GetDescription()
                else:
                    ov = ""
            nv = new_value
            if nv and is_object_id(nv):
                nv = ByID(nv)
                if nv:
                    nv = nv.GetDescription()
                else:
                    nv = ""
            if attribute.startswith("Status ("):
                label_de = attribute
                label_en = attribute
            else:
                label_de = config[clsname]["fields"][attribute]["de"]
                label_en = config[clsname]["fields"][attribute]["en"]
            type = sqlapi.SQL_CHAR
            if attribute in config[clsname]["fields"] and "attr_type" in config[clsname]["fields"][attribute]:
                type = config[clsname]["fields"][attribute]["attr_type"]
            if type == sqlapi.SQL_INTEGER:
                ov = "%s" % int(ov) if ov else "0"
                nv = "%s" % int(nv) if nv else "0"
            elif type == sqlapi.SQL_FLOAT:
                ov = "%s" % float(ov) if ov else "0.0"
                nv = "%s" % float(nv) if nv else "0.0"
            AuditTrailDetail.CreateNoResult(detail_object_id=cdbuuid.create_sortable_id(),
                                    audittrail_object_id=audittrail_object_id,
                                    attribute_name=attribute,
                                    old_value=ov,
                                    new_value=nv,
                                    label_de=label_de,
                                    label_en=label_en)

    def createAuditTrailLongText(self, audittrail_object_id, clsname, longtext, old_text, new_text):
        """
        Creates a new AuditTrailLongDetail entry

        :param audittrail_object_id: cdb_object_id of the encompassing AuditTrail entry
        :param longtest: Attribute name of the changed attribute
        :param old_text: Old text of the attribute
        :param new_text: New text of the attribute
        """
        self.initAuditTrail()
        if longtext in config[clsname]["fields"]:
            attr_length = getattr(AuditTrailDetailLongText, "old_value").length
            longdetail = AuditTrailDetailLongText.Create(detail_object_id=cdbuuid.create_sortable_id(),
                                                         audittrail_object_id=audittrail_object_id,
                                                         attribute_name=longtext,
                                                         old_value=shortenText(old_text, attr_length),
                                                         new_value=shortenText(new_text, attr_length),
                                                         label_de=config[clsname]["fields"][longtext]["de"],
                                                         label_en=config[clsname]["fields"][longtext]["en"])
            longdetail.SetText("cdb_audittrail_longtext_old", old_text)
            longdetail.SetText("cdb_audittrail_longtext_new", new_text)

    def createAuditTrailEntry(self, ctx=None):
        if ctx and ctx.error:
            return
        self.initAuditTrail()

        clsname = self.GetClassname()
        content_types = self.get_content_types_by_classname(clsname)
        if clsname in config:
            obj = self
            attributes = self.GetFieldNames()
            longtexts = self.GetTextFieldNames()
            if ctx and ctx.object:
                obj = ctx.object
                attributes = obj.get_attribute_names()
            audittrail = self.createAuditTrail('create')
            if config[clsname]["create_details"]:
                for attribute in attributes:
                    if attribute in longtexts:
                        continue
                    if attribute in list(config[clsname]["fields"]):
                        if obj[attribute]:
                            nv = obj[attribute]
                            if is_object_id(nv):
                                nv = ByID(nv)
                                if nv:
                                    nv = nv.GetDescription()
                                else:
                                    nv = ""
                            self.createAuditTrailDetail(
                                audittrail_object_id=audittrail.audittrail_object_id,
                                clsname=clsname,
                                attribute=attribute,
                                old_value="",
                                new_value=nv)

                for longtext in longtexts:
                    if longtext in list(config[clsname]["fields"]) and content_types.get(longtext) in ('', 'PlainText'):
                        new_text = self.GetText(longtext)
                        if new_text:
                            self.createAuditTrailLongText(
                                audittrail_object_id=audittrail.audittrail_object_id,
                                clsname=clsname,
                                longtext=longtext,
                                old_text="",
                                new_text=new_text)
            return audittrail

    def deleteAuditTrailEntry(self, ctx=None):
        if ctx and ctx.error:
            return
        return self.createAuditTrail('delete')

    def copyrelshipAuditTrailEntry(self, ctx=None):
        if ctx and ctx.error:
            return
        self.initAuditTrail()

        cdef = self.GetClassDef()
        rs_def = cdef.getRelationship(ctx.relationship_name)
        if rs_def and rs_def.is_valid():
            target_cdef = rs_def.get_reference_cldef()
            link_cdef = rs_def.get_link_cldef()
            if not link_cdef:
                return
            if target_cdef:
                result = []
                if link_cdef == target_cdef:
                    target_clsname = target_cdef.getClassname()
                    if target_clsname in config:
                        parent_handle = self.ToObjectHandle()
                        if cdef.isOneOnOne(rs_def):
                            resolver = UnaryRelshipResolver(parent_handle, ctx.relationship_name, target_clsname)
                            if resolver:
                                result = [resolver.resolve()]
                        else:
                            resolver = NaryRelshipResolver(parent_handle, ctx.relationship_name, target_clsname)
                            if resolver:
                                result = resolver.resolve()
                else:
                    link_clsname = link_cdef.getClassname()
                    if link_clsname in config:
                        link_cls_obj = ClassRegistry().find(link_cdef.getPrimaryTable())
                        relship = Relship.ByKeys(ctx.relationship_name)

                        referer_args = {}
                        for pair in relship.referer_kmap.split(';'):
                            lpair = pair.strip().split('=')
                            if len(lpair):
                                referer_args[lpair[1].strip()] = getattr(self, lpair[0].strip())
                        result = link_cls_obj.KeywordQuery(**referer_args)
                for obj in result:
                    if obj.GetClassname() in config:
                        obj.createAuditTrailEntry()

    def statechangeAuditTrailEntry(self, ctx=None):
        if ctx and ctx.error:
            return
        self.initAuditTrail()

        clsname = self.GetClassname()

        if clsname in config:
            cdef = entities.CDBClassDef(clsname)
            rootClassname = cdef.getRootClass().getClassname()
            valid_langs = config[clsname]["status_langs"]
            if rootClassname == 'document':
                status = 'z_status'
                object_art = 'z_art'
            else:
                status = 'status'
                object_art = 'cdb_objektart'

            old_value_status = ctx.old[status]
            new_value_status = ctx.new[status]
            old_value_objektart = ctx.old[object_art]
            new_value_objektart = ctx.new[object_art]
            old_value = StateDefinition.ByKeys(objektart=old_value_objektart, statusnummer=old_value_status)
            new_value = StateDefinition.ByKeys(objektart=new_value_objektart, statusnummer=new_value_status)
            audittrail = self.createAuditTrail('status_change')
            for l in old_value.GetLocalizedValues("statusbez").keys():
                if l in valid_langs or not valid_langs:
                    old_value_final = "%s (%s)" % (old_value["statusbez_" + l], old_value_status)
                    new_value_final = "%s (%s)" % (new_value["statusbez_" + l], new_value_status)
                    if old_value_final or new_value_final:
                        self.createAuditTrailDetail(audittrail_object_id=audittrail.audittrail_object_id,
                                                    clsname=clsname,
                                                    attribute="Status (" + l + ")",
                                                    old_value=old_value_final,
                                                    new_value=new_value_final)

            return audittrail

    def modifyAuditTrailEntry(self, ctx=None):
        if ctx and ctx.error:
            return
        self.initAuditTrail()

        audittrail_longtext = []
        audittrial_attributes = []

        clsname = self.GetClassname()
        content_types = self.get_content_types_by_classname(clsname)
        if clsname not in config:
            return None

        obj_attributes = ctx.object.get_attribute_names()
        obj_longtext = self.GetTextFieldNames()
        for attribute in ctx.previous_values.get_attribute_names():
            if attribute not in list(config[clsname]["fields"]):
                continue
            if attribute in obj_attributes:
                if attribute in obj_longtext and content_types.get(attribute) in ('', 'PlainText'):
                    longtext = self.GetText(attribute)
                    if ctx.previous_values[attribute] != longtext:
                        audittrail_longtext.append(attribute)
                elif ctx.previous_values[attribute] != ctx.object[attribute]:
                    audittrial_attributes.append(attribute)

        if audittrial_attributes or audittrail_longtext:
            audittrail = self.createAuditTrail('modify')
            insert = False
            for attribute in audittrial_attributes:
                if attribute in obj_longtext:
                    continue
                if attribute not in list(config[clsname]["fields"]):
                    continue
                if type(self[attribute]) == float:
                    compare_to = float(ctx.previous_values[attribute]) if ctx.previous_values[attribute] else 0.0
                    if (compare_to - self[attribute]) == 0:
                        continue
                    else:
                        insert = True
                else:
                    insert = True

                nv = self[attribute]
                if isinstance(nv, datetime.datetime):
                    if nv.time():
                        nv = nv.strftime("%d.%m.%Y %H:%M:%S")
                    else:
                        nv = nv.strftime("%d.%m.%Y")

                self.createAuditTrailDetail(audittrail_object_id=audittrail.audittrail_object_id,
                                            clsname=clsname,
                                            attribute=attribute,
                                            old_value=ctx.previous_values[attribute],
                                            new_value=nv)
            for longtext in audittrail_longtext:
                if longtext not in list(config[clsname]["fields"]):
                    continue
                else:
                    insert = True
                old_text = ctx.previous_values[longtext]
                new_text = self.GetText(longtext)
                self.createAuditTrailLongText(audittrail_object_id=audittrail.audittrail_object_id,
                                              clsname=clsname,
                                              longtext=longtext,
                                              old_text=old_text,
                                              new_text=new_text)
            if not insert:
                audittrail.Delete()
                return None
            return audittrail

    def get_content_types_by_classname(self, classname):
        import cdbwrapc
        cdef = cdbwrapc.CDBClassDef(classname)
        if cdef:
            return {adef.getName(): adef.getContentType() for adef in cdef.getAttributeDefs()}
        else:
            return None


class AuditTrailApi(object):
    @classmethod
    def createAuditTrails(cls, category, objs):
        """
        Creates AuditTrail entries based on a list of dicts representing the necessary metadata for
        those.

        :param category: Which type of entry is generated e.g. create, modify, etc.
        :param objs: A list of dicts representing the metadata necessary for an AuditTrail entry:

            .. code-block:: python

                    objs = [{"cdb_object_id": "x",
                             "idx": "y",
                             "description": "x/y"
                             "attach_to": ["abced-...", ...], ...]

        :return: objs with additional attribute audittrail_id in the obj dict
        """
        global config
        if not config:
            setConfig()

        # objs should be a list of dicts containing cdb_object_id, index, description and classname
        # eg. objs = [{"cdb_object_id": "x",
        #              "idx": "y",
        #              "description": "x/y",
        #              "classname": "test_class"}, ...]

        DBType = sqlapi.SQLdbms()
        create = False
        for partitions in partition(objs, 100):
            audittrail_inserts = """INSERT INTO cdb_audittrail (audittrail_object_id,object_id,
                                        object_description, object_description_ml_en,idx,cdb_cpersno,cdb_cdate,type) """
            audittrail_objects_inserts = "INSERT INTO cdb_audittrail_objects (audittrail_id, object_id) "
            if DBType == sqlapi.DBMS_ORACLE:
                audittrail_inserts += "WITH entries AS ("
                audittrail_objects_inserts += "WITH entries AS ("
            else:
                audittrail_inserts += "VALUES "
                audittrail_objects_inserts += "VALUES "
            for obj in partitions:
                if obj['classname'] in config:
                    uuid = cdbuuid.create_sortable_id()
                    if DBType == sqlapi.DBMS_ORACLE:
                        insert_statement = """{uuid},{obj_id},{obj_desc} AS object_description,
                                               {obj_desc_ml} AS object_description_ml_en,
                                               {idx},{persno},{date},{category}"""
                    else:
                        insert_statement = """{uuid},{obj_id},{obj_desc},{obj_desc_ml},
                                               {idx},{persno},{date},{category}"""
                    audittrail_insert = insert_statement.format(
                        uuid=AuditTrail.audittrail_object_id.make_literal(uuid),
                        obj_id=AuditTrail.object_id.make_literal(obj['cdb_object_id']),
                        obj_desc=AuditTrail.object_description.make_literal(obj['description']),
                        obj_desc_ml=AuditTrail.object_description_ml_en.make_literal(obj['description']),
                        idx=AuditTrail.idx.make_literal(obj['idx']),
                        persno=AuditTrail.cdb_cpersno.make_literal(auth.persno),
                        date=AuditTrail.cdb_cdate.make_literal(datetime.datetime.now(utc_tz)),
                        category=AuditTrail.type.make_literal(category)
                    )
                    for att in obj["attach_to"]:
                        audittrail_objects_insert = "'{uuid}', '{obj_id}'".format(obj_id=att,
                                                                                  uuid=uuid)
                        if DBType == sqlapi.DBMS_ORACLE:
                            audittrail_objects_inserts += "SELECT %s FROM dual UNION ALL " % audittrail_objects_insert
                        else:
                            audittrail_objects_inserts += "(%s)," % audittrail_objects_insert

                    if DBType == sqlapi.DBMS_ORACLE:
                        audittrail_inserts += "SELECT %s FROM dual UNION ALL " % audittrail_insert
                    else:
                        audittrail_inserts += "(%s)," % audittrail_insert
                    create = True
                    obj["audittrail_id"] = uuid

            if DBType == sqlapi.DBMS_ORACLE:
                audittrail_inserts = audittrail_inserts[:-10] + ") SELECT * FROM entries"
                audittrail_objects_inserts = audittrail_objects_inserts[:-10] + ") SELECT * FROM entries"
            else:
                audittrail_inserts = audittrail_inserts[:-1]
                audittrail_objects_inserts = audittrail_objects_inserts[:-1]
            if create:
                sqlapi.SQL(audittrail_inserts)
                sqlapi.SQL(audittrail_objects_inserts)
        if create:
            return objs
        return []

    @classmethod
    def createAuditTrailsWithDetails(cls, category, objs, longtext_stripper=None):
        """
        Creates AuditTrail and AuditTrailDetail entries based on a list of dicts representing the necessary metadata for
        those.

        :param category: Which type of entry is generated e.g. create, modify, etc.
        :param objs: A list of dicts representing the metadata necessary for AuditTrail and AuditTrailDetail entries:
        :param longtext_stripper: When using longtext which include html tags etc. provide a callback function to strip
               those of the preview description (new_value, old_value)

            .. code-block:: python

                    objs = [{"cdb_object_id": "x",
                             "idx": "y",
                             "description": "x/y",
                             "changes": [{"attribute_name": "test_attrib",
                                          "old_value": "a",
                                          "new_value": "b",
                                          "longtext": 1,
                                          "detail_classname": "cdb_audittrail_detail_richtext"},
                                         ...]
                            },
                            ...]

            attribute_name is a mandatory entry when including changes
        :return: Original list of objects

        """
        global config
        if not config:
            setConfig()
        attr_length = getattr(AuditTrailDetail, "old_value").length
        new_audittrails = AuditTrailApi.createAuditTrails(category, objs)
        longtexts = []
        # objs should be a list of dicts containing cdb_object_id, index, description,
        # classname and a list of changes in a dict with attribute_name, new and old value
        # eg. objs = [{"cdb_object_id": "x",
        #              "idx": "y",
        #              "description": "x/y",
        #              "changes": [{ "attribute_name": "test_attrib",
        #                            "old_value": "a",
        #                            "new_Value": "b"
        #                          }, ...],
        #             {"cdb_object_id": "a", ...
        #             }, ...]

        # For Oracle due to https://stackoverflow.com/questions/44160719/direct-path-insert-query-generates-ora-00918-error
        DBType = sqlapi.SQLdbms()
        create = False
        for partitions in partition(new_audittrails, 100):
            audittrail_inserts = """INSERT INTO cdb_audittrail_detail (detail_object_id,audittrail_object_id,
                                        attribute_name,old_value,new_value, label_de, label_en, cdb_classname) """
            if DBType == sqlapi.DBMS_ORACLE:
                audittrail_inserts += " "
            else:
                audittrail_inserts += "VALUES "

            for obj in partitions:
                if obj['classname'] in config and "changes" in obj:
                    for change in obj['changes']:
                        if change['attribute_name'] in list(config[obj['classname']]["fields"]):
                            detail_uuid = cdbuuid.create_sortable_id()
                            detail_clsname = 'cdb_audittrail_detail'

                            old_value = ""
                            if 'old_value' in change and change['old_value']:
                                old_value = six.text_type(change['old_value'])
                            new_value = ""
                            if 'new_value' in change and change['new_value']:
                                new_value = six.text_type(change['new_value'])

                            longtext = False
                            if 'longtext' in change and change['longtext'] == 1:
                                longtext = True
                                detail_clsname = 'cdb_audittrail_detail_longtext'
                                if 'detail_classname' in change:
                                    detail_clsname = change['detail_classname']
                                if longtext_stripper:
                                    new_value = longtext_stripper(new_value)
                                    old_value = longtext_stripper(old_value)

                            new_value = shortenText(new_value, attr_length)
                            old_value = shortenText(old_value, attr_length)
                            if DBType == sqlapi.DBMS_ORACLE:
                                insert_statement = """{uuid},{audittrail_id},{attribute_name} AS attribute_name,
                                                   {old_value} AS old_value, {new_value} AS new_value,
                                                   {label_de} AS label_de, {label_en} AS label_en,
                                                   {detail_classname}"""
                            else:
                                insert_statement = """{uuid},{audittrail_id},{attribute_name},{old_value},
                                                      {new_value},{label_de},{label_en},{detail_classname}"""
                            audittrail_insert = insert_statement.format(
                                uuid=AuditTrailDetail.detail_object_id.make_literal(detail_uuid),
                                audittrail_id=AuditTrailDetail.audittrail_object_id.make_literal(
                                    obj['audittrail_id']),
                                attribute_name=AuditTrailDetail.attribute_name.make_literal(
                                    change['attribute_name']),
                                old_value=AuditTrailDetail.old_value.make_literal(old_value),
                                new_value=AuditTrailDetail.new_value.make_literal(new_value),
                                label_de=AuditTrailDetail.label_de.make_literal(
                                    config[obj['classname']]["fields"][change['attribute_name']]["de"]),
                                label_en=AuditTrailDetail.label_en.make_literal(
                                    config[obj['classname']]["fields"][change['attribute_name']]["en"]),
                                detail_classname=AuditTrailDetail.cdb_classname.make_literal(
                                    detail_clsname)
                            )
                            if DBType == sqlapi.DBMS_ORACLE:
                                audittrail_inserts += "SELECT %s FROM dual UNION ALL " % audittrail_insert
                            else:
                                audittrail_inserts += "(%s)," % audittrail_insert
                            create = True
                            if longtext:
                                if old_value:
                                    longtexts.append({"textfield": "cdb_audittrail_longtext_old",
                                                      "detail_object_id": detail_uuid,
                                                      "text": change['old_value']})
                                if new_value:
                                    longtexts.append({"textfield": "cdb_audittrail_longtext_new",
                                                      "detail_object_id": detail_uuid,
                                                      "text": change['new_value']})

            if DBType == sqlapi.DBMS_ORACLE:
                audittrail_inserts = audittrail_inserts[:-10]
            else:
                audittrail_inserts = audittrail_inserts[:-1]
            if create:
                sqlapi.SQL(audittrail_inserts)
        if create:
            if longtexts:
                for lt in longtexts:
                    util.text_write(lt["textfield"],
                                    ["detail_object_id"],
                                    [lt["detail_object_id"]],
                                    lt["text"])

    @classmethod
    def getChangedObjectIDs(cls, root_object_id, start=None, end=None, query="", with_create=False):
        """
        Returns a list of cdb_object_id and classname tuples which meet the entered criterion

        :param root_object_id: The cdb_object_id of the object on which a search shall be triggered.
        :param start: Commencement of a period
        :param end: End of a period
        :param query: Further SQL queries to refine the search e.g. idx > 0 to capture only index levels greater than 0
        :param with_create: True if "create" entries shall also be considered
        :return: Dict of elements which match the entered criterion

        """
        root_obj = ByID(root_object_id)
        result = {}
        if root_obj:
            objs = {}
            if hasattr(root_obj, "getAuditTrailEntries"):
                objs = root_obj.getAuditTrailEntries()
            objs[root_object_id] = root_obj.GetClassname()
            audittrail_objects = AuditTrailObjects.KeywordQuery(object_id=list(objs))
            av_query = "type_en != 'Create'" if not with_create else "1=1"
            if query:
                av_query += " AND ( " + query + " ) AND %s" % AuditTrailView.audittrail_object_id.one_of(*audittrail_objects.audittrail_id)
            else:
                av_query += " AND %s" % AuditTrailView.audittrail_object_id.one_of(*audittrail_objects.audittrail_id)
            if start:
                av_query += " AND cdb_cdate >= %s" % sqlapi.make_literals(start)
            if end:
                av_query += " AND cdb_cdate <= %s" % sqlapi.make_literals(end)
            result_av_objs = AuditTrailView.Query(av_query)

            for obj in result_av_objs:
                if obj.object_id and obj.object_id in objs:
                    result[obj.object_id] = objs[obj.object_id]
        return result

    @classmethod
    def getChangedObjects(cls, root_object_id, start=None, end=None, query="", with_create=False):
        """
        Returns a list of Objects which meet the entered criterion

        :param root_object_id: The cdb_object_id of the object on which a search shall be triggered.
        :param start: Commencement of a period
        :param end: End of a period
        :param query: Further SQL queries to refine the search e.g. idx > 0 to capture only index levels greater than 0
        :param with_create: True if "create" entries shall also be considered
        :return: List of objects which match the entered criterion

        """
        obj_ids = AuditTrailApi.getChangedObjectIDs(root_object_id, start=start, end=end, query=query, with_create=with_create)
        result = []
        cls_dict = {}
        for obj_id, classname in six.iteritems(obj_ids):
            if classname in cls_dict:
                cls_dict[classname].append(obj_id)
            else:
                cls_dict[classname] = [obj_id]
        for classname, obj_ids in six.iteritems(cls_dict):
            cls_entity = ClassRegistry().find(entities.Entity.ByKeys(classname=classname).getTableName())
            for obj in cls_entity.Query(getattr(cls_entity, "cdb_object_id").one_of(*obj_ids)):
                if obj.CheckAccess("read"):
                    result.append(obj)
        return result

    @classmethod
    def getLatestAuditTrailEntries(cls, count, on_object=None, head_only=False):
        """
        Returns a list of the latest Audit Trail entries.

        :param count: Number of entries to be returned.
        :param on_object: Object on which the search shall be performed
        :param head_only: Only the head information (without old, new values, etc.)
        :return: List of AuditTrail entries

        """
        if on_object:
            audittrail_objects = AuditTrailObjects.KeywordQuery(object_id=on_object.cdb_object_id)
            if audittrail_objects:
                c = AuditTrailView
                if head_only:
                    c = AuditTrail
                return c.Query(AuditTrailView.audittrail_object_id.one_of(*audittrail_objects.audittrail_id),
                               order_by="cdb_cdate DESC",
                               access="read",
                               access_persno=auth.persno,
                               max_rows=count)
            else:
                return []
        else:
            c = AuditTrailView
            if head_only:
                c = AuditTrail
            return c.Query("",
                           order_by="cdb_cdate DESC",
                           access="read",
                           access_persno=auth.persno,
                           max_rows=count)
