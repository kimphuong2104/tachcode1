# -*- mode: python; coding: utf-8 -*-

#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module classes

This is the documentation for the classes module.
"""

import logging
import sys

from collections import namedtuple

from cdb import cdbuuid, sqlapi
from cdb import ue
from cdb import util
from cdb import i18n
from cdb import ElementsError
from cdbwrapc import CDBClassDef

from cdb.platform import gui
from cdb.platform.olc import StateDefinition

from cdb.objects import ByID
from cdb.objects import references
from cdb.objects import expressions
from cdb.objects import objectlifecycle
from cdb.objects.core import Object
from cdb.objects.typeselector import TypeSelector
from cdb.transactions import Transaction

from cs.classification import applicability
from cs.classification import catalog
from cs.classification import computations
from cs.classification import tools
from cs.classification.pattern import Pattern

from cs.documents import Document

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

fClassificationClass = expressions.Forward("cs.classification.classes.ClassificationClass")
fClassProperty = expressions.Forward("cs.classification.classes.ClassProperty")
fClassPropertyGroup = expressions.Forward("cs.classification.classes.ClassPropertyGroup")
fPropertyValue = expressions.Forward("cs.classification.catalog.PropertyValue")
fConstraint = expressions.Forward("cs.classification.constraints.Constraint")
fObjectReferenceClassProperty = expressions.Forward("cs.classification.classes.ObjectReferenceClassProperty")
fClassificationApplicability = expressions.Forward("cs.classification.applicability.ClassificationApplicability")
fClassificationReferenceApplicability = expressions.Forward(
    "cs.classification.applicability.ClassificationReferenceApplicability")
fRule = expressions.Forward("cs.classification.rules.Rule")
fBlockPropertyAssignment = expressions.Forward("cs.classification.catalog.BlockPropertyAssignment")
fBlockClassProperty = expressions.Forward("cs.classification.classes.BlockClassProperty")
fModelAssignment = expressions.Forward("cs.classification.classes.ModelAssignment")

LOG = logging.getLogger(__name__)

class ClassificationClass(Object):
    __maps_to__ = "cs_classification_class"
    __classname__ = "cs_classification_class"

    Applicabilities = references.Reference_N(
        fClassificationApplicability,
        fClassificationApplicability.classification_class_id == fClassificationClass.cdb_object_id
    )

    Parent = references.Reference_1(
        fClassificationClass,
        fClassificationClass.cdb_object_id == fClassificationClass.parent_class_id
    )

    def _get_all_parents(self):
        return ClassificationClass.get_base_classes(class_ids=[self.cdb_object_id])

    AllParents = references.Reference_Methods(fClassificationClass, _get_all_parents)

    Children = references.Reference_N(
        fClassificationClass,
        fClassificationClass.parent_class_id == fClassificationClass.cdb_object_id
    )

    Constraints = references.Reference_N(
        fConstraint,
        fConstraint.classification_class_id == fClassificationClass.cdb_object_id
    )

    OwnProperties = references.Reference_N(
        fClassProperty,
        fClassProperty.classification_class_id == fClassificationClass.cdb_object_id
    )

    def _allProperties(self):
        class_ids = [self.cdb_object_id] + ClassificationClass.get_base_class_ids(
            class_ids=[self.cdb_object_id]
        )
        return ClassProperty.KeywordQuery(classification_class_id=class_ids)

    Properties = references.ReferenceMethods_N(fClassProperty, _allProperties)

    PropertyGroups = references.Reference_N(
        fClassPropertyGroup,
        fClassPropertyGroup.classification_class_id == fClassificationClass.cdb_object_id
    )

    class EDIT(objectlifecycle.State):
        status = 0

    class RELEASED(objectlifecycle.State):
        status = 200

    class BLOCKED(objectlifecycle.State):
        status = 300

    def isActive(self):
        """ :return: True if the class can be used in the evaluation.

            In the default implementation this is the case, when the class
            has the status RELEASED. Customers can change this.
        """
        return self.status == self.RELEASED.status

    def is_applicable(self, dd_classname):
        return bool(ClassificationClass.get_applicable_classes(dd_classname, class_ids=[self.cdb_object_id]))

    def has_object_classifications(self):
        return ClassificationClass.has_class_object_classifications(class_ids=[self.cdb_object_id])

    def set_fields_readonly(self, ctx):
        ro_fields = ['code']
        for clazz in self.AllParents:
            if clazz.is_exclusive:
                ro_fields.append("is_exclusive")
                break
        ctx.set_fields_readonly(ro_fields)

    @classmethod
    def _use_dtag(cls):
        desciption_pattern = CDBClassDef(cls.__classname__).getObjDescriptionPattern()
        return "name" != desciption_pattern

    @classmethod
    def _create_class_where_condition(cls, class_ids=None, class_codes=None):
        if class_ids or class_codes:
            id_condition = tools.format_in_condition("cdb_object_id", class_ids)
            code_condition = tools.format_in_condition("code", class_codes)
            op = " OR " if id_condition and code_condition else ""
            return "{id_condition}{op}{code_condition}".format(
                id_condition=id_condition, op=op, code_condition=code_condition
            )
        else:
            raise ValueError("class_ids and or class_codes have to be given.")

    @classmethod
    def code_to_oid(cls, code):
        try:
            stmt = "select cdb_object_id from cs_classification_class where code = '{}'".format(code)
            return sqlapi.RecordSet2(sql=stmt)[0]['cdb_object_id']
        except Exception as ex:
            return ''

    @classmethod
    def codes_to_oid(cls, codes):
        result = {}
        try:
            sql_stmt = "select cdb_object_id, code from cs_classification_class where {}".format(
                tools.format_in_condition("code", codes)
            )
            for r in sqlapi.RecordSet2(sql=sql_stmt):
                result[r.code] = r.cdb_object_id
        except Exception as ex:
            LOG.exception(ex)
        return result

    @classmethod
    def oid_to_code(cls, oid):
        try:
            stmt = "select code from cs_classification_class where cdb_object_id = '{}'".format(oid)
            return sqlapi.RecordSet2(sql=stmt)[0]['code']
        except Exception as ex:
            return ''

    @classmethod
    def oids_to_code(cls, oids):
        result = {}
        if oids:
            try:
                sql_stmt = "select cdb_object_id, code from cs_classification_class where {}".format(
                    tools.format_in_condition("cdb_object_id", oids)
                )
                for r in sqlapi.RecordSet2(sql=sql_stmt):
                    result[r.cdb_object_id] = r.code
            except Exception as ex:
                LOG.exception(ex)
        return result

    @classmethod
    def get_access_rights(cls, dd_classname, class_ids=None, class_codes=None):
        try:
            cldef = CDBClassDef(dd_classname)
            class_names = [dd_classname] + list(cldef.getBaseClassNames())
        except ElementsError:
            return []

        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []

        sql_stmt = """
             WITH {recursive} class_hierarchy (cdb_object_id, parent_class_id, code) AS (
               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id, cs_classification_class.code
               FROM cs_classification_class
               WHERE {where_condition}

               UNION ALL

               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id, cs_classification_class.code
               FROM cs_classification_class, class_hierarchy
               WHERE cs_classification_class.cdb_object_id = class_hierarchy.parent_class_id
             )
             SELECT DISTINCT
                class_hierarchy.*, cs_classification_applicabilit.*
             FROM class_hierarchy
             LEFT JOIN cs_classification_applicabilit ON (
                class_hierarchy.cdb_object_id = cs_classification_applicabilit.classification_class_id AND
                cs_classification_applicabilit.is_active = 1 AND ({dd_classnames})
            )
        """.format(
            dd_classnames=tools.format_in_condition(
                "cs_classification_applicabilit.dd_classname", class_names
            ),
            recursive=tools.format_recursive(),
            where_condition=cls._create_class_where_condition(_class_ids, _class_codes)
        )
        access_info_by_class_id = {}
        for r in sqlapi.RecordSet2(sql=sql_stmt):
            access_rights = None
            if 1 == r.is_active:
                access_rights = (
                    r.write_access_obj, r.write_access_objclassification, r.olc_objclassification
                )
            access_info = access_info_by_class_id.get(r.cdb_object_id)
            use_new = True
            if access_info:
                for dd_class_name in class_names:
                    if dd_class_name == r.dd_classname:
                        # use settings for most special dd_class
                        break
                    elif dd_class_name == access_info["dd_classname"]:
                        # skip settings for more general dd_class
                        use_new = False
                        break
            if use_new:
                access_info_by_class_id[r.cdb_object_id] = {
                    "code": r.code,
                    "dd_classname": r.dd_classname,
                    "parent_class_id": r.parent_class_id,
                    "access_rights": access_rights
                }

        access_rights_by_code = {}
        for _, access_info in access_info_by_class_id.items():
            access_rights = access_info["access_rights"]
            if not access_rights:
                parent_class_id = access_info["parent_class_id"]
                while parent_class_id:
                    if parent_class_id not in access_info_by_class_id:
                        break
                    parent_class_access_info = access_info_by_class_id[parent_class_id]
                    if parent_class_access_info["access_rights"]:
                        access_rights = parent_class_access_info["access_rights"]
                        break
                    parent_class_id = parent_class_access_info["parent_class_id"]
            code = access_info["code"]
            parent_class_id = access_info["parent_class_id"]
            parent_code = access_info_by_class_id[parent_class_id]["code"] if parent_class_id else None
            access_rights_by_code[code] = {
                "code": code,
                "parent_class_code": parent_code,
                "parent_class_id": parent_class_id,
                "access_rights": access_rights
            }
        return access_rights_by_code

    @classmethod
    def get_copy_info(cls, dd_classname, class_ids=None, class_codes=None):
        try:
            cldef = CDBClassDef(dd_classname)
            class_names = [dd_classname] + list(cldef.getBaseClassNames())
        except ElementsError:
            return []

        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []

        if not _class_codes and not _class_ids:
            return {}

        sql_stmt = """
             WITH {recursive} class_hierarchy (cdb_object_id, parent_class_id, code) AS (
               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id, cs_classification_class.code
               FROM cs_classification_class
               WHERE {where_condition}

               UNION ALL

               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id, cs_classification_class.code
               FROM cs_classification_class, class_hierarchy
               WHERE cs_classification_class.cdb_object_id = class_hierarchy.parent_class_id
             )
             SELECT DISTINCT
                class_hierarchy.*, cs_classification_applicabilit.*
             FROM class_hierarchy
             LEFT JOIN cs_classification_applicabilit ON (
                class_hierarchy.cdb_object_id = cs_classification_applicabilit.classification_class_id AND
                cs_classification_applicabilit.is_active = 1 AND ({dd_classnames})
            )
        """.format(
            dd_classnames=tools.format_in_condition(
                "cs_classification_applicabilit.dd_classname", class_names
            ),
            recursive=tools.format_recursive(),
            where_condition=cls._create_class_where_condition(_class_ids, _class_codes)
        )
        copy_info_by_class_id = {}
        for r in sqlapi.RecordSet2(sql=sql_stmt):
            copy_classification = None
            if 1 == r.is_active:
                copy_classification = r.copy_classification

            copy_info = copy_info_by_class_id.get(r.cdb_object_id)
            use_new = True
            if copy_info:
                for dd_class_name in class_names:
                    if dd_class_name == r.dd_classname:
                        # use settings for most special dd_class
                        break
                    elif dd_class_name == copy_info["dd_classname"]:
                        # skip settings for more general dd_class
                        use_new = False
                        break
            if use_new:
                copy_info_by_class_id[r.cdb_object_id] = {
                    "code": r.code,
                    "dd_classname": r.dd_classname,
                    "parent_class_id": r.parent_class_id,
                    "copy_classification": copy_classification
                }

        copy_info_by_code = {}
        for _, copy_info in copy_info_by_class_id.items():
            copy_classification = copy_info["copy_classification"]
            if copy_classification is None:
                parent_class_id = copy_info["parent_class_id"]
                while parent_class_id:
                    if parent_class_id not in copy_info_by_class_id:
                        # copy in case of missing base class
                        copy_classification = 1
                        break
                    parent_class_copy_info = copy_info_by_class_id[parent_class_id]
                    if parent_class_copy_info["copy_classification"] is not None:
                        copy_classification = parent_class_copy_info["copy_classification"]
                        break
                    parent_class_id = parent_class_copy_info["parent_class_id"]
            copy_info_by_code[copy_info["code"]] = copy_classification

        return copy_info_by_code

    @classmethod
    def _get_applicable_classes(
        cls, dd_classname, where_condition, limit=-1,
        only_active=True, only_released=True, class_filter=None, include_base_classes=False, for_oplan=False
    ):  # pylint: disable=R0913
        """
        Get class infos for applicable classes.
        """

        def create_class_tree():
            try:
                cldef = CDBClassDef(dd_classname)
                class_names = [dd_classname] + list(cldef.getBaseClassNames())
            except ElementsError:
                return []

            sql_stmt = """
                 WITH {recursive} class_hierarchy (cdb_object_id, parent_class_id) AS (
                   SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id
                   FROM cs_classification_class
                   WHERE {where_condition}

                   UNION ALL

                   SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id
                   FROM cs_classification_class, class_hierarchy
                   WHERE cs_classification_class.cdb_object_id = class_hierarchy.parent_class_id
                 )
                 SELECT DISTINCT
                    cs_classification_applicabilit.is_active as is_applicable,
                    cs_classification_class.*
                 FROM class_hierarchy
                 JOIN cs_classification_class on class_hierarchy.cdb_object_id = cs_classification_class.cdb_object_id
                 LEFT JOIN cs_classification_applicabilit ON (
                    class_hierarchy.cdb_object_id = cs_classification_applicabilit.classification_class_id AND
                    ({dd_classnames}) {condition_active}
                )
            """.format(
                condition_active="AND cs_classification_applicabilit.is_active = 1" if only_active else "",
                dd_classnames=tools.format_in_condition(
                    "cs_classification_applicabilit.dd_classname", class_names
                ),
                recursive=tools.format_recursive(),
                where_condition=where_condition
            )

            classes_by_id = {}
            for r in sqlapi.RecordSet2(sql=sql_stmt):
                clazz = ClassificationClass()
                clazz._load_from_record(r, False) # pylint: disable=W0212
                classes_by_id[clazz.cdb_object_id] = {
                    'class': clazz,
                    'is_applicable': 1 if r['is_applicable'] else 0,
                    'is_exclusive': 1 if r['is_exclusive'] else 0,
                    'parent_class_ids': [],
                    'parent_class_codes': [],
                    'subclasses': []
                }

            class_tree = []
            root_class_ids = set()
            for clazz_id, class_info in classes_by_id.items():
                if class_info['class']['parent_class_id'] in classes_by_id:
                    parent_class_info = classes_by_id[class_info['class']['parent_class_id']]
                    parent_class_info['subclasses'].append(class_info)
                    parent_class = parent_class_info['class']
                    is_parent_applicable = 0
                    is_parent_exclusive = 0
                    while parent_class:
                        if 1 == parent_class_info['is_applicable']:
                            is_parent_applicable = 1
                        if 1 == parent_class_info['is_exclusive']:
                            is_parent_exclusive = 1
                        class_info['parent_class_ids'].insert(0, parent_class['cdb_object_id'])
                        class_info['parent_class_codes'].insert(0, parent_class['code'])
                        if parent_class['parent_class_id'] in classes_by_id:
                            parent_class_info = classes_by_id[parent_class_info['class']['parent_class_id']]
                            parent_class = parent_class_info['class']
                        else:
                            break
                    if is_parent_applicable:
                        # add applicability info from parent classes
                        class_info['is_applicable'] = 1
                    if is_parent_exclusive:
                        # add exclusive info from parent classes
                        class_info['is_parent_exclusive'] = 1
                elif clazz_id not in root_class_ids:
                    root_class_ids.add(clazz_id)
                    class_tree.append(classes_by_id[clazz_id])
            return class_tree

        def add_applicable_class(applicable_classes, class_info, deep=False):
            if -1 != limit and len(applicable_classes) >= limit:
                return
            if not class_filter or class_filter(class_info['class']):
                parent_class_codes = class_info['parent_class_codes']
                info = class_info['class'].create_class_info(
                    has_subclasses=1,
                    is_applicable=class_info['is_applicable'],
                    is_parent_class_exclusive=class_info['is_exclusive'],
                    parent_code=parent_class_codes[-1] if parent_class_codes else '',
                    oplan_tile_title_pattern = oplan_tile_title_pattern,
                    oplan_tile_subtitle_pattern = oplan_tile_subtitle_pattern
                )
                info['parent_class_codes'] = parent_class_codes
                info['parent_class_ids'] = class_info['parent_class_ids']
                applicable_classes.append(info)
            if deep:
                for class_info in class_info['subclasses']:
                    clazz = class_info['class']
                    if only_released and 200 != clazz['status']:
                        continue
                    if clazz and not clazz.CheckAccess("read"):
                        continue
                    add_applicable_class(applicable_classes, class_info, deep)

        def has_applicable_sub_classes(class_info):
            for sub_class_info in class_info['subclasses']:
                if only_released and 200 != sub_class_info['class'].status:
                    continue
                if sub_class_info['is_applicable'] or has_applicable_sub_classes(sub_class_info):
                    return True
            return False

        def get_applicable_classes(class_infos, applicable_classes):
            if -1 != limit and len(applicable_classes) >= limit:
                return
            for class_info in class_infos:
                clazz = class_info['class']
                if only_released and 200 != clazz['status']:
                    continue
                if clazz and not clazz.CheckAccess("read"):
                    # ignore subtree if base class has no read access
                    continue
                if class_info['is_applicable']:
                    add_applicable_class(applicable_classes, class_info, True)
                else:
                    if include_base_classes and has_applicable_sub_classes(class_info):
                        add_applicable_class(applicable_classes, class_info, False)
                    get_applicable_classes(class_info['subclasses'], applicable_classes)

        if for_oplan:
            oplan_tile_title = util.CDBMsg.getMessage("cs_classification_oplan_tile_title")
            oplan_tile_title_pattern = tools.parse_raw(oplan_tile_title)
            oplan_tile_subtitle = util.CDBMsg.getMessage("cs_classification_oplan_tile_subtitle")
            oplan_tile_subtitle_pattern = tools.parse_raw(oplan_tile_subtitle)
        else:
            oplan_tile_title_pattern = None
            oplan_tile_subtitle_pattern = None

        applicable_class_tree = create_class_tree()
        applicable_classes = []
        get_applicable_classes(applicable_class_tree, applicable_classes)
        result = sorted(applicable_classes, key=lambda entry: (entry["pos"], entry["label"]))
        return result


    @classmethod
    def get_applicable_classes(
        cls, dd_classname, class_ids=None, class_codes=None,
        only_active=True, only_released=True, for_oplan=False
    ):
        """
        Check if the given class ids or class codes are applicable and return the class infos for the
        applicable classes.
        """

        def filter_class(clazz):
            return (
                clazz.code in _class_codes or
                clazz.cdb_object_id in _class_ids
            )

        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []
        where_condition = cls._create_class_where_condition(_class_ids, _class_codes)
        return cls._get_applicable_classes(
            dd_classname, where_condition, limit=-1,
            only_active=only_active, only_released=only_released, class_filter=filter_class,
            for_oplan=for_oplan
        )

    @classmethod
    def search_applicable_classes(
        cls, dd_classname, query_string, limit=-1, only_active=True, only_released=True, for_oplan=False
    ):

        def filter_class(clazz):
            return (
                query_string_lower in clazz.code.lower() or
                query_string_lower in clazz.name.lower() or
                query_string_lower in clazz.tags.lower()
            )

        applicable_class_codes = cls.get_direct_applicable_class_codes(
            dd_classname, only_active=only_active, only_released=only_released
        )

        query_string_lower = query_string.lower()
        where_condition = "{condition_applicable} or LOWER(code) {like} or LOWER(name_{lang}) {like} or LOWER(tags_{lang}) {like}".format(
            condition_applicable=tools.format_in_condition(
                "code", applicable_class_codes
            ),
            lang=i18n.default(),
            like="like '%" + sqlapi.quote(query_string_lower) + "%'"
        )
        return cls._get_applicable_classes(
            dd_classname, where_condition, limit=limit,
            only_active=only_active, only_released=only_released,
            class_filter=filter_class, include_base_classes=True,
            for_oplan=for_oplan
        )

    @classmethod
    def get_direct_applicable_class_codes(cls, dd_classname, only_active=True, only_released=True):
        try:
            cldef = CDBClassDef(dd_classname)
            class_names = [dd_classname] + list(cldef.getBaseClassNames())
        except ElementsError:
            return []

        stmt = """
                   select cs_classification_class.code 
                   from cs_classification_applicabilit
                   join cs_classification_class on cs_classification_applicabilit.classification_class_id = cs_classification_class.cdb_object_id
                   where {dd_classnames} {condition_active} {only_released_condition}
        """.format(
            dd_classnames=tools.format_in_condition(
                "cs_classification_applicabilit.dd_classname", class_names
            ),
            condition_active="AND cs_classification_applicabilit.is_active = 1" if only_active else "",
            only_released_condition="AND cs_classification_class.status = 200" if only_released else ""
        )
        rset = sqlapi.RecordSet2(sql=stmt)
        applicable_class_codes = {r.code for r in rset}
        return applicable_class_codes

    @classmethod
    def get_applicable_root_classes(cls, dd_classname, only_active=True, only_released=True, for_oplan=False):  # pylint: disable=R0914

        def get_root_class_id(classes_by_oid, classification_class_id):
            classification_class = classes_by_oid.get(classification_class_id)
            if classification_class and classification_class.parent_class_id:
                return get_root_class_id(classes_by_oid, classification_class.parent_class_id)
            return classification_class_id

        try:
            cldef = CDBClassDef(dd_classname)
            class_names = [dd_classname] + list(cldef.getBaseClassNames())
        except ElementsError:
            return []

        if only_released:
            stmt = """
                select classification_class_id 
                from cs_classification_applicabilit
                join cs_classification_class on cs_classification_applicabilit.classification_class_id = cs_classification_class.cdb_object_id
                where {dd_classnames} {condition_active} AND cs_classification_class.status = 200
            """.format(
                dd_classnames = tools.format_in_condition(
                    "cs_classification_applicabilit.dd_classname", class_names
                ),
                condition_active = "AND cs_classification_applicabilit.is_active = 1" if only_active else ""
            )
        else:
            stmt = """
                select classification_class_id from cs_classification_applicabilit where {dd_classnames} {condition_active}
            """.format(
                dd_classnames = tools.format_in_condition(
                    "cs_classification_applicabilit.dd_classname", class_names
                ),
                condition_active = "AND cs_classification_applicabilit.is_active = 1" if only_active else ""
            )

        rset = sqlapi.RecordSet2(sql=stmt)
        applicable_class_ids = {r["classification_class_id"] for r in rset}

        if not applicable_class_ids:
            return []

        stmt = """
            WITH {recursive} class_hierarchy (cdb_object_id, parent_class_id) AS (
              SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id
              FROM cs_classification_class
              WHERE {condition_applicable}
                 
              UNION ALL
                 
              SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id
              FROM cs_classification_class, class_hierarchy
              WHERE cs_classification_class.cdb_object_id = class_hierarchy.parent_class_id
            )
            SELECT 
                (select count(cdb_object_id) from cs_classification_class where parent_class_id = class_hierarchy.cdb_object_id) as has_subclasses,
                cs_classification_class.* 
                FROM class_hierarchy
                JOIN cs_classification_class on class_hierarchy.cdb_object_id = cs_classification_class.cdb_object_id
        """.format(
            condition_applicable = tools.format_in_condition(
                "cs_classification_class.cdb_object_id", list(applicable_class_ids)
            ),
            recursive=tools.format_recursive()
        )

        classes_by_oid = {}
        class_ids_with_subclasses = set()
        rset = sqlapi.RecordSet2(sql=stmt)
        for r in rset:
            clazz_id = r["cdb_object_id"]
            clazz = ClassificationClass()
            clazz._load_from_record(r, False)  # pylint: disable=W0212
            classes_by_oid[clazz_id] = clazz
            if r["has_subclasses"] > 0:
                class_ids_with_subclasses.add(clazz_id)

        root_class_ids = set()
        for applicable_class_id in applicable_class_ids:
            root_class_id = get_root_class_id(classes_by_oid, applicable_class_id)
            root_class_ids.add(root_class_id)

        if for_oplan:
            oplan_tile_title = util.CDBMsg.getMessage("cs_classification_oplan_tile_title")
            oplan_tile_title_pattern = tools.parse_raw(oplan_tile_title)
            oplan_tile_subtitle = util.CDBMsg.getMessage("cs_classification_oplan_tile_subtitle")
            oplan_tile_subtitle_pattern = tools.parse_raw(oplan_tile_subtitle)
        else:
            oplan_tile_title_pattern = None
            oplan_tile_subtitle_pattern = None

        root_class_infos = []
        for root_class_id in root_class_ids:
            root_class = classes_by_oid.get(root_class_id)
            if not root_class:
                # not existing parent class id set
                continue
            if only_released and 200 != root_class["status"]:
                # ignore not released classes
                continue
            if not root_class.CheckAccess("read"):
                # ignore classes without read access
                continue
            parent_class = classes_by_oid.get(root_class.parent_class_id)
            class_info = root_class.create_class_info(
                has_subclasses=root_class_id in class_ids_with_subclasses,
                is_applicable=root_class_id in applicable_class_ids,
                is_parent_class_exclusive=False,
                parent_code=parent_class["code"] if parent_class else '',
                oplan_tile_title_pattern=oplan_tile_title_pattern,
                oplan_tile_subtitle_pattern=oplan_tile_subtitle_pattern
            )
            root_class_infos.append(class_info)

        result = sorted(root_class_infos, key=lambda entry: (entry["pos"], entry["label"]))
        return result

    @classmethod
    def get_applicable_sub_classes(
        cls, dd_classname,
        parent_class_code, is_parent_class_applicable=None, is_parent_class_exclusive=False,
        only_active=True, only_released=True, for_oplan=False
    ): # pylint: disable=R0913

        if is_parent_class_applicable is None:
            # applicability of parent unknown - has to be checked
            is_parent_class_applicable = bool(
                ClassificationClass.get_applicable_classes(
                    dd_classname, class_codes=[parent_class_code]
                )
            )

        released_condition = "AND child_classes.status = 200" if only_released else ""

        if is_parent_class_applicable:
            # applicability is inherited so we can query only the subclasses
            stmt = """
                SELECT 
                    (SELECT count(cdb_object_id) FROM cs_classification_class where parent_class_id = child_classes.cdb_object_id) has_subclasses,
                    child_classes.*
                FROM cs_classification_class child_classes
                WHERE 
                    child_classes.parent_class_id = (
                        select cdb_object_id from cs_classification_class where code = '{class_code}'
                    ) 
                    {released_condition}
            """.format(class_code=sqlapi.quote(parent_class_code), released_condition=released_condition)
        else:
            # applicability of subclasses needs to be checked
            try:
                cldef = CDBClassDef(dd_classname)
                class_names = [dd_classname] + list(cldef.getBaseClassNames())
            except ElementsError:
                return []

            stmt = """
                SELECT 
                    (select count(cdb_object_id) from cs_classification_class where parent_class_id = child_classes.cdb_object_id) as has_subclasses,
                    cs_classification_applicabilit.is_active as is_applicable,
                    child_classes.*
                FROM cs_classification_class child_classes
                LEFT JOIN cs_classification_applicabilit ON (
                    child_classes.cdb_object_id = cs_classification_applicabilit.classification_class_id AND
                    ({dd_classnames}) {condition_active}
                )
                WHERE 
                    child_classes.parent_class_id = (
                        select cdb_object_id from cs_classification_class where code = '{class_code}'
                    )
                    {released_condition}
                    AND (
                        cs_classification_applicabilit.is_active = 1 OR
                        (select count(cdb_object_id) from cs_classification_class where parent_class_id = child_classes.cdb_object_id) > 0
                    ) 
            """.format(
                class_code=sqlapi.quote(parent_class_code),
                condition_active="AND cs_classification_applicabilit.is_active = 1" if only_active else "",
                dd_classnames = tools.format_in_condition(
                    "cs_classification_applicabilit.dd_classname", class_names
                ),
                released_condition=released_condition
            )

        if for_oplan:
            oplan_tile_title = util.CDBMsg.getMessage("cs_classification_oplan_tile_title")
            oplan_tile_title_pattern = tools.parse_raw(oplan_tile_title)
            oplan_tile_subtitle = util.CDBMsg.getMessage("cs_classification_oplan_tile_subtitle")
            oplan_tile_subtitle_pattern = tools.parse_raw(oplan_tile_subtitle)
        else:
            oplan_tile_title_pattern = None
            oplan_tile_subtitle_pattern = None

        class_infos = []
        rset = sqlapi.RecordSet2(sql=stmt)
        for r in rset:
            has_subclasses = r["has_subclasses"]
            clazz = ClassificationClass()
            clazz._load_from_record(r, False)  # pylint: disable=W0212
            is_clazz_applicable = 1 if is_parent_class_applicable or r["is_applicable"] else 0
            if clazz and clazz.CheckAccess("read"):
                class_info = clazz.create_class_info(
                    has_subclasses=has_subclasses,
                    is_applicable=is_clazz_applicable,
                    is_parent_class_exclusive=is_parent_class_exclusive,
                    parent_code=parent_class_code,
                    oplan_tile_title_pattern=oplan_tile_title_pattern,
                    oplan_tile_subtitle_pattern=oplan_tile_subtitle_pattern
                )
                class_infos.append(class_info)

        result = sorted(class_infos, key=lambda entry: (entry["pos"], entry["label"]))
        return result

    @classmethod
    def get_base_class_infos(
        cls, class_ids=None, class_codes=None, include_given=False, only_released=True, check_rights=True
    ):
        """
        Get a list of all base class infos. Depending on the check_rights flag the list is filtered by read
        right of classification class.
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :param include_given: specify if given classes shall also be added to the returned list
        :param only_released: specify if only released classes chall be retrived
        :param check_rights: specify if the read right on the classification class shall be evaluated
        :return: list of all base class infos
        """

        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []

        sql_stmt = """
             WITH {recursive} class_hierarchy (cdb_object_id, parent_class_id) AS (
               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id
               FROM cs_classification_class
               WHERE {where_condition} 
               
               UNION ALL

               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id
               FROM cs_classification_class, class_hierarchy
               WHERE cs_classification_class.cdb_object_id = class_hierarchy.parent_class_id
             )
             SELECT cs_classification_class.* 
             FROM class_hierarchy
             JOIN cs_classification_class on class_hierarchy.cdb_object_id = cs_classification_class.cdb_object_id
        """.format(
            recursive = tools.format_recursive(),
            where_condition=cls._create_class_where_condition(_class_ids, _class_codes)
        )

        use_dtag = ClassificationClass._use_dtag()
        classes_by_id = {}
        for r in sqlapi.RecordSet2(sql=sql_stmt):
            clazz = ClassificationClass()
            clazz._load_from_record(r, False) # pylint: disable=W0212
            classes_by_id[clazz.cdb_object_id] = {
                'class': clazz,
                'is_exclusive': clazz.is_exclusive,
                'parent_class_ids': [],
                'parent_class_codes': [],
                'subclasses': []
            }
        class_tree = []
        root_class_ids = set()
        for clazz_id, class_info in classes_by_id.items():
            if class_info['class']['parent_class_id'] in classes_by_id:
                parent_class_info = classes_by_id[class_info['class']['parent_class_id']]
                parent_class_info['subclasses'].append(class_info)
                parent_class = parent_class_info['class']
                while parent_class:
                    if 1 == parent_class_info['class']['is_exclusive']:
                        class_info['is_exclusive'] = 1
                    class_info['parent_class_ids'].insert(0, parent_class['cdb_object_id'])
                    class_info['parent_class_codes'].insert(0, parent_class['code'])
                    if parent_class['parent_class_id'] in classes_by_id:
                        parent_class_info = classes_by_id[parent_class_info['class']['parent_class_id']]
                        parent_class = parent_class_info['class']
                    else:
                        break
            elif clazz_id not in root_class_ids:
                root_class_ids.add(clazz_id)
                class_tree.append(classes_by_id[clazz_id])

        def filter_classes(class_infos, classes):
            for class_info in class_infos:
                clazz = class_info["class"]
                if only_released and 200 != clazz["status"]:
                    continue
                if check_rights and clazz and not clazz.CheckAccess("read"):
                    # ignore subtree if base class has no read access
                    continue
                if (
                        not include_given and (
                            clazz["code"] in _class_codes or
                            clazz["r.cdb_object_id"] in _class_ids
                        )
                ):
                    continue
                parent_class_codes = class_info["parent_class_codes"]
                name = tools.get_label("name", clazz)
                info = {
                    "cdb_object_id": clazz["cdb_object_id"],
                    "code": clazz["code"],
                    "description": tools.get_label('description', clazz),
                    "is_abstract": clazz.is_abstract,
                    "is_exclusive": class_info["is_exclusive"],
                    "label": clazz.GetDescription() if use_dtag else name,
                    "name": name,
                    "pos": 0 if clazz.pos is None else clazz.pos,
                    "parent_code": parent_class_codes[-1] if parent_class_codes else "",
                    "parent_id": clazz.parent_class_id,
                    "parent_class_codes": parent_class_codes,
                    "parent_class_ids": class_info["parent_class_ids"],
                    "status": clazz.status,
                    "subclasses": [
                        subclass_info["class"]["code"] for subclass_info in class_info["subclasses"]
                    ],
                    "subclass_ids": [
                        subclass_info["class"]["cdb_object_id"] for subclass_info in class_info["subclasses"]
                    ]
                }
                classes.append(info)
                if class_info['subclasses']:
                    filter_classes(class_info['subclasses'], classes)

        base_classes = []
        filter_classes(class_tree, base_classes)
        return base_classes

    @classmethod
    def get_base_classes(cls, class_ids=None, class_codes=None, include_given=False):
        """
        Get all baseclasses for the given class codes or cdb_object_ids.
        The list is not filtered by rights!
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :param include_given: specify if given classes shall also be added to the returned list
        :return: list of all base classes
        """

        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []

        sql_stmt = """
             WITH {recursive} class_hierarchy (cdb_object_id, parent_class_id) AS (
               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id
               FROM cs_classification_class
               WHERE {where_condition}

               UNION ALL

               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id
               FROM cs_classification_class, class_hierarchy
               WHERE cs_classification_class.cdb_object_id = class_hierarchy.parent_class_id
             )
             SELECT cs_classification_class.*
             FROM class_hierarchy
             JOIN cs_classification_class on class_hierarchy.cdb_object_id = cs_classification_class.cdb_object_id
        """.format(
            recursive=tools.format_recursive(),
            where_condition=cls._create_class_where_condition(_class_ids, _class_codes)
        )

        result = []
        for r in sqlapi.RecordSet2(sql=sql_stmt):
            if (
                    not include_given and
                    (r.code in _class_codes or r.cdb_object_id in _class_ids)
            ):
                continue

            clazz = ClassificationClass()
            clazz._load_from_record(r, False)  # pylint: disable=W0212
            result.append(clazz)
        return result

    @classmethod
    def _get_base_class_keys(cls, class_ids=None, class_codes=None, return_code=False, include_given=False):

        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []

        sql_stmt = """
             WITH {recursive} class_hierarchy(cdb_object_id, parent_class_id, code) AS (
               SELECT cdb_object_id, parent_class_id, code
               FROM cs_classification_class
               WHERE {where_condition}

               UNION ALL

               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id, cs_classification_class.code
               FROM cs_classification_class, class_hierarchy
               WHERE cs_classification_class.cdb_object_id = class_hierarchy.parent_class_id
             )
             SELECT code, cdb_object_id FROM class_hierarchy
        """.format(
            recursive=tools.format_recursive(),
            where_condition = cls._create_class_where_condition(_class_ids, _class_codes)
        )

        result = []
        for r in sqlapi.RecordSet2(sql=sql_stmt):
            if (
                    not include_given and
                    (r.code in _class_codes or r.cdb_object_id in _class_ids)
            ):
                continue
            if return_code:
                result.append(r.code)
            else:
                result.append(r.cdb_object_id)
        return result


    @classmethod
    def get_base_class_codes(cls, class_ids=None, class_codes=None, include_given=False):
        """
        Get all baseclass codes for the given class codes or cdb_object_ids.
        The list is not filtered by rights!
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :param include_given: specify if given classes shall also be added to the returned list
        :return: list of all base class codes
        """
        return cls._get_base_class_keys(
            class_ids=class_ids, class_codes=class_codes, return_code=True, include_given=include_given
        )

    @classmethod
    def get_base_class_ids(cls, class_ids=None, class_codes=None, include_given=False):
        """
        Get cdb_object_ids of baseclasses for the given class codes or cdb_object_ids.
        The list is not filtered by rights!
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :param include_given: specify if given classes shall also be added to the returned list
        :return: list of all base class cdb_object_ids
        """
        return cls._get_base_class_keys(
            class_ids=class_ids, class_codes=class_codes, return_code=False, include_given=include_given
        )

    @classmethod
    def _get_base_class_keys_with_parent_info(
        cls, class_ids=None, class_codes=None, return_code=False, include_given=False
    ):

        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []

        sql_stmt = """
             WITH {recursive} class_hierarchy(cdb_object_id, parent_class_id, code) AS (
               SELECT cdb_object_id, parent_class_id, code
               FROM cs_classification_class
               WHERE {where_condition}

               UNION ALL

               SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id, cs_classification_class.code
               FROM cs_classification_class, class_hierarchy
               WHERE cs_classification_class.cdb_object_id = class_hierarchy.parent_class_id
             )
             SELECT code, cdb_object_id, parent_class_id FROM class_hierarchy
        """.format(
            recursive=tools.format_recursive(),
            where_condition = cls._create_class_where_condition(_class_ids, _class_codes)
        )

        by_oid = {}
        for r in sqlapi.RecordSet2(sql=sql_stmt):
            by_oid[r.cdb_object_id] = {
                'code': r.code,
                'cdb_object_id': r.cdb_object_id,
                'parent_class_code': '',
                'parent_class_id': r.parent_class_id
            }

        result = {}
        for class_oid, class_details in by_oid.items():
            if (
                    not include_given and
                    (class_details['code'] in _class_codes or class_details['cdb_object_id'] in _class_ids)
            ):
                continue

            if class_details['parent_class_id']:
                parent_details = by_oid.get(class_details['parent_class_id'])
                if parent_details:
                    class_details['parent_class_code'] = parent_details['code']

            result[class_details['code' if return_code else 'cdb_object_id']] = class_details

        return result

    @classmethod
    def get_base_class_info_by_code(cls, class_ids=None, class_codes=None, include_given=False):
        """
        Get all baseclass infos for the given class codes or cdb_object_ids.
        The list is not filtered by rights!
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :param include_given: specify if given classes shall also be added to the returned list
        :return: map of base class infos by cdb_object_id of the classes
        """
        return cls._get_base_class_keys_with_parent_info(
            class_ids=class_ids, class_codes=class_codes, return_code=True, include_given=include_given
        )

    @classmethod
    def get_base_class_info_by_id(cls, class_ids=None, class_codes=None, include_given=False):
        """
        Get all baseclass infos for the given class codes or cdb_object_ids.
        The list is not filtered by rights!
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :param include_given: specify if given classes shall also be added to the returned list
        :return: map of base class infos by code of the classes
        """
        return cls._get_base_class_keys_with_parent_info(
            class_ids=class_ids, class_codes=class_codes, return_code=False, include_given=include_given
        )


    @classmethod
    def _get_sub_class_keys(cls, class_ids=None, class_codes=None, return_code=False, include_given=False):
        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []
        sql_stmt = """
            WITH {recursive} class_hierarchy(cdb_object_id, parent_class_id, code) AS (
              SELECT cdb_object_id, parent_class_id, code
              FROM cs_classification_class
              WHERE {where_condition}

              UNION ALL

              SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id, cs_classification_class.code
              FROM cs_classification_class, class_hierarchy
              WHERE cs_classification_class.parent_class_id = class_hierarchy.cdb_object_id
            )
            SELECT code, cdb_object_id FROM class_hierarchy
       """.format(
            recursive=tools.format_recursive(),
            where_condition=cls._create_class_where_condition(_class_ids, _class_codes)
        )

        result = []
        for r in sqlapi.RecordSet2(sql=sql_stmt):
            if (
                    not include_given and
                    (r.code in _class_codes or r.cdb_object_id in _class_ids)
            ):
                continue
            if return_code:
                result.append(r.code)
            else:
                result.append(r.cdb_object_id)
        return result

    @classmethod
    def get_sub_class_codes(cls, class_ids=None, class_codes=None, include_given=False):
        """
        Get all subclass codes for the given class codes or cdb_object_ids.
        The list is not filtered by rights!
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :param include_given: specify if given classes shall also be added to the returned list
        :return: list of all sub class codes
        """
        return cls._get_sub_class_keys(
            class_ids=class_ids, class_codes=class_codes, return_code=True, include_given=include_given
        )

    @classmethod
    def get_sub_class_ids(cls, class_ids=None, class_codes=None, include_given=False):
        """
        Get cdb_object_ids of baseclasses for the given class codes or cdb_object_ids.
        The list is not filtered by rights!
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :param include_given: specify if given classes shall also be added to the returned list
        :return: list of all base class cdb_object_ids
        """
        return cls._get_sub_class_keys(
            class_ids=class_ids, class_codes=class_codes, return_code=False, include_given=include_given
        )

    @classmethod
    def has_class_object_classifications(cls, class_ids=None, class_codes=None):
        """
        Check if there are any object classifications for the given class codes or cdb_object_ids or their
        subclasses
        :param class_ids: list of class cdb_object_ids (at least one of the lists - class_ids or class_codes - must contain a value)
        :param class_codes: list of class codes (at least one of the lists - class_ids or class_codes - must contain a value)
        :return: true if there are any object classifications with one of the given class codes or cdb_object_ids ans all of their subclasses
        """

        _class_codes = class_codes if class_codes else []
        _class_ids = class_ids if class_ids else []

        sql_stmt = """
            WITH {recursive} class_hierarchy(cdb_object_id, parent_class_id, code) AS (
              SELECT cdb_object_id, parent_class_id, code
              FROM cs_classification_class
              WHERE {where_condition}

              UNION ALL

              SELECT cs_classification_class.cdb_object_id, cs_classification_class.parent_class_id, cs_classification_class.code
              FROM cs_classification_class, class_hierarchy
              WHERE cs_classification_class.parent_class_id = class_hierarchy.cdb_object_id
            )
            SELECT code FROM class_hierarchy
            JOIN cs_object_classification on cs_object_classification.class_code = class_hierarchy.code
       """.format(
            recursive=tools.format_recursive(),
            where_condition=cls._create_class_where_condition(_class_ids, _class_codes)
        )
        return len(sqlapi.RecordSet2(sql=sql_stmt)) > 0

    @classmethod
    def get_class_names(cls, class_codes):
        return [clazz.name for clazz in cls.KeywordQuery(code=class_codes)]

    @classmethod
    def get_class_documents(cls, code):
        from cs.documents import Document
        sql_stmt = """
            SELECT zeichnung.* FROM cs_classification_class2docume
            JOIN zeichnung on cs_classification_class2docume.z_nummer=zeichnung.z_nummer
            AND cs_classification_class2docume.z_index=zeichnung.z_index
            WHERE cs_classification_class2docume.classification_class_id = '{class_id}'
            ORDER BY  cs_classification_class2docume.pos
        """.format(class_id=cls.code_to_oid(code))
        assigned_documents = Document.SQL(sql_stmt)
        return assigned_documents

    def check_recursion(self, ctx):
        if self.cdb_object_id == self.parent_class_id:
            raise ue.Exception("cs_classification_class_hierarchie_recursive")
        stmt = "WITH {recursive} t(cdb_object_id, parent_class_id) AS ( " \
            "SELECT cdb_object_id, parent_class_id FROM cs_classification_class WHERE cdb_object_id='{parent_class_id}' " \
            "UNION ALL "\
            "SELECT t2.cdb_object_id, t2.parent_class_id FROM cs_classification_class t2 " \
            "JOIN t ON t.parent_class_id = t2.cdb_object_id " \
            ") SELECT * FROM t WHERE parent_class_id = '{cdb_object_id}'".format(
                parent_class_id=self.parent_class_id,
                cdb_object_id=self.cdb_object_id,
                recursive=tools.format_recursive()
            )
        rset = sqlapi.RecordSet2(sql=stmt)
        if len(rset) > 0:
            raise ue.Exception("cs_classification_class_hierarchie_recursive")

    def create_class_info(
        self,
        has_subclasses, is_applicable, is_parent_class_exclusive,
        parent_code='',
        oplan_tile_title_pattern=None, oplan_tile_subtitle_pattern=None
    ):
        class_info = {
            "is_applicable": is_applicable,
            "label": self.GetDescription() if self._use_dtag() else tools.get_label('name', self),
            "name": tools.get_label('name', self),
            "description": self["description"],
            "cdb_object_id": self["cdb_object_id"],
            "code": self["code"],
            "parent_code": parent_code,
            "parent_id": self["parent_class_id"],
            "flags": [
                1 if is_applicable and not self["is_abstract"] else 0,
                1 if is_parent_class_exclusive or self["is_exclusive"] else 0,
                1 if has_subclasses else 0
            ],
            "pos": 0 if self["pos"] is None else self["pos"],
            "status": self["status"]
        }
        if oplan_tile_title_pattern:
            class_info["oplan_tile_title"] = oplan_tile_title_pattern % tools._ValueAccessor(self)
        if oplan_tile_subtitle_pattern:
            class_info["oplan_tile_subtitle"] = oplan_tile_subtitle_pattern % tools._ValueAccessor(self)

        return class_info

    @classmethod
    def allow_catalog_prop_import(cls, classification_class_id, catalog_property):
        if not catalog_property.isActive():
            raise ue.Exception("cs_classification_property_not_active", catalog_property.code)
        parent_class = ClassificationClass.ByKeys(cdb_object_id=classification_class_id)
        if parent_class.external_modification_only:
            raise ue.Exception("cs_classification_external_class_not_modifiable")

    def allow_delete(self, ctx):
        if self.has_object_classifications():
            raise ue.Exception("cs_classification_class_delete")

    def allow_modify(self, ctx):
        self.check_recursion(ctx)

        ue_exception = ""

        persistentObject = self.getPersistentObject()
        old_parent_class_id = persistentObject.parent_class_id
        if old_parent_class_id is None:
            old_parent_class_id = ""
        new_parent_class_id = self.parent_class_id
        if old_parent_class_id != new_parent_class_id:
            ue_exception = "cs_classification_change_base_class"

        old_exclusive = persistentObject.is_exclusive
        new_exclusive = self.is_exclusive
        if 0 == old_exclusive and 1 == new_exclusive:
            ue_exception = "cs_classification_set_exclusive_error"

        if ue_exception and self.has_object_classifications():
            raise ue.Exception(ue_exception)

    @classmethod
    def get_valid_code(cls, code):
        from cs.classification.util import check_code, create_code, make_code_unique
        valid_code = code if check_code(code) else create_code(code)
        unique_code = make_code_unique("SELECT code FROM cs_classification_class", valid_code)
        return unique_code

    def modify_query_condition(self, ctx):
        if "is_root_class" not in ctx.dialog.get_attribute_names():
            pass
        else:
            if ctx.dialog["is_root_class"] == '0':
                ctx.set_additional_query_cond("parent_class_id is not null and parent_class_id <> ''")
            elif ctx.dialog["is_root_class"] == '1':
                ctx.set_additional_query_cond("parent_class_id is null or parent_class_id = ''")

    def check_code(self, ctx):
        new_code = ctx.dialog.code
        ClassificationClass.check_class_code(new_code)

    @classmethod
    def copy_dialog_pre_submit_hook(cls, hook):
        from cdb import util as cdb_util

        new_code = hook.get_new_value("code")
        try:
            ClassificationClass.check_class_code(new_code)
        except ue.Exception as ex:
            title = cdb_util.CDBMsg(
                cdb_util.CDBMsg.kFatal, "cs_classification_err_copy_class_title"
            )
            hook.set_error(title.getText(i18n.default(), True), str(ex))

    @classmethod
    def check_class_code(cls, new_code):
        from cs.classification import util as cutil
        if not cutil.check_code(new_code):
            raise ue.Exception("cs_classification_invalid_code")

        rset = sqlapi.RecordSet2(
            sql="SELECT code FROM cs_classification_class where code = '{}'".format(new_code)
        )
        if len(rset):
            raise ue.Exception("cs_classification_class_code_not_unique", new_code)

    def copy_class_operation(self, ctx):
        from cdb import cmsg
        from cs.classification.validation import ClassificationValidator

        clazz_args = {
            'code': ctx.dialog.code
        }
        attribute_names = ctx.dialog.get_attribute_names()
        for lang_key in self.GetLocalizedValues('name'):
            name_arg = 'name_' + lang_key
            if name_arg in attribute_names:
                clazz_args[name_arg] = ctx.dialog[name_arg]
            else:
                clazz_args[name_arg] = ''

        copied_clazz = self.copy(clazz_args)
        ctx.keep("copied_classification_class_code", ctx.dialog.code)

        ClassificationValidator.reload_all()
        # open class detail view of copied class
        msg = cmsg.Cdbcmsg("cs_classification_class", "cs_classification_class_overview", 0)
        msg.add_item("cdb_object_id", "cs_classification_class", copied_clazz.cdb_object_id)

        if ctx.uses_webui:
            ctx.url(msg.url(""))
        else:
            ctx.url(msg.eLink_url())

    def copy(self, clazz_args, prop_code_mapping=None, prop_id_mapping=None, skip_solr=False):
        from cdb import transactions
        from cdb.objects.cdb_file import CDB_File
        from cs.classification import solr_schema_sync
        from cs.classification.util import make_code_unique

        with transactions.Transaction():
            olc = self.GetObjectKind()
            if olc:
                st = StateDefinition.ByKeys(ClassificationClass.EDIT.status, olc)
                clazz_args['status'] = st.statusnummer
                clazz_args['cdb_status_txt'] = st.statusbez_en if st else ''
            else:
                clazz_args['status'] = 0
                clazz_args['cdb_status_txt'] = ''
            copied_clazz = self.Copy(**clazz_args)

            # copy applicabilities
            rset = sqlapi.RecordSet2(
                "cs_classification_applicabilit", "classification_class_id='{}'".format(self.cdb_object_id)
            )
            for r in rset:
                r.copy(
                    classification_class_id=copied_clazz.cdb_object_id
                )

            # copy properties and catalog values
            if prop_code_mapping is None:
                prop_code_mapping = {}
            if prop_id_mapping is None:
                prop_id_mapping = {}
            own_prop_id_mapping = {}
            for prop in self.OwnProperties:
                prop_args = {
                    'classification_class_id': copied_clazz.cdb_object_id,
                    'code': ClassProperty.get_new_class_prop_code(copied_clazz, prop.catalog_property_code)
                }
                copied_property = prop.Copy(**prop_args)
                prop_code_mapping[prop.code] = (copied_property.code)
                prop_id_mapping[prop.cdb_object_id] = (copied_property.cdb_object_id)
                own_prop_id_mapping[prop.cdb_object_id] = (copied_property.cdb_object_id)

                prop_value_id_mapping = {}
                rset = sqlapi.RecordSet2(
                    "cs_property_value", "property_object_id='{}'".format(prop.cdb_object_id)
                )
                for r in rset:
                    new_value_id = cdbuuid.create_uuid()
                    r.copy(
                        cdb_object_id=new_value_id,
                        property_object_id=copied_property.cdb_object_id
                    )
                    prop_value_id_mapping[r.cdb_object_id] = (new_value_id)
                rset = sqlapi.RecordSet2(
                    "cs_property_value_exclude", "class_property_id='{}'".format(prop.cdb_object_id)
                )
                for r in rset:
                    r.copy(
                        classification_class_id=copied_clazz.cdb_object_id,
                        class_property_id=copied_property.cdb_object_id
                    )
                if copied_property.default_value_oid in prop_value_id_mapping:
                    # correct default_value_oid if default values has been a
                    # property value defined in source property
                    copied_property.default_value_oid = prop_value_id_mapping[copied_property.default_value_oid]

            if not skip_solr:
                solr_schema_sync.process_fields(
                    None,
                    """
                    SELECT cdb_classname, code
                    FROM cs_class_property
                    WHERE classification_class_id = '{}'
                    """.format(
                        copied_clazz.cdb_object_id
                    )
                )

            # copy property groups
            rset = sqlapi.RecordSet2(
                "cs_class_property_group", "classification_class_id='{}'".format(self.cdb_object_id)
            )
            for r in rset:
                copied_group_id = cdbuuid.create_uuid()
                r.copy(
                    cdb_object_id=copied_group_id,
                    classification_class_id=copied_clazz.cdb_object_id
                )
                rset_group_assignments = sqlapi.RecordSet2(
                    "cs_property_group_assign", "group_object_id='{}'".format(r.cdb_object_id)
                )
                for row_group_assignment in rset_group_assignments:
                    row_group_assignment.copy(
                        group_object_id=copied_group_id,
                        property_object_id=prop_id_mapping[row_group_assignment.property_object_id]
                    )

            # copy pictures and document links
            file_objs = CDB_File.KeywordQuery(cdbf_object_id=self.cdb_object_id)
            for f in file_objs:
                f.Copy(cdb_object_id="", cdbf_object_id=copied_clazz.cdb_object_id, cdbf_name=f.cdbf_name)

            rset = sqlapi.RecordSet2(
                "cs_classification_class2docume", "classification_class_id='{}'".format(self.cdb_object_id)
            )
            for r in rset:
                r.copy(classification_class_id=copied_clazz.cdb_object_id)

            # fix class description tags
            class_description_tags = copied_clazz.GetLocalizedValues('class_description_tag')
            replaced_class_description_tags = {}
            for lang, class_description_tag in class_description_tags.items():
                key = 'class_description_tag_' + lang
                if class_description_tag:
                    replaced_class_description_tags[key] = tools.replace_all_identifier(
                        prop_code_mapping, class_description_tag
                    )
                else:
                    replaced_class_description_tags[key] = ''
            copied_clazz.Update(**replaced_class_description_tags)

            # copy constraints
            rset = sqlapi.RecordSet2(
                "cs_classification_constraint", "classification_class_id='{}'".format(self.cdb_object_id)
            )
            for r in rset:
                r.copy(
                    cdb_object_id=cdbuuid.create_uuid(),
                    classification_class_id=copied_clazz.cdb_object_id,
                    when_condition=tools.replace_all_identifier(prop_code_mapping, r.when_condition),
                    expression=tools.replace_all_identifier(prop_code_mapping, r.expression)
                )

            if own_prop_id_mapping:
                # copy formulas and rules
                rset = sqlapi.RecordSet2(
                    "cs_classification_rule", "{}".format(
                        tools.format_in_condition("class_property_id", list(own_prop_id_mapping))
                    )
                )
                for r in rset:
                    r.copy(
                        cdb_object_id=cdbuuid.create_uuid(),
                        class_property_id=own_prop_id_mapping[r.class_property_id],
                        expression=tools.replace_all_identifier(prop_code_mapping, r.expression)
                    )
                rset = sqlapi.RecordSet2(
                    "cs_classification_computation", "{}".format(
                        tools.format_in_condition("property_id", list(own_prop_id_mapping))
                    )
                )
                for r in rset:
                    r.copy(
                        cdb_object_id=cdbuuid.create_uuid(),
                        property_id=own_prop_id_mapping[r.property_id],
                        when_condition=tools.replace_all_identifier(prop_code_mapping, r.when_condition),
                        value_formula=tools.replace_all_identifier(prop_code_mapping, r.value_formula)
                    )

            for subclass in self.Children:
                subclass_args = {
                    'code': make_code_unique("SELECT code FROM cs_classification_class", subclass.code),
                    'parent_class_id': copied_clazz.cdb_object_id
                }
                subclass.copy(
                    subclass_args,
                    prop_code_mapping=prop_code_mapping,
                    prop_id_mapping=prop_id_mapping,
                    skip_solr=skip_solr
                )
        return copied_clazz

    event_map = {
        ('delete', 'pre'): 'allow_delete',
        ('modify', 'pre_mask'): 'set_fields_readonly',
        ('modify', 'pre'): 'allow_modify',
        (('query', 'requery'), 'pre'): 'modify_query_condition',
        ('cs_classification_class_copy', 'post_mask'): 'check_code',
        ('cs_classification_class_copy', 'now'): 'copy_class_operation'
    }


class ClassPropertyValuesView(Object):
    __maps_to__ = "cs_class_property_values_v"

    @property
    def value(self):
        valdict = self.value_dict
        if len(valdict) == 1:
            # ugly, but to satisfy old usages only the value must be returned,
            # if value consists of only one attr
            return valdict[list(valdict)[0]]
        return valdict

    @property
    def value_dict(self):
        attr = catalog.PropertyValue.get_value_attr(self.cdb_classname)
        if isinstance(attr, str):
            return {attr: self[attr]}
        else:
            return {key: self[key] for key in attr}

    @classmethod
    def get_catalog_text_value(cls, property_code, text_value, active_only):
        args = {
            "property_code": property_code,
            "text_value": text_value
        }
        if active_only:
            args["is_active"] = 1
        try:
            value = cls.KeywordQuery(**args)[0]
        except Exception: # pylint: disable=W0703
            value = None
        return value

    @classmethod
    def get_catalog_values(cls, class_code, property_code, active_only, request=None):
        from cs.classification.catalog import PropertyValue
        data = cls.get_catalog_value_objects(class_code, property_code, active_only)
        return PropertyValue.to_json_data(data, request)

    @classmethod
    def get_catalog_value_objects(cls, class_code, property_code, active_only):
        classification_class_id = ClassificationClass.code_to_oid(class_code)
        args = {"classification_class_id": classification_class_id,
                "property_code": property_code}
        if active_only:
            args["is_active"] = 1
        return cls.KeywordQuery(**args)


class ClassPropertyValueExclude(Object):
    __maps_to__ = "cs_property_value_exclude"
    __classname__ = "cs_property_value_exclude"


class ClassProperty(Object):
    __maps_to__ = "cs_class_property"
    __classname__ = "cs_class_property"

    Property = references.Reference_1(
        catalog.Property,
        catalog.Property.cdb_object_id == fClassProperty.catalog_property_id
    )

    Class = references.Reference_1(
        ClassificationClass,
        ClassificationClass.cdb_object_id == fClassProperty.classification_class_id
    )

    ClassPropertyValues = references.Reference_N(
        fPropertyValue,
        fPropertyValue.property_object_id == fClassProperty.cdb_object_id
    )

    @classmethod
    def get_value_class_name(cls, property_class_name):
        return class_prop_value_map.get(property_class_name, '')

    @classmethod
    def get_value_column_name(cls, property_class_name):
        return class_prop_value_column_map.get(property_class_name, '')

    @classmethod
    def get_value_col(cls):
        pass

    def _property_values(self, active_only=True, count=False):
        args = {"classification_class_id": self.classification_class_id,
                "property_id": self.cdb_object_id}
        if active_only:
            args["is_active"] = 1
        if count:
            return len(ClassPropertyValuesView.KeywordQuery(**args))
        else:
            return ClassPropertyValuesView.KeywordQuery(**args)

    def property_values(self, active_only=True):
        return self._property_values(active_only, count=False)

    def has_property_values(self, active_only=True):
        return self._property_values(active_only, count=True) > 0

    def default_value(self):
        return ClassPropertyValuesView.ByKeys(classification_class_id=self.classification_class_id,
                                              property_id=self.cdb_object_id,
                                              value_oid=self.default_value_oid)

    Formulas = references.Reference_N(
        computations.ComputationFormula,
        computations.ComputationFormula.property_id == fClassProperty.cdb_object_id
    )

    Rules = references.Reference_N(
        fRule,
        fRule.class_property_id == fClassProperty.cdb_object_id
    )

    # This only makes sense for object reference properties
    # but we need it here because otherwise it can't be navigated by
    # the module content resolver
    Applicabilities = references.Reference_N(
        applicability.ClassificationReferenceApplicability,
        fClassificationReferenceApplicability.property_id == fClassProperty.cdb_object_id
    )

    class RELEASED(objectlifecycle.State):
        status = 200

    class BLOCKED(objectlifecycle.State):
        status = 300

    def isActive(self):
        """ :return: True if the property can be used in the evaluation.

            In the default implementation this is the case, when the property
            has the status RELEASED. Customers can change this.
        """
        return self.status == self.RELEASED.status

    def set_initial_status(self, ctx):
        self.status = self.RELEASED.status

    def set_defaults(self, ctx):
        self.id = cdbuuid.create_uuid()

    def set_fields_readonly(self, ctx):
        readonly_attrs = ['code', 'is_multivalued']
        ctx.set_fields_readonly(readonly_attrs)

    def is_local_class_property(self):
        return not self.catalog_property_id

    @classmethod
    def copy_from_catalog(cls, ctx):
        group_id = None
        if ctx.relationship_name == 'cs_class_property_group2properties':
            group = ClassPropertyGroup.ByKeys(ctx.parent.cdb_object_id)
            group_id = group.cdb_object_id
            classification_class_id = group.classification_class_id
        elif ctx.relationship_name in (
            'cs_classification_class_properties', 'cs_classification_class2table_column'
        ):
            classification_class_id = ctx.parent.cdb_object_id
        else:
            raise ue.Exception("cs_classification_property_import")

        if not ctx.catalog_selection:
            parent_class = ClassificationClass.ByKeys(cdb_object_id=classification_class_id)
            if parent_class.external_modification_only:
                raise ue.Exception("cs_classification_external_class_not_modifiable")
            ctx.start_selection(catalog_name='cs_classification_import_props')
        else:
            for obj in ctx.catalog_selection:
                prop = catalog.Property.ByKeys(cdb_object_id=obj.cdb_object_id)
                if prop:
                    ClassificationClass.allow_catalog_prop_import(classification_class_id, prop)
                    cls.NewPropertyFromCatalog(prop, classification_class_id, group_id=group_id)
                    ctx.refresh_tables(['cs_class_property'])

    @classmethod
    def copy_from_catalog_web(cls, ctx):

        if "catalog_property_codes" not in ctx.dialog.get_attribute_names():
            return
        if "cdb_object_id" not in ctx.parent.get_attribute_names():
            return

        group_id = None
        if ctx.relationship_name == 'cs_class_property_group2properties':
            group = ClassPropertyGroup.ByKeys(ctx.parent.cdb_object_id)
            group_id = group.cdb_object_id
            classification_class_id = group.classification_class_id
        elif ctx.relationship_name in (
            'cs_classification_class_properties', 'cs_classification_class2table_column'
        ):
            classification_class_id = ctx.parent.cdb_object_id
        else:
            raise ue.Exception("cs_classification_property_import")

        catalog_prop_codes = ctx.dialog.catalog_property_codes.split(",")
        for prop in catalog.Property.Query(catalog.Property.code.one_of(*catalog_prop_codes)):
            if prop:
                ClassificationClass.allow_catalog_prop_import(classification_class_id, prop)
                cls.NewPropertyFromCatalog(prop, classification_class_id, group_id=group_id)

    @classmethod
    def NewPropertyFromCatalog(cls, catalog_property, classification_class_id, group_id=None, skip_solr=False, **kwargs):
        """
        Create a new property by copying a catalog property.

        :param catalog_property: the instance of the catalog property
        :param classification_class_id: the class to import the property to
        :param group_id: the property group to assign the property to

        :return: the new property
        """

        from cs.classification import solr_schema_sync

        with Transaction():
            clazz = type_map[catalog_property.getType()]

            cdb_objektart = "cs_class_property"
            st = StateDefinition.ByKeys(ClassProperty.RELEASED.status, cdb_objektart)

            args = {
                "catalog_property_code": catalog_property.code,
                "classification_class_id": classification_class_id,
                "catalog_property_id": catalog_property.cdb_object_id,
                "default_unit_object_id": catalog_property.unit_object_id,
                "status": st.statusnummer,
                "cdb_status_txt": st.statusbez_en,
                "cdb_objektart": cdb_objektart,
                "display_option": "New Line"
            }

            args.update(catalog_property.getClassDefaults())
            if not group_id:
                args["position"] = cls.get_next_position(classification_class_id)
            args.update(kwargs)
            if "code" not in args:
                # create code if not given
                parent_class = ClassificationClass.ByKeys(cdb_object_id=classification_class_id)
                args["code"] = ClassProperty.get_new_class_prop_code(parent_class, catalog_property.code)
            result = clazz.Create(**args)
            if not skip_solr:
                solr_schema_sync.add_field(result)
            if group_id:
                args = {
                    "display_option": "New Line",
                    "group_object_id": group_id,
                    "property_object_id": result.cdb_object_id,
                    "position": PropertyGroupAssignment.get_next_position(group_id)
                }
                PropertyGroupAssignment.Create(**args)
            return result

    @classmethod
    def get_new_class_prop_code(cls, classification_class, catalog_property_code):
        from cs.classification import util as classification_util

        if classification_class.external_class_type:
            prefix = "{}_{}".format(
                classification_class.external_system if classification_class.external_system else '',
                classification_class.external_class_type
            )
            prefix = classification_util.create_code(prefix)
        else:
            prefix = classification_class.code

        class_prop_code_base = "{prefix}_{prop_code}".format(
            prefix=prefix,
            prop_code=catalog_property_code
        )

        if classification_class.external_class_type:
            stmt = "SELECT code FROM cs_class_property " \
                "WHERE code like '{class_prop_code}%' and classification_class_id = '{class_oid}'" \
                "UNION ALL "\
                "SELECT code FROM cs_property " \
                "WHERE code like '{class_prop_code}%'".format(
                    class_oid=classification_class.cdb_object_id, class_prop_code=class_prop_code_base
                )
        else:
            prefix = classification_class.code
            stmt = "SELECT code FROM cs_class_property " \
                "WHERE code like '{class_prop_code}%' " \
                "UNION ALL "\
                "SELECT code FROM cs_property " \
                "WHERE code like '{class_prop_code}%'".format(class_prop_code=class_prop_code_base)

        rset = sqlapi.RecordSet2(sql=stmt)
        prop_codes = set([r.code for r in rset])

        class_prop_code = class_prop_code_base
        class_prop_code_counter = 1
        while class_prop_code in prop_codes:
            class_prop_code = class_prop_code_base + "_" + str(class_prop_code_counter)
            class_prop_code_counter += 1
        return class_prop_code

    def change_active_flag_for_all_catalog_property_values(self, active):
        """
        Method to enable or disable all catalog property values.
        This method does only work for customized class_properties!
        """
        with Transaction():
            if active:
                # delete all rows
                sqlapi.SQLdelete(
                    "from cs_property_value_exclude where classification_class_id='{class_id}' AND class_property_id='{prop_id}'".format(
                        class_id=self.classification_class_id,
                        prop_id=self.cdb_object_id
                    )
                )
            else:
                records = sqlapi.RecordSet2(
                    "cs_property_value_exclude",
                    "classification_class_id='{class_id}' AND class_property_id='{prop_id}'".format(
                        class_id=self.classification_class_id,
                        prop_id=self.cdb_object_id
                    )
                )
                entries = dict([(record.property_value_id, record) for record in records])
                for prop_val in self.Property.property_values(active_only=False):
                    entry = entries.get(prop_val.cdb_object_id, None)
                    if entry:
                        entry.update(exclude=1)
                    else:
                        ins = util.DBInserter("cs_property_value_exclude")
                        ins.add("classification_class_id", self.classification_class_id)
                        ins.add("class_property_id", self.cdb_object_id)
                        ins.add("property_value_id", prop_val.cdb_object_id)
                        ins.add("property_id", self.catalog_property_id)
                        ins.add("exclude", 1)
                        ins.insert()

    @classmethod
    def get_next_position(cls, classification_class_id):
        stmt = "max(position) FROM cs_class_property WHERE classification_class_id='%s'" \
               % classification_class_id
        t = sqlapi.SQLselect(stmt)

        max_position = 0
        if not sqlapi.SQLnull(t, 0, 0):
            max_position = sqlapi.SQLinteger(t, 0, 0)
        return max_position + 10

    def disable_default(self, ctx):
        ctx.set_readonly('default_value_oid')

    def preset_position(self, ctx):
        if ctx.relationship_name == 'cs_classification_class_properties':
            self.position = ClassProperty.get_next_position(ctx.parent.cdb_object_id)

    def preset_class(self, ctx):
        if ctx.relationship_name == 'cs_class_property_group2properties':
            grp = ClassPropertyGroup.ByKeys(ctx.parent.cdb_object_id)
            self.classification_class_id = grp.classification_class_id

    def set_has_enum_values(self, has_values_hint=False):
        if has_values_hint or self.has_property_values():
            if not self.has_enum_values:
                self.has_enum_values = 1
        elif self.has_enum_values:
            self.has_enum_values = 0

    def reset_default_value(self, value_oid):
        if self.default_value_oid == value_oid:
            self.default_value_oid = None

    def value_exists(self):
        from cs.classification import ObjectPropertyValue
        return ObjectPropertyValue.value_exists(self.code)

    def handle_catalog_dragdrop(self, ctx):
        # set values and skip dialog
        if "cdb_object_id" in ctx.dragged_obj.get_attribute_names():
            catalog_prop = catalog.Property.ByKeys(cdb_object_id=ctx.dragged_obj.cdb_object_id)
            if catalog_prop:
                ClassificationClass.allow_catalog_prop_import(self.classification_class_id, catalog_prop)
                defaults = catalog_prop.getClassDefaults()
                for attr, value in defaults.items():
                    self[attr] = value
                classification_class = ClassificationClass.ByKeys(cdb_object_id=self.classification_class_id)
                class_prop_code = ClassProperty.get_new_class_prop_code(classification_class, catalog_prop.code)
                self["code"] = class_prop_code
                self["catalog_property_code"] = catalog_prop.code
                self["default_unit_object_id"] = catalog_prop.unit_object_id
                self["display_option"] = "New Line"
                self["status"] = 200
                ctx.skip_dialog()
            else:
                raise ue.Exception("cs_classification_err_only_catalog_properties_allowed")

    def handle_catalog_dragdrop_post(self, ctx):
        # This code is for proper drag & drop of multiple catalog properties into classes.
        # It handles the platform behaviour, that the type select operation runs only once
        # for all dropped objects, if the drop target is a relationship result table and not
        # a relationship node within a structure view.
        # In this case the create operations for all dropped objects run with the same class,
        # which has been determined by the first type select call. As a result the cdb_classname
        # attribute and other type specific attributes of the newly created object are wrong or empty.
        # The following code repairs these attributes afterwards.
        if ctx.dragdrop_op_count > 1:
            catalog_prop = catalog.Property.ByKeys(cdb_object_id=ctx.dragged_obj.cdb_object_id)
            if catalog_prop:
                args = catalog_prop.getClassDefaults()
                clazz = type_map[catalog_prop.getType()]
                args["cdb_classname"] = clazz._getClassname()
                self.getPersistentObject().Update(**args)

    def has_object_property_values(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            from_str = "FROM dual"
        else:
            from_str = ""
        stmt = "SELECT 1 AS cnt %s WHERE EXISTS (SELECT * FROM cs_object_property_value WHERE property_code = '%s')"\
               % (from_str, self.code)
        rset = sqlapi.RecordSet2(sql=stmt)
        return len(rset) > 0

    def allow_delete(self, ctx):
        clazz = self.Class
        if clazz and not clazz.has_object_classifications():
            # the property can be deleted if there are no object classifications
            return

        if self.has_object_property_values():
            raise ue.Exception("cs_classification_class_property_delete")

    def delete_group_assignments(self, ctx):
        sqlapi.SQLdelete(
            "from cs_property_group_assign where property_object_id = '%s'" % self.cdb_object_id
        )

    def delete_prop_value_excludes(self, ctx):
        sqlapi.SQLdelete(
            "from cs_property_value_exclude where class_property_id = '%s'" % self.cdb_object_id
        )

    def delete_table_columns(self, ctx):
        sqlapi.SQLdelete(
            "from cs_class_table_columns where class_property_id = '%s'" % self.cdb_object_id
        )

    def check_for_variants_is_not_multivalued(self, _):
        if self.is_multivalued and self.for_variants:
            raise ue.Exception("cs_classification_class_property_multivalue_and_for_variants")

    event_map = {
        ('create', 'pre'): 'set_defaults',
        (('create', 'modify'), 'pre'): ('check_for_variants_is_not_multivalued'),
        (('create', 'copy'), 'pre'): ('set_initial_status'),
        (('create', 'copy'), 'pre_mask'): ('disable_default', 'preset_position', 'preset_class'),
        ('create', 'pre_mask'): ('handle_catalog_dragdrop'),
        ('create', 'post'): 'handle_catalog_dragdrop_post',
        ('delete', 'pre'): 'allow_delete',
        ('delete', 'post'): ('delete_group_assignments', 'delete_prop_value_excludes', 'delete_table_columns'),
        ('modify', 'pre_mask'): 'set_fields_readonly',
        ('cs_classification_catalog_prop', 'now'): 'copy_from_catalog',
        ('cs_classification_catalog_prop_w', 'now'): 'copy_from_catalog_web'
    }


class TextClassProperty(ClassProperty):
    __classname__ = "cs_text_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "text"

    @classmethod
    def get_value_col(cls):
        return "text_value"

    def validate_pattern(self, ctx):
        text_prop_pattern = self.pattern
        should_validate = False

        if "pattern" not in ctx.object.get_attribute_names():
            # Its new
            if text_prop_pattern != "":
                # Its not empty
                should_validate = True
        elif text_prop_pattern != ctx.object.pattern:
            # Its now new and the pattern has changed
            should_validate = True
        if should_validate:
            regex = Pattern.create_reg_ex(text_prop_pattern)
            self.regex = regex

    event_map = {
        (('create', 'modify'), 'pre'): ('validate_pattern')
    }


class BooleanClassProperty(ClassProperty):
    __classname__ = "cs_boolean_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "boolean"

    @classmethod
    def get_value_col(cls):
        return "boolean_value"


class DatetimeClassProperty(ClassProperty):
    __classname__ = "cs_datetime_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "datetime"

    @classmethod
    def get_value_col(cls):
        return "datetime_value"


class IntegerClassProperty(ClassProperty):
    __classname__ = "cs_integer_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "integer"

    @classmethod
    def get_value_col(cls):
        return "integer_value"


class FloatClassProperty(ClassProperty):
    __classname__ = "cs_float_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "float"

    @classmethod
    def get_value_col(cls):
        return "float_value"

    def change_unit_fields(self, ctx):
        if self.unit_object_id:
            ctx.set_mandatory('default_unit_object_id')
        else:
            ctx.set_fields_readonly(['default_unit_object_id', 'is_unit_changeable'])

    event_map = {
        (('modify'), 'pre_mask'): 'change_unit_fields'
    }


class FloatRangeClassProperty(ClassProperty):
    __classname__ = "cs_float_range_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "float_range"

    @classmethod
    def get_value_col(cls):
        # FIXME: ranges
        return "float_value"

    def change_unit_fields(self, ctx):
        if self.unit_object_id:
            ctx.set_mandatory('default_unit_object_id')
        else:
            ctx.set_fields_readonly(
                ['default_unit_object_id', 'is_unit_changeable'])

    event_map = {
        (('modify'), 'pre_mask'): 'change_unit_fields'
    }


class MultilangClassProperty(ClassProperty):
    __classname__ = "cs_multi_lang_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "multilang"

    @classmethod
    def get_value_col(cls):
        return "text_value"


class ObjectReferenceClassProperty(ClassProperty):
    __classname__ = "cs_object_ref_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "objectref"

    @classmethod
    def get_value_col(cls):
        return "object_reference_value"


class BlockClassProperty(ClassProperty):
    __classname__ = "cs_block_class_property"
    __match__ = ClassProperty.cdb_classname >= __classname__

    BlockPropertyAssignments = references.Reference_N(fBlockPropertyAssignment,
                                                      fBlockPropertyAssignment.block_property_code == fBlockClassProperty.code)

    @classmethod
    def getType(cls):
        return "block"

    def has_object_property_values(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            from_str = "FROM dual"
        else:
            from_str = ""
        stmt = "SELECT 1 AS cnt %s WHERE EXISTS (SELECT * FROM cs_object_property_value " \
               "WHERE property_path like '%s/%%' OR property_path like '%s:%%/%%')" % (from_str, self.code, self.code)
        rset = sqlapi.RecordSet2(sql=stmt)
        return len(rset) > 0

    def set_readonly(self, ctx):
        if ctx.dialog['is_multivalued'] == '1':
            if ctx.dialog['key_property_code']:
                ctx.set_writeable('create_block_variants')
            else:
                ctx.set_readonly('create_block_variants')
        else:
            ctx.set_readonly('create_block_variants')

    event_map = {
        (('create', 'modify', 'copy'), ('pre_mask', 'dialogitem_change')): 'set_readonly'
    }


class_prop_value_map = {
    DatetimeClassProperty.__classname__: catalog.DatetimePropertyValue.__classname__,
    FloatClassProperty.__classname__: catalog.FloatPropertyValue.__classname__,
    FloatRangeClassProperty.__classname__: catalog.FloatRangePropertyValue.__classname__,
    IntegerClassProperty.__classname__: catalog.IntegerPropertyValue.__classname__,
    MultilangClassProperty.__classname__: catalog.MultilangPropertyValue.__classname__,
    ObjectReferenceClassProperty.__classname__: catalog.ObjectRefPropertyValue.__classname__,
    TextClassProperty.__classname__: catalog.TextPropertyValue.__classname__,
}

class_prop_value_column_map = {
    DatetimeClassProperty.__classname__: "datetime_value",
    FloatClassProperty.__classname__: "float_value",
    FloatRangeClassProperty.__classname__: "min_float_value",
    IntegerClassProperty.__classname__: "integer_value",
    MultilangClassProperty.__classname__: "multilang_value",
    ObjectReferenceClassProperty.__classname__: "object_reference_value",
    TextClassProperty.__classname__: "text_value",
}


type_map = {

    "text": TextClassProperty,
    "boolean": BooleanClassProperty,
    "datetime": DatetimeClassProperty,
    "integer": IntegerClassProperty,
    "float": FloatClassProperty,
    "float_range": FloatRangeClassProperty,
    "multilang": MultilangClassProperty,
    "objectref": ObjectReferenceClassProperty,
    "block": BlockClassProperty
}

classname_type_map = {
    "cs_text_class_property": "text",
    "cs_boolean_class_property": "boolean",
    "cs_datetime_class_property": "datetime",
    "cs_integer_class_property": "integer",
    "cs_float_class_property": "float",
    "cs_float_range_class_property": "float_range",
    "cs_multi_lang_class_property": "multilang",
    "cs_object_ref_class_property": "objectref",
    "cs_block_class_property": "block"
}


class DocumentAssignment(Object):
    __maps_to__ = "cs_classification_class2docume"
    __classname__ = "cs_classification_class2document"

    @classmethod
    def get_next_position(cls, classification_class_id):
        stmt = "max(pos) FROM cs_classification_class2docume WHERE classification_class_id='%s'" \
               % classification_class_id
        t = sqlapi.SQLselect(stmt)
        max_position = 0
        if not sqlapi.SQLnull(t, 0, 0):
            max_position = sqlapi.SQLinteger(t, 0, 0)
        return max_position + 10

    def on_create_pre_mask(self, ctx):
        if ctx.relationship_name == 'cs_classification_class2document':
            self.pos = DocumentAssignment.get_next_position(ctx.parent.cdb_object_id)


class ModelAssignment(Object):
    __maps_to__ = "cs_classification_class2model"
    __classname__ = "cs_classification_class2model"

    Class = references.Reference_1(
        ClassificationClass, fModelAssignment.classification_class_id
    )

    Model = references.Reference_1(Document, fModelAssignment.z_nummer, fModelAssignment.z_index)


class ClassPropertyGroup(Object):
    __maps_to__ = "cs_class_property_group"
    __classname__ = "cs_class_property_group"


POSITION_NOT_SET_MARKER = -1000000

class PropertyGroupAssignment(Object):
    __maps_to__ = "cs_property_group_assign"
    __classname__ = "cs_property_group_assign"

    @classmethod
    def get_next_position(cls, group_object_id):
        stmt = "max(position) FROM cs_property_group_assign WHERE group_object_id='%s'" \
               % group_object_id
        t = sqlapi.SQLselect(stmt)

        max_position = 0
        if not sqlapi.SQLnull(t, 0, 0):
            max_position = sqlapi.SQLinteger(t, 0, 0)
        return max_position + 10

    def on_create_pre_mask(self, ctx):
        if ctx.relationship_name == 'cs_class_property_group2properties':
            if ctx.dragdrop_op_count:
                # for search and assign all pre mask user exits are called at the beginning in webui
                # set a marker to set the correct position in pre user exit.
                self.position = POSITION_NOT_SET_MARKER
            else:
                self.position = PropertyGroupAssignment.get_next_position(ctx.parent.cdb_object_id)
            grp = ClassPropertyGroup.ByKeys(self.group_object_id)
            ctx.set("classification_class_id", grp.classification_class_id)

    def on_create_pre(self, ctx):
        # property must belong to the class or a base class of the group
        grp = ClassPropertyGroup.ByKeys(self.group_object_id)
        valid_class_ids = ClassificationClass.get_base_class_ids(
            class_ids=[grp.classification_class_id], include_given=True
        )
        prop = ClassProperty.ByKeys(self.property_object_id)
        if prop.classification_class_id not in valid_class_ids:
            raise ue.Exception(
                'cs_classification_err_prop_group_assign',
                ClassificationClass.oid_to_code(grp.classification_class_id)
            )
        if self.position == POSITION_NOT_SET_MARKER:
            self.position = PropertyGroupAssignment.get_next_position(ctx.parent.cdb_object_id)


class TableColumnsAssignment(Object):
    __maps_to__ = "cs_class_table_columns"
    __classname__ = "cs_class_table_columns"

    @classmethod
    def get_next_position(cls, classification_class_id):
        stmt = "max(pos) FROM cs_class_table_columns WHERE classification_class_id='%s'" \
               % classification_class_id
        t = sqlapi.SQLselect(stmt)

        max_position = 0
        if not sqlapi.SQLnull(t, 0, 0):
            max_position = sqlapi.SQLinteger(t, 0, 0)
        return max_position + 10

    def on_create_pre_mask(self, ctx):
        if ctx.relationship_name == 'cs_classification_class2table_column':
            if ctx.dragdrop_op_count:
                # for search and assign all pre mask user exits are called at the beginning in webui
                # set a marker to set the correct position in pre user exit.
                self.pos =POSITION_NOT_SET_MARKER
            else:
                self.pos = TableColumnsAssignment.get_next_position(ctx.parent.cdb_object_id)

    def on_create_pre(self, ctx):
        # property must belong to the class or a base class of the group
        valid_class_ids = ClassificationClass.get_base_class_ids(
            class_ids=[self.classification_class_id], include_given=True
        )
        prop = ClassProperty.ByKeys(self.class_property_id)
        if prop.classification_class_id not in valid_class_ids:
            raise ue.Exception(
                'cs_classification_err_prop_group_assign',
                ClassificationClass.oid_to_code(self.classification_class_id)
            )
        if self.pos == POSITION_NOT_SET_MARKER:
            self.pos = TableColumnsAssignment.get_next_position(ctx.parent.cdb_object_id)


DisplayOption = namedtuple("DisplayOption", "id label")


class DisplayOptions(object):
    NewLine = DisplayOption(0, "New Line")
    NewLineSep = DisplayOption(1, "New Line & Separator")
    InLine = DisplayOption(2, "In-Line")

    all_display_options = [NewLine, NewLineSep, InLine]

    @classmethod
    def by_label(cls, label):
        if label:
            for opt in cls.all_display_options:
                if opt.label == label:
                    return opt
        return cls.NewLine


class ClassPropertyTypeSelector(TypeSelector):

    def on_object_dragdrop_pre_mask(self):
        return False

    def on_object_dragdrop_pre(self):
        clazz = type_map[catalog.classname_type_map[self.ctx.dragged_obj.cdb_classname]]
        self.set_new_class(clazz._getClassname())


class ClassPropertiesCatalog(gui.CDBCatalog):

    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def get_value(self, key):
        try:
            return self.getInvokingDlgValue(key)
        except KeyError:
            return None

    def init(self):
        classification_class = None
        classification_class_id = self.get_value("classification_class_id")

        if classification_class_id:
            classification_class = ClassificationClass.ByKeys(cdb_object_id=classification_class_id)
        else:
            group_object_id = self.get_value("group_object_id")
            cdb_object_id = self.get_value("cdb_object_id")
            if group_object_id:
                parent_obj = ClassPropertyGroup.ByKeys(cdb_object_id=group_object_id)
            elif cdb_object_id:
                parent_obj = ByID(cdb_object_id)
            else:
                parent_obj = None

            if isinstance(parent_obj, ClassPropertyGroup):
                classification_class = ClassificationClass.ByKeys(
                    cdb_object_id=parent_obj.classification_class_id
                )
            elif isinstance(parent_obj, ClassificationClass):
                classification_class = parent_obj
            else:
                classification_class = None

        self.setResultData(ClassPropertiesCatalogContent(classification_class, self))


class ClassPropertiesCatalogContent(gui.CDBCatalogContent):

    def __init__(self, classification_class, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        gui.CDBCatalogContent.__init__(self, tabdef)
        self._data = []
        if classification_class:
            self._data = classification_class.Properties

    def getNumberOfRows(self):
        return len(self._data)

    def getRowObject(self, row):
        return self._data[row].ToObjectHandle()
