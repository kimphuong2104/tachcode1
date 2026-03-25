#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure as Subst

t9508619_teilenummer = "9508619"
t9508619_t_index = ""
t9508619_keys = {"teilenummer": "9508619", "t_index": ""}
t9508620_teilenummer = "9508620"
t9508620_t_index = ""
t9508620_keys = {"teilenummer": "9508620", "t_index": ""}
t9508620_bom_item_object_id = "8f235510-fc0a-11eb-923e-f875a45b4131"
t9508621_teilenummer = "9508621"
t9508621_t_index = ""
t9508621_keys = {"teilenummer": "9508621", "t_index": ""}
t9508622_teilenummer = "9508622"
t9508622_t_index = ""
t9508622_keys = {"teilenummer": "9508622", "t_index": ""}
t9508623_teilenummer = "9508623"
t9508623_t_index = ""
t9508623_keys = {"teilenummer": "9508623", "t_index": ""}
t9508624_teilenummer = "9508624"
t9508624_t_index = ""
t9508624_cdb_object_id = "8f2354ef-fc0a-11eb-923e-f875a45b4131"
t9508624_keys = {"teilenummer": "9508624", "t_index": ""}
t9508625_teilenummer = "9508625"
t9508625_t_index = ""
t9508625_keys = {"teilenummer": "9508625", "t_index": ""}
t9508626_teilenummer = "9508626"
t9508626_t_index = ""
t9508626_keys = {"teilenummer": "9508626", "t_index": ""}
t9508627_teilenummer = "9508627"
t9508627_t_index = ""
t9508627_keys = {"teilenummer": "9508627", "t_index": ""}
t9508627_bom_item_object_id = "8f235548-fc0a-11eb-923e-f875a45b4131"

t9508628_teilenummer = "9508628"
t9508628_t_index = ""
t9508628_keys = {"teilenummer": "9508628", "t_index": ""}
VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_I1_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_I1_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0_object_id = (
    "512deba6-d08a-4bc5-b552-0cf8d9c3d033"
)
VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1_keys = {
    "occurrence_id": "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1"
}
VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1_object_id = (
    "206782a5-880a-4d13-bcb7-ebb00ff6a322"
)

t9508628 = Subst(
    t9508628_keys,
    occurrence_keys=[
        VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0_keys,
        VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1_keys,
    ],
)
t9508627 = Subst(
    t9508627_keys,
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0_keys],
)
t9508626 = Subst(
    t9508626_keys,
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_I1_OC0_keys],
)
t9508625 = Subst(
    t9508625_keys,
    children=[t9508627, t9508628],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0_keys],
)
t9508624 = Subst(
    t9508624_keys,
    children=[t9508626],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0_keys],
)
t9508623 = Subst(
    t9508623_keys,
    children=[t9508624, t9508625],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0_keys],
)
t9508622 = Subst(
    t9508622_keys,
    children=[t9508623],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0_keys],
)
t9508621 = Subst(
    t9508621_keys,
    children=[t9508622],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0_keys],
)
t9508620 = Subst(
    t9508620_keys,
    children=[t9508621],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys],
)

# variant 1
# 9508629@ - VAR_TEST_MAXBOM_DEEP_WIDE
#  +- 9508630@ - VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1
#     +- > VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0
#     +- 9508631@ - VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1
#        +- > VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0
#        +- 9508632@ - VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1
#           +- > VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0
#           +- 9508633@ - VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1
#              +- > VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0
#              +- 9508634@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1
#              |  +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0
#              +- 9508635@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2
#                 +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0
#                 +- 9508627@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1
#                 |  +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0
#                 +- 9508628@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2
#                    +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0

