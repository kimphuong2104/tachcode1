#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# pylint: disable-msg=C0302,W0612,W0622,W0212,W0142

r"""
Some subject characteristics tools

The following example shows how an property check can be done::

    class MyItem(cs.vp.items.Item):

        def on_modify_post_mask(self, ctx):
            errmsgs = sml.checkPropertyFormat(ctx.dialog, self.sachgruppe)
            if errmsgs:
                raise ue.Exception(1024, "\n".join(errmsgs))

        def on_modify_dialogitem_change(self, ctx):
            errmsgs = sml.checkPropertyFormat(ctx.dialog, ctx.object.sachgruppe,
                                              ctx.changed_item)
            if errmsgs:
                raise ue.Exception(1024, "\n".join(errmsgs))
"""



__revision__ = "$Id$"

import numbers
import re
import sys
import traceback

from cdbwrapc import PhysQuantity
from cdbwrapc import build_state_escape_query_chars
from cdbwrapc import getAttributeDefByUUID
from cdbwrapc import is_cdb_pq

from cdb import cdbuuid
from cdb import decomp
from cdb import misc
from cdb import sqlapi
from cdb import transaction
from cdb import util

from cdb.platform import gui
from cdb.objects import Forward


__all__ = []

Document = Forward("cs.documents.Document")

IMAGECLASSES = {'oplan': ["Bild im Objektplan", "Bild in Maske/Objektplan"],
                'mask': ["Bild in Maske", "Bild in Maske/Objektplan"],
                }


class PropsetValueCatalog(gui.CDBCatalog):
    """
    Catalog to show possible Property values for a given property
    """

    def __init__(self):
        """ Initializes a catalog."""
        gui.CDBCatalog.__init__(self)
        self.result = []

    def handlesSimpleCatalog(self):
        return True

    def _getPropMk(self, attrdef):
        attrname = attrdef.getName()
        from cdb.platform.mom import fields
        facet_cldef = attrdef.getClassDef()
        field = fields.DDField.ByKeys(facet_cldef.getClassname(), attrname)
        if field:
            from cs.vp import classification
            field_uuid = field.cdb_object_id
            propref = classification.PropertyReference.KeywordQuery(dd_attr_uuid=field_uuid)
            try:
                # Nicht erst die Länge abfragen, da dies zu einem unnötigem
                # select count(*) führt
                attrname = propref[0].prop_mk
            except Exception:
                attrname = ""

        return attrname

    def getCatalogEntries(self):
        """
        Retrieving the values
        """
        if not self.result:
            # Add empty value to reset the selection
            self.result.append("")

            c = self.getInvokingOpClassDef()
            if c:
                a = c.getFacetAttributeDefinition(self.getInvokingField())
                if a:
                    facet_cldef = a.getClassDef()

                    if facet_cldef:
                        pset_id = facet_cldef.getClassname()
                        prop_mk = self._getPropMk(a)
                        t = sqlapi.SQLselect(
                            "DISTINCT cdbsml_pval_subset_v.pval_value FROM cdbsml_pval_subset_v  "
                            "WHERE (((cdbsml_pval_subset_v.prop_mk = '%s') AND "
                            "NOT (cdbsml_pval_subset_v.pval_value = '') AND "
                            "(cdbsml_pval_subset_v.pset_id = '%s') AND "
                            "(cdbsml_pval_subset_v.pval_exclude = '0' OR "
                            " cdbsml_pval_subset_v.pval_exclude IS NULL OR "
                            " cdbsml_pval_subset_v.pval_exclude=''))) "
                            " ORDER BY cdbsml_pval_subset_v.pval_value" % (
                                sqlapi.quote(prop_mk), sqlapi.quote(pset_id)))
                        rows = sqlapi.SQLrows(t)
                        for r in range(0, rows):
                            if self.getInvokingOpName() in ["CDB_Search", "CDB_SearchAgain"]:
                                self.result.append(build_state_escape_query_chars(sqlapi.SQLstring(t, 0, r)))
                            else:
                                self.result.append(sqlapi.SQLstring(t, 0, r))
                        # If the attribute is numeric - we have to sort the
                        # values
                        try:
                            if a.getSQLType() in (sqlapi.SQL_INTEGER, sqlapi.SQL_FLOAT):  # numeric value (Integer, Float)
                                # We want to display the original (string)
                                # value, so build a dict
                                if a.getSQLType() == sqlapi.SQL_INTEGER:
                                    result_dict = {str_val: int(str_val)
                                                   for str_val in self.result if str_val}
                                else:
                                    result_dict = {str_val: float(str_val)
                                                   for str_val in self.result if str_val}

                                self.result = [""]  # The empty entry to reset a catalog selection
                                for key, value in sorted(result_dict.items(), key=lambda t: (t[1], t[0])):
                                    self.result.append(key)
                        except Exception as exc:
                            misc.log_error("Failed to sort the SML property values:%s" % exc)
                            # No ue.Exception - self.result will contain the
                            # unsorted values - thats better than nothing
        return self.result


