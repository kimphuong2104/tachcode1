# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import re

REFERENCE_MASK_REGEX = re.compile(r':(.+?):`(.+?)`')
REFERENCE_MASK_FORMAT = r'#\g<1>#\g<2>#\g<1>#'
REFERENCE_UNMASK_REGEX = re.compile(r'#(.+?)#(.+?)#(.+?)#')
REFERENCE_UNMASK_FORMAT = r':\g<1>:`\g<2>`'

REPLACEMENT_MSG_REGEX = re.compile(r'\|(.*?)\.(.*?)\|')
REPLACEMENT_MASK_FORMAT = r'|\g<1>#\g<2>|'
REPLACEMENT_UNMASK_REGEX = re.compile(r'\|(.*?)#(.*?)\|')
REPLACEMENT_UNMASK_FORMAT = r'|\g<1>.\g<2>|'


def mask_rst(msgid):
    # First: Mask the "." in replacements
    msgid = REPLACEMENT_MSG_REGEX.sub(REPLACEMENT_MASK_FORMAT, msgid)
    # Parse the references from the sentences
    msgid = REFERENCE_MASK_REGEX.sub(REFERENCE_MASK_FORMAT, msgid)
    # Return the masked message
    return msgid


def unmask_rst(msgstr):
    msgstr = REPLACEMENT_UNMASK_REGEX.sub(REPLACEMENT_UNMASK_FORMAT, msgstr)
    # Replace the references with the correct ones
    msgstr = REFERENCE_UNMASK_REGEX.sub(REFERENCE_UNMASK_FORMAT, msgstr)
    # Return the unmasked message
    return msgstr
