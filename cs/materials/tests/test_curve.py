# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json
import os

from webtest import TestApp as Client

from cdb import ue
from cs.materials.curve import Curve
from cs.materials.tests import MaterialsTestCase, test_utils
from cs.materials.tests.test_utils_context import TestImportContext
from cs.platform.web.root import Root


class TestCurve(MaterialsTestCase):
    def test_import_curve_data(self):
        name = "TestCurve:test_import_curve_data"

        material = test_utils.create_material(name)
        diagram = test_utils.create_diagram(material, name)
        curve = test_utils.create_curve(diagram, name)

        json_data = """
            {
                "x": [1, 2, 3, 4, 5, 6, 7, 8],
                "y": [19.6, 24.1, 26.7, 28.3, 27.5, 30.5, 32.8, 33.1]
            }
        """

        ctx = TestImportContext("test_data.json", json_data=json_data)
        curve.download_import_file(ctx)
        curve.import_curve_data(ctx)

        self.assertEqual(
            Curve.format_json(json.loads(json_data)), curve.GetText("curve_data")
        )

    def test_import_invalid_curve_data(self):
        name = "TestCurve:test_import_invalid_curve_data"

        material = test_utils.create_material(name)
        diagram = test_utils.create_diagram(material, name)
        curve = test_utils.create_curve(diagram, name)

        for json_data in ["", "invalid json"]:
            ctx = TestImportContext("test_data.json", json_data=json_data)
            curve.download_import_file(ctx)

            with self.assertRaisesRegexp(
                ue.Exception,
                str(test_utils.get_error_message("csmat_json_import_error")),
            ):
                curve.import_curve_data(ctx)

    def test_export_curve_data(self):
        name = "TestCurve:test_export_curve_data"

        client = Client(Root())

        json_data = """
            {
                "x": [1, 2, 3, 4, 5, 6, 7, 8],
                "y": [19.6, 24.1, 26.7, 28.3, 27.5, 30.5, 32.8, 33.1]
            }
        """

        material = test_utils.create_material(name)
        diagram = test_utils.create_diagram(material, name)
        curve = test_utils.create_curve(diagram, name, curve_data=json_data)

        for uses_webui in [True, False]:
            ctx = TestImportContext(
                export_file="diagram_export.json", uses_webui=uses_webui
            )
            curve.export_curve_data(ctx)

            # Read back the export result
            if ctx.uses_webui:
                # Web UI
                result = client.get(ctx.dest_url, status=200)
                export_data = json.loads(result.body)
            else:
                # PC Client
                self.assertTrue(os.path.isfile(ctx.server_file))
                with open(ctx.server_file, encoding="utf-8") as server_file:
                    export_data = json.load(server_file)

            self.assertEqual(
                Curve.format_json(export_data),
                curve.GetText("curve_data"),
            )
