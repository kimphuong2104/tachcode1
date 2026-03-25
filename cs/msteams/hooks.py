#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.msteams import astream, queue


def handle_as_channel_action(ctx):
    """
    Powerscript Hook that is called by the Activity Stream Framework whenever
    a posting or comment is created or updated.
    """
    # Actually we do not want to transfer a posting multiple times and have
    # decided to ignore changes
    if not ctx.is_create():
        return
    obj = ctx.get_object()
    if queue.use_message_queue():
        queue.create_job(obj)
    else:
        astream.handle_as_obj(obj)
