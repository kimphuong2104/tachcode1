# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
The module provides complex database objects
"""


from cdb import sqlapi
from cdb.platform.acs import OrgContext
from cdb.platform.mom.fields import DDField, DDMultiLangFieldBase

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


def get_collation():
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault

        collate = f" COLLATE {CollationDefault.get_default_collation()} "
    else:
        collate = ""
    return collate


def _generate_select(attr, prefix, classname, attrname, fallback=""):
    """
    Generates a part of a view definition for multilingual display of responsible.
    :param attr: multi language attribute of ``cdb_global_role``
    :param prefix: attribute prefix that has to be used in the view
    :param classname: used to retrieve the data
    :param attrname: used to retrieve the data
                     If it is a multi language attribute, the languages of
                     `attrname` are mapped to the languages of `attr`.
    :param fallback: used as attribute, if no target is given with `classname` and `attrname`
    :return: type unicode
    """
    result = ""
    ml_field = DDMultiLangFieldBase.ByKeys(classname="cdb_global_role", field_name=attr)
    target_field = None
    if attrname:
        target_field = DDField.ByKeys(classname=classname, field_name=attrname)

    for lang_def in ml_field.LangFields:
        iso_lang = lang_def.cdb_iso_language_code
        fld = fallback
        if target_field:
            if isinstance(target_field, DDMultiLangFieldBase):
                fld = "''"
                # Find the specific language
                for lang_field in target_field.LangFields:
                    if lang_field.cdb_iso_language_code == iso_lang:
                        fld = lang_field.field_name
                        break
            else:
                fld = target_field.field_name

        result += f", {fld} AS {prefix}{iso_lang}"
    return result


def generate_sharing_subjects_all():
    """
    Creates a view of all persons, common roles and roles of organizational contexts
    Multi language support does exist for Common Roles and PCS Roles.
    Multi languages support do not apply to persons. Names are not multilingual.
    Multiple languages for other contexts cannot be supported. Role catalog is not known.
    :return: type: unicode
    """
    # Multilanguage names of persons and common roles
    select_names_for_persons = _generate_select(
        "name", "subject_name_", "cdb_person", "name"
    )
    select_names_for_common_roles = _generate_select(
        "name", "subject_name_", "cdb_global_role", "name"
    )

    # Add ID and subject type of persons and common roles
    select_for_persons = f"""SELECT
                                personalnummer AS subject_id,
                                'Person' {get_collation()} AS subject_type,
                                active_account AS active
                                {select_names_for_persons}
                            FROM angestellter
                         """

    select_for_common_roles = f"""SELECT
                                     role_id  AS subject_id,
                                     'Common Role' {get_collation()} AS subject_type,
                                     '1' AS active
                                     {select_names_for_common_roles}
                                 FROM cdb_global_role
                              """

    # Add organizational contexts
    all_contexts = OrgContext.Query()

    select_for_pcs_roles = ""
    # Add ID and subject type of PCS Roles, if ProjectContext exists
    if "ProjectContext" in all_contexts.context_name:
        select_names_for_pcs_roles = _generate_select(
            "name", "subject_name_", "cdbpcs_role_def", "name_ml"
        )
        select_for_pcs_roles = f"""SELECT
                                      name AS subject_id,
                                      'PCS Role' {get_collation()} AS subject_type,
                                      '1' AS active
                                      {select_names_for_pcs_roles}
                                  FROM cdbpcs_role_def
                                """

    # Basic statement of other contexts
    select_names_for_other_context = _generate_select(
        "name", "subject_name_", None, None, "role_id"
    )
    select_for_other_context = f"""SELECT
                                      DISTINCT role_id AS subject_id,
                                      '%s' {get_collation()} AS subject_type,
                                      '1' AS active
                                      {select_names_for_other_context}
                                  FROM %s
                               """

    # Add ID and subject type of Other Roles
    select_for_all_contexts = []
    for context in all_contexts:
        if context.context_name in ("GlobalContext", "ProjectContext"):
            # Contexts have already been processed
            continue
        select_for_all_contexts.append(
            select_for_other_context % (context.role_identifier, context.role_relation)
        )

    context_statement = ""
    if select_for_all_contexts:
        context_statement = f" UNION {' UNION '.join(select_for_all_contexts)}"

    statement = (
        f"{select_for_persons} UNION {select_for_common_roles} "
        f"UNION {select_for_pcs_roles} {context_statement}"
    )

    return statement