class LabelPart:
    def __init__(self, strLabelPart, aDataDictList, strStaticLanguage=''):
        misc.log(8, "LabelPart::__init__(%s, %s, %s): LabelPart initialized." % (
            strLabelPart, aDataDictList, strStaticLanguage))
        self.__strUUID = cdbuuid.create_uuid()
        self.__strResolvedValue = ""
        self.__strRawLabelPart = strLabelPart
        self.__strLabelPart = strLabelPart
        # determine sublabelparts
        seperator = re.compile(r"(?<=[^\\])\+")
        self.__labelSubParts = []
        labelSubparts = [re.sub("^[ ]*|[ ]*$", "", strSubPart) for strSubPart in seperator.split(strLabelPart)]  # strip leading and following spaces
        for strLabelSubpart in labelSubparts:
            self.__labelSubParts.append(LabelSubpart(strLabelSubpart, aDataDictList, strStaticLanguage))

    def GetRawOptionalLabel(self):
        return "[%s]" % (self.__strRawLabelPart,)

    def GetUUID(self):
        return self.__strUUID

    def GetOptionalValue(self):
        strResolvedValue = ""
        if self.__strResolvedValue == "":
            for aLabelPart in self.__labelSubParts:
                strLabelSubPartValue = aLabelPart.GetFixedValue()
                if len(strLabelSubPartValue) == 0:
                    return ""
                strResolvedValue += strLabelSubPartValue
            self.__strResolvedValue = strResolvedValue

        misc.log(8, "LabelPart::GetOptionalValue(): Resolved '%s' for '%s' " % (self.__strResolvedValue, self.GetRawOptionalLabel()))
        return self.__strResolvedValue

    def GetValue(self):
        if self.__strResolvedValue == "":
            strResolvedValue = ""
            for aLabelPart in self.__labelSubParts:
                strResolvedValue += aLabelPart.GetFixedValue()
            self.__strResolvedValue = strResolvedValue

        misc.log(8, "LabelPart::GetValue(): Resolved '%s' for '%s' " % (self.__strResolvedValue, self.__strRawLabelPart))
        return self.__strResolvedValue


class LabelSubpart:
    def __init__(self, strLabelPart, aDataDictList, strStaticLanguage=''):
        misc.log(8, "LabelSubpart::__init__(%s, %s, %s): LabelSubpart initialized." % (strLabelPart, aDataDictList, strStaticLanguage))
        self.__strResolvedValue = ""
        self.__aDataDictList = aDataDictList
        self.__strStaticLanguage = strStaticLanguage
        self.__strRawLabelPart = re.sub(r"\\(?=\[|\])", "", strLabelPart)  # revoke quoting of '[' and ']'
        self.__strLabelPart = self.__strRawLabelPart
        self.__isAttribute = self.IsAttribute()
#         #Further implementation for limiting length of each labelpart
#         self.__minLength = -1
#         self.__calcedLength = -1
#         self.__strLengthLimiter = ""
#         self.__isAttribute = self.IsAttribute()
#         self.DetermineMinLength()

#     def DetermineMinLength(self):
#         self.__strRawLabelPart
#         m = re.compile(r"(?P<pre>\{)(?P<length>.*?)(?P<separator>,+)(?P<limiter>.*?)(?P<post>\})").search(self.__strRawLabelPart)
#         if m:
#             #detemine minimal length and limiter characters of current labelpart
#             self.__minLength = int(m.groupdict().get('length', -1))
#             self.__strLengthLimiter = re.sub(r"^['\"]*|[\"']*$", "", m.groupdict().get('limiter', ''))
#             #delete this format-expression from labelpart
#             self.__strLabelPart = re.sub("\{.*,.*\}", "", self.__strLabelPart)
#             misc.log(8, "LabelSubpart::DetermineMinLength(): format-expression found: length => %d; limiter => %s" % (self.__minLength, self.__strLengthLimiter))
#         else:
#             misc.log(8, "LabelSubpart::DetermineLength(): No format-expression found."

    def IsAttribute(self):
        m = re.compile(r"^['\"]+?.*[\"']+?$").search(self.__strLabelPart)
        if m:
            misc.log(8, "LabelSubpart::IsAttribute(): %s is identified as a constant string." % self.__strLabelPart)
            return False

        misc.log(8, "LabelSubpart::IsAttribute(): %s is identified as an attribute." % self.__strLabelPart)
        return True

    def ResolveEnvVar(self):
        misc.log(8, "LabelSubpart::ResolveEnvVar(): Resolve environment-variables and substitute them for %s." % self.__strLabelPart)
        m = re.compile(r"(?P<pre>\$\()(?P<varname>.*?)(?P<post>\))").search(self.__strLabelPart)
        if m:
            strEnvVarName = m.groupdict().get('varname', '')
            strEnvVarValue = misc.getConfigValue(strEnvVarName)
            if strEnvVarValue is None:
                strEnvVarValue = ''

            misc.log(8, "LabelSubpart::ResolveEnvVar(): Determined value '%s' for environment-variable '%s'." % (strEnvVarValue, strEnvVarName))
            self.__strLabelPart = re.sub(r"\$\(%s\)" % strEnvVarName, strEnvVarValue, self.__strLabelPart)
            self.ResolveEnvVar()

    def GetValueFromDataDictList(self, strAttribute):
        for aDataDict in self.__aDataDictList:
            if strAttribute in aDataDict:
                misc.log(8, "LabelSubpart::GetValueFromDataDictList(): Determined value '%s' for attribute '%s'." % (aDataDict[strAttribute], strAttribute))
                val = aDataDict[strAttribute]
                return "" if val is None else val
        misc.log(8, "LabelSubpart::GetValueFromDataDictList(): No value found for attribute '%s'." % strAttribute)
        return ''

    def GetFixedValue(self):
        misc.log(8, "LabelSubpart::GetFixedValue():(Labelpart: '%s') Special "
                 "behavior for keeping internalisation: 'CADDOK_ISOLANG' will "
                 "be substitude with '%s', if present." % (
                     self.__strLabelPart, self.__strStaticLanguage))

        if self.__strResolvedValue == '':
            if self.__isAttribute:
                # special handling for downward compatibility
                self.__strLabelPart = re.sub(r"\$\(CADDOK_ISOLANG\)", self.__strStaticLanguage, self.__strLabelPart)

            return self.GetValue()
        return self.__strResolvedValue

    def GetValue(self):
        if self.__strResolvedValue == '':
            if self.__isAttribute:
                # strip leading and following spaces
                self.__strLabelPart = re.sub("^[ ]*|[ ]*$", "", self.__strLabelPart)
                # resolve further environment variables
                self.ResolveEnvVar()
                self.__strResolvedValue = self.GetValueFromDataDictList(self.__strLabelPart)
            else:
                self.__strLabelPart = re.sub(r"^['\"]|[\"']$", "", self.__strLabelPart)
                self.ResolveEnvVar()
                self.__strResolvedValue = self.__strLabelPart

        misc.log(8,
                 "LabelSubpart::GetValue(): Determined value '%s' for labelpart '%s'." %
                 (self.__strResolvedValue,
                  self.__strLabelPart))

        return self.__strResolvedValue


