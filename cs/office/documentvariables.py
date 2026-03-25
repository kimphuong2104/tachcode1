#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals

from collections import OrderedDict
from datetime import date, datetime
import json
import os
import tempfile
import warnings
import logging

from cdb import CADDOK, ElementsError, misc, sqlapi, util, constants
from cdb.constants import kOperationModify
from cdb.objects import DataDictionary
from cdb.objects.core import ClassRegistry, Object
from cdb.objects.operations import operation
from cdb.objects.org import User
from cdb.platform.mom.entities import Entity
from cdb.platform.mom.fields import DDDateField, DDFloatField, DDIntegerField, DDPredefinedField
from cdb.typeconversion import from_legacy_date_format

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class OfficeLinkContent(object):
    def __init__(self, obj, doc_vars):
        self.document_variables = doc_vars
        self.object = obj

    def log(self, msg, level=7, channel=None, trace=False):
        if level == 0:
            logging.error(msg)
        elif level < 7:
            logging.info(msg)
        else:
            logging.debug(msg)


class DocumentVariable(object):

    def __init__(self, var_str, values=None):
        toks = var_str.split(".")
        self.access_mode = toks[1]
        self.relationship = toks[2]
        self.attribute = toks[3]
        self.cardinality = "1" if (len(toks) < 5) else toks[4]
        self.parameter = "" if (len(toks) < 7) else toks[6]
        if isinstance(values, list):
            self.values = values
        else:
            self.values = [values] if (values is not None) else []

    def get_values(self, obj_or_objs, verbose):
        from babel.dates import format_date, format_datetime
        objs = obj_or_objs if isinstance(obj_or_objs, list) else [obj_or_objs]
        values = []
        for obj in objs:
            if not obj:
                values.append("ERROR: No accessible object found" if verbose else "")

            elif self.attribute.startswith("_SML"):
                # TODO: Remove the SML feature in CDB 16.0!
                val = None
                _type = self.attribute[4]
                _id = self.attribute[5:]
                if _type == "_":
                    val = self.get_merkmal_value_by_kennung(obj, _id)
                elif _type == "N":
                    val = self.get_merkmal_kennung_by_row(obj, _id)
                elif _type == "V":
                    val = self.get_merkmal_value_by_row(obj, _id)
                values.append(val)

            elif not hasattr(obj, self.attribute):
                if self.attribute in obj.GetTextFieldNames():
                    values.append(obj.GetText(self.attribute))
                else:
                    values.append(("ERROR: Attribute '%s' not found" % self.attribute)
                                  if verbose else "")
            else:
                val = getattr(obj, self.attribute)
                if isinstance(val, date):
                    if isinstance(val, datetime) and val.time():
                        # Only keep the time part if it isn't 00:00:00 (E051393)
                        val = format_datetime(val, format="medium", locale=CADDOK.ISOLANG)
                    else:
                        val = format_date(val, format="medium", locale=CADDOK.ISOLANG)
                if val is None:
                    val = "?" if verbose else ""
                values.append("%s" % val)
        if self.cardinality == "1":
            if not objs:
                values.append("ERROR: Referenced object not found" if verbose else "")
            return values   # Neues Office moechte immer eine Liste von Values
        return values

    def get_sachmerkmal(self, part, sachgruppe):
        teilenummer = getattr(part, "teilenummer")
        t_index = getattr(part, "t_index")
        cls_def = Entity.ByKeys(sachgruppe).getClassDef()
        rs = sqlapi.RecordSet2(cls_def.getPrimaryTable(), "teilenummer='%s' AND t_index='%s'" %
                               (sqlapi.quote(teilenummer), sqlapi.quote(t_index)))
        return rs[0] if (len(rs) == 1) else None

    def get_merkmal_value_by_kennung(self, part, kennung):
        val = "ERROR: Relationship returned no or multiple referenced objects"
        sachgruppe = getattr(part, "sachgruppe")
        if not sachgruppe:
            val = "ERROR: Relationship object has no 'sachgruppe' value"
        else:
            sachmerkmal = self.get_sachmerkmal(part, sachgruppe)
            if sachmerkmal:
                merkmale = self.get_merkmal_kennungen(sachgruppe)
                if kennung in merkmale:
                    val = "%s" % getattr(sachmerkmal, merkmale[kennung])
                else:
                    val = "ERROR: Generic group property '%s' does not exist" % kennung
            else:
                val = "ERROR: Could not find SML object"
        return val

    def get_merkmal_kennung_by_row(self, part, row):
        row = int(row)
        val = "ERROR: Relationship returned no or multiple referenced objects"
        sachgruppe = getattr(part, "sachgruppe")
        if not sachgruppe:
            val = "ERROR: Relationship object has no 'sachgruppe' value"
        else:
            merkmale = self.get_merkmal_kennungen(sachgruppe)
            if row > len(merkmale.keys()):
                val = "ERROR: SML list contains less values"
            else:
                val = merkmale.keys()[row - 1]
        return val

    def get_merkmal_value_by_row(self, part, row):
        row = int(row)
        val = "ERROR: Relationship returned no or multiple referenced objects"
        sachgruppe = getattr(part, "sachgruppe")
        if not sachgruppe:
            val = "ERROR: Relationship object has no 'sachgruppe' value"
        else:
            sachmerkmal = self.get_sachmerkmal(part, sachgruppe)
            if sachmerkmal:
                merkmale = self.get_merkmal_kennungen(sachgruppe)
                if row > len(merkmale.keys()):
                    val = "ERROR: SML list contains less values"
                else:
                    attr = merkmale[merkmale.keys()[row - 1]]
                    val = "%s" % getattr(sachmerkmal, attr)
            else:
                val = "ERROR: Could not find SML object"
        return val

    def get_merkmal_kennungen(self, sachgruppe):
        merkmale = OrderedDict()
        res_tbl = sqlapi.SQLselect("a.field_name, b.prop_mk FROM cdbdd_field a, cdbsml_pset_prop b "
                                   "WHERE a.cdb_object_id=b.dd_attr_uuid AND classname='%s'"
                                   % sachgruppe)
        for row in range(0, sqlapi.SQLrows(res_tbl)):
            merkmale.setdefault(res_tbl.get_string("prop_mk", row),
                                res_tbl.get_string("field_name", row))
        return merkmale


