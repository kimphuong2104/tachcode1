#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

MAX_LIMIT_VARIANT_EDITOR_TABLE = 1000000
SEPARATOR = "#"
CLASSIFICATION_FLAG_FOR_INSTANTIATOR = "__IS_INSTANTIATOR__"
IS_INSTANTIATE = (
    "isinstantiate"  # used to indicate copy operation is started during instantiate
)
IS_INSTANTIATE_CREATE_ROOT_PART = "IS_INSTANTIATE_CREATE_ROOT_PART"
IS_INSTANTIATE_CREATE_SUB_PART = "IS_INSTANTIATE_CREATE_SUB_PART"
# if an update has breaking checksums then this value is used to identify
# the old instantiated sub parts
OBSOLETE_CHECKSUM_KEY = "obsolete"