t9508629_teilenummer = "9508629"
t9508629_keys = {"teilenummer": t9508629_teilenummer, "t_index": ""}
t9508634_teilenummer = "9508634"
t9508634_t_index = ""
t9508634_keys = {"teilenummer": t9508634_teilenummer, "t_index": ""}
t9508634_cdb_object_id = "edc325d2-fc37-11eb-923e-f875a45b4131"
t9508633_teilenummer = "9508633"
t9508633_keys = {"teilenummer": t9508633_teilenummer, "t_index": ""}
t9508632_teilenummer = "9508632"
t9508632_t_index = ""
t9508632_keys = {"teilenummer": t9508632_teilenummer, "t_index": ""}
t9508631_teilenummer = "9508631"
t9508631_keys = {"teilenummer": t9508631_teilenummer, "t_index": ""}
t9508630_teilenummer = "9508630"
t9508630_keys = {"teilenummer": t9508630_teilenummer, "t_index": ""}
t9508630_bom_item_object_id = "edc325e4-fc37-11eb-923e-f875a45b4131"
t9508635_id = "edc325d6-fc37-11eb-923e-f875a45b4131"
t9508635_teilenummer = "9508635"
t9508635_t_index = ""
t9508635_keys = {"teilenummer": "9508635", "t_index": ""}

t9508628_v1 = Subst(
    t9508628_keys,
    occurrence_keys=[
        VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0_keys,
    ],
)

t9508635 = Subst(
    t9508635_keys,
    children=[t9508627, t9508628_v1],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0_keys],
)

t9508634 = Subst(
    t9508634_keys,
    children=[],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0_keys],
)

t9508633 = Subst(
    t9508633_keys,
    children=[t9508634, t9508635],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0_keys],
)

t9508632 = Subst(
    t9508632_keys,
    children=[t9508633],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0_keys],
)
t9508631 = Subst(
    t9508631_keys,
    children=[t9508632],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0_keys],
)
t9508630 = Subst(
    t9508630_keys,
    children=[t9508631],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys],
)
t9508629 = Subst(
    t9508629_keys,
    children=[t9508630],
)


# variant 2
# 9508636@ - VAR_TEST_MAXBOM_DEEP_WIDE
#  +- 9508637@ - VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1
#     +- > VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0
#     +- 9508638@ - VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1
#        +- > VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0
#        +- 9508639@ - VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1
#           +- > VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0
#           +- 9508640@ - VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1
#              +- > VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0
#              +- 9508641@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1
#              |  +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0
#              |  +- 9508626@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_I1
#              |     +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_I1_OC0
#              +- 9508642@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2
#                 +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0
#                 +- 9508627@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1
#                 |  +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0
#                 +- 9508628@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2
#                    +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1

t9508636_teilenummer = "9508636"
t9508636_keys = {"teilenummer": t9508636_teilenummer, "t_index": ""}

t9508637_teilenummer = "9508637"
t9508637_keys = {"teilenummer": t9508637_teilenummer, "t_index": ""}

t9508638_teilenummer = "9508638"
t9508638_keys = {"teilenummer": t9508638_teilenummer, "t_index": ""}

t9508639_teilenummer = "9508639"
t9508639_keys = {"teilenummer": t9508639_teilenummer, "t_index": ""}

t9508640_teilenummer = "9508640"
t9508640_keys = {"teilenummer": t9508640_teilenummer, "t_index": ""}

t9508641_teilenummer = "9508641"
t9508641_keys = {"teilenummer": t9508641_teilenummer, "t_index": ""}

t9508642_teilenummer = "9508642"
t9508642_keys = {"teilenummer": t9508642_teilenummer, "t_index": ""}


t9508628_v2 = Subst(
    t9508628_keys,
    occurrence_keys=[
        VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1_keys,
    ],
)


t9508642 = Subst(
    t9508642_keys,
    children=[t9508627, t9508628_v2],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0_keys],
)

t9508641 = Subst(
    t9508641_keys,
    children=[t9508626],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0_keys],
)

t9508640 = Subst(
    t9508640_keys,
    children=[t9508641, t9508642],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0_keys],
)

t9508639 = Subst(
    t9508639_keys,
    children=[t9508640],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0_keys],
)

t9508638 = Subst(
    t9508638_keys,
    children=[t9508639],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0_keys],
)

t9508637 = Subst(
    t9508637_keys,
    children=[t9508638],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys],
)

t9508636 = Subst(
    t9508636_keys,
    children=[t9508637],
    occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys],
)
