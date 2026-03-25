# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module schema

This is the documentation for the schema module.
"""


from cdb import ddl
from cdb import sqlapi
from cdb.platform.mom.fields import DDField
from cdb.platform.mom.fields import DDMultiLangFieldBase


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


def get_collation():
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault
        collate = " COLLATE %s " % CollationDefault.get_default_collation()
    else:
        collate = ""
    return collate


def _generate_select(attr, prefix, classname, attrname, fallback=''):
    """
    Generates a part of a view definition for multilingual display of subjects.
    :param attr: multi language attribute of ``cdb_global_role``
    :param prefix: attribute prefix that has to be used in the view
    :param classname: used to retrieve the data
    :param attrname: used to retrieve the data
                     If it is a multi language attribute, the languages of `attrname` are mapped to the
                     languages of `attr`.
    :param fallback: used as attribute, if no target is given with `classname` and `attrname`
    :rtype: basestring
    """
    result = ""
    ml_field = DDMultiLangFieldBase.ByKeys("cdb_global_role", attr)
    target_field = None
    if attrname:
        target_field = DDField.ByKeys(classname, attrname)

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

        result += ", %s AS %s%s\n" % (fld, prefix, iso_lang)
    return result


def _generate_persons_for_subject():
    """
    Generates a part of a view definition for multilingual display of persons.
    Note: System accounts are being filtered out
    :rtype: basestring
    """
    select_names_for_persons = _generate_select("name",
                                                "subject_name_",
                                                "cdb_person",
                                                "name")
    select_descriptions_for_persons = _generate_select("name",
                                                       "description_",
                                                       "cdb_person",
                                                       "name")

    select_for_persons = """SELECT
                                personalnummer AS subject_id,
                                'Person' {} AS subject_type,
                                1 AS ranking,
                                active_account AS active,
                                visibility_flag AS preselection
                                {}
                                {}
                            FROM
                                angestellter
                            WHERE
                                is_system_account = 0
                         """.format(get_collation(),
                                    select_names_for_persons,
                                    select_descriptions_for_persons)
    return select_for_persons


def _generate_common_roles_for_subjects():
    """
    Generates a part of a view definition for multilingual display of common roles
    :rtype: basestring
    """

    select_names_for_common_roles = _generate_select("name",
                                                     "subject_name_",
                                                     "cdb_global_role",
                                                     "name")
    select_description_for_common_roles = _generate_select("name",
                                                           "description_",
                                                           "cdb_global_role",
                                                           "description")

    select_for_common_roles = """SELECT
                                     role_id  AS subject_id,
                                     'Common Role' {} AS subject_type,
                                     3 AS ranking,
                                     '1' AS active,
                                     is_org_role AS preselection
                                     {}
                                     {}
                                 FROM cdb_global_role
                              """.format(get_collation(),
                                         select_names_for_common_roles,
                                         select_description_for_common_roles)

    return select_for_common_roles


def _generate_project_roles_for_subjects():
    """
    Generates a part of a view definition for multilingual display of project roles.
    if database table of the project role catalog (cdbpcs_role_def) exists
    :rtype: basestring
    """
    db_table_name = "cdbpcs_role_def"
    if not ddl.Table(db_table_name).exists():
        return ""

    select_names_for_project_roles = _generate_select("name",
                                                      "subject_name_",
                                                      db_table_name,
                                                      "name_ml")
    select_description_for_project_roles = _generate_select("name",
                                                           "description_",
                                                           db_table_name,
                                                           "description_ml")

    select_for_project_roles = """SELECT
                                      name AS subject_id,
                                      'PCS Role' {} AS subject_type,
                                      2 AS ranking,
                                      '1' AS active,
                                      CASE
                                          WHEN obsolete > 0 THEN 0
                                          ELSE 1
                                      END AS preselection
                                       {}
                                      {}
                                  FROM {}
                                  """.format(get_collation(),
                                             select_names_for_project_roles,
                                             select_description_for_project_roles,
                                             db_table_name)

    return select_for_project_roles


def generate_task_board_subjects():
    """
    Creates a view of all persons, common roles and project roles
    Multi language support does exist for Common Roles and PCS Roles.
    Multi languages support do not apply to persons. Names are not multilingual.
    Selected field notes:
    - ranking: default sorting by sibject type
    - active: property of persons only, always true for roles
    - preselection: based on
      - persons.visibility_flag,
      - cdb_global_role.is_org_role
      - cdbpcs_role_def.obsolete (this value has been inverted: True if greater than 0, else False)
    :rtype: basestring
    """
    select_for_persons = _generate_persons_for_subject()
    select_for_common_roles = _generate_common_roles_for_subjects()
    select_for_project_roles = _generate_project_roles_for_subjects()

    statement = "{} UNION {}".format(
        select_for_persons,
        select_for_common_roles
    )

    if select_for_project_roles:
        statement = "{} UNION {}".format(
            statement,
            select_for_project_roles
        )

    return statement
