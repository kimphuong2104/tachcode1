# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
Contains plain text converter for posting/comment text.
"""

from __future__ import absolute_import

from cs.web.components import richtext_content_type

__docformat__ = "restructuredtext en"


class PostingTextConverter(richtext_content_type.RichTextConverter):
    """
    Override standard rich text converter to handle legacy plain text
    content by postings and comments
    """

    def convert(self, content):
        # Attempt to parse posting text as rich text
        try:
            return super(PostingTextConverter, self).convert(content)
        except (SyntaxError, ValueError, TypeError):
            # It is saved as plain text, just use that
            return content