class SMLException(Exception):
    def __init__(self, msg):
        super(SMLException, self).__init__()
        self.msg = msg

    def __str__(self):
        return "SMLException: %s" % self.msg


class CatDecompBuilder:
    def __init__(self):

        # Read categories
        cdbsml_propcat = sqlapi.RecordSet2("cdbsml_propcat")
        self.cat_by_id = {}
        for cat in cdbsml_propcat:
            self.cat_by_id[cat.cat_id] = cat
            cat.children = []
            cat.parent = None

        # Read hierarchy relationships
        for x in sqlapi.RecordSet2("cdbsml_propcathier"):
            parent = self.getcat(x.cat_id, None)
            child = self.getcat(x.child_id, None)
            if parent and child:
                parent.children.append(child)
                child.parent = parent

    def getcat(self, myid, deflt=None):
        return self.cat_by_id.get(myid, deflt)

    def cat_path(self, node):
        path = []
        while node:
            path.insert(0, node.cat_id)
            node = node.parent
        return path

    def print_cathier(self, node, level=0):
        print(level * " ", node.cat_id, node.name_de, self.cat_path(node))
        for child in node.children:
            self.print_cathier(child, level + 1)

    def __call__(self):
        with transaction.Transaction():
            for prop in sqlapi.RecordSet2("cdbsml_property"):
                cat = self.getcat(prop.cat_id)
                path = self.cat_path(cat)
                attrs = {}
                i = 1
                for elem in path:
                    a = "cat_id%s" % i
                    i += 1
                    attrs[a] = elem
                if attrs:
                    prop.update(**attrs)

            sqlapi.SQLdelete("from cdbsml_propcathier where cat_id=''")
            sqlapi.SQLinsert("into cdbsml_propcathier values ('', '1')")
            CatDecompBuilder.rebuild_decomposition()

    @classmethod
    def rebuild_decomposition(cls):
        src = decomp.DecompSource("cp", "cdbsml_propcat_v", "cat_id", "parent_id",
                                  {"cat_id<level>": "cat_id"},
                                  {"cat_id,cat_id,cat_id": "cat_id"}, {},
                                  "name_<language>", "", "", "", "Folder", "",
                                  py_generator="cs.vp.classification.sml.CatDecompBuilder.rebuild_decomposition")
        src.delete_decompositions()
        src.generate_decomposition("cdbsml_propcat")


def rebuild_smldecomp():
    with transaction.Transaction():
        rset = sqlapi.RecordSet2("cdbsml_propset")
        for rec in rset:
            key = 0
            cgroup_map = {}
            rset2 = sqlapi.RecordSet2(sql="select cgroup_id from cdbsml_cg_pset where pset_id = '%s'" % sqlapi.quote(rec.pset_id))
            if len(rset2) == 1:
                cgroup_id = rset2[0].cgroup_id
                cgroup_map[key] = cgroup_id
                while True:
                    rset3 = sqlapi.RecordSet2(sql="select cgroup_id from cdbsml_cg_hier where child_id = '%s'" % sqlapi.quote(cgroup_id))
                    if len(rset3) == 1:
                        if rset3[0].cgroup_id == 'root':
                            break
                        key -= 1
                        cgroup_map[key] = cgroup_id = rset3[0].cgroup_id
                    else:
                        break
                attrs = {}
                for key in cgroup_map.keys():
                    lvl = 1 + key - min(cgroup_map.keys())
                    a = "cgroup_id%s" % lvl
                    attrs[a] = cgroup_map[key]
                if attrs:
                    rec.update(**attrs)

    src = decomp.DecompSource("cg", "cdbsml_cghier_v", "cgroup_id", "parent_id",
                              {"cgroup_id<level>": "cgroup_id"},
                              {"pset_id": "cgroup_id"}, {},
                              "label_<language>", "", "icon_id", "", "Folder",
                              "", "root", "cgroup_id",
                              py_generator="cs.vp.classification.sml.rebuild_smldecomp")
    src.delete_decompositions()
    src.generate_decomposition("cdbsml_cgroup")


