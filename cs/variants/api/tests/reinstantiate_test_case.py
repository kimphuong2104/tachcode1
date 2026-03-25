#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

from cs.variants import VariabilityModel, Variant
from cs.variants.api.tests.base_test_case import BaseTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure
from cs.vp import items
from cs.vp.bom import AssemblyComponent, AssemblyComponentOccurrence


# pylint: disable=too-many-instance-attributes
class ReinstantiateTestCase(BaseTestCase):
    _variability_model = None
    _var1 = None
    _var2 = None
    _maxbom = None
    _maxbom_indexed = None
    _maxbom_deep = None
    _maxbom_deep_bom_item_level5 = None
    _maxbom_deep_bom_item_occurrence2_level5 = None
    _part1 = None
    _subassembly1 = None
    _indexed_subassembly1 = None
    _bom_item_part2 = None
    _bom_item_subassembly1 = None
    _bom_item_subassembly2 = None
    _var1_part1_smaller_maxbom = None
    _var2_part1_smaller_maxbom = None
    _var1_part2_no_selection_condition = None
    _var2_part2_no_selection_condition = None
    _var1_part3 = None
    _var2_part3 = None
    _var2_part4_approved = None
    _var1_part_maxbom_deep = None
    _var2_part_maxbom_deep = None

    expression_valid_for_variant1 = 'VAR_TEST_REINSTANTIATE_VAR_TEST_TEXT == "VALUE2"'
    expression_valid_for_variant2 = 'VAR_TEST_REINSTANTIATE_VAR_TEST_TEXT == "VALUE1"'

    maxbom_id = "d98e5c4f-23ff-11eb-9218-24418cdf379c"
    maxbom_teilenummer = "9508575"
    maxbom_keys = {
        "teilenummer": maxbom_teilenummer,
        "t_index": "",
        "cdb_object_id": maxbom_id,
    }
    copy_of_maxbom_keys = {
        "!teilenummer": maxbom_teilenummer,
    }

    maxbom_indexed_id = "fa7cb8a6-a32f-11eb-b94b-98fa9bf98f6d"
    maxbom_indexed_keys = {
        "teilenummer": maxbom_teilenummer,
        "t_index": "a",
        "cdb_object_id": maxbom_indexed_id,
    }
    copy_of_maxbom_indexed_keys = {
        "!teilenummer": maxbom_teilenummer,
    }

    maxbom_deep_id = "ae11f2fa-ca9a-11eb-b955-98fa9bf98f6d"
    maxbom_deep_teilenummer = "9508596"
    maxbom_deep_keys = {
        "teilenummer": maxbom_deep_teilenummer,
        "t_index": "",
        "cdb_object_id": maxbom_deep_id,
    }
    copy_of_maxbom_deep_keys = {
        "!teilenummer": maxbom_deep_teilenummer,
    }

    maxbom_part1_keys = {"teilenummer": "9508576", "t_index": ""}
    maxbom_part1_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_PART_1_OC0"
    }

    maxbom_part2_keys = {"teilenummer": "9508580", "t_index": ""}
    maxbom_part2_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_PART_2_OC0"
    }
    maxbom_part2_occurrence2_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_PART_2_OC1"
    }

    maxbom_subassembly1_keys = {"teilenummer": "9508579", "t_index": ""}
    maxbom_subassembly1_id = "b1752105-a1d9-11eb-b94b-98fa9bf98f6d"
    maxbom_subassembly1_teilenummer = "9508579"
    copy_of_maxbom_subassembly1_keys = {
        "!teilenummer": maxbom_subassembly1_teilenummer,
        "t_index": "",
        "!cdb_object_id": maxbom_subassembly1_id,
    }
    maxbom_subassembly1_keys = {
        "teilenummer": maxbom_subassembly1_teilenummer,
        "t_index": "",
        "cdb_object_id": maxbom_subassembly1_id,
    }
    maxbom_subassembly1_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_OC0"
    }
    maxbom_indexed_subassembly1_id = "138d6582-a330-11eb-b94b-98fa9bf98f6d"
    copy_of_maxbom_indexed_subassembly1_keys = {
        "!teilenummer": "9508579",
        "t_index": "",
        "!cdb_object_id": maxbom_indexed_subassembly1_id,
    }
    maxbom_indexed_subassembly1_keys = {
        "teilenummer": "9508579",
        "t_index": "a",
        "cdb_object_id": maxbom_indexed_subassembly1_id,
    }
    maxbom_subassembly1_part1_keys = {"teilenummer": "9508582", "t_index": ""}
    maxbom_subassembly1_part1_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_P1_OC0"
    }

    maxbom_subassembly1_part2_keys = {"teilenummer": "9508583", "t_index": ""}
    maxbom_subassembly1_part2_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_P2_OC0"
    }
    maxbom_subassembly1_part2_occurrence2_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_P2_OC1"
    }

    maxbom_subassembly2_id = "131f02c0-a1da-11eb-b94b-98fa9bf98f6d"
    maxbom_subassembly2_teilenummer = "9508581"
    copy_of_maxbom_subassembly2_keys = {
        "!teilenummer": maxbom_subassembly2_teilenummer,
        "t_index": "",
        "!cdb_object_id": maxbom_subassembly2_id,
    }
    maxbom_subassembly2_keys = {
        "teilenummer": maxbom_subassembly2_teilenummer,
        "t_index": "",
        "cdb_object_id": maxbom_subassembly2_id,
    }
    maxbom_subassembly2_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_OC0"
    }
    maxbom_subassembly2_occurrence2_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_OC1"
    }
    maxbom_indexed_subassembly2_keys = {"teilenummer": "9508581", "t_index": "a"}
    maxbom_subassembly2_part1_keys = {"teilenummer": "9508584", "t_index": ""}
    maxbom_subassembly2_part1_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_P1_OC0"
    }

    maxbom_subassembly2_part2_keys = {"teilenummer": "9508585", "t_index": ""}
    maxbom_subassembly2_part2_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_P2_OC0"
    }
    maxbom_subassembly2_part2_occurrence2_keys = {
        "occurrence_id": "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_P2_OC1"
    }

    var1_part1_smaller_maxbom_keys = {
        "teilenummer": "9508577",
        "t_index": "",
    }
    var2_part1_smaller_maxbom_keys = {"teilenummer": "9508578", "t_index": ""}

    var1_part2_no_selection_condition_keys = {"teilenummer": "9508586", "t_index": ""}
    var2_part2_no_selection_condition_keys = {"teilenummer": "9508587", "t_index": ""}

    var1_part3_keys = {"teilenummer": "9508588", "t_index": ""}
    var1_part3_subassembly1_keys = {
        "teilenummer": "9508589",
        "t_index": "",
    }
    var1_part3_subassembly1_id = "ea4057fc-a1df-11eb-b94b-98fa9bf98f6d"
    var1_part3_subassembly1_bom_item_keys = {
        "cdb_object_id": "ea405803-a1df-11eb-b94b-98fa9bf98f6d",
    }

    var2_part3_keys = {"teilenummer": "9508590", "t_index": ""}
    var2_part4_approved_keys = {
        "teilenummer": "9508594",
        "t_index": "",
    }

    var1_part_maxbom_deep_keys = {
        "teilenummer": "9508603",
        "t_index": "",
    }
    var2_part_maxbom_deep_keys = {
        "teilenummer": "9508604",
        "t_index": "",
    }

    expected_maxbom_part1 = SubassemblyStructure(
        maxbom_part1_keys,
        occurrence_keys=[maxbom_part1_occurrence1_keys],
    )
    expected_maxbom_part2 = SubassemblyStructure(
        maxbom_part2_keys,
        occurrence_keys=[maxbom_part2_occurrence1_keys, maxbom_part2_occurrence2_keys],
    )

    expected_maxbom_subassembly1_part1 = SubassemblyStructure(
        maxbom_subassembly1_part1_keys,
        occurrence_keys=[maxbom_subassembly1_part1_occurrence1_keys],
    )
    expected_maxbom_subassembly1_part2 = SubassemblyStructure(
        maxbom_subassembly1_part2_keys,
        occurrence_keys=[
            maxbom_subassembly1_part2_occurrence1_keys,
            maxbom_subassembly1_part2_occurrence2_keys,
        ],
    )

    expected_subassembly1_structure = SubassemblyStructure(
        maxbom_subassembly1_keys,
        children=[
            expected_maxbom_subassembly1_part1,
            expected_maxbom_subassembly1_part2,
        ],
        occurrence_keys=[maxbom_subassembly1_occurrence1_keys],
    )
    expected_indexed_subassembly1_structure = SubassemblyStructure(
        maxbom_indexed_subassembly1_keys,
        children=[
            expected_maxbom_subassembly1_part1,
            expected_maxbom_subassembly1_part2,
        ],
        occurrence_keys=[maxbom_subassembly1_occurrence1_keys],
    )

    expected_maxbom_subassembly2_part1 = SubassemblyStructure(
        maxbom_subassembly2_part1_keys,
        occurrence_keys=[maxbom_subassembly2_part1_occurrence1_keys],
    )
    expected_maxbom_subassembly2_part2 = SubassemblyStructure(
        maxbom_subassembly2_part2_keys,
        occurrence_keys=[
            maxbom_subassembly2_part2_occurrence1_keys,
            maxbom_subassembly2_part2_occurrence2_keys,
        ],
    )

    expected_subassembly2_structure = SubassemblyStructure(
        maxbom_subassembly2_keys,
        children=[
            expected_maxbom_subassembly2_part1,
            expected_maxbom_subassembly2_part2,
        ],
        occurrence_keys=[
            maxbom_subassembly2_occurrence1_keys,
            maxbom_subassembly2_occurrence2_keys,
        ],
    )
    expected_indexed_subassembly2_structure = SubassemblyStructure(
        maxbom_indexed_subassembly2_keys,
        children=[
            expected_maxbom_subassembly2_part1,
            expected_maxbom_subassembly2_part2,
        ],
        occurrence_keys=[
            maxbom_subassembly2_occurrence1_keys,
            maxbom_subassembly2_occurrence2_keys,
        ],
    )

    maxbom_children = [
        expected_maxbom_part1,
        expected_maxbom_part2,
        expected_subassembly1_structure,
        expected_subassembly2_structure,
    ]
    expected_maxbom_structure = SubassemblyStructure(
        maxbom_keys, children=maxbom_children
    )

    maxbom_indexed_children = [
        expected_maxbom_part1,
        expected_maxbom_part2,
        expected_indexed_subassembly1_structure,
        expected_indexed_subassembly2_structure,
    ]
    expected_maxbom_indexed_structure = SubassemblyStructure(
        maxbom_indexed_keys, children=maxbom_indexed_children
    )

    maxbom_deep_part_level5_keys = {"teilenummer": "9508602", "t_index": ""}
    maxbom_deep_part_level5_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5_OC1"
    }
    maxbom_deep_part_level5_occurrence1_id = "7822f3ba-4a3f-45c3-86a3-f06187b3e9d1"
    maxbom_deep_part_level5_occurrence2_id = "df18373e-8e5e-43f3-a43c-f3f3e283b72d"
    maxbom_deep_part_level5_occurrence2_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5_OC2"
    }
    maxbom_deep_part_level5 = SubassemblyStructure(
        maxbom_deep_part_level5_keys,
        occurrence_keys=[
            maxbom_deep_part_level5_occurrence1_keys,
            maxbom_deep_part_level5_occurrence2_keys,
        ],
    )

    maxbom_deep_subassembly_level5_id = "ae11f31b-ca9a-11eb-b955-98fa9bf98f6d"
    maxbom_deep_subassembly_level5_teilenummer = "9508601"
    maxbom_deep_subassembly_level5_keys = {
        "cdb_object_id": maxbom_deep_subassembly_level5_id,
        "teilenummer": maxbom_deep_subassembly_level5_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level5_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL5_OC1"
    }
    copy_of_maxbom_deep_subassembly_level5_keys = {
        "!teilenummer": maxbom_deep_subassembly_level5_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level5 = SubassemblyStructure(
        maxbom_deep_subassembly_level5_keys,
        children=[maxbom_deep_part_level5],
        occurrence_keys=[maxbom_deep_subassembly_level5_occurrence1_keys],
    )

    maxbom_deep_subassembly_level4_id = "ae11f315-ca9a-11eb-b955-98fa9bf98f6d"
    maxbom_deep_subassembly_level4_teilenummer = "9508600"
    maxbom_deep_subassembly_level4_keys = {
        "cdb_object_id": maxbom_deep_subassembly_level4_id,
        "teilenummer": maxbom_deep_subassembly_level4_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level4_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4_OC1"
    }
    maxbom_deep_subassembly_level4_occurrence2_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4_OC2"
    }
    copy_of_maxbom_deep_subassembly_level4_keys = {
        "!teilenummer": maxbom_deep_subassembly_level4_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level4 = SubassemblyStructure(
        maxbom_deep_subassembly_level4_keys,
        children=[maxbom_deep_subassembly_level5],
        occurrence_keys=[
            maxbom_deep_subassembly_level4_occurrence1_keys,
            maxbom_deep_subassembly_level4_occurrence2_keys,
        ],
    )

    maxbom_deep_subassembly_level3_id = "ae11f30f-ca9a-11eb-b955-98fa9bf98f6d"
    maxbom_deep_subassembly_level3_teilenummer = "9508599"
    maxbom_deep_subassembly_level3_keys = {
        "cdb_object_id": maxbom_deep_subassembly_level3_id,
        "teilenummer": maxbom_deep_subassembly_level3_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level3_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL3_OC1"
    }
    copy_of_maxbom_deep_subassembly_level3_keys = {
        "!teilenummer": maxbom_deep_subassembly_level3_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level3 = SubassemblyStructure(
        maxbom_deep_subassembly_level3_keys,
        children=[maxbom_deep_subassembly_level4],
        occurrence_keys=[maxbom_deep_subassembly_level3_occurrence1_keys],
    )

    maxbom_deep_subassembly_level2_id = "ae11f309-ca9a-11eb-b955-98fa9bf98f6d"
    maxbom_deep_subassembly_level2_teilenummer = "9508598"
    maxbom_deep_subassembly_level2_keys = {
        "cdb_object_id": maxbom_deep_subassembly_level2_id,
        "teilenummer": maxbom_deep_subassembly_level2_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level2_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC1"
    }
    maxbom_deep_subassembly_level2_occurrence2_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC2"
    }
    copy_of_maxbom_deep_subassembly_level2_keys = {
        "!teilenummer": maxbom_deep_subassembly_level2_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level2 = SubassemblyStructure(
        maxbom_deep_subassembly_level2_keys,
        children=[maxbom_deep_subassembly_level3],
        occurrence_keys=[
            maxbom_deep_subassembly_level2_occurrence1_keys,
            maxbom_deep_subassembly_level2_occurrence2_keys,
        ],
    )

    maxbom_deep_subassembly_level1_id = "ae11f303-ca9a-11eb-b955-98fa9bf98f6d"
    maxbom_deep_subassembly_level1_teilenummer = "9508597"
    maxbom_deep_subassembly_level1_keys = {
        "cdb_object_id": maxbom_deep_subassembly_level1_id,
        "teilenummer": maxbom_deep_subassembly_level1_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level1_occurrence1_keys = {
        "occurrence_id": "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL1_OC1"
    }
    copy_of_maxbom_deep_subassembly_level1_keys = {
        "!teilenummer": maxbom_deep_subassembly_level1_teilenummer,
        "t_index": "",
    }
    maxbom_deep_subassembly_level1 = SubassemblyStructure(
        maxbom_deep_subassembly_level1_keys,
        children=[maxbom_deep_subassembly_level2],
        occurrence_keys=[maxbom_deep_subassembly_level1_occurrence1_keys],
    )

    expected_maxbom_deep_structure = SubassemblyStructure(
        maxbom_deep_keys, children=[maxbom_deep_subassembly_level1]
    )

    var1_part1_child_part1_bom_item_id = "8d974667-8ca5-11eb-b944-98fa9bf98f6d"
    expected_var1_part1_smaller_maxbom_structure = SubassemblyStructure(
        var1_part1_smaller_maxbom_keys,
        children=[
            SubassemblyStructure(
                maxbom_part1_keys,
                bom_item_keys={"cdb_object_id": var1_part1_child_part1_bom_item_id},
                occurrence_keys=[maxbom_part1_occurrence1_keys],
            ),
        ],
    )
    expected_var2_part1_smaller_maxbom_structure = SubassemblyStructure(
        var2_part1_smaller_maxbom_keys,
        children=[
            SubassemblyStructure(
                maxbom_part1_keys,
                bom_item_keys={"cdb_object_id": "8d9746a7-8ca5-11eb-b944-98fa9bf98f6d"},
                occurrence_keys=[maxbom_part1_occurrence1_keys],
            ),
        ],
    )

    expected_var1_part2_no_selection_condition_structure = SubassemblyStructure(
        var1_part2_no_selection_condition_keys,
        children=[
            SubassemblyStructure(
                maxbom_part1_keys,
                bom_item_keys={"cdb_object_id": "af35cca1-a1df-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[maxbom_part1_occurrence1_keys],
            ),
            SubassemblyStructure(
                maxbom_part2_keys,
                bom_item_keys={"cdb_object_id": "af35cca2-a1df-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[
                    maxbom_part2_occurrence1_keys,
                    maxbom_part2_occurrence2_keys,
                ],
            ),
            SubassemblyStructure(
                maxbom_subassembly1_keys,
                bom_item_keys={"cdb_object_id": "af35cca3-a1df-11eb-b94b-98fa9bf98f6d"},
                children=[
                    expected_maxbom_subassembly1_part1,
                    expected_maxbom_subassembly1_part2,
                ],
                occurrence_keys=[maxbom_subassembly1_occurrence1_keys],
            ),
            SubassemblyStructure(
                maxbom_subassembly2_keys,
                bom_item_keys={"cdb_object_id": "af35cca4-a1df-11eb-b94b-98fa9bf98f6d"},
                children=[
                    expected_maxbom_subassembly2_part1,
                    expected_maxbom_subassembly2_part2,
                ],
                occurrence_keys=[
                    maxbom_subassembly2_occurrence1_keys,
                    maxbom_subassembly2_occurrence2_keys,
                ],
            ),
        ],
    )
    expected_var2_part2_no_selection_condition_structure = SubassemblyStructure(
        var2_part2_no_selection_condition_keys,
        children=[
            SubassemblyStructure(
                maxbom_part1_keys,
                bom_item_keys={"cdb_object_id": "af35ccb8-a1df-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[maxbom_part1_occurrence1_keys],
            ),
            SubassemblyStructure(
                maxbom_part2_keys,
                bom_item_keys={"cdb_object_id": "af35ccb9-a1df-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[
                    maxbom_part2_occurrence1_keys,
                    maxbom_part2_occurrence2_keys,
                ],
            ),
            SubassemblyStructure(
                maxbom_subassembly1_keys,
                bom_item_keys={"cdb_object_id": "af35ccba-a1df-11eb-b94b-98fa9bf98f6d"},
                children=[
                    expected_maxbom_subassembly1_part1,
                    expected_maxbom_subassembly1_part2,
                ],
                occurrence_keys=[maxbom_subassembly1_occurrence1_keys],
            ),
            SubassemblyStructure(
                maxbom_subassembly2_keys,
                bom_item_keys={"cdb_object_id": "af35ccbb-a1df-11eb-b94b-98fa9bf98f6d"},
                children=[
                    expected_maxbom_subassembly2_part1,
                    expected_maxbom_subassembly2_part2,
                ],
                occurrence_keys=[
                    maxbom_subassembly2_occurrence1_keys,
                    maxbom_subassembly2_occurrence2_keys,
                ],
            ),
        ],
    )

    expected_var1_part3_subassembly1_structure = SubassemblyStructure(
        var1_part3_subassembly1_keys,
        bom_item_keys=var1_part3_subassembly1_bom_item_keys,
        children=[
            SubassemblyStructure(
                maxbom_subassembly1_part2_keys,
                bom_item_keys={"cdb_object_id": "ea405802-a1df-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[
                    maxbom_subassembly1_part2_occurrence1_keys,
                ],
            )
        ],
        occurrence_keys=[maxbom_subassembly1_occurrence1_keys],
    )
    expected_var1_part3_structure = SubassemblyStructure(
        var1_part3_keys,
        children=[
            SubassemblyStructure(
                maxbom_part2_keys,
                bom_item_keys={"cdb_object_id": "ea4057fb-a1df-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[
                    maxbom_part2_occurrence1_keys,
                ],
            ),
            expected_var1_part3_subassembly1_structure,
        ],
    )

    expected_var2_part3_structure = SubassemblyStructure(
        var2_part3_keys,
        [
            SubassemblyStructure(
                maxbom_part1_keys,
                bom_item_keys={"cdb_object_id": "ea405818-a1df-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[maxbom_part1_occurrence1_keys],
            ),
            SubassemblyStructure(
                maxbom_part2_keys,
                bom_item_keys={"cdb_object_id": "ea405819-a1df-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[
                    maxbom_part2_occurrence1_keys,
                    maxbom_part2_occurrence2_keys,
                ],
            ),
            SubassemblyStructure(
                maxbom_subassembly1_keys,
                bom_item_keys={"cdb_object_id": "asdasd"},
                children=[
                    expected_maxbom_subassembly1_part1,
                    expected_maxbom_subassembly1_part2,
                ],
                occurrence_keys=[maxbom_subassembly1_occurrence1_keys],
            ),
            SubassemblyStructure(
                maxbom_subassembly2_keys,
                bom_item_keys={"cdb_object_id": "asdasd"},
                children=[
                    expected_maxbom_subassembly2_part1,
                    expected_maxbom_subassembly2_part2,
                ],
                occurrence_keys=[
                    maxbom_subassembly2_occurrence1_keys,
                    maxbom_subassembly2_occurrence2_keys,
                ],
            ),
        ],
    )

    expected_var2_part4_approved_structure = SubassemblyStructure(
        var2_part4_approved_keys,
        children=[
            SubassemblyStructure(
                maxbom_part2_keys,
                bom_item_keys={"cdb_object_id": "46958fcd-a355-11eb-b94b-98fa9bf98f6d"},
                occurrence_keys=[
                    maxbom_part2_occurrence1_keys,
                    maxbom_part2_occurrence2_keys,
                ],
            ),
            SubassemblyStructure(
                copy_of_maxbom_indexed_subassembly1_keys,
                bom_item_keys={"cdb_object_id": "46958fd5-a355-11eb-b94b-98fa9bf98f6d"},
                children=[expected_maxbom_subassembly1_part2],
                occurrence_keys=[maxbom_subassembly1_occurrence1_keys],
            ),
        ],
    )

    @property
    def variability_model(self):
        if self._variability_model is None:
            self._variability_model = VariabilityModel.ByKeys(
                cdb_object_id="39a54ecc-2401-11eb-9218-24418cdf379c"
            )

        return self._variability_model

    @property
    def var1(self):
        if self._var1 is None:
            self._var1 = Variant.ByKeys(
                variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id=1
            )

        return self._var1

    @property
    def var2(self):
        if self._var2 is None:
            self._var2 = Variant.ByKeys(
                variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id=2
            )

        return self._var2

    @property
    def maxbom(self):
        if self._maxbom is None:
            self._maxbom = items.Item.ByKeys(**self.maxbom_keys)

        return self._maxbom

    @property
    def maxbom_indexed(self):
        if self._maxbom_indexed is None:
            self._maxbom_indexed = items.Item.ByKeys(**self.maxbom_indexed_keys)

        return self._maxbom_indexed

    @property
    def maxbom_deep(self):
        if self._maxbom_deep is None:
            self._maxbom_deep = items.Item.ByKeys(**self.maxbom_deep_keys)

        return self._maxbom_deep

    @property
    def maxbom_deep_bom_item_level5(self):
        if self._maxbom_deep_bom_item_level5 is None:
            bom_item_keys = {
                "baugruppe": self.maxbom_deep_subassembly_level5_teilenummer
            }
            bom_item_keys.update(self.maxbom_deep_part_level5_keys)

            self._maxbom_deep_bom_item_level5 = AssemblyComponent.ByKeys(
                **bom_item_keys
            )

        return self._maxbom_deep_bom_item_level5

    @property
    def maxbom_deep_bom_item_occurrence2_level5(self):
        if self._maxbom_deep_bom_item_occurrence2_level5 is None:
            self._maxbom_deep_bom_item_occurrence2_level5 = (
                AssemblyComponentOccurrence.ByKeys(
                    self.maxbom_deep_part_level5_occurrence2_id
                )
            )

        return self._maxbom_deep_bom_item_occurrence2_level5

    @property
    def part1(self):
        if self._part1 is None:
            self._part1 = items.Item.ByKeys(**self.maxbom_part1_keys)

        return self._part1

    @property
    def subassembly1(self):
        if self._subassembly1 is None:
            self._subassembly1 = items.Item.ByKeys(**self.maxbom_subassembly1_keys)

        return self._subassembly1

    @property
    def indexed_subassembly1(self):
        if self._indexed_subassembly1 is None:
            self._indexed_subassembly1 = items.Item.ByKeys(
                **self.maxbom_indexed_subassembly1_keys
            )

        return self._indexed_subassembly1

    @property
    def bom_item_part2(self):
        if self._bom_item_part2 is None:
            bom_item_keys = {"baugruppe": self.maxbom_teilenummer, "b_index": ""}
            bom_item_keys.update(self.maxbom_part2_keys)
            self._bom_item_part2 = AssemblyComponent.ByKeys(**bom_item_keys)

        return self._bom_item_part2

    @property
    def bom_item_subassembly1(self):
        if self._bom_item_subassembly1 is None:
            bom_item_keys = {
                "baugruppe": self.maxbom_teilenummer,
                "b_index": "",
                "teilenummer": self.maxbom_subassembly1_teilenummer,
                "t_index": "",
            }
            self._bom_item_subassembly1 = AssemblyComponent.ByKeys(**bom_item_keys)

        return self._bom_item_subassembly1

    @property
    def bom_item_subassembly2(self):
        if self._bom_item_subassembly2 is None:
            bom_item_keys = {
                "baugruppe": self.maxbom_teilenummer,
                "b_index": "",
                "teilenummer": self.maxbom_subassembly2_teilenummer,
                "t_index": "",
            }
            self._bom_item_subassembly2 = AssemblyComponent.ByKeys(**bom_item_keys)

        return self._bom_item_subassembly2

    @property
    def var1_part1_smaller_maxbom(self):
        if self._var1_part1_smaller_maxbom is None:
            self._var1_part1_smaller_maxbom = items.Item.ByKeys(
                **self.var1_part1_smaller_maxbom_keys
            )

        return self._var1_part1_smaller_maxbom

    @property
    def var2_part1_smaller_maxbom(self):
        if self._var2_part1_smaller_maxbom is None:
            self._var2_part1_smaller_maxbom = items.Item.ByKeys(
                **self.var2_part1_smaller_maxbom_keys
            )

        return self._var2_part1_smaller_maxbom

    @property
    def var1_part2_no_selection_condition(self):
        if self._var1_part2_no_selection_condition is None:
            self._var1_part2_no_selection_condition = items.Item.ByKeys(
                **self.var1_part2_no_selection_condition_keys
            )

        return self._var1_part2_no_selection_condition

    @property
    def var2_part2_no_selection_condition(self):
        if self._var2_part2_no_selection_condition is None:
            self._var2_part2_no_selection_condition = items.Item.ByKeys(
                **self.var2_part2_no_selection_condition_keys
            )

        return self._var2_part2_no_selection_condition

    @property
    def var1_part3(self):
        if self._var1_part3 is None:
            self._var1_part3 = items.Item.ByKeys(**self.var1_part3_keys)

        return self._var1_part3

    @property
    def var1_part_maxbom_deep(self):
        if self._var1_part_maxbom_deep is None:
            self._var1_part_maxbom_deep = items.Item.ByKeys(
                **self.var1_part_maxbom_deep_keys
            )

        return self._var1_part_maxbom_deep

    @property
    def var2_part3(self):
        if self._var2_part3 is None:
            self._var2_part3 = items.Item.ByKeys(**self.var2_part3_keys)

        return self._var2_part3

    @property
    def var2_part4_approved(self):
        if self._var2_part4_approved is None:
            self._var2_part4_approved = items.Item.ByKeys(
                **self.var2_part4_approved_keys
            )

        return self._var2_part4_approved

    @property
    def var2_part_maxbom_deep(self):
        if self._var2_part_maxbom_deep is None:
            self._var2_part_maxbom_deep = items.Item.ByKeys(
                **self.var2_part_maxbom_deep_keys
            )

        return self._var2_part_maxbom_deep
