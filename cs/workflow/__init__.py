#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module wfm

This is the documentation for the wfm module.
"""

from cdb import sqlapi
from cdb.ddl import Table

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def get_collation():
    """
    :returns: Collate statement for use with constant values in MS SQL
    :rtype: str
    """
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault

        return " COLLATE {} ".format(CollationDefault.get_default_collation())
    return ""


def get_cdbwf_resp_browser_schema():
    """
    :returns: Columns used in view cdbwf_resp_browser
    :rtype: list
    """
    table_view = Table("cdbwf_resp_browser")
    return [column.colname for column in table_view.reflect()]


def _retrieve_languages(classname, field_name):
    # It seems to be a problem to access the cdb.objects
    # classes at the very first time by using something like
    # CommonRole.name.getLanguageFields().keys()
    from cdb.platform.mom.fields import DDMultiLangFieldBase
    ml_field = DDMultiLangFieldBase.ByKeys(classname, field_name)
    if ml_field:
        return [fld.cdb_iso_language_code for fld in ml_field.LangFields]
    else:
        return []


def _generate_select(
    iso_langs, view_attr, src_classname, src_attrname, src_alias, fallback=u"''"
):
    """
    :param isolangs:
      The ISO language codes for the attributes to generate
    :param view_attr:
      The name of the multilanguage attribute in the view.
    :param src_classname:
      The name of the class where the data is retrieved
    :param src_attrname:
      The name of the attribute where the data is retrieved
    :src_alias:
      The alias name of the source class in the view
    :fallback:
      Value that is used if there is no attribute for an iso lang
      in the source
    """
    from cdb.platform.mom.fields import DDField, DDMultiLangFieldBase

    alias = "{}.".format(src_alias) if src_alias else ""
    result = []
    target_field = None
    if src_attrname:
        target_field = DDField.ByKeys(src_classname, src_attrname)
    for iso_lang in iso_langs:
        fld = None
        if target_field:
            if isinstance(target_field, DDMultiLangFieldBase):
                language_fields = target_field.LangFields
                language_fields_iso_code = language_fields.cdb_iso_language_code
                language_fields_names = language_fields.field_name
                # Find the specific language
                if iso_lang in language_fields_iso_code:
                    fld = language_fields_names[
                        language_fields_iso_code.index(iso_lang)
                    ]
            else:
                fld = target_field.field_name  # noqa: F812

        result.append((fld, iso_lang))
    return u"".join(
        [
            ", {} AS {}_{}".format(
                "{}{}".format(alias, fld) if fld else fallback, view_attr, lang
            )
            for fld, lang in result  # noqa: F812
        ]
    )


def generate_cdbwf_resp_browser():
    """
    :returns: Select statement to generate cdbwf_resp_browser, containing
        persons and roles to take on responsibilities in workflows.
    :rtype: str
    """
    collation = get_collation()
    t = Table("cdbpcs_prj_role")

    global_role_langs = _retrieve_languages("cdb_global_role", "name")
    global_descr_langs = _retrieve_languages("cdb_global_role", "description_ml")
    proj_role_langs = _retrieve_languages("cdbpcs_role_def", "name_ml")
    proj_desc_langs = _retrieve_languages("cdbpcs_role_def", "description_ml")

    if t.exists():
        role_langs = list(set(global_role_langs).intersection(proj_role_langs))
        descr_langs = list(set(global_descr_langs).intersection(proj_desc_langs))
    else:
        role_langs = global_role_langs
        descr_langs = global_descr_langs

    select_global_name = _generate_select(
        role_langs, "subject_name", "cdb_global_role", "name", "gr"
    )
    select_angestellter_name = _generate_select(
        role_langs, "subject_name", "cdb_person", "name", "angestellter"
    )
    select_pcs_name = _generate_select(
        role_langs, "subject_name", "cdbpcs_role_def", "name_ml", "rdef"
    )

    select_global_descr = _generate_select(
        descr_langs, "description", "cdb_global_role", "description_ml", "gr"
    )
    select_angestellter_descr = _generate_select(
        descr_langs, "description", "cdb_person", "name", "angestellter"
    )
    select_pcs_descr = _generate_select(
        descr_langs, "description", "cdbpcs_role_def", "description_ml", "rdef"
    )

    STATIC_ANGESTELLTER = """
        SELECT 
            angestellter.personalnummer AS subject_id
            {select_angestellter_descr},
            'Person' {collation} AS subject_type
            {select_angestellter_name},
            '' {collation} AS cdb_project_id,
            1 AS order_by
        FROM angestellter
        WHERE 
            active_account='1'
            AND visibility_flag=1
            AND (is_system_account=0 OR is_system_account IS NULL)""".format(
                collation=collation,
                select_angestellter_descr=select_angestellter_descr,
                select_angestellter_name=select_angestellter_name)

    STATIC_GLOBAL = """
        UNION SELECT 
            gr.role_id  AS subject_id
            {select_global_descr},
            'Common Role' {collation} AS subject_type
            {select_global_name},
            '' {collation} AS cdb_project_id,
            2 AS order_by
        FROM cdb_global_role gr 
        WHERE is_org_role = 1 """.format(
            collation=collation,
            select_global_descr=select_global_descr,
            select_global_name=select_global_name)

    STATIC_PCS = """
        UNION SELECT 
            prj_role.role_id AS subject_id
            {select_pcs_descr},
            'PCS Role' {collation} AS subject_type
            {select_pcs_name},
            prj_role.cdb_project_id AS cdb_project_id,
            3 AS order_by
        FROM 
            cdbpcs_role_def rdef, cdbpcs_prj_role prj_role
        WHERE 
            prj_role.role_id=rdef.name """.format(collation=collation,
                                                  select_pcs_descr=select_pcs_descr,
                                                  select_pcs_name=select_pcs_name)

    PARTS = [STATIC_ANGESTELLTER, STATIC_GLOBAL]
    if t.exists():
        PARTS += [STATIC_PCS]
    return " ".join(PARTS)


def generate_cdbwf_resp_mapping():
    """
    :returns: Select statement to generate cdbwf_resp_mapping, containing
        internationalized names for potential responsible persons and roles.
    :rtype: str
    """
    collation = get_collation()
    t = Table("cdbpcs_prj_role")

    global_role_langs = _retrieve_languages("cdb_global_role", "name")
    proj_role_langs = _retrieve_languages("cdbpcs_role_def", "name_ml")

    if t.exists():
        role_langs = list(set(global_role_langs).intersection(proj_role_langs))
    else:
        role_langs = global_role_langs

    select_angestellter = _generate_select(role_langs, "subject_name", "cdb_person", "name", "angestellter")
    select_global = _generate_select(role_langs, "subject_name", "cdb_global_role", "name", "gr")
    select_pcs = _generate_select(role_langs, "subject_name", "cdbpcs_role_def", "name_ml", "rdef")

    STATIC_ANGESTELLTER = """
        SELECT 
            angestellter.personalnummer AS subject_id,
            'Person' {collation} AS subject_type
            {select_angestellter}
        FROM angestellter""".format(
            collation=collation, select_angestellter=select_angestellter)

    STATIC_GLOBAL = """
        UNION SELECT 
            gr.role_id  AS subject_id,
            'Common Role' {collation} AS subject_type
            {select_global} 
        FROM cdb_global_role gr""".format(collation=collation, select_global=select_global)

    STATIC_PCS = """
        UNION SELECT 
            rdef.name AS subject_id,
            'PCS Role' {collation} AS subject_type
            {select_pcs} 
        FROM 
            cdbpcs_role_def rdef""".format(collation=collation, select_pcs=select_pcs)

    PARTS = [STATIC_ANGESTELLTER, STATIC_GLOBAL]
    if t.exists():
        PARTS += [STATIC_PCS]
    return " ".join(PARTS)
