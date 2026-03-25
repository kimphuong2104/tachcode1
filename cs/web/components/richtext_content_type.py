# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import absolute_import
import ast


class RichTextConverter(object):
    def convert(self, content):
        data = ast.literal_eval(content)
        plaintext = ""
        for block in data["blocks"]:
            plaintext += "%s\n" % block["text"]
        return plaintext
