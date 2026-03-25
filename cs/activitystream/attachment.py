#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

from cdb import constants
from cdb.objects import Object
from cdb.objects.operations import operation

__docformat__ = "restructuredtext en"


class Attachment(Object):
    __classname__ = "cdbblog_attachment"
    __maps_to__ = "cdbblog_attachment"

    @classmethod
    def addAttachment(cls, posting_id, attachment_id):
        """Helper function to create attachment using operation routine
        to ensure calling event handler.
        """
        # TODO: access rights should be configured
        if posting_id and attachment_id:
            return operation(
                constants.kOperationNew,
                cls,
                posting_id=posting_id,
                attachment_id=attachment_id,
            )
        return None

    @classmethod
    def deleteAttachment(cls, posting_id, attachment_id):
        """Helper function to delete attachment using operation routine
        to ensure calling event handler.
        """
        # TODO: access rights should be configured
        if posting_id and attachment_id:
            attachments = cls.KeywordQuery(
                posting_id=posting_id, attachment_id=attachment_id
            )
            if attachments:
                operation(
                    constants.kOperationDelete,
                    attachments[0],
                )
