# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
from __future__ import absolute_import
from cdb import sqlapi
from cdb.ddl import Table
from cdb.objects import ViewObject
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import CDBCatalogContent
from cdb.platform.mom import CDBObjectHandle
from cdb.platform.mom import SimpleArgument
from cdb.platform.mom import SimpleArgumentList
from cdb.typeconversion import to_untyped_c_api

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class ResponsibleBrowser(ViewObject):
    """Only for query.
    """
    __classname__ = "cdbpco_resp_browser"
    __maps_to__ = "cdbpco_resp_browser"


def get_collation():
    """
    :returns: Collate statement for use with constant values in MS SQL
    :rtype: str
    """
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault
        return " COLLATE {} ".format(CollationDefault.get_default_collation())
    return ""


def get_cdbpco_resp_browser_schema():
    """
    :returns: Columns used in view cdbpco_resp_browser
    :rtype: list
    """
    iso = [
        "de",
        "en",
        "cs",
        "es",
        "fr",
        "it",
        "ja",
        "ko",
        "pl",
        "pt",
        "tr",
        "zh",
    ]
    return (
        ["subject_id"] +
        ["description_{}".format(x) for x in iso] +
        ["subject_type"] +
        ["subject_name_{}".format(x) for x in iso] +
        ["cdb_project_id", "order_by"])


def generate_cdbpco_resp_browser():
    """
    :returns: Select statement to generate cdbpco_resp_browser, containing
        persons and roles to take on responsibilities in calculations.
    :rtype: str
    """
    collation = get_collation()

    def _retrieve_languages(classname, field_name):
        # It seems to be a problem to access the cdb.objects
        # classes at the very first time by using something like
        # CommonRole.name.getLanguageFields().keys()
        from cdb.platform.mom.fields import DDMultiLangFieldBase
        ml_field = DDMultiLangFieldBase.ByKeys(classname, field_name)
        return [fld.cdb_iso_language_code for fld in ml_field.LangFields]

    def _generate_select(iso_langs,
                         view_attr,
                         src_classname, src_attrname, src_alias,
                         fallback=u"''"):
        """
        :param isolangs:
          The ISO language codes for the attributes to generate
        :param view_attr:
          The name of the multilanguage attribute in the view.
        :param src_classname:
          The name of the class where the data is retrieved
        :param src_attrame:
          The name of the attribute where the data is retrieved
        :src_alias:
          The alias name of the source class in the view
        :fallback:
          Value that is used if there is no attribute for an iso lang
          in the source
        """
        from cdb.platform.mom.fields import DDField, DDMultiLangFieldBase
        if src_alias:
            src_alias += "."
        result = ""
        target_field = None
        if src_attrname:
            target_field = DDField.ByKeys(src_classname, src_attrname)

        for iso_lang in iso_langs:
            fld = fallback
            if target_field:
                if isinstance(target_field, DDMultiLangFieldBase):
                    fld = "''"
                    # Find the specific language
                    for lang_field in target_field.LangFields:
                        if lang_field.cdb_iso_language_code == iso_lang:
                            fld = src_alias + lang_field.field_name
                            break
                else:
                    fld = src_alias + target_field.field_name

            result += ", %s AS %s%s" % (fld, view_attr, iso_lang)
        return result

    global_role_langs = _retrieve_languages("cdb_global_role", "name")
    global_descr_langs = _retrieve_languages("cdb_global_role", "description_ml")
    proj_role_langs = _retrieve_languages("cdbpcs_role_def", "name_ml")
    proj_desc_langs = _retrieve_languages("cdbpcs_role_def", "description_ml")

    role_langs = list(set(global_role_langs).intersection(proj_role_langs))
    descr_langs = list(set(global_descr_langs).intersection(proj_desc_langs))

    select_global = _generate_select(role_langs, "subject_name_",
                                     "cdb_global_role", "name", "gr")
    select_angestellter = _generate_select(role_langs, "subject_name_",
                                            "cdb_person", "name", "angestellter")
    select_pcs = _generate_select(role_langs, "subject_name_",
                                  "cdbpcs_role_def", "name_ml", "rdef")

    select_global += _generate_select(descr_langs, "description_ml_",
                                      "cdb_global_role", "description_ml",
                                      "gr")
    select_angestellter += _generate_select(descr_langs,
                                            "description_ml_",
                                            "cdb_person", "name", "angestellter")
    select_pcs += _generate_select(descr_langs, "description_ml_",
                                   "cdbpcs_role_def",
                                   "description_ml",
                                   "rdef")

    STATIC_ANGESTELLTER = ("SELECT angestellter.personalnummer AS subject_id, "
                           " 'Person' {collation} AS subject_type, "
                           " '' {collation} AS cdb_project_id, "
                           " 1 AS order_by "
                           " {select_angestellter} FROM angestellter "
                           " WHERE (angestellter.cdb_classname = "
                           " 'angestellter') "
                           " AND active_account='1'"
                           " AND visibility_flag=1 "
                           " AND (is_system_account=0 OR is_system_account IS NULL)".format(collation=collation,
                                                                                            select_angestellter=select_angestellter))
    STATIC_GLOBAL = (" UNION SELECT gr.role_id  AS subject_id, "
                     " 'Common Role' {collation} AS subject_type, "
                     " '' {collation} AS cdb_project_id, "
                     " 2 AS order_by "
                     " {select_global} FROM cdb_global_role gr ".format(collation=collation,
                                                                        select_global=select_global))
    STATIC_PCS = (" UNION SELECT rdef.name AS subject_id, "
                  " 'PCS Role' {collation} AS subject_type, "
                  " prj_role.cdb_project_id AS cdb_project_id,"
                  " 3 AS order_by "
                  " {select_pcs} FROM cdbpcs_role_def rdef, cdbpcs_prj_role prj_role "
                  " WHERE prj_role.role_id=rdef.name ".format(collation=collation,
                                                              select_pcs=select_pcs))

    t = Table('cdbpcs_prj_role')
    return "{} {} {}".format(STATIC_ANGESTELLTER, STATIC_GLOBAL, STATIC_PCS) \
        if t.exists() else "{} {}".format(STATIC_ANGESTELLTER, STATIC_GLOBAL)


