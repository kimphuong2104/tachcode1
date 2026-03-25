#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import mock
import unittest
from cs.costing.component_structure import query_patterns


class Utility(unittest.TestCase):
    @mock.patch.object(query_patterns, "open", create=True)
    @mock.patch.object(query_patterns.os.path, "abspath")
    @mock.patch.object(query_patterns.os.path, "dirname")
    @mock.patch.object(query_patterns.misc, "jail_filename")
    def test_load_query_pattern(self, jail_filename, dirname, abspath,
                                mock_open):
        read = mock_open.return_value.__enter__.return_value.read
        self.assertEqual(
            query_patterns.load_query_pattern("foo"),
            read.return_value,
        )
        mock_open.assert_called_once_with(jail_filename.return_value, "r")
        read.assert_called_once_with()
        jail_filename.assert_called_once_with(abspath.return_value, "foo")
        abspath.assert_called_once_with(dirname.return_value)
        dirname.assert_called_once_with(query_patterns.__file__)

if __name__ == "__main__":
    unittest.main()
