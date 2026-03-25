#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
The module provides classes that helps you to create and send message cards
to Microsoft Teams.
"""

import logging
import re

import requests

from cdb.platform.mom import CDBObjectHandle
from cs.activitystream.objects import Posting
from cs.activitystream.web.main import get_posting_link
from cs.platform.web import get_root_url
from cs.platform.web.uisupport import get_webui_link


def _prepare_for_markdown(text):
    """
    Escapes characters that have special meanings in markdown.
    """
    parse = re.sub(r"([_*\[\]()~`>\#\+\-=|\.!])", r"\\\1", text)
    reparse = re.sub(r"\\\\([_*\[\]()~`>\#\+\-=|\.!])", r"\1", parse)
    # Add Spaces to line endings to force the line break
    return reparse.replace("\n", "  \n")


class MessageCardBase:
    def __init__(self, language):
        self.json_dict = {"potentialAction": []}
        self.language = language

    def add_link(self, name, url):
        """
        Add a button, that navigates to the given url.

        :param name:
           The label of the button
        :param url:
           The target url.
        """
        self.json_dict["potentialAction"].append(
            {
                "@type": "OpenUri",
                "name": name,
                "targets": [{"os": "default", "uri": url}],
            }
        )

    def add_object_link(self, obj, title=None):
        """
        Add a button, that navigates to the given object.

        :param obj:
           The target object
        :param title:
           The title of the button. If not set the object description will
           be used.
        """
        if not obj:
            return None
        url = ""
        if isinstance(obj, Posting):
            url = get_posting_link(obj)
        else:
            url = get_root_url() + get_webui_link(None, obj)
        if url:
            if title is None:
                if isinstance(obj, CDBObjectHandle):
                    title = obj.getDesignation("", self.language)
                else:
                    title = obj.GetDescription(self.language)
            self.add_link(title, url)


class MessageCardSection(MessageCardBase):
    def __init__(
        self, title=None, subtitle=None, text=None, startGroup=True, language=None
    ):
        """
        Create a message card section with the given values. `language`
        is used to determine the language used for object links.
        """
        MessageCardBase.__init__(self, language)
        self.json_dict["startGroup"] = startGroup
        if title is not None:
            self.json_dict["activityTitle"] = _prepare_for_markdown(title)
        if subtitle is not None:
            self.json_dict["activitySubtitle"] = _prepare_for_markdown(subtitle)
        if text is not None:
            self.json_dict["activityText"] = _prepare_for_markdown(text)


class MessageCard(MessageCardBase):
    def __init__(self, title, text, language="en"):
        """
        Create a message card with the given values. `language`
        is used to determine the language used for object links.
        """
        MessageCardBase.__init__(self, language)
        self.json_dict.update(
            {
                "@context": "https://schema.org/extensions",
                "@type": "MessageCard",
                "themeColor": "0072C6",
                "title": title,
                "text": _prepare_for_markdown(text),
                "potentialAction": [],
                "sections": [],
            }
        )

    def add_section(self, section):
        """
        Add a section to the message card.

        :param section:
           A `MessageCardSection` object.
        """
        self.json_dict["sections"].append(section.json_dict)

    def post(self, channel):
        """
        Sends a ``POST`` request to MS Teams to transfer the message card.
        Raises a `RuntimeError` if the call does not succeed.
        """
        r = requests.post(channel.webhook_url, json=self.json_dict, timeout=(15, 20))
        if not r.ok:
            logging.warning(
                "Failed to send card to channel '%s': '%s'",
                channel.webhook_url,
                self.json_dict,
            )
            error_msg = f"Failed to send: {r.status_code}:{r.reason}"
            raise RuntimeError(error_msg)