class RecordDict:
    def __init__(self, records, key):
        self.records = records
        self.by_id = {}
        self.key = key
        self.add_records(records)

    def add_records(self, records):
        for record in records:
            self.add_record(record)

    def add_record(self, record):
        self.by_id[record[self.key]] = record

    def __getitem__(self, key):
        return self.by_id[key]

    def has_key(self, key):
        return key in self.by_id

    def keys(self):
        return list(self.by_id)

    def values(self):
        return list(self.by_id.values())

    def items(self):
        return list(self.by_id.items())

    def get(self, key, default):
        return self.by_id.get(key, default)


def cgroup_hierarchy():
    cgroups = sqlapi.RecordSet2("cdbsml_cgroup")
    cg_by_id = {}
    for cgroup in cgroups:
        cg_by_id[cgroup.cgroup_id] = cgroup
        cgroup.children = []
        cgroup.classification = ""
    cg_hier = sqlapi.RecordSet2("cdbsml_cg_hier", addtl="order by child_id")

    from cs.vp import classification
    from cdbwrapc import build_sml_label
    for x in cg_hier:
        parent = cg_by_id[x.cgroup_id]
        child = cg_by_id.get(x.child_id, None)
        if child:
            # Determine label depending on smfm-property
            update_dict = {}
            child.classification = x.get("klassifikation", None) or ""
            parent.children.append(child)
            for iso_lang, fld in classification.CGCategoryReference.label.getLanguageFields().items():
                cat_field = classification.ClassificationCategory.name.getLanguageField(iso_lang)
                if cat_field:
                    update_dict[fld.name] = build_sml_label(x.child_id,
                                                            child.classification,
                                                            child[cat_field.name])

            misc.log(0, "cgroup_hierarchy(parent-id='%s': cgroup-id='%s'): "
                     "Labels = '%s'" % (x.cgroup_id, x.child_id, update_dict))

            x.update(**update_dict)
        else:
            misc.log_error("Unknown CGROUP %s in CDBSML_CG_HIER" % x.child_id)

    return cg_by_id['root']


def cgroup_print(cg, level=0):
    print(level * " ", cg.cgroup_id, cg.name_de, cg.classification)
    for child in cg.children:
        cgroup_print(child, level + 1)


def trimLabel(label, max_length):
    """
    Returns `label` or a shortened label
    if label is longer than `max_length`.
    If `label` contains multiple lines separated by
    ``\\n`` the lines will be shortened in a way that
    long lines will be shortened first. Shortened labels
    or label lines will end with ``...``.
    """
    if label and len(label) > max_length:
        # Shorten the longest lines makes only sense if there
        # remains enough space for each line, so drop lines
        # if there are too many lines. 8 is the number of
        # chars each line should contain
        max_lines = max(max_length / 8, 1)
        label_lines = label.split("\\n")
        # Shorten the lines until the remaining label is short enough or
        # max_lines is reached
        while len("\\n".join(label_lines)) > max_length and len(label_lines) > max_lines:
            label_lines = label_lines[:-1]
        # Keep the \\n (2 characters)
        available_chars = max_length - ((len(label_lines) - 1) * 2)
        label_lines_len = [len(s) for s in label_lines]

        # Shorten the length of the longest lines until the sum fits
        while sum(label_lines_len) > available_chars:
            max_len = max(label_lines_len)
            label_lines_len = [l - 1 if l == max_len else l for l in label_lines_len]

        for pos in range(0, len(label_lines)):
            if len(label_lines[pos]) > label_lines_len[pos]:
                if label_lines_len[pos] > 3:
                    label_lines[pos] = label_lines[pos][:label_lines_len[pos] - 3] + "..."
                else:
                    # if there are less than 4 chars it makes no sense to
                    # overwrite the chars with dots
                    label_lines[pos] = label_lines[pos][:label_lines_len[pos]]

        label = "\\n".join(label_lines)

    return label


def get_label(cdb_property, cdbsml_pset_prop, cdbsml_property, lang, propval_dflt=""):
    strLabel = ""
    strCDBProperty = util.get_prop(cdb_property)
    if not strCDBProperty:
        strCDBProperty = propval_dflt

    strLabelProperty = strCDBProperty
    if strCDBProperty != '':
        try:
            misc.log(8, "Determine label based on cdb-property '%s'" % strCDBProperty)
            aDataDictList = [cdbsml_pset_prop, cdbsml_property]
            aOptionalLabelPartDict = {}

            for pre, optinal, post in re.compile(r"(?P<pre>(?<=[^\\])\[)(?P<varname>.*?)(?P<post>(?<=[^\\])\])").findall(strLabelProperty):
                aLabelPartOptional = LabelPart(optinal, aDataDictList, lang)
                strLabelProperty = strLabelProperty.replace(aLabelPartOptional.GetRawOptionalLabel(), aLabelPartOptional.GetUUID())
                aOptionalLabelPartDict[aLabelPartOptional.GetUUID()] = aLabelPartOptional.GetOptionalValue()

            aDataDictList.append(aOptionalLabelPartDict)
            strLabel = LabelPart(strLabelProperty, aDataDictList, lang).GetValue()
            misc.log(8, "Label determination based on cdb-property '%s' delivered '%s'." % (strCDBProperty, strLabel))

        except Exception:
            misc.log_error("Label determination based on cdb-property '%s' failed." % strCDBProperty)

    else:
        misc.log(8, "CDB-Property '%s' is not set." % cdb_property)

    return strLabel