class DocumentVariables(object):

    @classmethod
    def auto_fill(cls, ctx, check_access_user_login):
        """
        Retrieve values for all variables still containing None. If a value is not None then the
        variable was already filled by a custom handler (implemented by connecting to the the signal
        'officelink_metadata_read'.
        """
        relationships = {}
        for var, value in ctx.document_variables.items():
            if value is not None:
                continue  # skip already handled variables
            _var = DocumentVariable(var)
            relationships.setdefault(_var.relationship, [])
            relationships[_var.relationship].append(var)

        if relationships:
            # we set verbose to False. Was never documented
            verbose = False
            ctx.log("METADATA_SYNC_VERBOSE=%s" % verbose)

            obj = cls.get_full_object(ctx.object)

            check_access_user = None
            if check_access_user_login:
                check_access_user = User.ByKeys(login=check_access_user_login)
                if check_access_user:
                    check_access_user = check_access_user.personalnummer

            for relationship, doc_vars in relationships.items():

                if relationship == "this":
                    _obj = obj if cls.is_access_granted(
                        obj, check_access_user, relationship, "read", ctx.log) else None
                    for var in doc_vars:
                        _var = DocumentVariable(var)
                        ctx.document_variables[var] = _var.get_values(_obj, verbose)

                elif relationship.startswith("BY_ZNUM_ZIDX_FROM_"):
                    # Step 1: For now only a warning
                    warnings.warn("Variables of type 'BY_ZNUM_ZIDX_FROM' will soon be deprecated!",
                                  DeprecationWarning)
                    # for var in doc_vars:
                    #     ctx.document_variables[var] = \
                    #         "ERROR: Variables of type 'BY_ZNUM_ZIDX_FROM' are deprecated!"
                    # Step 2: Get rid of the code below with CE 16.0
                    tbl_name = relationship.replace("BY_ZNUM_ZIDX_FROM_", "")
                    rs = sqlapi.RecordSet2(tbl_name, "z_nummer='%s' AND z_index='%s'" %
                                           (sqlapi.quote(getattr(obj, "z_nummer", "")),
                                            sqlapi.quote(getattr(obj, "z_index", ""))))
                    if len(rs) == 0:
                        error = "ERROR: Referenced object not found" if verbose else ""
                    elif len(rs) == 1:
                        error = None
                        _obj = rs[0]
                        if not cls.is_access_granted(_obj, check_access_user, tbl_name,
                                                     "read", ctx.log):
                            _obj = None
                    else:
                        error = "ERROR: No unambiguous referenced object found" if verbose else ""
                    for var in doc_vars:
                        _var = DocumentVariable(var)
                        ctx.document_variables[var] = error or _var.get_values(_obj, verbose)

                else:
                    try:
                        tbl = obj.ToObjectHandle().navigate_relship_tableresult(relationship)
                    except ElementsError as ex:
                        # Reading out non-existing relships is also logged and skipped when
                        # updating variables via OfficeLink/TalkAPI
                        misc.log_traceback("")
                        for var in doc_vars:
                            _var = DocumentVariable(var)
                            ctx.document_variables[var] = "%s" % ex if verbose else ""
                        continue
                    objs = []
                    for oh in [tbl.getObjectHandle(r) for r in range(0, tbl.getNumberOfRows())]:
                        _obj = cls.get_full_object(oh)
                        if cls.is_access_granted(_obj, check_access_user,
                                                 relationship, "read", ctx.log):
                            objs.append(_obj)
                        else:
                            objs.append(None)
                    for var in doc_vars:
                        _var = DocumentVariable(var)
                        ctx.document_variables[var] = _var.get_values(objs, verbose)
        else:
            ctx.log("No document variables found to be auto filled")

    @classmethod
    def auto_write(cls, ctx, check_access_user_login):
        """
        Write given document variable values to DB. Variables with special parameters aren't handled
        by this standard method. The signal 'officelink_metadata_write' can be used to implement
        custom handlers. Writing variables with 1:N relations also isn't supported.
        """
        this_doc_vars = dict()
        relationships = {}
        for var, values in ctx.document_variables.items():
            _var = DocumentVariable(var, values)
            relationships.setdefault(_var.relationship, [])
            relationships[_var.relationship].append(_var)

        if relationships:
            obj = cls.get_full_object(ctx.object)
            check_access_user = None
            if check_access_user_login:
                check_access_user = User.ByKeys(login=check_access_user_login)
                if check_access_user:
                    check_access_user = check_access_user.personalnummer

            for relationship, doc_vars in relationships.items():
                if relationship == "this":
                    if not cls.is_access_granted(obj, check_access_user,
                                                 relationship, constants.kAccessSave, ctx.log):
                        obj_desc = obj.GetDescription() if hasattr(obj, "GetDescription") else obj
                        raise Exception("Metadata sync: Failed write access check "
                                        "for '%s'" % obj_desc)
                    if doc_vars:
                        for dVar in doc_vars:
                            if dVar.values:
                                v = dVar.values[0]
                                if v is not None:
                                    this_doc_vars[dVar.attribute] = [v]
                                    # Return as list for "neues Office"

                elif relationship.startswith("BY_ZNUM_ZIDX_FROM_"):
                    raise Exception("Metadata sync: Server-side writing variables of type "
                                    "'BY_ZNUM_ZIDX_FROM' are not supported")
                else:
                    if doc_vars and doc_vars[0].cardinality == "N":
                        raise Exception("Metadata sync: Server-side writing variables are not "
                                        "supported for 1:N relationships")
                    tbl = obj.ToObjectHandle().navigate_relship_tableresult(relationship)
                    if tbl.getNumberOfRows() > 0:
                        ref_obj = tbl.getObjectHandle(0)
                        ref_obj = cls.get_full_object(ref_obj)
                        if not cls.is_access_granted(ref_obj, check_access_user,
                                                     relationship, constants.kAccessSave, ctx.log):
                            obj_desc = ref_obj.GetDescription() \
                                if hasattr(ref_obj, "GetDescription") else ref_obj
                            raise Exception("Metadata sync: Failed write access check "
                                            "for '%s'" % obj_desc)
                        cls.write_vars_to_object(ref_obj, doc_vars)
        else:
            ctx.log("No document variables found to be written to DB")
        return this_doc_vars

    @classmethod
    def get_full_object(cls, obj):
        if isinstance(obj, Object):
            obj.Reload()
            return obj
        elif hasattr(obj, "getClassDef"):
            cls_def = obj.getClassDef()
            tbl_keys = {k: getattr(obj, k) for k in cls_def.getKeyNames()}
        elif "cdb_classname" in obj:
            entity = Entity.ByKeys(obj["cdb_classname"])
            cls_def = entity.getClassDef()
            tbl_keys = {k: obj[k] for k in cls_def.getKeyNames()}
        else:
            raise Exception("Can't receive full object for '%s'" % obj)
        tbl_name = cls_def.getPrimaryTable() or cls_def.getRelation()
        _class = ClassRegistry().find(tbl_name)
        if _class:
            ret_obj = _class.ByKeys(**tbl_keys)
            ret_obj.Reload()  # E056311 (else e.g. joined attributes not always up to date)
            return ret_obj
        else:
            return sqlapi.RecordSet2(tbl_name, " AND ".join(["%s='%s'" % (k, sqlapi.quote(v))
                                                             for k, v in tbl_keys.items()]))[0]

    @classmethod
    def is_access_granted(cls, obj, user, relationship, permission, log):
        """
        Return False if given user doesn't have given permission (read, save,..) on given object.
        The relationship parameter is for logging purposes only.
        """
        granted = True
        if user:
            obj_desc = obj.GetDescription() if hasattr(obj, "GetDescription") else obj
            log("Checking access right (user=%s, relationship=%s, permission=%s, object=%s)" %
                (user, relationship, permission, obj_desc))
            if isinstance(obj, Object):
                granted = obj.CheckAccess(permission, user)
            elif isinstance(obj, sqlapi.Record):
                granted = util.check_access_record(obj, permission, user)
            else:
                raise Exception("Can't check access right for '%s'" % obj)
        if not granted:
            log("ERROR: Access check failed")
        return granted

    @classmethod
    def write_vars_to_object(cls, obj, doc_vars):
        """
        Convert all variable values into correct types depending on the attribute definitions in the
        data dictionary before modifying the targeted object.
        Warning: Currently the method can't handle date/time strings not formatted in our legacy
        style (german).
        """
        tbl_name = obj.GetTableName()
        sw_rec = DataDictionary().getRootClassRecord(tbl_name)
        entity = Entity.ByKeys(sw_rec.classname)
        args = {}
        for var in doc_vars:
            dd_field = entity.getField(var.attribute)
            if isinstance(dd_field, DDPredefinedField):
                dd_field = dd_field.ReferencedField
            if isinstance(dd_field, DDDateField):
                value = from_legacy_date_format(var.values[0]) \
                    if (var.values[0] not in [None, ""]) else None
            elif isinstance(dd_field, DDFloatField):
                value = float(var.values[0]) if (var.values[0] not in [None, ""]) else None
            elif isinstance(dd_field, DDIntegerField):
                value = int(var.values[0]) if (var.values[0] not in [None, ""]) else None
            else:
                value = var.values[0]
            args[var.attribute] = value
        operation(kOperationModify, obj, **args)

    @classmethod
    def prepare_result(cls, ctx):
        """
        Converts lists to json strings before converting everything to a json string, since the
        OfficeLink Add-In can initially only handle strings as dictionary values.
        """
        result_vars = dict()
        for var in ctx.document_variables:
            value = ctx.document_variables[var]
            if not isinstance(value, str):
                result_vars[var] = json.dumps(value)
            else:
                result_vars[var] = value
        return result_vars

    @classmethod
    def write_metadata_xml(cls, ctx, filename):
        """
        Exports the document variable dictionary of the context into an XML file which is required
        for OfficeLink updating document variables in an Office file "offline".
        """
        from lxml import objectify
        msodocvarlist = objectify.Element("msodocvarlist")
        for var, value in ctx.document_variables.items():
            if value is None:
                ctx.log("Skipping non-value variable: %s" % var)
                continue
            ctx.log("Exporting variable: %s ==> %s" % (var, value))
            msodocvar = objectify.SubElement(msodocvarlist, "msodocvar")
            msodocvar.set("name", var)
            for val in (value if isinstance(value, list) else [value]):
                value_elem = objectify.SubElement(msodocvar, "value")
                value_elem._setText(val)

        objectify.deannotate(msodocvarlist, xsi_nil=True, cleanup_namespaces=True)
        # lxml's file writer can't fully handle unicode paths (E053168)
        _tempfile = tempfile.NamedTemporaryFile()
        _tempfilename = _tempfile.name
        _tempfile.close()
        msodocvarlist.getroottree().write(_tempfilename,
                                          encoding='UTF-8',
                                          pretty_print=True,
                                          xml_declaration=True)
        os.rename(_tempfilename, filename)
        ctx.log("Successfully exported variables to: %s" % filename)
