# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
REST API for variant management. It provides resources to:

- Solve a variability model
- Solve a variability model view
- Solve both a variability model and one or more views combined
- Evaluate a BOM position for a variant
- TODO: Filter a maximum BOM for a variant
- TODO: Instantiate a maximum BOM for a variant
"""

from __future__ import unicode_literals

import itertools
import sys

from webob import exc

from cdb import sqlapi
from cs.classification import api as classification_api
from cs.classification import classes, util
from cs.classification.validation import ClassificationValidator
from cs.platform.web import JsonAPI, root
from cs.variants import (
    NO_VARIANT_ID,
    VARIANT_STATUS_INVALID,
    VARIANT_STATUS_OK,
    VariabilityModel,
    Variant,
    VariantPart,
)
from cs.variants import api as variants_api
from cs.variants import classification_helper
from cs.variants import exceptions as variants_exceptions
from cs.variants.api.filter import CsVariantsFilterContextPlugin
from cs.variants.api.variants_classification import VariantsClassification
from cs.variants.web.editor import STATUS_FILTER_DISCRIMINATOR

VIEWS_SEPARATOR = ";"


class VariantsAPI(JsonAPI):
    """
    App for public variants api. e.g.

    http://localhost/api/cs.variants/v1/
    """


@root.Api.mount(app=VariantsAPI, path="cs.variants/v1")
def mount_variants_api_app():
    return VariantsAPI()


class VariabilityModelModel:
    def __init__(self, variability_model_oid=None):
        self.variability_model = VariabilityModel.ByKeys(
            cdb_object_id=variability_model_oid
        )

        if self.variability_model is None:
            raise exc.HTTPNotFound()


@VariantsAPI.path(
    path="variability_model/{variability_model_oid}", model=VariabilityModelModel
)
def variability_model_path(_, variability_model_oid):
    return VariabilityModelModel(variability_model_oid=variability_model_oid)


def should_filter_variant(presets, classification_data):
    try:
        for preset_prop_key, preset_values in presets.items():
            # Multiple not support so hard code to index 0
            preset_value = preset_values[0]
            if classification_helper.has_property_entry_none_value(preset_value):
                # Ignoring none in presets for filtering!
                continue

            if not util.are_property_values_equal(
                preset_value["property_type"],
                preset_value["value"],
                # Multiple not support so hard code to index 0
                classification_data[preset_prop_key][0]["value"],
            ):
                return True
    except KeyError:
        return True

    return False


def compatible_status(variant, status_filter):
    # TODO: Check for manually created variants.
    if variant["status"] == VARIANT_STATUS_OK:
        if "saved" in status_filter and not status_filter["saved"]:
            return False

    if variant["status"] == VARIANT_STATUS_INVALID:
        if "invalid" in status_filter and not status_filter["invalid"]:
            return False

    return True


def is_incomplete(classification, compatability_kwarg=None):
    """
    For compatability reasons (mainly with cs.designpush E070936) this function needs to support two arguments
    """
    for property_code in classification:
        # No multiple allowed so hard code to index 0
        if classification_helper.has_property_entry_none_value(
            classification[property_code][0]
        ):
            return True
    return False


def extract_filter(request):
    id_filter = NO_VARIANT_ID
    presets = None
    status_filter = {}
    only_incomplete = False

    applied_filter_data = request.json.get("appliedFilterData", {})

    if CsVariantsFilterContextPlugin.DISCRIMINATOR in applied_filter_data:
        (
            variant_id,
            classification_properties,
        ) = CsVariantsFilterContextPlugin.get_filter_context_data_from_rest_data(
            applied_filter_data[CsVariantsFilterContextPlugin.DISCRIMINATOR]
        )

        if variant_id is not None:
            try:
                id_filter = int(variant_id)
            except (TypeError, ValueError) as ex:
                raise exc.HTTPBadRequest(str(ex))

        presets = classification_properties
        if presets is not None:
            try:
                classification_helper.ensure_existence_of_float_normalize(presets)
            except ValueError as ex:
                raise exc.HTTPBadRequest(str(ex))

    try:
        status_filter_data = applied_filter_data[STATUS_FILTER_DISCRIMINATOR]
    except KeyError:
        status_filter_data = None

    if status_filter_data is not None:
        status_filter = status_filter_data
        only_incomplete = status_filter_data.get("onlyIncomplete", False)

    return id_filter, presets, status_filter, only_incomplete


@VariantsAPI.json(model=VariabilityModelModel, name="solve", request_method="POST")
def solve(model, request):
    # pylint: disable=too-many-locals, too-many-nested-blocks, too-many-branches, too-many-statements

    collection_app = root.get_v1(request).child("collection")
    result_solutions = []
    variant_complete = True

    try:
        json_payload = request.json
    except ValueError:
        json_payload = None

    if json_payload is None:
        json_payload = {}

    limit = json_payload.get("limit")
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError) as ex:
            raise exc.HTTPBadRequest(str(ex))

    id_filter, presets, status_filter, only_incomplete = extract_filter(request)
    result = {"solutions": result_solutions, "complete": variant_complete}

    ClassificationValidator.reload_constraints()

    variability_model = model.variability_model
    class_codes = [variability_model.class_code]

    variants_classification = VariantsClassification(class_codes)

    variants = variants_classification.get_variants_classification(
        variability_model, add_enum_labels=True
    )

    instance_count_query = sqlapi.RecordSet2(
        table=VariantPart.GetTableName(),
        condition=(VariantPart.variability_model_id == variability_model.cdb_object_id),
        columns=["COUNT(variant_id) as count", "variant_id"],
        addtl="GROUP BY variant_id",
    )
    instance_count_map = {r.variant_id: r.count for r in instance_count_query}

    for variant in variants:
        if presets is None or not should_filter_variant(
            presets, variant["classification"]
        ):
            if compatible_status(variant, status_filter):
                if not only_incomplete or is_incomplete(variant["classification"]):
                    if (
                        id_filter == NO_VARIANT_ID
                        or int(variant["variant"].id) == id_filter
                    ):
                        result_solutions.append(
                            {
                                "id": variant["variant"].cdb_object_id,
                                "variant": {
                                    "status": variant["status"],
                                    "object": request.view(
                                        variant["variant"], app=collection_app
                                    ),
                                    "relships": {
                                        "instancesCount": instance_count_map.get(
                                            variant["variant"].id, 0
                                        )
                                    },
                                },
                                "props": variant["classification"],
                            }
                        )

                        if limit is not None and len(result_solutions) >= limit:
                            break

    variant_complete = len(result_solutions) == len(variants)

    if only_incomplete:
        return result

    if "notEvaluated" in status_filter and not status_filter["notEvaluated"]:
        return result

    if id_filter > NO_VARIANT_ID:
        return result

    if model.variability_model is not None:
        try:
            solutions = variants_api.solve(
                model.variability_model,
                presets=presets,
                limit=limit,
                constrain_classification_checksum=[
                    each["variant"]["classification_checksum"] for each in variants
                ],
            )
        except variants_exceptions.InvalidPropertyCode as ex:
            raise exc.HTTPBadRequest(str(ex))
        except variants_exceptions.InvalidPresets:
            return result
    else:
        raise exc.HTTPNotFound()

    remaining_count = (
        max(0, limit - len(result_solutions)) if limit is not None else sys.maxsize
    )
    solutions_slice = itertools.islice(solutions, remaining_count)

    for solution, checksum in solutions_slice:
        result_solutions.append(
            {
                "id": checksum,
                "props": solution,
            }
        )

    result["complete"] = variant_complete and solutions.complete
    return result


class VariantModel:
    def __init__(self, variant_object_id):
        self.variant = Variant.ByKeys(cdb_object_id=variant_object_id)


@VariantsAPI.path(path="variant/{variant_object_id}", model=VariantModel)
def get_variant_api(app, variant_object_id):
    return VariantModel(variant_object_id=variant_object_id)


@VariantsAPI.json(model=VariantModel, name="validate", request_method="POST")
def validate_variant(model, request):
    data = request.json
    class_codes = classes.ClassificationClass.get_base_class_codes(
        class_codes=data["class_codes"], include_given=True
    )
    classification_data = classification_api.get_classification(
        model.variant.cdb_object_id, narrowed=False
    )
    # FIXME: ensure that cache always contains actual constraints
    ClassificationValidator.reload_constraints()
    violated_constraints = ClassificationValidator.check_violated_constraints(
        class_codes, classification_data["properties"]
    )
    return {"violated_constraints": violated_constraints}
