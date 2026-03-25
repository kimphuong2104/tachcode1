#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure as Subst

t9508651_object_id = "86a2be2d-4c4f-11ec-924b-f875a45b4131"
t9508651_teilenummer = "9508651"
t9508651_t_index = ""
t9508651_keys = {"teilenummer": "9508651", "t_index": ""}

t9508652_object_id = "86a2be36-4c4f-11ec-924b-f875a45b4131"
t9508652_teilenummer = "9508652"
t9508652_t_index = ""
t9508652_keys = {"teilenummer": "9508652", "t_index": ""}

t9508653_object_id = "86a2be3c-4c4f-11ec-924b-f875a45b4131"
t9508653_teilenummer = "9508653"
t9508653_t_index = ""
t9508653_keys = {"teilenummer": "9508653", "t_index": ""}

t9508654_object_id = "86a2be42-4c4f-11ec-924b-f875a45b4131"
t9508654_teilenummer = "9508654"
t9508654_t_index = ""
t9508654_keys = {"teilenummer": "9508654", "t_index": ""}

t9508655_object_id = "86a2be48-4c4f-11ec-924b-f875a45b4131"
t9508655_teilenummer = "9508655"
t9508655_t_index = ""
t9508655_keys = {"teilenummer": "9508655", "t_index": ""}


t9508655 = Subst(
    t9508655_keys,
    children=[],
)

t9508654 = Subst(
    t9508654_keys,
    children=[t9508655],
)

t9508653 = Subst(
    t9508653_keys,
    children=[t9508654],
)

t9508652 = Subst(
    t9508652_keys,
    children=[t9508654],
)

t9508651 = Subst(
    t9508651_keys,
    children=[t9508652, t9508653],
)

t9508656_keys = {"teilenummer": "9508656", "t_index": ""}
t9508657_keys = {"teilenummer": "9508657", "t_index": ""}
t9508658_keys = {"teilenummer": "9508658", "t_index": ""}
t9508659_keys = {"teilenummer": "9508659", "t_index": ""}


t9508658 = Subst(
    t9508658_keys,
    children=[],
)
t9508659 = Subst(
    t9508659_keys,
    children=[t9508658],
)
t9508657 = Subst(
    t9508657_keys,
    children=[t9508658],
)
t9508656 = Subst(
    t9508656_keys,
    children=[t9508657, t9508659],
)
