#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals

import base64
import json
import os
import sys

from six.moves.urllib.parse import urlparse

from cs.platform.web import external_tempfile, get_root_url

from cs.fileclient.protocol import FileClientProtocol

py2 = sys.version_info[0] == 2


# External API

def make_upload_link(view_files, main_filename):
    """
    Returns a URL to upload all given `view_files` from server to client machine in view
    mode by using the File Client. After processing the URL (e.g. by calling ctx.url())
    `main_filename` (as included in `view_files`) gets opened by the File Client in view mode.

    :param view_files: A list of tuples (<filename>, <file URL>) containing all files to be
                       downloaded by the File Client in view mode, where <filename> might contain
                       slashes in order to create subfolder structures on client side (e.g.
                       'subfolder/file.docx')
    :type view_files: list
    :param main_filename: Name of the file (as included in `view_files`) to be opened by
                          the File Client after the download
    :type main_filename: string

    :return: cdbf:// protocol URL
    :rtype: string
    """
    protocol = FileClientProtocol()
    main_filename_found = False
    all_filenames = []

    for filename, file_url in view_files:

        if filename in all_filenames:
            raise Exception("The File Client can't open multiple view files with the same name")
        else:
            all_filenames.append(filename)

        if filename == main_filename:
            protocol.add_file_entry(filename, file_url, "view", True)
            main_filename_found = True
        else:
            protocol.add_file_entry(filename, file_url, "view", False)

    if not main_filename_found:
        raise Exception("The main filename wasn't found in the list of view files")

    with external_tempfile.get_external_temp_file() as proxy:
        _json = protocol.to_json()
        if not py2:
            _json = _json.encode()
        proxy.write(_json)

    return make_cdbf_link("protocol_file", link=proxy.get_url())


# Internal API

def make_cdbf_link(protocol, **kwargs):
    """
    Returns cdbf:// URL for given protocol and keyword arguments.

    :param protocol: Protocol to use. `for_object` when selecting a document object for editing its
                     primary file. `parameters` when directly selecting a file object for editing
                     it. `protocol_file` when creating a temp JSON protocol file on server side to
                     be further processed by the File Client.
    :type protocol: string
    :param query_dict: Query or section parameters
    :type query_dict: kwargs

    :return: cdbf:// protocol URL
    :rtype: string
    """
    root_url = os.environ.get('CADDOK_PROXYSERVER_BASE', get_root_url())
    (scheme, host_and_port, _, _, _, _) = urlparse(root_url)

    if protocol == "for_object":
        rest_classname = kwargs["rest_classname"]
        rest_key = kwargs["rest_key"]
        return "cdbf://%s/%s/%s/%s/%s" % (host_and_port, scheme, protocol, rest_classname, rest_key)

    elif protocol in ["parameters", "protocol_file"]:
        query = json.dumps(kwargs)
        # TODO: base64.urlsafe_b64encode() should be used instead, but then it must
        #       also be used in cs.web at multiple places (Python and Javascript) (E067287)
        if not py2:
            query = query.encode()
        query = base64.b64encode(query)
        if not py2:
            query = query.decode()
        return "cdbf://%s/%s/%s?%s" % (host_and_port, scheme, protocol, query)

    else:
        raise Exception("Given protocol is not supported")
