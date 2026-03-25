#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import json
import os
import six

from cs.workspaces import open_with_cdbwscall
from cs.platform.web.rest.support import get_restlink
from cdb.objects.cdb_file import CDB_File


def viewonclient(ctx, main_file, additional_files=None, main_file_local_filename=None):
    """
    Implementation of entry point (see setup.py).
    :param ctx: CDB UE context
    :param main_file: The file to open on the client. A CDB_File or a local file
    :param additional_files: optional additional files to download. (Also CDB_File's or local files)
    :param main_file_local_filename: optional name to use on client as local filename
    """
    upload_to_workspaces_client(
        ctx, main_file, additional_files, main_file_local_filename, office_mode=True
    )


def upload_to_workspaces_client(
    ctx,
    main_file,
    additional_files=None,
    main_file_local_filename=None,
    description=None,
    office_mode=False,
):
    """
    Upload and open a file (and some additional files) on the client,
    using Workspaces Desktop and its cdbwscall protocol.

    This function needs cs.platform 15.6 or newer.
    It only works if the Web adapter is used in WSD (not the Windows Client).

    :param ctx: CDB UE context
    :param main_file: The file to open on the client. A CDB_File or a local file
    :param additional_files: optional additional files to download. (Also CDB_File's or local files)
    :param main_file_local_filename: optional name to use on client as local filename
    :param description: optional description of context
    :param office_mode: True of WSD should be startet in Office Mode if not already running
    """
    protocol_file_path = create_protocol_file(
        main_file, additional_files, main_file_local_filename, description
    )
    open_with_cdbwscall(
        ctx,
        _CDBWSCALL_DOWNLOAD_AND_OPEN_FILE,
        protocol_file_path=protocol_file_path,
        office_mode_value="1" if office_mode else "0",
    )


def create_protocol_file(
    main_file, additional_files, main_file_local_filename, description
):
    if additional_files is None:
        additional_files = []

    content = {
        "main_file": make_file_description(main_file, main_file_local_filename),
        "action": "view",
        "additional_files": [make_file_description(f) for f in additional_files],
        "description": description or "",
    }

    # local import because this is only available starting with Platform 15.6
    from cs.platform.web import external_tempfile

    with external_tempfile.get_external_temp_file() as proxy:
        if six.PY3:
            proxy.write(json.dumps(content, indent=4).encode("utf-8"))
        else:
            json.dump(content, proxy, indent=4)

    return proxy.get_url()


def make_file_description(f, local_filename=None):
    if isinstance(f, CDB_File):
        filename = local_filename or f.cdbf_name
        file_link = get_restlink(f)
    elif os.path.isfile(f):
        filename = local_filename or os.path.basename(f)
        # local import because this is only available starting with Platform 15.6
        from cs.platform.web import external_tempfile

        with external_tempfile.get_external_temp_file() as proxy:
            proxy.copy_from_file(f)
        file_link = proxy.get_url()
    else:
        raise RuntimeError("The file '%s' wasn't found or is no cdb_file object" % f)

    return {"link": file_link, "filename": filename}


_CDBWSCALL_DOWNLOAD_AND_OPEN_FILE = u"""<?xml version="1.0"?>
<cdbwsinfo>
   <command>downloadandopenfile</command>
   <options>
      <office_mode>{office_mode_value}</office_mode>
   </options>
   <parameters>
       <parameter>{protocol_file_path}</parameter>
   </parameters>
</cdbwsinfo>
"""
