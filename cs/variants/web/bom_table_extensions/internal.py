#  -*- mode: python; coding: utf-8 -*-

#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

#
import json

from cdb.objects import IconCache
from cs.variants.api.filter import (
    CsVariantsFilterContextPlugin,
    CsVariantsVariabilityModelContextPlugin,
    get_variant_filter,
)
from cs.vp.bom.enhancement import get_bom_enhancement_data_from_request
from cs.vp.bom.web.table.internal import TableInternal, TableInternalBomItemOccurrences


class _VariantsBomItemOccurrenceAttributeAccessor:
    def __init__(
        self,
        bom_item_occurrence,
        cs_variants_has_selection_condition,
    ):
        self.bom_item_occurrence = bom_item_occurrence

        self.cs_variants_has_selection_condition = (
            1 if cs_variants_has_selection_condition else 0
        )
        # Occurrence can have no alternative
        self.cs_variants_is_alternative = 0

    def __getitem__(self, name):
        if name == "cs_variants_has_selection_condition":
            return self.cs_variants_has_selection_condition
        elif name == "cs_variants_is_alternative":
            return self.cs_variants_is_alternative
        else:
            return self.bom_item_occurrence.__getitem__(name)

    def as_selection_condition_column_dict(self):
        return {
            "cdb_object_id": self.bom_item_occurrence["cdb_object_id"],
            "cs_variants_has_selection_condition": self.cs_variants_has_selection_condition,
            "selection_condition_icon": IconCache.getIcon(
                "cs_variants_selection_condition", accessor=self
            ),
        }


@TableInternal.path(path="bom_item_occurrences/cs.variants")
class TableInternalBomItemOccurrencesWithVariabilityModel(
    TableInternalBomItemOccurrences
):
    SCOPE = "cs.variants.TableInternalBomItemOccurrencesWithVariabilityModel"

    def __init__(self):
        super().__init__()

        self.variability_model_id = None
        self.variant_filter = None

    def get_additional_select_statement(self):
        return """,
                CASE
                    WHEN EXISTS (
                        SELECT 42
                        FROM cs_selection_condition sc
                        WHERE sc.ref_object_id=o.cdb_object_id
                            AND sc.variability_model_id='{variability_model_id}'
                    ) THEN 1
                    ELSE 0
                END has_selection_condition_on_oc
        """.format(
            variability_model_id=self.variability_model_id
        )

    def additional_values(self, bom_item_occurrence):
        accessor = _VariantsBomItemOccurrenceAttributeAccessor(
            bom_item_occurrence, bom_item_occurrence["has_selection_condition_on_oc"]
        )

        return {
            "selection_condition": json.dumps(
                accessor.as_selection_condition_column_dict()
            )
        }

    def filter_query_results(self, bom_item_occurrences):
        if self.variant_filter is not None:
            return [
                each
                for each in bom_item_occurrences
                if self.variant_filter.eval_bom_item(each)
            ]

        return super().filter_query_results(bom_item_occurrences)

    def get_table_data(self, request):
        bom_enhancement_data = get_bom_enhancement_data_from_request(request)

        if (
            CsVariantsVariabilityModelContextPlugin.DISCRIMINATOR
            in bom_enhancement_data
        ):
            var_model_id = CsVariantsVariabilityModelContextPlugin.get_variability_model_id_from_rest_data(
                bom_enhancement_data[
                    CsVariantsVariabilityModelContextPlugin.DISCRIMINATOR
                ]
            )
            self.variability_model_id = var_model_id

        if (
            self.variability_model_id is not None
            and CsVariantsFilterContextPlugin.DISCRIMINATOR in bom_enhancement_data
        ):
            (
                variant_id,
                classification_properties,
            ) = CsVariantsFilterContextPlugin.get_filter_context_data_from_rest_data(
                bom_enhancement_data[CsVariantsFilterContextPlugin.DISCRIMINATOR]
            )
            self.variant_filter = get_variant_filter(
                self.variability_model_id, variant_id, classification_properties
            )

        return super().get_table_data(request)


@TableInternal.json(
    model=TableInternalBomItemOccurrencesWithVariabilityModel, request_method="POST"
)
def json_post_bom_item_occurrences_with_variability_model(model, request):
    return model.get_table_data(request)