def PremaskImages(ctx):
    """
    Replacing SML-Icons in SML-Masks
    """
    # Check 'dialog' and 'object' to catch all cases for UEs
    sg = 0
    if "sachgruppe" in ctx.dialog.get_attribute_names():
        sg = ctx.dialog.sachgruppe
    elif "sachgruppe" in ctx.object.get_attribute_names():
        sg = ctx.object.sachgruppe

    if sg:
        pics = sqlapi.RecordSet2("cdbsml_pset_doc", "pset_id='%s'" % sqlapi.quote(sg),
                                 addtl="order by position")
        bild = 1
        for pic in pics:
            if pic.purpose in IMAGECLASSES["mask"]:
                doc = Document.ByKeys(pic.z_nummer, pic.z_index)
                if doc:
                    for smlfile in doc.getPrimaryFiles():
                        ctx.redirect_icon("bild%s" % bild, smlfile)
                        bild += 1


def ClearSMLConfigSchema():
    sqlapi.SQLdelete("from cdbsml_cgroup where cgroup_id <> 'root'")
    sqlapi.SQLdelete("from cdbsml_cg_docs")
    sqlapi.SQLdelete("from cdbsml_cg_hier")
    sqlapi.SQLdelete("from cdbsml_cg_pset")
    # sqlapi.SQLdelete("from cdbsml_cg_types")
    # sqlapi.SQLdelete("from cdbsml_doc_purpose")
    sqlapi.SQLdelete("from cdbsml_preset")
    sqlapi.SQLdelete("from cdbsml_propcat where cat_id <> '1'")
    sqlapi.SQLdelete("from cdbsml_propcathier")
    sqlapi.SQLdelete("from cdbsml_propdoc")
    sqlapi.SQLdelete("from cdbsml_property")
    sqlapi.SQLdelete("from cdbsml_propset")
    sqlapi.SQLdelete("from cdbsml_propvalue")
    sqlapi.SQLdelete("from cdbsml_pset_doc")
    sqlapi.SQLdelete("from cdbsml_pset_names")
    sqlapi.SQLdelete("from cdbsml_pset_prop")
    sqlapi.SQLdelete("from cdbsml_pset_view")
    sqlapi.SQLdelete("from cdbsml_pval_subset")
    # sqlapi.SQLdelete("from cdbsml_unit_names")


# Code to access SML values for parts below. Public APIs are
# those with a doc string.

# A simple cache of records. 'get' is to be used with
# RecordSet.__init__ compatible keyword args.
class RecordSetCache:
    def __init__(self, table):
        self.table = table
        self._rsets = {}

    def get(self, **kwargs):
        def sorted_items(d):
            keys = list(d)
            keys.sort()
            for k in keys:
                yield k, d[k]

        key = ",".join(["%s=%s" % t for t in sorted_items(kwargs)])
        rset = self._rsets.get(key, None)
        if rset is None:
            rset = sqlapi.RecordSet2(self.table, **kwargs)
            self._rsets[key] = rset
        return rset

# Caches for database tables
__CDBSML_PSET_PROP = RecordSetCache("cdbsml_pset_prop")
__CDBSML_PROPERTY = RecordSetCache("cdbsml_property")


# Simple wrapper to the PHYS_QUANT_DEF table.
class PUDef:
    def __init__(self, name):
        self.name = name
        records = sqlapi.RecordSet2("phys_quant_def", "quantity='%s'" % sqlapi.quote(name))
        if not records:
            raise Exception("PHYS_QUANT_DEF entry with quantity='%s' not found" % name)
        self.record = records[0]

    # 'Parse' the [a|b|c|...] syntax of the PHYS_QUANT_DEF.VALID_SYMS
    # field and return a list of string items.
    def symbols(self):
        valid_syms = self.record.valid_syms[1:-1].split("|")
        return valid_syms


# A simple wrapper to the PHYS_QUANT_TYPES table.
class PUType:
    def __init__(self, type_id):
        self.type_id = type_id
        records = sqlapi.RecordSet2("phys_quant_types", "type=%d" % self.type_id)
        if not records:
            raise Exception("PHYS_QUANT_TYPES entry with type=%d not found" % self.type_id)
        self.record = records[0]
        self.base = PU_DEFS[self.record.quantity]

    # Returns a unit symbol for the base unit of this type (i.e. the
    # unit assumed for values entered without a symbol).
    def base_unit(self):
        default_sym = self.base.symbols()[0]
        return self.record.base_prefix + default_sym


