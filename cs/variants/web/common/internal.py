# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
from webob import exc

from cdb.objects import ByID
from cs.classification.object_classification import ClassificationData
from cs.classification.rest import utils as classification_rest_utils
from cs.platform.web import JsonAPI, root
from cs.platform.web.rest import get_collection_app
from cs.variants import VariabilityModel, Variant
from cs.variants.api import VariantsClassification
from cs.variants.selection_condition import SelectionCondition


class VariantsCommonInternal(JsonAPI):
    pass


@root.Internal.mount(app=VariantsCommonInternal, path="variant_filter")
def _mount_internal():
    return VariantsCommonInternal()


@VariantsCommonInternal.path(
    path="variant_by_id/{variant_id}/variability_model/{variability_model_id}"
)
class VariantById:
    def __init__(self, variant_id, variability_model_id):
        self.variant = Variant.ByKeys(
            id=variant_id, variability_model_id=variability_model_id
        )
        if self.variant is None:
            raise exc.HTTPNotFound("Variant not found")

        self.variability_model = VariabilityModel.ByKeys(
            cdb_object_id=variability_model_id
        )
        if self.variability_model is None:
            raise exc.HTTPNotFound()

    def get_variant_by_id(self, request):
        variant_as_json_response = request.view(
            self.variant, app=get_collection_app(request)
        )
        data = ClassificationData(
            self.variant,
            class_codes=[self.variability_model.class_code],
            request=request,
        )
        values, _, _ = data.get_classification()

        variants_classification = VariantsClassification(
            [self.variability_model.class_code]
        )
        properties = variants_classification.get_variant_driving_properties_by_class()

        variant_driving_classification = {}
        for property_definition in properties[self.variability_model.class_code]:
            code = property_definition["code"]
            variant_driving_classification[code] = values[code]

        return {
            "object": variant_as_json_response,
            "classification": classification_rest_utils.ensure_json_serialiability(
                variant_driving_classification
            ),
        }


@VariantsCommonInternal.json(model=VariantById)
def variant_by_id(model, request):
    return model.get_variant_by_id(request)


class VariantsSelectionConditionInternal(JsonAPI):
    pass


@root.Internal.mount(app=VariantsSelectionConditionInternal, path="selection_condition")
def _mount_internal_selection_condition():
    return VariantsSelectionConditionInternal()


@VariantsSelectionConditionInternal.path(path="by_keys")
class SelectionConditionWithPermission:
    def __init__(self, variability_model_id=None, ref_object_id=None):
        self.selection_condition = SelectionCondition.ByKeys(
            variability_model_id=variability_model_id,
            ref_object_id=ref_object_id,
        )

        self.reference_object = ByID(ref_object_id)
        if self.reference_object is None:
            raise exc.HTTPNotFound(
                "Not able to reference object for selection condition"
            )

    @staticmethod
    def get_permission_of_object(obj):
        return obj.CheckAccess("save") if obj is not None else False

    def get_selection_condition_with_permission(self, request):
        result = {
            "object": request.view(
                self.selection_condition, app=get_collection_app(request)
            ),
            "permission": self.get_permission_of_object(self.reference_object),
        }

        return result


@VariantsSelectionConditionInternal.json(model=SelectionConditionWithPermission)
def selection_condition_with_permission(model, request):
    return model.get_selection_condition_with_permission(request)
