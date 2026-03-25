# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import json
import os
import unittest

import pytest

from cs.pcs.projects.common.web import collect_url_patterns


@pytest.mark.integration
class Utility(unittest.TestCase):
    @staticmethod
    def _load_json(path):
        with open(path, "r", encoding="utf8") as jsonfile:
            result = json.load(jsonfile)

        return result

    def test_write_url_patterns(self):
        self.assertIsNone(collect_url_patterns.write_url_patterns())
        result = self._load_json(
            os.path.join(
                os.path.dirname(collect_url_patterns.__file__),
                "js",
                "src",
                "url_patterns.json",
            )
        )
        expected = self._load_json(
            os.path.join(
                os.path.dirname(__file__),
                "testdata",
                "url_patterns.json",
            )
        )
        self.maxDiff = None
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
