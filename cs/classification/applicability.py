# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module classes

This is the documentation for the applicability module.
"""

from cdb import kernel, sqlapi, ue, util
from cdb.objects import Object
from cdb.objects import references
from cdb.objects import expressions
import six

fClassificationClass = expressions.Forward("cs.classification.classes.ClassificationClass")
fClassificationApplicability = expressions.Forward("cs.classification.applicability.ClassificationApplicability")
fClassificationReferenceApplicability = expressions.Forward(
    "cs.classification.applicability.ClassificationReferenceApplicability")


class ClassificationApplicability(Object):
    __maps_to__ = "cs_classification_applicabilit"
    __classname__ = "cs_classification_applicability"

    ClassificationClass = references.Reference_1(fClassificationClass,
                                                 fClassificationClass.cdb_object_id ==
                                                 fClassificationApplicability.classification_class_id)

    def check_if_object_classification_exists(self, ctx):
        from cdb import ElementsError
        from cdbwrapc import CDBClassDef
        from cs.classification import classes, ObjectClassification, tools

        try:
            cldef = CDBClassDef(self.dd_classname)
            class_names = [self.dd_classname] + list(cldef.getBaseClassNames())
            dd_relation = kernel.getPrimaryTableForClass(self.dd_classname)
        except ElementsError:
            return

        base_class_ids = classes.ClassificationClass.get_base_class_ids(
            class_ids=[self.classification_class_id]
        )
        if base_class_ids:
            stmt = "SELECT classification_class_id FROM cs_classification_applicabilit WHERE {} and {}".format(
                tools.format_in_condition("classification_class_id", base_class_ids),
                tools.format_in_condition("dd_classname", class_names)
            )
            if len(sqlapi.RecordSet2(sql=stmt)):
                # If at least one classification base class is still assigned, the sub class assignment
                # can be removed. Assignments are inherited.
                return

        classification_class = self.ClassificationClass
        direct_applicable_class_codes = classes.ClassificationClass.get_direct_applicable_class_codes(
            self.dd_classname, only_active=False, only_released=False
        )
        if direct_applicable_class_codes:
            applicable_class_codes = direct_applicable_class_codes.union(
                classes.ClassificationClass.get_sub_class_codes(class_codes=direct_applicable_class_codes)
            )
        else:
            applicable_class_codes = direct_applicable_class_codes
        direct_applicable_class_codes_after_delete = set(direct_applicable_class_codes)
        direct_applicable_class_codes_after_delete.remove(classification_class.code)
        if direct_applicable_class_codes_after_delete:
            applicable_class_codes_after_delete = direct_applicable_class_codes_after_delete.union(
                classes.ClassificationClass.get_sub_class_codes(
                    class_codes=direct_applicable_class_codes_after_delete
                )
            )
        else:
            applicable_class_codes_after_delete = direct_applicable_class_codes_after_delete
        deleted_applicabilities = list(applicable_class_codes - applicable_class_codes_after_delete)
        for class_codes in tools.chunk(deleted_applicabilities, 10000):
            sql_stmt = """
                SELECT ref_object_id FROM cs_object_classification
                JOIN cdb_object on cs_object_classification.ref_object_id = cdb_object.id
                WHERE cdb_object.relation = '%s' and %s
            """ % (dd_relation, ObjectClassification.class_code.one_of(*class_codes))

            if tools.exists_query(sql_stmt):
                raise ue.Exception("cs_classification_delete_class_applicability_error")

    event_map = {
        ('delete', 'pre'): 'check_if_object_classification_exists'
    }


class ClassificationReferenceApplicability(Object):
    __maps_to__ = "cs_classification_ref_appl"
    __classname__ = "cs_classification_ref_appl"

    def _get_property(self):
        from cdb.objects import ByID
        return ByID(self.property_id)

    # TODO fix target (Object)?
    Property = references.ReferenceMethods_1(Object, _get_property)


class ObjectTypeNotApplicableError(ValueError):
    pass


def check_object_type_applicability(prop, value):
    """
    Checks if an object can be applied to a given object reference property

    :param prop: an object reference property
    :param value: the object (or it's id) to apply to the given object reference property

    :raises ObjectTypeNotApplicableError: if the object cannot be applied to the reference property
    """
    from cs.classification import catalog, classes
    from cdb.objects import ByID

    if isinstance(prop, (catalog.ObjectReferenceProperty, classes.ObjectReferenceClassProperty)):
        # check if the object reference can be created based on the configuration of the property
        allowed_classnames = ClassificationReferenceApplicability.KeywordQuery(
            property_id=prop.cdb_object_id).dd_classname

        if value is None:
            # want to set property value `None`, so do nothing
            return
        elif isinstance(value, (str, Object)):
            # single value property or single value of multivalue property

            if isinstance(value, str):
                value = ByID(value)
            if value is not None and len(allowed_classnames) > 0 and value.GetClassname() not in allowed_classnames:
                label = util.CDBMsg(util.CDBMsg.kFatal, "cs_classification_type_not_applicable")
                raise ObjectTypeNotApplicableError(str(label))
        else:
            # should not happen
            raise TypeError("Need string for check, got '%s'", type(value))
