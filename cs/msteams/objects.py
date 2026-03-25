#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import datetime
import json

import requests

from cdb import ue
from cdb.objects import ByID, Forward, Object, Reference_1

fMSTeamsChannel = Forward(__name__ + ".MSTeamsChannel")
fMSTeamsASAssignment = Forward(__name__ + ".MSTeamsASAssignment")
fMSTeamsFailedJob = Forward(__name__ + ".MSTeamsFailedJob")


class MSTeamsChannel(Object):
    __maps_to__ = "ce_msteams_channel"
    __classname__ = "ce_msteams_channel"

    def on_ce_post_to_msteams_channel_pre_mask(self, ctx):
        json = """
        {
           "@context": "https://schema.org/extensions",
           "@type": "MessageCard",
           "themeColor": "0072C6",
           "title": "Test Posting from CONTACT Elements",
           "text": "This is the main text",
           "potentialAction": [
              {
                 "@type": "OpenUri",
                 "name": "Main Button",
                 "targets": [{ "os": "default", "uri": "https://www.contact-software.com" }]
              }],
        "sections": [{
           "startGroup": true,
           "activityTitle": "SectionTitle",
           "activitySubtitle": "SectionSubTitle",
           "activityText": "Sections text containing formatting like\\n# Heading 1\\n## Heading 2\\n\\n- a list\\n- item\\n\\nand a [Link](https://www.contact-software.com)", # noqa
           "potentialAction": [
              {
                 "@type": "OpenUri",
                 "name": "Section Button",
                 "targets": [{ "os": "default", "uri": "https://www.contact-software.com" }]
              }]
           }]
        }
        """
        ctx.set("json", json)

    def on_ce_post_to_msteams_channel_now(self, ctx):
        json_string = getattr(ctx.dialog, "json", "")
        json_data = {}
        try:
            json_data = json.loads(json_string)
        except ValueError as err:
            raise ue.Exception("err_invalid_json") from err
        r = requests.post(self.webhook_url, json=json_data, timeout=(15, 20))
        if not r.ok:
            raise ue.Exception(1024, f"Failed to send: {r.status_code}:{r.reason}")

    def hide_cctl(self, ctx):
        ctx.set_hidden(
            [
                "cdb_cdate",
                "cdb_cpersno",
                "mapped_cpersno",
                "cdb_mdate",
                "cdb_mpersno",
                "mapped_mpersno",
            ]
        )

    event_map = {(("create", "copy", "modify"), "pre_mask"): "hide_cctl"}


class MSTeamsASAssignment(Object):
    __maps_to__ = "ce_msteams_as_assign"
    __classname__ = "ce_msteams_as_assign"

    TeamsChannel = Reference_1(fMSTeamsChannel, fMSTeamsASAssignment.msteams_channel_id)

    @classmethod
    def get_channel_cfg(cls, topic_uuids):
        """
        Retrieve channel configurations assigned to the given uuids.
        The method might cache the channel configuration in the future.
        """
        return cls.KeywordQuery(as_channel_id=topic_uuids)

    def hide_cctl(self, ctx):
        ctx.set_hidden(
            [
                "cdb_cdate",
                "cdb_cpersno",
                "mapped_cpersno",
                "cdb_mdate",
                "cdb_mpersno",
                "mapped_mpersno",
            ]
        )

    event_map = {(("create", "copy", "modify"), "pre_mask"): "hide_cctl"}


class MSTeamsFailedJob(Object):
    __maps_to__ = "ce_msteams_failed_job"
    __classname__ = "ce_msteams_failed_job"

    TeamsChannel = Reference_1(fMSTeamsChannel, fMSTeamsFailedJob.msteams_channel_id)

    def get_postingorcomment(self):
        # At this time the uuid is used as ID in cdb.objects
        return ByID(self.posting_object_id)

    @classmethod
    def on_restart_msteams_transfer_now(cls, ctx):
        # Late import to avoid circular references
        from cs.msteams import astream, queue

        objs = list(cls.PersistentObjectsFromContext(ctx))

        # Sort the objects by date to get the best order
        # in the channel
        def _get_date(obj):
            return obj.error_datetime

        objs.sort(key=_get_date)
        for obj in objs:
            postingorcomment = obj.get_postingorcomment()
            channel = obj.TeamsChannel
            # Remove the enty - if the job fails again a new entry will be
            # created with the same keys
            obj.Delete()
            if queue.use_message_queue():
                queue.create_job(postingorcomment, channel)
            else:
                if obj.Channel:
                    astream.handle_as_obj(postingorcomment, channel)

    @classmethod
    def create_log_entry(cls, channel, posting, msg):
        cls.CreateNoResult(
            msteams_channel_id=channel.cdb_object_id,
            posting_object_id=posting.cdb_object_id,
            error_datetime=datetime.datetime.utcnow(),
            error_message=msg,
        )
