# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json
import logging
import tempfile

from cdb import ue
from cdb.objects import expressions, references
from cdb.objects.core import Object
from cs.classification import api as classification_api
from cs.classification.rest.utils import ensure_json_serialiability
from cs.platform.web import external_tempfile

fCurve = expressions.Forward("cs.materials.curve.Curve")
fDiagram = expressions.Forward("cs.materials.diagram.Diagram")
fMaterial = expressions.Forward("cs.materials.Material")

LOG = logging.getLogger(__name__)


class Curve(Object):
    __maps_to__ = "csmat_curve"
    __classname__ = "csmat_curve"

    EXPORT_ATTRIBUTES = ["label"]

    Diagram = references.Reference_1(fDiagram, fCurve.diagram_id)

    @classmethod
    def format_json(cls, table_data):
        return json.dumps(table_data, ensure_ascii=False, indent=4, sort_keys=True)

    def download_import_file(self, ctx):
        client_path = ctx.dialog.import_file
        with tempfile.NamedTemporaryFile(
            prefix="csmat_curve_import", delete=False
        ) as f_temp:
            LOG.info(
                "Downloading file from client to server: %s to %s",
                client_path,
                f_temp.name,
            )
            ctx.download_from_client(
                client_path, f_temp.name, delete_file_after_download=0
            )
            ctx.keep("import_tmp_path", f_temp.name)

    def export_curve_data(self, ctx):
        """Menu action UE to export the current curve data."""

        diagram = self.Diagram

        filename = "{}-{}_{}_{}.json".format(
            diagram.material_id,
            diagram.material_index,
            diagram.title if diagram.title else "",
            self.label if self.label else "",
        )

        export_path = ctx.dialog.export_file
        if not export_path or "*.json" == export_path:
            # use filename and default download dir
            export_path = filename

        try:
            json_data = json.loads(self.GetText("curve_data"))
        except Exception as ex:  # pylint: disable=W0703
            LOG.error(ex)
            raise ue.Exception("csmat_json_export_error")

        if ctx.uses_webui:
            # Web UI

            with external_tempfile.get_external_temp_file(
                filename, "application/json"
            ) as proxy:
                json_string = json.dumps(
                    json_data, ensure_ascii=False, indent=4, sort_keys=True
                )
                proxy.write(json_string.encode())
            ctx.url(proxy.get_url())
        else:
            # PC Client

            with tempfile.NamedTemporaryFile(
                prefix="csmat_diagram_export", delete=False, mode="w", encoding="utf-8"
            ) as export_file:
                json.dump(
                    json_data, export_file, ensure_ascii=False, indent=4, sort_keys=True
                )

            ctx.upload_to_client(
                export_file.name,
                client_filename=export_path,
                delete_file_after_upload=1,
            )

    def import_curve_data(self, ctx):
        from os import path, remove

        if (
            "import_tmp_path" not in ctx.ue_args.get_attribute_names()
            or not path.isfile(ctx.ue_args["import_tmp_path"])
        ):
            LOG.error("No import file given")
            raise ue.Exception("csmat_no_import_file_given")

        diagram = self.Diagram

        import_tmp_path = ctx.ue_args["import_tmp_path"]
        LOG.info(
            "Importing to %s/%s - %s - %s from file: %s",
            diagram.material_id,
            diagram.material_index,
            diagram.title if diagram.title else "",
            self.label if self.label else "",
            import_tmp_path,
        )

        try:
            with open(import_tmp_path, encoding="utf-8") as f:
                json_data = json.load(f)
                self.SetText("curve_data", self.format_json(json_data))
        except Exception as ex:  # pylint: disable=W0703
            LOG.exception(ex)
            raise ue.Exception("csmat_json_import_error")

        try:
            remove(import_tmp_path)
        except IOError as ex:
            LOG.exception(ex)
            LOG.warning("Cannot remove file: %s", import_tmp_path)

    def to_json(self):
        try:
            curve_data = json.loads(self.GetText("curve_data"))
        except Exception as ex:  # pylint: disable=W0703
            curve_data = {}
            LOG.error("Cannot load curve data for '%s': %s", self.label, str(ex))
        classification_data = classification_api.get_classification(self)
        json_data = {
            "properties": ensure_json_serialiability(classification_data["properties"]),
            "x": curve_data.get("x", []),
            "y": curve_data.get("y", []),
        }
        for attr in Curve.EXPORT_ATTRIBUTES:
            json_data[attr] = self[attr]
        return json_data

    event_map = {
        ("csmat_json_export", "now"): "export_curve_data",
        ("csmat_json_import", "now"): "download_import_file",
        ("csmat_json_import", "post"): "import_curve_data",
    }
