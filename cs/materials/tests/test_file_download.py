# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json

from webtest import TestApp as Client

from cdb import testcase
from cs.materials.tests import MaterialsTestCase
from cs.platform.web import external_tempfile
from cs.platform.web.root import Root


class TestFileDownloadApp(MaterialsTestCase):
    def setUp(self):
        super(TestFileDownloadApp, self).setUp()
        self.client = Client(Root())

    def test_download_file(self):
        json_data = json.loads(
            """
            {
                "title": "Stress-Strain",
                "xlabel": "Strain in %",
                "ylabel": "Stress in MPa",
                "xtype": "linear",
                "ytype": "log",
                "x": [1, 2, 3, 4, 5, 6, 7, 8],
                "y": [
                    {
                        "color": "green",
                        "label": "20°C",
                        "y": [19.6, 24.1, 26.7, 28.3, 27.5, 30.5, 32.8, 33.1]
                    },
                    {
                        "label": "0°C",
                        "y": [24.8, 28.9, 31.3, 33.0, 34.9, 35.6, 38.4, 39.2]
                    }
                ]
            }
        """
        )

        filename = "test_download.json"
        with external_tempfile.get_external_temp_file(
            filename, "application/json"
        ) as proxy:
            json_str = json.dumps(
                json_data, ensure_ascii=False, indent=4, sort_keys=True
            )
            data = json_str.encode()
            proxy.write(data)
            file_size = len(data)

        with testcase.error_logging_disabled():
            result = self.client.get(proxy.get_url(), status=200)

            for key, value in result.headerlist:
                if "Content-Type" == key:
                    self.assertEquals("application/json", value)
                elif "Content-Length" == key:
                    self.assertEquals(str(file_size), value)
                elif "Content-Disposition" == key:
                    self.assertIn("attachment", value)
                    self.assertIn(filename, value)

            self.assertDictEqual(json_data, json.loads(result.body))