# A simple cache of objects of type 'cached_class', which
# must be constructible with the 'key' argument.
class SimpleCache:
    def __init__(self, cached_class):
        self.__class = cached_class
        self.__instances = {}

    def __getitem__(self, key):
        result = self.__instances.get(key)
        if result is None:
            result = self.__class(key)
            self.__instances[key] = result
        return result

PU_DEFS = SimpleCache(PUDef)
PU_TYPES = SimpleCache(PUType)


# A global 'is_pq' predicate; can be called on anything,
# esp. an plain field values from a properties dict or
# a simple record.
def is_pq(prop):
    if hasattr(prop, 'is_pq'):
        return prop.is_pq()
    return False


class PropertyValue(object):
    """Represents a CIM DATABASE/SML property value. Use 'value' to
    access the value, which is either a string, an int or a float
    object, or, if 'is_pq()' returns True, 'value' and
    'normalized' are tuples of the form (<float value>, <unit as
    text>).
    """

    def __init__(self, value, normalized=(), property=None):
        self.__normalized = normalized
        self.__value = value
        self.__property = property

    value = property(lambda self: self.__value)
    normalized = property(lambda self: self.__normalized)
    property = property(lambda self: self.__property)

    def is_pq(self):
        return bool(self.normalized)

    def __repr__(self):
        return "PropertyValue(%s, %s)" % (repr(self.value), repr(self.normalized))

    def _formatted(self):
        myformat = "%s"
        if self.is_pq():
            v = self.value[0]
        else:
            v = self.value
        if v is None:
            return "?"
        if isinstance(v, float):
            v1 = "0" if not self.__property.din4001_mm_v1 else self.__property.din4001_mm_v1
            n1 = "0" if not self.__property.din4001_mm_n1 else self.__property.din4001_mm_n1
            myformat = "%" + ("%s" % v1) + "." + ("%s" % n1) + "f"
        return myformat % v

    def __str__(self):
        if self.is_pq() and self.value[0] is not None:
            return "%s%s" % (self._formatted(), self.value[1])
        return self._formatted()


def LoadProperties(part):
    """Return a dictionary of CIM DATABASE/SML properties for the
    given 'part' (which should be an sqlapi.Record, containing at
    least 'teilenummer', 't_index' and 'sachgruppe').
    """
    result = {}
    from cdbwrapc import sml_table
    # Find the SQL table that stores property values.
    sqltable = sml_table(part.sachgruppe)
    if sqltable:
        # Access the property table for the given 'part'.
        smldata = sqlapi.RecordSet2(sqltable,
                                    "teilenummer='%s' AND t_index='%s'"
                                    % (sqlapi.quote(part.teilenummer),
                                       sqlapi.quote(part.t_index)))
        if smldata:
            smlrecord = smldata[0]

            # Loop over the properties and collect PropertyValue
            # objects in 'result'.
            pset_props = __CDBSML_PSET_PROP.get(condition="pset_id='%s'" % part.sachgruppe)
            for pset_prop in pset_props:
                try:
                    myprop = __CDBSML_PROPERTY.get(condition="prop_id='%s'" % pset_prop.prop_id)[0]
                    if myprop:
                        sqlattr = ""
                        attrdef = getAttributeDefByUUID(pset_prop.dd_attr_uuid)
                        if attrdef:
                            sqlattrs = attrdef.getSQLSelectNames()
                            if sqlattrs:
                                sqlattr = sqlattrs[0]
                        if sqlattr:
                            cdb_type = 0
                            if myprop.din4001_mm_me:
                                cdb_type = int(myprop.din4001_mm_me)
                            if is_cdb_pq(cdb_type):
                                pu = PU_TYPES[cdb_type]
                                # Access wrapped kernel class PhysQuantity.
                                pq = PhysQuantity(cdb_type, sqltable, sqlattr)
                                attr_pqunit = pq.get_pq_attrname(sqlattr)
                                v0 = smlrecord[sqlattr]
                                if v0 is not None:
                                    pqunit = smlrecord[attr_pqunit]
                                    pqunit = pqunit if pqunit is not None else ""
                                    v1 = pq.val(v0, pqunit)
                                    elems = pq.reverse_norm(v0, pqunit).strip().split()
                                    if elems[1:]:
                                        v_unit = elems[1]
                                    else:
                                        v_unit = pu.base_unit()
                                else:
                                    v1 = None
                                    v_unit = pu.base_unit()
                                val = PropertyValue((v1, v_unit), (v0, pu.base_unit()), property=myprop)
                            elif int(cdb_type) == 999:
                                val = PropertyValue(smlrecord[sqlattr] +
                                                    smlrecord[sqlattr[:-2] + 'n'] +
                                                    smlrecord[sqlattr[:-2] + 'a2'],
                                                    property=myprop)
                            else:
                                val = PropertyValue(smlrecord[sqlattr], property=myprop)
                            result[pset_prop.prop_mk] = val
                except Exception:
                    excStr = " ".join(traceback.format_exception(*sys.exc_info()))
                    misc.log_error(("\n========\nscript exception:\n %s" % (excStr) + "\nraised in sml handling for part '%(teilenummer)s' '%(t_index)s'\n========\n" % part))
    return result