class CatalogCalcResponsibleData(CDBCatalogContent):
    def __init__(self, cdb_project_id, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()

        if self.cdef:
            tabdef = self.cdef.getProjection(tabdefname, True)
        else:
            tabdef = tabdefname

        CDBCatalogContent.__init__(self, tabdef)
        self.cdb_project_id = cdb_project_id
        self.data = None

    def _initData(self, refresh=False):
        if not self.data or refresh:
            condition = self.getSQLCondition()
            self.data = sqlapi.RecordSet2("cdbpco_resp_browser",
                                          "{}".format(condition),
                                          addtl=" ORDER BY order_by")

    def onSearchChanged(self):
        self._initData(True)

    def refresh(self):
        self._initData(True)

    def getNumberOfRows(self):
        self._initData()
        return len(self.data)

    def getRowObject(self, row):
        if not self.cdef:
            return CDBCatalogContent.getRowObject(self, row)

        else:
            self._initData()
            keys = SimpleArgumentList()

            for keyname in self.cdef.getKeyNames():
                keys.append(SimpleArgument(keyname, self.data[row][keyname]))

            return CDBObjectHandle(self.cdef, keys, False, True)

    def _get_value(self, rec, attr):
        "Retrieves the value of `attr` from the record `rec`"
        result = u""

        if self.cdef:
            adef = self.cdef.getAttributeDefinition(attr)

            for db_name in adef.getSQLSelectNames():
                result = rec[db_name]

                if result:
                    break
        else:
            result = rec[attr]

        return to_untyped_c_api(result)

    def getRowData(self, row):
        self._initData()
        result = []
        tdef = self.getTabDefinition()

        for col in tdef.getColumns():
            attr = col.getAttribute()
            value = u""

            try:
                obj = self.data[row]
                value = self._get_value(obj, attr)
                if not value:
                    value = u""

            except Exception:
                value = u""

            result.append(value)

        return result


class CatalogCalcResponsible(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        # if the project is known, we fill the catalog on our own
        cdb_project_id = ""
        try:
            cdb_project_id = self.getInvokingDlgValue("cdb_project_id")
        except Exception:
            pass

        if cdb_project_id:
            self.setResultData(CatalogCalcResponsibleData(cdb_project_id, self))
