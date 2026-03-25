#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json
import os


def load_json(file_name):
    """
    Load json from file with given filename.
    """
    filepath = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        "json_files/{}.json".format(file_name),
    )
    with open(filepath, "r", encoding="utf-8") as testdata:
        return json.load(testdata)


def make_request(url, params, req_type="get"):
    """
    test utility

    sends request to mock http server
    """
    # set up mock http server
    from webtest import TestApp as Client

    # pylint: disable=no-name-in-module
    from cs.platform.web.root import Root

    client = Client(Root())
    if req_type == "get":
        return client.get(url, params)
    elif req_type == "post_json":
        return client.post_json(url, params)
    else:
        return None
