#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import io
import json
import logging
import os
import sys

import pika

from cdb import rte
from cdb.objects import ByID
from cs.msteams import astream
from cs.platform.web.rest.generic import convert


class ConnectionInfo:
    def __init__(self):
        self._connection_data = None  # The content of the configuration json file

    def _init_connection_data(self):
        """
        Initializes `_connection_data`.
        """
        if self._connection_data is not None:
            # Already initialized
            return
        self._connection_data = {}
        conffile = rte.environ.get("CADDOK_MSTEAMS_QUEUE_DESC")
        if conffile:
            filename = os.path.normpath(os.path.expandvars(conffile))
            with io.open(filename, "rb") as descfile:
                self._connection_data = json.load(descfile)

    def __contains__(self, item):
        self._init_connection_data()
        return item in self._connection_data

    def get(self, key, default=None):
        self._init_connection_data()
        return self._connection_data.get(key, default)


_connection_info = ConnectionInfo()


def use_message_queue():
    """
    Returns ``True`` if there is a message queue configuration.
    """
    return "ConnectionParameters" in _connection_info


def ensure_queue_exist(channel):
    """
    Creates the queue if it does not exist and returns the name
    of the queue.
    """
    queue_name = "PostingsForMSTeams"
    channel.queue_declare(queue=queue_name, durable=True)
    return queue_name


def get_connection():
    connection_params = _connection_info.get("ConnectionParameters", {})
    store = rte.get_runtime().secrets
    user = store.resolve("cs.platform/msteams/rabbitmq/user")
    if user:
        if isinstance(user, bytes):
            user = user.decode("utf-8")
        pwd = store.resolve("cs.platform/msteams/rabbitmq/password")
        if isinstance(pwd, bytes):
            pwd = pwd.decode("utf-8")
        credentials = pika.PlainCredentials(user, pwd if pwd else "")
        connection_params["credentials"] = credentials
    return pika.BlockingConnection(pika.ConnectionParameters(**connection_params))


def create_job(posting_or_comment, channel_obj=None):
    """
    Create a job for a posting or comment. If `channel` is ``None`` the
    configuration will be used by the worker.
    """
    connection = get_connection()
    channel = connection.channel()
    routing_key = ensure_queue_exist(channel)
    params = {
        "id": posting_or_comment.ID(),
        "cdb_mdate": convert.dump_datetime(posting_or_comment.cdb_mdate),
    }
    if channel_obj is not None:
        params["channel_id"] = channel_obj.ID()
    channel.basic_publish(
        exchange="",
        routing_key=routing_key,
        body=json.dumps(params),
        properties=pika.BasicProperties(
            delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE
        ),
    )
    connection.close()


def queue_callback(ch, method, properties, body):
    data = json.loads(body)
    oid = data.get("id")
    if oid:
        ok = True
        obj = ByID(oid)
        channel = None
        channel_id = data.get("channel_id")
        if channel_id:
            channel = ByID(channel_id)
            if not channel:
                logging.getLogger(__name__).warning(
                    "Channel '%s' does not exist any longer", channel_id
                )
                ok = False
        try:
            if ok:
                astream.handle_as_obj(obj, channel)
        except Exception as e:  # pylint: disable=broad-except
            logging.getLogger(__name__).error(
                "Failed to transfer posting '%s':%s", oid, str(e)
            )
    ch.basic_ack(delivery_tag=method.delivery_tag)


def receive_jobs():
    connection = get_connection()
    channel = connection.channel()
    routing_key = ensure_queue_exist(channel)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=routing_key, on_message_callback=queue_callback)
    channel.start_consuming()


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)-8s] [%(name)s] %(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )
    if use_message_queue():
        receive_jobs()
    else:
        logging.getLogger(__name__).warning(
            "Do not start MS Teams worker because the MQ configuration is missing"
        )