def BuildDescriptiveText(template, part, properties):
    """
    Process a `template` string. Replace all occurences of
    ``[modifier(propname)!expr|format]`` with the data of a property
    named `propname` in one of the dictionaries `properties` or
    `part`.
    """

    def replacer(match):
        def appropriate_format(pval):
            if fmt:
                return fmt
            if isinstance(pval, float):
                return "%f"
            return "%s"

        def normalized(prop):
            x = prop.normalized[0]
            return x, appropriate_format(x)

        def asgiven(prop):
            x, u = prop.value
            return (x, u), "%s%%s" % appropriate_format(x)

        MODIFIER_MAP = {
            'normalized': normalized,
            'asgiven': asgiven,
        }

        # Grep elements from the match object.
        field = match.groupdict().get('property')
        fmt = match.groupdict().get('format')
        modifier = MODIFIER_MAP.get(match.groupdict().get('modifier'), normalized)
        expr = match.groupdict("prop").get('expr')
        # We expect to find the named field either in 'properties'
        # (first) or in 'part'. Otherwise we flag an error by
        # replacing '[field?]'
        if field in properties:
            prop = properties.get(field)
        elif field in part:
            prop = part.get(field)
        else:
            return "[%s?]" % field

        if is_pq(prop):
            prop, fmt = modifier(prop)
        pval = eval(expr)
        fmt = appropriate_format(pval)
        replacement = fmt % pval
        if not replacement or pval is None:
            replacement = "?"

        # if value is float, drop trailing zeros (E049563)
        if (
            isinstance(pval, numbers.Number) or
            (isinstance(pval, PropertyValue) and isinstance(pval.value, numbers.Number))
        ):
            replacement = re.sub("(?:\.0*|0*)$", "", replacement)

        return replacement

    # Sloppily match the syntax [modifier(property)!expr|format] by a
    # more-or-less simple regular expression.
    return re.sub(r"\["
                  r"((?P<modifier>\w+)\()?"
                  r"(?P<property>\w+)"
                  r"\)?"
                  r"(!(?P<expr>[^|]+))?"
                  r"(\|(?P<format>[^\]]*))?"
                  r"\]",
                  replacer, template)

# A cache for propsets.
__PROPSETS = RecordSetCache("cdbsml_propset")


def AddDescriptiveText(part, attribute):
    """
    Apply `BuildDescriptiveText` to `part` and update part's `attribute`
    with the result. `part` should be an updatable of type `cdb.sqlapi.Record`.
    The function retrieves the template to generate the description
    from the part's property set (``part.sachgruppe``).
    """
    pset = __PROPSETS.get(condition="pset_id='%s'" % part.sachgruppe)
    text = None
    if pset:
        pset = pset[0]
        textrule = pset.textrule
        if textrule:
            properties = LoadProperties(part)
            text = BuildDescriptiveText(textrule, part, properties)
            ti = util.tables["teile_stamm"]
            text = text[:ti.column(attribute).length()]
            updates = {attribute: text}
            part.update(**updates)
    return text


# Liefert ein Tupel aus Vorkomma und Nachkommastellen
def _getDigitCount(value):
    integer_digits = -1
    fractional_digits = -1
    if isinstance(value, str):
        value = value.strip()
        if value.find("e") != -1:
            # Exponentialdarstellung - dann wandeln wir in float
            return _getDigitCount(float(value))
        else:
            # Führende Nullen und Vorzeichen und Leerzeichen weg
            value = value.lstrip("0+- ")
            dotpos = value.find(".")
            if dotpos == -1:
                integer_digits = len(value)
                fractional_digits = 0
            else:
                integer_digits = dotpos
                fractional_digits = len(value) - (dotpos + 1)

    elif type(value) == int:
        integer_digits = len(str(value).lstrip("-"))
        fractional_digits = 0

    elif type(value) == float:
        # Wg. der Rundungs(un)-genauigkeiten solange floats erzeugen, bis es
        # passt. Genau geht es nicht, daher ein Delta angeben, ab dem es ok ist
        allowed_difference = 0.0000000001
        integer_digits = len(str(int(value)).lstrip("-"))

        precision = 0
        precision_str = "%%.%df" % precision
        for precision in range(0, 12):
            precision_str = "%%.%df" % precision
            str_val = precision_str % (value)
            if abs(float(str_val) - value) < allowed_difference:
                break
        fractional_digits = precision
    else:
        # Wenn das nichts von alledem ist, in Strings wandeln
        return _getDigitCount(str(value))

    return (integer_digits, fractional_digits)


