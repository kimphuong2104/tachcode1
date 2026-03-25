# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import importlib
import json
import logging
import tempfile

from cdb import ue
from cdb.objects import Object
from cs.platform.web import external_tempfile

LOG = logging.getLogger(__name__)


class MaterialExportFormat(Object):
    __maps_to__ = "csmat_material_export"
    __classname__ = "csmat_material_export"


def export_material(material, ctx):
    try:
        export_func_fqpn = ctx.dialog.export_function
        export_func_fqpn_splitted = export_func_fqpn.rsplit(".", 1)
        export_func_module = export_func_fqpn_splitted[0]
        export_func_name = export_func_fqpn_splitted[1]
        export_func = getattr(
            importlib.import_module(export_func_module), export_func_name
        )
    except Exception as ex:  # pylint: disable=W0703
        LOG.error("Cannot find export function %s: %s", export_func_fqpn, ex)
        raise ue.Exception("csmat_material_no_exportfunction", export_func_fqpn)

    filename = "{}-{}.json".format(material.material_id, material.material_index)

    export_path = ctx.dialog.export_file
    if not export_path:
        # use filename and default download dir
        export_path = filename

    try:
        if ctx.uses_webui:
            # Web UI

            with external_tempfile.get_external_temp_file(
                filename, "application/json"
            ) as proxy:
                export_func(proxy, material.to_json())
            ctx.url(proxy.get_url())
        else:
            # PC Client

            with tempfile.NamedTemporaryFile(
                prefix="csmat_material_export", delete=False
            ) as export_file:
                export_func(export_file, material.to_json())

            ctx.upload_to_client(
                export_file.name,
                client_filename=export_path,
                delete_file_after_upload=1,
            )

    except (IOError, OSError) as ex:
        LOG.error(ex)
        raise ue.Exception("csmat_export_error")


def json_export(out, json_data):
    """Default custom material export function - simply writes the material json structure into the output
    stream.

    :param out: The destination stream which receives the result of the export.
    :param json_data: The material data as a python dictionary in JSON format
    """

    json_string = json.dumps(json_data, ensure_ascii=False, indent=4, sort_keys=True)
    out.write(json_string.encode())
