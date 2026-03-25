# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import json

from cdb import ElementsError, objects


class VariantsError(ElementsError):
    pass


class InvalidPropertyCode(VariantsError):
    def __init__(self, prop_code):
        super().__init__("Invalid preset: property %s does not exist" % (prop_code))


class InvalidPresets(VariantsError):
    def __init__(self, prop_code, value):
        super().__init__(
            "Invalid preset: property %s " "has not the value %s" % (prop_code, value)
        )


class NotAnInstanceException(VariantsError):
    def __init__(self, part):
        super().__init__(
            "The part (%s) is not an instance of a maxbom" % part.GetDescription()
        )
        self.part = part


class NotAllowedToReinstantiateError(VariantsError):
    def __init__(self, part):
        super().__init__(
            "Not allowed to reinstante part: {0}".format(part.GetDescription())
        )

        self.part = part


class MultiplePartsReinstantiateWithFailedPartsError(VariantsError):
    def __init__(self, all_parts, failed_parts_exceptions):
        self.all_parts_lookup = {each.cdb_object_id: each for each in all_parts}
        self.failed_parts_exceptions = failed_parts_exceptions

        super().__init__(
            "Reinstantiate for {0} parts out of {1} parts failed.\n{2}".format(
                len(self.failed_parts_exceptions),
                len(self.all_parts_lookup),
                "\n".join(
                    [
                        "{0}: {1}".format(
                            self.all_parts_lookup[x].GetDescription(),
                            self.failed_parts_exceptions[x],
                        )
                        for x in self.failed_parts_exceptions
                    ]
                ),
            )
        )


class VariantIncompleteError(VariantsError):
    def __init__(self, variant):
        super().__init__(
            "Not all variant driving properties for variant (id: {0}, variability_model: {1}) are set".format(
                variant.id, variant.variability_model_id
            )
        )


class SelectionConditionEvaluationError(VariantsError):
    def __init__(
        self,
        message,
        ref_object_id=None,
        properties=None,
        selection_condition_cdb_object_id=None,
    ):
        self.ref_object_id = ref_object_id
        self.properties = {} if properties is None else properties
        self.selection_condition_cdb_object_id = selection_condition_cdb_object_id

        super().__init__(message)

    def build_message(self):
        ref_object_db_info = None
        if self.ref_object_id is not None:
            ref_object_object = objects.ByID(self.ref_object_id)

            if ref_object_object is not None:
                ref_object_db_info = ref_object_object.DBInfo()
            else:
                ref_object_db_info = self.ref_object_id

        selection_condition_db_info = None
        if self.selection_condition_cdb_object_id is not None:
            selection_condition_object = objects.ByID(
                self.selection_condition_cdb_object_id
            )

            if selection_condition_object is not None:
                selection_condition_db_info = selection_condition_object.DBInfo()
            else:
                selection_condition_db_info = self.selection_condition_cdb_object_id

        return """{original_message}
Reference object:
{ref_object_db_info}
Selection condition:
{selection_condition_db_info}
Properties:
{properties}
""".format(
            original_message=str(self),
            ref_object_db_info=ref_object_db_info,
            selection_condition_db_info=selection_condition_db_info,
            properties=json.dumps(self.properties, indent=2),
        )