# TODO: Rausnehmen und durch Data-Dictionary automatisch durchführen lassen
def checkPropertyFormat(item, generic_group="", property=""):
    """
    Checks, whether the subject characteristic property values of `item` are
    correct. `item` is the classified part that contains the property values to
    be checked. If a value can't be accessed it will not be
    checked. `generic_group` is the subject characteristic that contains the
    definition of the properties. If it is empty it will be retrieved from
    `item`. If the parameter `property` is empty all numeric properties will be
    checked - if it contains an database attribute, only this attribute will be
    checked.

    The function returns a list of internationalized error messages or an empty
    list, if all checks has been successful.
    """
    from cdb.platform.mom import entities
    errmsg = []
    try:
        if not generic_group:
            generic_group = item["sachgruppe"]
        prop_txt = "all properties"
        if property:
            prop_txt = "property '%s'" % property
        misc.log(0, "Checking characteristics groups '%s' characteristic format for %s" % (generic_group, prop_txt))

        # Die Merkmale ermitteln
        pset_props = __CDBSML_PSET_PROP.get(condition="pset_id='%s'" % generic_group)
        for pset_prop in pset_props:
            try:
                myprop = __CDBSML_PROPERTY.get(condition="prop_id='%s'" % pset_prop.prop_id)[0]
                if myprop:
                    # Wir überprüfen erst mal nur Zahlfelder
                    if myprop.din4001_mm_dt == "Z":
                        vorkomma = myprop["din4001_mm_v1"]
                        nachkomma = myprop["din4001_mm_n1"]
                        if (vorkomma is not None) or (nachkomma is not None):
                            # Es ist was zu prüfen
                            sqlattr = ""
                            attrdef = getAttributeDefByUUID(pset_prop.dd_attr_uuid)
                            if attrdef:
                                sqlattrs = attrdef.getSQLSelectNames()
                                if sqlattrs:
                                    sqlattr = sqlattrs[0]
                            val = None
                            if sqlattr and not property or property == sqlattr:
                                # Den für den Artikel gültigen Identifier
                                # suchen
                                partcldef = entities.CDBClassDef("part")
                                sgrattrdef = partcldef.getAttributeDefinition("sachgruppe")
                                attrid = partcldef.getFacetAttrIdentifier(sgrattrdef, attrdef)
                                # Hack - die Identifier stimmen noch nicht
                                #        zwingend mit dem Kontextadapter
                                #        uberein, daher ggf. die Relation
                                #        rausnehmen
                                try:
                                    val = item[attrid]
                                except Exception:
                                    if attrid[:12] == "teile_stamm.":
                                        attrid = attrid[12:]
                                        val = item[attrid]
                                    else:
                                        raise

                            if val and val is not None:
                                vk, nk = _getDigitCount(val)
                                if (vorkomma is not None) and vk > vorkomma:
                                    m = gui.Message.GetMessage("sml_format_vk", attrdef.getLabel(), vorkomma)
                                    misc.log(0, m)
                                    errmsg.append(m)

                                if (nachkomma is not None) and nk > nachkomma:
                                    m = gui.Message.GetMessage("sml_format_nk", attrdef.getLabel(), nachkomma)
                                    misc.log(0, m)
                                    errmsg.append(m)

            except Exception as e:
                misc.log_error("checkPropertyFormat: Ignore Exception %s" % str(e))
    except Exception:
        pass
    return errmsg


def check_pset_id(pset_id):
    """
    Check, whether pset_id exists in cdbsml_cgroup or cdbsml_propset and raises an
    ue.Exception, if pset_id exists
    """
    from cdb import ue
    aCGroupRecordSet = sqlapi.RecordSet2("cdbsml_cgroup", "cgroup_id='%s'" % sqlapi.quote(pset_id))
    aPropSetRecordSet = sqlapi.RecordSet2("cdbsml_propset", "pset_id='%s'" % sqlapi.quote(pset_id))

    if len(aCGroupRecordSet) > 0:
        raise ue.Exception("cdbsml_invalid_key", util.get_label("cdbsml_cgroup"), pset_id)
    if len(aPropSetRecordSet) > 0:
        raise ue.Exception("cdbsml_invalid_key", util.get_label("cdbsml_propset"), pset_id)


def getFQSMLAttrIdentifier(pset_id, prop_id):
    """
    Retrieves an identifier that identifies the property within a
    `cdb.mom.CDBObjectHandle`. The function returns ``None`` if there is no
    property with the identification `prop_id` within the class list of characteristics
    `pset_id`. Note that `prop_id` is the value of `cdbsml_pset_prop.prop_mk`.
    You can use this identifier if you set a value within a user exit, e.g.
    if you call `cdb._ctx.cdbserver.Context.set`.
    """
    from cdb.platform.mom import entities
    from cs.vp import classification
    result = None

    prop = classification.PropertyReference.ByKeys(pset_id, prop_id)
    if prop:
        dd_field = prop.DDField
        if dd_field:
            partcldef = entities.CDBClassDef("part")
            sc_cldef = entities.CDBClassDef(dd_field.classname)
            sgr_attrdef = partcldef.getAttributeDefinition("sachgruppe")
            prop_attrdef = sc_cldef.getAttributeDefinition(dd_field.field_name)
            result = partcldef.getFacetAttrIdentifier(sgr_attrdef, prop_attrdef)
    return result


def getSMLAttrIdentifier(pset_id, prop_id):
    """
    Retrieve an identifier that can be used to
    access the property `prop_id` of the
    subject characteristic `pset_id` within context
    adaptor objects like `ctx.dialog`.
    The function returns ``None`` if there is no
    property with the identification
    `prop_id` within the class list of characteristics `pset_id`.
    Note that `prop_id` is the value of `cdbsml_pset_prop.prop_mk`.
    """
    result = getFQSMLAttrIdentifier(pset_id, prop_id)
    if result and result[:12] == "teile_stamm.":
        result = result[12:]
    return result


if __name__ == '__main__':
    if "print" in sys.argv:
        myroot = cgroup_hierarchy()
        cgroup_print(myroot)
    if "propcat" in sys.argv:
        b = CatDecompBuilder()
        b()
    if "clear" in sys.argv:
        ClearSMLConfigSchema()
