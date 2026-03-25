# -*- mode: python; coding: utf-8 -*-

# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import logging
import pytest

from copy import deepcopy

from requests import ConnectionError
from webtest import TestApp as Client

from cdb.storage.index.errors import InvalidService

from cs.platform.web.root import Root

from cs.classification import api, ClassificationConstants
from cs.classification.rest.utils import convert_from_json
from cs.classification.tests import utils
from cs.classification.units import Unit

from cs.classification.tests.test_search_parser import TestSearchParser


LOG = logging.getLogger(__name__)


class TestSearch(utils.ClassificationTestCase):

    @classmethod
    def _runs_on_buildbot(cls):
        import getpass
        return getpass.getuser() == "buildbot"

    def setUp(self):
        super(TestSearch, self).setUp()

    def _timeout(self):
        from time import sleep
        if TestSearch._runs_on_buildbot():
            sleep(4)
        else:
            sleep(1)

    def _create_document_with_value(self, title, class_code, property_code, property_values):
        doc = self.create_document(title)
        if class_code:
            classification_data = api.get_new_classification([class_code], with_defaults=False)
        else:
            classification_data = api.create_additional_props([property_code])
        self._set_values(classification_data, property_code, property_values)
        if class_code:
            api.update_classification(doc, classification_data, type_conversion=convert_from_json)
        else:
            api.update_additional_props(doc, classification_data, type_conversion=convert_from_json)
        self._timeout()
        return doc

    def _search_document(self, classification_data, docs_to_be_found=None, docs_not_to_be_found=None):
        try:
            found_oids = set()
            for found_oid in api.search(classification_data):
                if docs_not_to_be_found:
                    for doc in docs_not_to_be_found:
                        self.assertFalse(
                            found_oid == doc.cdb_object_id,
                            "Doc {} should not be found".format(doc.titel)
                        )
                found_oids.add(found_oid)
            if docs_to_be_found:
                for doc in docs_to_be_found:
                    self.assertTrue(
                        doc.cdb_object_id in found_oids,
                        "Doc {} should be found".format(doc.titel)
                    )
        except (ConnectionError, InvalidService):
            # ignore solr connection exceptions
            pass

    def _set_values(self, classification_data, property_path, property_value):
        prop_dict = classification_data[ClassificationConstants.PROPERTIES]
        prop_path = property_path.split('/')
        for path_segment in prop_path[:-1]:
            code_and_pos = path_segment.split(':')
            prop_code = code_and_pos[0]
            value_pos = 0 if len(code_and_pos) == 1 else int(code_and_pos[1])
            prop_dict = prop_dict[prop_code][value_pos][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]

        prop_code = prop_path[-1]
        pos = 0
        prop_val = prop_dict[prop_code]
        for property_value in property_value:
            if pos >= len(prop_val):
                prop_val.append(dict(prop_dict[prop_code][0]))
            prop_val[pos][ClassificationConstants.VALUE] = property_value
            pos += 1

    def test_combined_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code_text = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"
        prop_code_int = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"

        doc_0 = self.create_document("doc 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code_text, [None])
        self._set_values(classification_data, prop_code_int, [None])
        api.update_classification(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code_text, ["test text 1"])
        self._set_values(classification_data, prop_code_int, [1])
        api.update_classification(doc_1, classification_data, type_conversion=convert_from_json)

        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1], []
        )

        self._set_values(classification_data, prop_code_text, ['test text 1'])
        self._set_values(classification_data, prop_code_int, [2])
        self._search_document(
            classification_data, [], [doc_0, doc_1]
        )

        self._set_values(classification_data, prop_code_text, ['test text 1'])
        self._set_values(classification_data, prop_code_int, [1])
        self._search_document(
            classification_data, [doc_1], [doc_0]
        )

    def test_bool_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL"

        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [True])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, [False])

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2], []
        )
        self._set_values(classification_data, prop_code, [None])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2], []
        )
        self._set_values(classification_data, prop_code, ['*'])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2], []
        )
        self._set_values(classification_data, prop_code, ['!=""'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0]
        )

        self._set_values(classification_data, prop_code, ['=""'])
        self._search_document(
            classification_data, [doc_0], [doc_1, doc_2]
        )

        # normal search values ...
        self._set_values(classification_data, prop_code, [True])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2]
        )
        self._set_values(classification_data, prop_code, [False])
        self._search_document(
            classification_data, [doc_2], [doc_0, doc_1]
        )

    def test_date_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"

        doc_not_to_be_found = self._create_document_with_value(
            "other doc", class_code, prop_code, ["14.02.2018"]
        )
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["3.7.1987"])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, ["1.1.1979"])
        doc_12 = self._create_document_with_value("doc 12", class_code, prop_code, ["04.09.2008 13:30:00"])

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found], []
        )
        self._set_values(classification_data, prop_code, ['*'])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found], []
        )
        self._set_values(classification_data, prop_code, ['!=""'])
        self._search_document(
            classification_data, [doc_1, doc_2, doc_12, doc_not_to_be_found], [doc_0]
        )
        self._set_values(classification_data, prop_code, ['=""'])
        self._search_document(
            classification_data, [doc_0], [doc_1, doc_2, doc_12, doc_not_to_be_found]
        )

        # normal search values ...
        self._set_values(classification_data, prop_code, ['3.7.1987'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, [' 3.7.1987 '])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['04.09.2008 13:30:00'])
        self._search_document(
            classification_data, [doc_12], [doc_0, doc_1, doc_2, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['!=1.1.1979'])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_12, doc_not_to_be_found], [doc_2]
        )

        self._set_values(classification_data, prop_code, ['=3.7.1987 OR =1.1.1979'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['<04.09.2008'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['>1.1.1979 AND <=04.09.2008 13:30:00'])
        self._search_document(
            classification_data, [doc_1, doc_12], [doc_0, doc_2, doc_not_to_be_found]
        )

    def test_date_multival_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE_MULTIVALUE"

        doc_not_to_be_found = self._create_document_with_value(
            "other doc", class_code, prop_code, ["14.02.2018", "14.02.2081"]
        )
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["1.1.1979", "3.7.1987"])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, ["1.1.1979", "9.9.1999"])

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        # search for partial list ...
        self._set_values(classification_data, prop_code, ['1.1.1979'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_not_to_be_found]
        )
        # search for exact match ...
        self._set_values(classification_data, prop_code, ['1.1.1979', '3.7.1987'])
        self._search_document(
            classification_data, [doc_1], [doc_2, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, ['1.1.1979', '9.9.1999'])
        self._search_document(
            classification_data, [doc_2], [doc_1, doc_not_to_be_found]
        )

    def test_float_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"

        float_value_dict = {
            "float_value": 4711.123,
            "float_value_normalized": None,
            "unit_object_id": None
        }

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, [float_value_dict])

        float_value_dict["float_value"] = None
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [float_value_dict])

        float_value_dict["float_value"] = 1.1
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [float_value_dict])

        float_value_dict["float_value"] = 2.2
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, [float_value_dict])

        float_value_dict["float_value"] = 12.12
        doc_12 = self._create_document_with_value("doc 12", class_code, prop_code, [float_value_dict])

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found], []
        )
        float_value_dict["float_value"] = '!=""'
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1, doc_2, doc_12, doc_not_to_be_found], [doc_0]
        )
        float_value_dict["float_value"] = '=""'
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_0], [doc_1, doc_2, doc_12, doc_not_to_be_found]
        )

        # normal search value ...
        float_value_dict["float_value"] = 1.1
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = '1,1'
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = '1.1'
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = '!=2.2'
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_12, doc_not_to_be_found], [doc_2]
        )

        float_value_dict["float_value"] = '=1.1 OR =2.2'
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_12, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = '<12.11'
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_12, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = '>1.1 AND <=12.12'
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_2, doc_12], [doc_0, doc_1, doc_not_to_be_found]
        )

    def test_signed_float_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"

        float_value_dict = {
            "float_value": 4711.123,
            "float_value_normalized": None,
            "unit_object_id": None
        }

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, [float_value_dict])

        float_value_dict["float_value"] = None
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [float_value_dict])

        float_value_dict["float_value"] = 1.1
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [float_value_dict])

        float_value_dict["float_value"] = -1.1
        doc_2 = self._create_document_with_value("doc 1", class_code, prop_code, [float_value_dict])

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        # normal search value ...
        float_value_dict["float_value"] = -1.1
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_2], [doc_1, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = "-1.1"
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_2], [doc_0, doc_1, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = "+1.1"
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = "=+1.1 OR =-1.1"
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_not_to_be_found]
        )

        float_value_dict["float_value"] = ">=-1.1 AND <=+1.1"
        self._set_values(classification_data, prop_code, [float_value_dict])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_not_to_be_found]
        )


    def test_float_multival_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_MULTIVALUE"

        float_value_dict_1 = {
            "float_value": None,
            "float_value_normalized": None,
            "unit_object_id": None
        }
        float_value_dict_2 = dict(float_value_dict_1)

        float_value_dict_1["float_value"] = 4711.11
        float_value_dict_2["float_value"] = 4712.22
        doc_not_to_be_found = self._create_document_with_value(
            "other doc", class_code, prop_code, [float_value_dict_1, float_value_dict_2]
        )

        float_value_dict_1["float_value"] = 1.1
        float_value_dict_2["float_value"] = 2.2
        doc_1 = self._create_document_with_value(
            "doc 1", class_code, prop_code, [float_value_dict_1, float_value_dict_2]
        )

        float_value_dict_1["float_value"] = 1.1
        float_value_dict_2["float_value"] = 3.3
        doc_2 = self._create_document_with_value(
            "doc 2", class_code, prop_code, [float_value_dict_1, float_value_dict_2]
        )

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        # search for partial list ...
        float_value_dict_1["float_value"] = 1.1
        self._set_values(classification_data, prop_code, [float_value_dict_1])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_not_to_be_found]
        )
        # search for exact match ...
        float_value_dict_1["float_value"] = 1.1
        float_value_dict_2["float_value"] = 2.2
        self._set_values(classification_data, prop_code, [float_value_dict_1, float_value_dict_2])
        self._search_document(
            classification_data, [doc_1], [doc_2, doc_not_to_be_found]
        )
        float_value_dict_1["float_value"] = 1.1
        float_value_dict_2["float_value"] = 3.3
        self._set_values(classification_data, prop_code, [float_value_dict_1, float_value_dict_2])
        self._search_document(
            classification_data, [doc_2], [doc_1, doc_not_to_be_found]
        )

    def test_float_with_units_search(self):
        class_code = "TEST_CLASS_UNITS"
        prop_code = "TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_2"

        float_value_dict_min = {
            "float_value": None,
            "float_value_normalized": None,
            "unit_object_id": "a64c2ed1-3f9f-11e7-b812-28d24433bf35"
        }

        float_value_dict_hour = {
            "float_value": None,
            "float_value_normalized": None,
            "unit_object_id": "f2b00fa1-3f8e-11e7-ae52-28d24433bf35"
        }

        float_value_dict_min["float_value"] = None
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [float_value_dict_min])
        float_value_dict_min["float_value"] = 90.0
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [float_value_dict_min])
        float_value_dict_min["float_value"] = 60.0
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, [float_value_dict_min])

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        float_value_dict_min["float_value"] = 90.0
        self._set_values(classification_data, prop_code, [float_value_dict_min])
        self._search_document(classification_data, [doc_1], [doc_0, doc_2])

        float_value_dict_hour["float_value"] = 1.5
        self._set_values(classification_data, prop_code, [float_value_dict_hour])
        self._search_document(classification_data, [doc_1], [doc_0, doc_2])

        float_value_dict_hour["float_value"] = '>=1.0 AND <1.75'
        self._set_values(classification_data, prop_code, [float_value_dict_hour])
        self._search_document(classification_data, [doc_1, doc_2], [doc_0])

    def test_int_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, [4711])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [1])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, [2])
        doc_12 = self._create_document_with_value("doc 12", class_code, prop_code, [12])

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found], []
        )

        self._set_values(classification_data, prop_code, ['=""'])
        self._search_document(
            classification_data, [doc_0], [doc_1, doc_2, doc_12, doc_not_to_be_found]
        )

        # normal int as search value ...
        self._set_values(classification_data, prop_code, [1])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, ['1'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, [' 1 '])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['!=2'])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_12, doc_not_to_be_found], [doc_2]
        )

        self._set_values(classification_data, prop_code, ['=1 OR =2'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['<12'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['>1 AND <=12'])
        self._search_document(
            classification_data, [doc_2, doc_12], [doc_0, doc_1, doc_not_to_be_found]
        )

    def test_int_multival_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT_MULTIVALUE"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, [4711, 4712])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [1, 2])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, [1, 3])

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        # search for partial list ...
        self._set_values(classification_data, prop_code, [1])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_not_to_be_found]
        )
        # search for exact match ...
        self._set_values(classification_data, prop_code, [1, 2])
        self._search_document(
            classification_data, [doc_1], [doc_2, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, [1, 3])
        self._search_document(
            classification_data, [doc_2], [doc_1, doc_not_to_be_found]
        )

    def test_multilang_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"

        multilang_other_value = {
            "de": {
                "iso_language_code": "de",
                "text_value": "de other test text"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en other test text"
            }
        }
        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, [multilang_other_value])

        multilang_value_1 = {
            "de": {
                "iso_language_code": "de",
                "text_value": "de value 1"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en value"
            }
        }
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [multilang_value_1])

        multilang_value_2 = {
            "de": {
                "iso_language_code": "de",
                "text_value": "de value 2"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en value"
            }
        }
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, [multilang_value_2])

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_1, doc_2, doc_not_to_be_found], []
        )

        # search for two languages ...
        self._set_values(classification_data, prop_code, [multilang_value_1])
        self._search_document(
            classification_data, [doc_1], [doc_2, doc_not_to_be_found]
        )

        # search for one language ...
        multilang_value = {
            "en": {
                "iso_language_code": "en",
                "text_value": "en value"
            }
        }
        self._set_values(classification_data, prop_code, [multilang_value])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_not_to_be_found]
        )

    def test_multilang_multival_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"

        multilang_other_value = {
            "de": {
                "iso_language_code": "de",
                "text_value": "de other test text"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en other test text"
            }
        }
        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, [multilang_other_value])

        multilang_value_1 = {
            "de": {
                "iso_language_code": "de",
                "text_value": "de value 1"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en value"
            }
        }
        multilang_value_2 = {
            "de": {
                "iso_language_code": "de",
                "text_value": "de value 2"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en value"
            }
        }
        multilang_value_3 = {
            "de": {
                "iso_language_code": "de",
                "text_value": "de value 3"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en value 3"
            }
        }

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [multilang_value_1, multilang_value_2])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, [multilang_value_1, multilang_value_3])

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        # search for partial list ...
        self._set_values(classification_data, prop_code, [multilang_value_1])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_not_to_be_found]
        )
        # search for exact match ...
        self._set_values(classification_data, prop_code, [multilang_value_1, multilang_value_2])
        self._search_document(
            classification_data, [doc_1], [doc_2, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, [multilang_value_1, multilang_value_3])
        self._search_document(
            classification_data, [doc_2], [doc_1, doc_not_to_be_found]
        )

        # search for cross languages ...
        multilang_value = dict(multilang_value_1)
        multilang_value["en"] = multilang_value_3["en"]
        self._set_values(classification_data, prop_code, [multilang_value])
        self._search_document(
            classification_data, [doc_2], [doc_1, doc_not_to_be_found]
        )

    @pytest.mark.skip(reason="Flaky")
    def test_objref_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF"

        ref_doc_1 = self.create_document("ref 1")
        ref_doc_2 = self.create_document("ref 2")

        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [ref_doc_1.cdb_object_id])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, [ref_doc_2.cdb_object_id])
        doc_12 = self._create_document_with_value("doc 12", class_code, prop_code, [ref_doc_1.cdb_object_id])

        self._timeout()

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2, doc_12], []
        )
        self._set_values(classification_data, prop_code, ['*'])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2, doc_12], []
        )

        self._set_values(classification_data, prop_code, ['=""'])
        self._search_document(
            classification_data, [doc_0], [doc_1, doc_2, doc_12]
        )
        self._set_values(classification_data, prop_code, ['!=""'])
        self._search_document(
            classification_data, [doc_1, doc_2, doc_12], [doc_0]
        )

        # normal search value ...
        self._set_values(classification_data, prop_code, [ref_doc_1.cdb_object_id])
        self._search_document(
            classification_data, [doc_1, doc_12], [doc_0, doc_2]
        )
        self._set_values(classification_data, prop_code, [ref_doc_2.cdb_object_id])
        self._search_document(
            classification_data, [doc_2], [doc_1, doc_12]
        )

        self._set_values(classification_data, prop_code, ['!={}'.format(ref_doc_2.cdb_object_id)])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_12], [doc_2]
        )

        self._set_values(
            classification_data, prop_code,
            ['={} OR ={}'.format(ref_doc_1.cdb_object_id, ref_doc_2.cdb_object_id)]
        )
        self._search_document(
            classification_data, [doc_1, doc_2, doc_12], [doc_0]
        )

    @pytest.mark.skip(reason="Flaky")
    def test_objref_multival_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF_MULTIVALUE"

        ref_doc_1 = self.create_document("ref 1")
        ref_doc_2 = self.create_document("ref 2")
        ref_doc_3 = self.create_document("ref 3")

        doc_1 = self._create_document_with_value(
            "doc 1", class_code, prop_code, [ref_doc_1.cdb_object_id, ref_doc_2.cdb_object_id]
        )
        doc_2 = self._create_document_with_value(
            "doc 2", class_code, prop_code, [ref_doc_1.cdb_object_id, ref_doc_3.cdb_object_id]
        )
        self._timeout()

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        # search for partial list ...
        self._set_values(classification_data, prop_code, [ref_doc_1.cdb_object_id])
        self._search_document(
            classification_data, [doc_1, doc_2]
        )
        # search for exact match ...
        self._set_values(classification_data, prop_code, [ref_doc_1.cdb_object_id, ref_doc_2.cdb_object_id])
        self._search_document(
            classification_data, [doc_1], [doc_2]
        )
        self._set_values(classification_data, prop_code, [ref_doc_1.cdb_object_id, ref_doc_3.cdb_object_id])
        self._search_document(
            classification_data, [doc_2], [doc_1]
        )

    def test_text_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["test text 1"])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, ["test text 2"])
        doc_12 = self._create_document_with_value("doc 12", class_code, prop_code, ["test text 1 or 2"])

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found], []
        )

        self._set_values(classification_data, prop_code, ['=""'])
        self._search_document(
            classification_data, [doc_0], [doc_1, doc_2, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['test text 1'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, [' test text 1 '])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['test text*'])
        self._search_document(
            classification_data, [doc_1, doc_2, doc_12], [doc_0, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, ['test text%'])
        self._search_document(
            classification_data, [doc_1, doc_2, doc_12], [doc_0, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, ['test text ?'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['!="test text 1"'])
        self._search_document(
            classification_data, [doc_0, doc_2, doc_12, doc_not_to_be_found], [doc_1]
        )

        self._set_values(classification_data, prop_code, ['="test text 1" OR ="test text 2"'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_0, doc_12, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['test text 1 \or 2']) # pylint: disable=W1401
        self._search_document(
            classification_data, [doc_12], [doc_0, doc_1, doc_2, doc_not_to_be_found]
        )
        doc_wildcards = self._create_document_with_value(
            "doc with wildcards", class_code, prop_code, ['value with wildcards *, % and ?']
        )
        self._set_values(classification_data, prop_code, ["*\**\%*\\and*\?*"]) # pylint: disable=W1401
        self._search_document(
            classification_data, [doc_wildcards], [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found]
        )

    def test_text_multival_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"

        doc_not_to_be_found = self._create_document_with_value(
            "other doc", class_code, prop_code, ["other test text 1", "other test text 2"]
        )
        doc_1 = self._create_document_with_value(
            "doc 1", class_code, prop_code, ["test text 1", "test text 2"]
        )
        doc_2 = self._create_document_with_value(
            "doc 2", class_code, prop_code, ["test text 1", "test text 3"]
        )

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        # search for partial list ...
        self._set_values(classification_data, prop_code, ['test text 1'])
        self._search_document(
            classification_data, [doc_1, doc_2], [doc_not_to_be_found]
        )
        # search for exact match ...
        self._set_values(classification_data, prop_code, ['test text 1', 'test text 2'])
        self._search_document(
            classification_data, [doc_1], [doc_2, doc_not_to_be_found]
        )
        self._set_values(classification_data, prop_code, ['test text 1', 'test text 3'])
        self._search_document(
            classification_data, [doc_2], [doc_1, doc_not_to_be_found]
        )

    def test_float_range_search(self):
        class_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE"
        property_code = "%s_TEST_PROP_FLOAT_RANGE" % class_code
        stecker_1 = self._create_document_with_value(
            "Stecker 1", class_code, property_code, [{
                "min": {"float_value": 100, "range_identifier": "min"},
                "max": {"float_value": 120, "range_identifier": "max"},
            }]
        )
        stecker_2 = self._create_document_with_value(
            "Stecker 2", class_code, property_code, [{
                "min": {"float_value": 200, "range_identifier": "min"},
                "max": {"float_value": 240, "range_identifier": "max"},
            }]
        )
        stecker_3 = self._create_document_with_value(
            "Stecker 3", class_code, property_code, [{
                "min": {"float_value": 110, "range_identifier": "min"},
                "max": {"float_value": 220, "range_identifier": "max"},
            }]
        )
        stecker_4 = self._create_document_with_value(
            "Stecker 4", class_code, property_code, [{
                "min": {"float_value": 100, "range_identifier": "min"},
                "max": {"float_value": 120, "range_identifier": "max"},
            }, {
                "min": {"float_value": 200, "range_identifier": "min"},
                "max": {"float_value": 240, "range_identifier": "max"},
            }]
        )
        search_data = api.get_new_classification(
            [class_code], with_defaults=False
        )

        # Search by class code
        self._search_document(
            search_data,
            [stecker_1, stecker_2, stecker_3, stecker_4],
            [],
        )

        # Search discrete value
        self._set_values(search_data, property_code, [{
            "min": {"float_value": 110, "range_identifier": "min"},
            "max": {"float_value": 110, "range_identifier": "max"},
        }])
        self._search_document(
            search_data,
            [stecker_1, stecker_3, stecker_4],
            [stecker_2],
        )

        # Search exact lower boundary
        self._set_values(search_data, property_code, [{
            "min": {"float_value": "=100", "range_identifier": "min"},
            "max": {"float_value": "*", "range_identifier": "max"},
        }])
        self._search_document(
            search_data,
            [stecker_1, stecker_4],
            [stecker_2, stecker_3],
        )

        # Search exact upper boundary
        self._set_values(search_data, property_code, [{
            "min": {"float_value": "*", "range_identifier": "min"},
            "max": {"float_value": "=240", "range_identifier": "max"},
        }])
        self._search_document(
            search_data,
            [stecker_2, stecker_4],
            [stecker_1, stecker_3],
        )

        # Search exact range
        self._set_values(search_data, property_code, [{
            "min": {"float_value": "=100", "range_identifier": "min"},
            "max": {"float_value": "=120", "range_identifier": "max"},
        }])
        self._search_document(
            search_data,
            [stecker_1, stecker_4],
            [stecker_2, stecker_3],
        )

        # Search partial range
        self._set_values(search_data, property_code, [{
            "min": {"float_value": "<=110", "range_identifier": "min"},
            "max": {"float_value": ">=120", "range_identifier": "max"},
        }])
        self._search_document(
            search_data,
            [stecker_1, stecker_3, stecker_4],
            [stecker_2],
        )

        # Search intersection
        self._set_values(search_data, property_code, [{
            "min": {"float_value": "120", "range_identifier": "min"},
            "max": {"float_value": "130", "range_identifier": "max"},
        }])
        self._search_document(
            search_data,
            [stecker_1, stecker_3, stecker_4],
            [stecker_2],
        )
        self._set_values(search_data, property_code, [{
            "min": {"float_value": "90", "range_identifier": "min"},
            "max": {"float_value": "130", "range_identifier": "max"},
        }])
        self._search_document(
            search_data,
            [stecker_1, stecker_3, stecker_4],
            [stecker_2],
        )
        self._set_values(search_data, property_code, [{
            "min": {"float_value": "190", "range_identifier": "min"},
            "max": {"float_value": "200", "range_identifier": "max"},
        }])
        self._search_document(
            search_data,
            [stecker_2, stecker_3, stecker_4],
            [stecker_1],
        )

    def test_float_range_multival_search(self):
        class_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE"
        property_code = "%s_TEST_PROP_FLOAT_RANGE" % class_code
        property_values = [
            {
                "min": {"float_value": 100, "range_identifier": "min"},
                "max": {"float_value": 120, "range_identifier": "max"},
            }, {
                "min": {"float_value": 200, "range_identifier": "min"},
                "max": {"float_value": 240, "range_identifier": "max"},
            },
        ]
        stecker_1 = self._create_document_with_value(
            "Stecker 1", class_code, property_code, [property_values[0]]
        )
        stecker_4 = self._create_document_with_value(
            "Stecker 4", class_code, property_code, property_values
        )
        search_data = api.get_new_classification(
            [class_code], with_defaults=False
        )
        self._set_values(search_data, property_code, property_values)
        self._search_document(search_data, [stecker_4], [stecker_1])

    def test_block_search(self):
        class_code = "TEST_CLASS_SEARCH"

        doc_0 = self.create_document("doc 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        api.update_classification(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEXT_EDITABLE",
            ["text"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEXT_MULTIVALUE",
            ["text 1", "text 2"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["block text"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["block text 1", "block text 2"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ["nested block text"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["sub block text"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["sub block text 1", "sub block text 2"]
        )
        api.update_classification(doc_1, classification_data, type_conversion=convert_from_json)

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1], []
        )

        # search for top level values ...
        self._set_values(classification_data, "TEST_CLASS_SEARCH_TEXT_EDITABLE", ['text'])
        self._search_document(classification_data, [doc_1], [doc_0])
        self._set_values(classification_data, "TEST_CLASS_SEARCH_TEXT_MULTIVALUE", ["text 1"])
        self._search_document(classification_data, [doc_1], [doc_0])

        # search for top level blocks ...
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["block text"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["block text 2"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])

        # search for sub level blocks ...
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ["nested block text"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["sub block text"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["sub block text 1", "sub block text 2"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])

        # search for empty top level block properties
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1], []
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ['=""']
        )
        self._search_document(classification_data, [doc_0], [doc_1])

        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ['!=""']
        )
        self._search_document(classification_data, [doc_1], [doc_0])

        # search for empty sub level block properties
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1], []
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ['=""']
        )
        self._search_document(classification_data, [doc_0], [doc_1])
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ['!=""']
        )
        self._search_document(classification_data, [doc_1], [doc_0])

    def test_multivalue_block_search(self):
        class_code = "TEST_CLASS_SEARCH"

        doc_0 = self.create_document("doc 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        api.update_classification(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1", "multivalue text 1.1.2"]
        )
        classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE"].append(
            deepcopy(
                classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE"][0]
            )
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:001/TEXT_EDITABLE",
            ["text 1.2"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:001/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1", "multivalue text 1.2.2"]
        )
        api.update_classification(doc_1, classification_data, type_conversion=convert_from_json)

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1], []
        )

        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])

        # mixed block child value search should not have a result
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1"]
        )
        self._search_document(classification_data, [], [doc_0, doc_1])

        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])

    def test_multivalue_nested_block_search(self):
        class_code = "TEST_CLASS_SEARCH"

        doc_0 = self.create_document("doc 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        api.update_classification(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1.1", "multivalue text 1.1.1.2"]
        )
        classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"].append(
            deepcopy(
                classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"][0]
            )
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.2.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1.1", "multivalue text 1.2.1.2"]
        )

        api.update_classification(doc_1, classification_data, type_conversion=convert_from_json)

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_0, doc_1], []
        )

        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1.1"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])

        # mixed block child value search should not have a result
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1.1"]
        )
        self._search_document(classification_data, [], [doc_0, doc_1])

        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1.1"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])

    def test_mixed_multivalue_nested_block_search(self):
        class_code = "TEST_CLASS_SEARCH"

        doc_0 = self.create_document("doc 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        api.update_classification(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_TEXT",
            ["A"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1.1", "multivalue text 1.1.1.2"]
        )
        classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"].append(
            deepcopy(
                classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"][0]
            )
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_TEXT",
            ["B"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.2.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1.1", "multivalue text 1.2.1.2"]
        )
        api.update_classification(doc_1, classification_data, type_conversion=convert_from_json)

        # search with mixed block values on different block levels ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_TEXT",
            ["B"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1.1", "multivalue text 1.1.1.2"]
        )

        # query does not work as expected with solr and the current classification index data.
        # doc_1 is found because solr queries are aggregated for each block level.
        self._search_document(classification_data, [doc_1], [doc_0])

    def test_catalog_property_search(self):
        prop_code = "TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value(
            "other doc", None, prop_code, ["other test text"]
        )
        doc_0 = self._create_document_with_value("doc 0", None, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", None, prop_code, ["test text 1"])
        doc_2 = self._create_document_with_value("doc 2", None, prop_code, ["test text 2"])
        doc_12 = self._create_document_with_value("doc 12", None, prop_code, ["test text 1 or 2"])

        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        class_prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        class_doc_not_to_be_found = self._create_document_with_value(
            "other doc with class", class_code, class_prop_code, ["other test text"]
        )
        class_doc_0 = self._create_document_with_value(
            "doc with class 0", class_code, class_prop_code, [None]
        )
        class_doc_1 = self._create_document_with_value(
            "doc with class 1", class_code, class_prop_code, ["test text 1"]
        )
        class_doc_2 = self._create_document_with_value(
            "doc with class 2", class_code, class_prop_code, ["test text 2"]
        )
        class_doc_12 = self._create_document_with_value(
            "doc with class 12", class_code, class_prop_code, ["test text 1 or 2"]
        )

        classification_data = api.create_additional_props([prop_code])
        classification_data["class_independent_property_codes"] = [prop_code]
        self._set_values(classification_data, prop_code, ['=""'])
        self._search_document(
            classification_data,
            [
                doc_0, class_doc_0
            ],
            [
                doc_1, class_doc_1,
                doc_2, class_doc_2,
                doc_12, class_doc_12,
                doc_not_to_be_found, class_doc_not_to_be_found
            ]
        )

        self._set_values(classification_data, prop_code, ['test text 1'])
        self._search_document(
            classification_data,
            [
                doc_1, class_doc_1
            ],
            [
                doc_0, class_doc_0,
                doc_2, class_doc_2,
                doc_12, class_doc_12,
                doc_not_to_be_found, class_doc_not_to_be_found
            ]
        )

        self._set_values(classification_data, prop_code, ['test text*'])
        self._search_document(
            classification_data,
            [
                doc_1, class_doc_1,
                doc_2, class_doc_2,
                doc_12, class_doc_12
            ],
            [
                doc_0, class_doc_0,
                doc_not_to_be_found, class_doc_not_to_be_found
            ]
        )

        self._set_values(classification_data, prop_code, ['test text%'])
        self._search_document(
            classification_data,
            [
                doc_1, class_doc_1,
                doc_2, class_doc_2,
                doc_12, class_doc_12
            ],
            [
                doc_0, class_doc_0,
                doc_not_to_be_found, class_doc_not_to_be_found
            ]
        )

        self._set_values(classification_data, prop_code, ['test text ?'])
        self._search_document(
            classification_data,
            [
                doc_1, class_doc_1,
                doc_2, class_doc_2
            ],
            [
                doc_0, class_doc_0,
                doc_12, class_doc_12,
                doc_not_to_be_found, class_doc_not_to_be_found
            ]
        )

        self._set_values(classification_data, prop_code, ['!="test text 1"'])
        self._search_document(
            classification_data,
            [
                doc_0, class_doc_0,
                doc_2, class_doc_2,
                doc_12, class_doc_12,
                doc_not_to_be_found, class_doc_not_to_be_found
            ],
            [
                doc_1, class_doc_1
            ]
        )

        self._set_values(classification_data, prop_code, ['="test text 1" OR ="test text 2"'])
        self._search_document(
            classification_data,
            [
                doc_1, class_doc_1,
                doc_2, class_doc_2
            ],
            [
                doc_0, class_doc_0,
                doc_12, class_doc_12,
                doc_not_to_be_found, class_doc_not_to_be_found
            ]
        )

        self._set_values(classification_data, prop_code, ['test text 1 \or 2']) # pylint: disable=W1401
        self._search_document(
            classification_data,
            [
                doc_12, class_doc_12
            ],
            [
                doc_0, class_doc_0,
                doc_1, class_doc_1,
                doc_2, class_doc_2,
                doc_not_to_be_found, class_doc_not_to_be_found
            ]
        )

        doc_special_chars = self._create_document_with_value(
            "doc with wildcards", None, prop_code, ['value with wildcards *, % and ?']
        )
        class_doc_special_chars = self._create_document_with_value(
            "class doc with wildcards", class_code, class_prop_code, ['value with wildcards *, % and ?']
        )
        self._set_values(classification_data, prop_code, ["*\**\%*\\and*\?*"]) # pylint: disable=W1401
        self._search_document(
            classification_data,
            [
                doc_special_chars, class_doc_special_chars
            ],
            [
                doc_0, class_doc_0,
                doc_1, class_doc_1,
                doc_2, class_doc_2,
                doc_12, class_doc_12,
                doc_not_to_be_found, class_doc_not_to_be_found
            ]
        )

    def test_catalog_property_block_search(self):
        prop_code = "TEST_PROP_SEARCH_BLOCK"
        prop_code_nested = "TEST_PROP_SEARCH_BLOCK_NESTED"

        doc_0 = self.create_document("doc 0")
        classification_data = api.create_additional_props([prop_code, prop_code_nested])
        api.update_additional_props(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.create_additional_props([prop_code, prop_code_nested])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["block text"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["block text 1", "block text 2"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ["nested block text"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["sub block text"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["sub block text 1", "sub block text 2"]
        )
        api.update_additional_props(doc_1, classification_data, type_conversion=convert_from_json)

        # search for top level blocks ...
        classification_data = api.create_additional_props([prop_code])
        classification_data["class_independent_property_codes"] = [prop_code, prop_code_nested]

        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["block text"]
        )
        self._search_document(
            classification_data, [doc_1], [doc_0]
        )

        # search for sub level blocks ...
        classification_data = api.create_additional_props([prop_code_nested])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ["nested block text"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["sub block text"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["sub block text 1", "sub block text 2"]
        )
        self._search_document(classification_data, [doc_1], [doc_0])

        # search for empty top level block properties
        classification_data = api.create_additional_props([prop_code])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ['=""']
        )
        self._search_document(classification_data, [doc_0], [doc_1])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ['!=""']
        )
        self._search_document(classification_data, [doc_1], [doc_0])

        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ['!="value not set"']
        )
        self._search_document(classification_data, [doc_0, doc_1], [])

    def test_catalog_multivalue_block_search(self):
        class_code = "TEST_CLASS_SEARCH"

        class_doc_0 = self.create_document("class doc 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        api.update_classification(class_doc_0, classification_data, type_conversion=convert_from_json)

        class_doc_1 = self.create_document("class doc 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1", "multivalue text 1.1.2"]
        )
        classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE"].append(
            deepcopy(
                classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE"][0]
            )
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:001/TEXT_EDITABLE",
            ["text 1.2"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_MULTIVALUE:001/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1", "multivalue text 1.2.2"]
        )
        api.update_classification(class_doc_1, classification_data, type_conversion=convert_from_json)

        prop_code = "TEST_PROP_SEARCH_BLOCK_MULTIVALUE"

        doc_0 = self.create_document("doc 0")
        classification_data = api.create_additional_props([prop_code])
        api.update_additional_props(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.create_additional_props([prop_code])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1", "multivalue text 1.1.2"]
        )
        classification_data[ClassificationConstants.PROPERTIES]["TEST_PROP_SEARCH_BLOCK_MULTIVALUE"].append(
            deepcopy(
                classification_data[ClassificationConstants.PROPERTIES]["TEST_PROP_SEARCH_BLOCK_MULTIVALUE"][0]
            )
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_MULTIVALUE:001/TEXT_EDITABLE",
            ["text 1.2"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_MULTIVALUE:001/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1", "multivalue text 1.2.2"]
        )
        api.update_additional_props(doc_1, classification_data, type_conversion=convert_from_json)

        classification_data = api.create_additional_props([prop_code])
        classification_data["class_independent_property_codes"] = [prop_code]
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1"]
        )
        self._search_document(classification_data, [doc_1, class_doc_1], [doc_0, class_doc_0])

        # mixed block child value search should not have a result
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1"]
        )
        self._search_document(classification_data, [], [doc_0, class_doc_0, doc_1, class_doc_1])

        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1"]
        )
        self._search_document(classification_data, [doc_1, class_doc_1], [doc_0, class_doc_0])

    def test_catalog_multivalue_nested_block_search(self):
        class_code = "TEST_CLASS_SEARCH"

        class_doc_0 = self.create_document("class doc 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        api.update_classification(class_doc_0, classification_data, type_conversion=convert_from_json)

        class_doc_1 = self.create_document("class doc 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1.1", "multivalue text 1.1.1.2"]
        )
        classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"].append(
            deepcopy(
                classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"][0]
            )
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.2.1"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1.1", "multivalue text 1.2.1.2"]
        )
        api.update_classification(class_doc_1, classification_data, type_conversion=convert_from_json)

        prop_code_nested = "TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"

        doc_0 = self.create_document("doc 0")
        classification_data = api.create_additional_props([prop_code_nested])
        api.update_additional_props(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.create_additional_props([prop_code_nested])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1.1"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1.1", "multivalue text 1.1.1.2"]
        )
        classification_data[ClassificationConstants.PROPERTIES]["TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"].append(
            deepcopy(
                classification_data[ClassificationConstants.PROPERTIES]["TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE"][0]
            )
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.2.1"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:001/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1.1", "multivalue text 1.2.1.2"]
        )
        api.update_additional_props(doc_1, classification_data, type_conversion=convert_from_json)

        classification_data = api.create_additional_props([prop_code_nested])
        classification_data["class_independent_property_codes"] = [prop_code_nested]
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_EDITABLE",
            ["text 1.1.1"]
        )
        self._search_document(classification_data, [class_doc_1], [class_doc_0])

        # mixed block child value search should not have a result
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.2.1.1"]
        )
        self._search_document(classification_data, [], [class_doc_0, class_doc_1])

        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED_MULTIVALUE:000/TEST_PROP_SEARCH_BLOCK_MULTIVALUE:000/TEXT_MULTIVALUE",
            ["multivalue text 1.1.1.1"]
        )
        self._search_document(classification_data, [class_doc_1], [class_doc_0])

    def test_catalog_block_used_in_classes_search(self):
        prop_code = "TEST_PROP_BLOCK_WITH_DATE"

        doc_0 = self.create_document("doc 0")
        classification_data = api.create_additional_props([prop_code])
        api.update_additional_props(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.create_additional_props([prop_code])
        self._set_values(
            classification_data,
            "TEST_PROP_BLOCK_WITH_DATE/TEST_PROP_DATE",
            ["3.7.1987"]
        )
        api.update_additional_props(doc_1, classification_data, type_conversion=convert_from_json)

        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"

        class_doc_0 = self.create_document("doc with class 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        api.update_classification(class_doc_0, classification_data, type_conversion=convert_from_json)

        class_doc_1 = self.create_document("doc with class 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE/TEST_PROP_DATE",
            ["3.7.1987"]
        )
        api.update_classification(class_doc_1, classification_data, type_conversion=convert_from_json)

        # search for top level blocks ...
        classification_data = api.create_additional_props([prop_code])
        classification_data["class_independent_property_codes"] = [prop_code]

        self._set_values(
            classification_data,
            "TEST_PROP_BLOCK_WITH_DATE/TEST_PROP_DATE",
            ["3.7.1987"]
        )
        self._search_document(
            classification_data, [doc_1, class_doc_1], [doc_0, class_doc_0]
        )

    def test_catalog_block_nested_used_in_classes_search(self):
        class_code = "TEST_CLASS_SEARCH"

        class_doc_0 = self.create_document("class doc 0")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        api.update_classification(class_doc_0, classification_data, type_conversion=convert_from_json)

        class_doc_1 = self.create_document("class doc 1")
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["block text"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["block text 1", "block text 2"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ["nested block text"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["sub block text"]
        )
        self._set_values(
            classification_data,
            "TEST_CLASS_SEARCH_TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["sub block text 1", "sub block text 2"]
        )
        api.update_classification(class_doc_1, classification_data, type_conversion=convert_from_json)

        prop_code = "TEST_PROP_SEARCH_BLOCK"
        prop_code_nested = "TEST_PROP_SEARCH_BLOCK_NESTED"

        doc_0 = self.create_document("doc 0")
        classification_data = api.create_additional_props([prop_code, prop_code_nested])
        api.update_additional_props(doc_0, classification_data, type_conversion=convert_from_json)

        doc_1 = self.create_document("doc 1")
        classification_data = api.create_additional_props([prop_code, prop_code_nested])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["block text"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["block text 1", "block text 2"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ["nested block text"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["sub block text"]
        )
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["sub block text 1", "sub block text 2"]
        )
        api.update_additional_props(doc_1, classification_data, type_conversion=convert_from_json)

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [class_doc_0, class_doc_1], []
        )

        # search for sub level blocks ...
        classification_data = api.create_additional_props([prop_code, prop_code_nested])
        classification_data["class_independent_property_codes"] = [prop_code, prop_code_nested]
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ["nested block text"]
        )
        self._search_document(classification_data, [doc_1, class_doc_1], [doc_0, class_doc_0])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ["sub block text"]
        )
        self._search_document(classification_data, [doc_1, class_doc_1], [doc_0, class_doc_0])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_SEARCH_BLOCK/TEXT_MULTIVALUE",
            ["sub block text 1", "sub block text 2"]
        )
        self._search_document(classification_data, [doc_1, class_doc_1], [doc_0, class_doc_0])

        # search for empty top level block properties
        classification_data = api.create_additional_props([prop_code, prop_code_nested])
        classification_data["class_independent_property_codes"] = [prop_code, prop_code_nested]
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ['=""']
        )
        self._search_document(classification_data, [class_doc_0, doc_0], [class_doc_1, doc_1])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK/TEXT_EDITABLE",
            ['!=""']
        )
        self._search_document(classification_data, [class_doc_1, doc_1], [class_doc_0, doc_0])

        # search for empty sub level block properties
        classification_data = api.create_additional_props([prop_code, prop_code_nested])
        classification_data["class_independent_property_codes"] = [prop_code, prop_code_nested]
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ['=""']
        )
        self._search_document(classification_data, [class_doc_0, doc_0], [class_doc_1, doc_1])
        self._set_values(
            classification_data,
            "TEST_PROP_SEARCH_BLOCK_NESTED/TEST_PROP_TEXT",
            ['!=""']
        )
        self._search_document(classification_data, [class_doc_1, doc_1], [class_doc_0, doc_0])

    def test_search_after_partial_update(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["test text 1"])

        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['test text 1'])
        self._search_document(
            classification_data, [doc_1], []
        )

        addtl_prop_data = api.create_additional_props(["TEST_PROP_TEXT"])
        addtl_prop_data["properties"]["TEST_PROP_TEXT"][0]["value"] = "test free text"
        api.update_additional_props(doc_1, addtl_prop_data, type_conversion=convert_from_json)

        self._search_document(
            classification_data, [doc_1], []
        )

    def test_search_with_enum_labels(self):
        class_code = "TEST_CLASS_ENUM_LABELS"
        prop_code = "TEST_CLASS_ENUM_LABELS_TEST_PROP_ENUM_LABELS"

        doc_bt = self._create_document_with_value("Doc BT", class_code, prop_code, ["BT"])
        doc_lt = self._create_document_with_value("Doc LT", class_code, prop_code, ["LT"])
        doc_ut = self._create_document_with_value("Doc UT", class_code, prop_code, ["UT"])

        # search for values
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['BT'])
        self._search_document(
            classification_data, [doc_bt], [doc_lt, doc_ut]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['!=BT'])
        self._search_document(
            classification_data, [doc_lt, doc_ut], [doc_bt]
        )

        # search for labels
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['Lagertemperatur'])
        self._search_document(
            classification_data, [doc_lt], [doc_bt, doc_ut]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['!=Lagertemperatur'])
        self._search_document(
            classification_data, [doc_bt, doc_ut], [doc_lt]
        )

        # search with wildcards
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['Betriebs*'])
        self._search_document(
            classification_data, [doc_bt], [doc_lt, doc_ut]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['Betriebs\*'])
        self._search_document(
            classification_data, [], [doc_bt, doc_lt, doc_ut]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['!=Betriebs*'])
        self._search_document(
            classification_data, [doc_lt, doc_ut], [doc_bt]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['*temp*'])
        self._search_document(
            classification_data, [doc_bt, doc_lt, doc_ut], []
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['!=*temp*'])
        self._search_document(
            classification_data, [], [doc_bt, doc_lt, doc_ut]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['=?etriebstemperatur'])
        self._search_document(
            classification_data, [doc_bt], [doc_lt, doc_ut]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['=\?etriebstemperatur'])
        self._search_document(
            classification_data, [], [doc_bt, doc_lt, doc_ut]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['=?T'])
        self._search_document(
            classification_data, [doc_bt, doc_lt, doc_ut], []
        )

        # search with logical expressions
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['=Betriebs* OR =UT'])
        self._search_document(
            classification_data, [doc_bt, doc_ut], [doc_lt]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['=Betriebs* AND =BT'])
        self._search_document(
            classification_data, [doc_bt], [doc_lt, doc_ut]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['=Betriebs* AND !=LT'])
        self._search_document(
            classification_data, [doc_bt], [doc_lt, doc_ut]
        )

        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['((=Betriebs* OR =LT) AND !=Umgeb*)'])
        self._search_document(
            classification_data, [doc_bt, doc_lt], [doc_ut]
        )

    def test_search_currency(self):
        class_code = "TEST_CLASS_CURRENCY"
        prop_code = "TEST_CLASS_CURRENCY_TEST_PROP_CURRENCY"

        eur = Unit.KeywordQuery(symbol="EUR")[0]
        gbp = Unit.KeywordQuery(symbol="GBP")[0]
        usd = Unit.KeywordQuery(symbol="USD")[0]

        none_value_dict = {
            "float_value": None,
            "float_value_normalized": None,
            "unit_object_id": eur.cdb_object_id
        }
        doc_none = self._create_document_with_value("Doc EUR", class_code, prop_code, [none_value_dict])

        value_dict = {
            "float_value": 1000.01,
            "float_value_normalized": 200.00,
            "unit_object_id": eur.cdb_object_id
        }
        doc_eur = self._create_document_with_value("Doc EUR", class_code, prop_code, [value_dict])

        value_dict["unit_object_id"] = gbp.cdb_object_id
        doc_gbp = self._create_document_with_value("Doc GBP", class_code, prop_code, [value_dict])

        value_dict["unit_object_id"] = usd.cdb_object_id
        doc_usd_1 = self._create_document_with_value("Doc USD 1", class_code, prop_code, [value_dict])
        value_dict["float_value"] = 200.00
        doc_usd_2 = self._create_document_with_value("Doc USD 2", class_code, prop_code, [value_dict])

        # no search value set, search only with assigned class ...
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._search_document(
            classification_data, [doc_eur, doc_gbp, doc_usd_1, doc_usd_2, doc_none], []
        )

        # search for non empty value
        value_dict["float_value"] = '!=""'
        value_dict["unit_object_id"] = eur.cdb_object_id
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_eur], [doc_gbp, doc_usd_1, doc_usd_2, doc_none]
        )

        # search for empty value
        value_dict["float_value"] = '=""'
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_none], [doc_eur, doc_gbp, doc_usd_1, doc_usd_2]
        )

        # search for values
        value_dict = {
            "float_value": 1000.01,
            "float_value_normalized": None,
            "unit_object_id": eur.cdb_object_id
        }
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_eur], [doc_gbp, doc_usd_1, doc_usd_2, doc_none]
        )

        value_dict = {
            "float_value": 1000.01,
            "float_value_normalized": None,
            "unit_object_id": usd.cdb_object_id
        }
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_usd_1], [doc_eur, doc_gbp, doc_usd_2, doc_none]
        )

        value_dict["unit_object_id"] = eur.cdb_object_id
        value_dict["float_value"] = '1000.01'
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_eur], [doc_gbp, doc_usd_1, doc_usd_2, doc_none]
        )

        value_dict["unit_object_id"] = usd.cdb_object_id
        value_dict["float_value"] = '!=200.0'
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_usd_1], [doc_eur, doc_gbp, doc_usd_2, doc_none]
        )

        value_dict["unit_object_id"] = usd.cdb_object_id
        value_dict["float_value"] = '=200.0 OR =1000.01'
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_usd_1, doc_usd_2], [doc_eur, doc_gbp, doc_none]
        )

        value_dict["unit_object_id"] = usd.cdb_object_id
        value_dict["float_value"] = '<900.00'
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_usd_2], [doc_usd_1, doc_eur, doc_gbp, doc_none]
        )

        value_dict["unit_object_id"] = usd.cdb_object_id
        value_dict["float_value"] = '>99.99 AND <=1000.00'
        self._set_values(classification_data, prop_code, [value_dict])
        self._search_document(
            classification_data, [doc_usd_2], [doc_usd_1, doc_eur, doc_gbp, doc_none]
        )

    def test_search_classification(self):
        """  Test search classification with external rest api. """

        client = Client(Root())
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        created_ids = set()
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        created_ids.add(doc_0.cdb_object_id)
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["test text 1"])
        created_ids.add(doc_1.cdb_object_id)
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, ["test text 2"])
        created_ids.add(doc_2.cdb_object_id)
        doc_12 = self._create_document_with_value("doc 12", class_code, prop_code, ["test text 1 or 2"])
        created_ids.add(doc_12.cdb_object_id)

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        url = "/api/cs.classification/v1/search"
        classification_data["max_results"] = 1000
        classification_data["with_classification"] = False
        result = client.post_json(url, classification_data)
        assert result

        found_ids = set()
        for doc in result.json:
            found_ids.add(doc['cdb_object_id'])
            self.assertFalse('system:classification' in doc)

        self.assertTrue(created_ids.issubset(found_ids))

        classification_data["with_classification"] = True
        result = client.post_json(url, classification_data)
        assert result

        found_ids = set()
        for doc in result.json:
            assert doc['system:classification']

    def test_text_search_with_date(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["061-102&0100-0-001C3"])

        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="061-102&0100-0-001C3"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

    def test_text_search_with_hash(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["#150"])

        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="#150"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['="#*"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

    def test_text_search_with_special_chars(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value(
            "doc with wildcards", class_code, prop_code, [''.join(TestSearchParser.specialchars)]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, [''.join(TestSearchParser.specialchars)])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )
        for specialchar in TestSearchParser.specialchars:
            self._set_values(classification_data, prop_code, ['="*{}*"'.format(specialchar)])
            self._search_document(
                classification_data, [doc_1], [doc_0, doc_not_to_be_found]
            )

    def test_text_search_with_special_chars_to_be_masked(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value(
            "doc with wildcards", class_code, prop_code, [''.join(TestSearchParser.specialchars_to_be_masked)]
        )
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['\\'.join(TestSearchParser.specialchars_to_be_masked)])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )
        for specialchar in TestSearchParser.specialchars_to_be_masked:
            self._set_values(classification_data, prop_code, ['="*\\{}*"'.format(specialchar)])
            self._search_document(
                classification_data, [doc_1], [doc_0, doc_not_to_be_found]
            )

    def test_text_search_with_chinese_and_japanese_unicode_letters(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["測試"])

        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="測試"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["テスト"])
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="テスト"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

    def test_text_search_with_special_unicode_chars(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["".join(TestSearchParser.unicode_special_chars)])

        classification_data = api.get_new_classification([class_code], with_defaults=False)
        for special_car in TestSearchParser.unicode_special_chars:
            self._set_values(classification_data, prop_code, ['="*{}*"'.format(special_car)])
            self._search_document(
                classification_data, [doc_1], [doc_0, doc_not_to_be_found]
            )

    def test_text_search_with_description_including_special_chars(self):
        class_code = "TEST_CLASS_SEARCH_DESCRIPTION"
        prop_code = "TEST_CLASS_SEARCH_DESCRIPTION_TEST_PROP_TEXT_ENUM_WITH_DESCRIPTION"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["1_"])
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['=1\('])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["_1"])
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['=\(1'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["1-"])
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="1_"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["1-1"])
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="1_1"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["-1"])
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="_1"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["-1-1"])
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="_1_1"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["-1-1-"])
        classification_data = api.get_new_classification([class_code], with_defaults=False)
        self._set_values(classification_data, prop_code, ['="_1_1_"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_not_to_be_found]
        )

    def test_text_search_including_special_chars(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code, ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [">150"])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, ["<150"])
        doc_3 = self._create_document_with_value("doc 2", class_code, prop_code, ["15<0"])
        doc_4 = self._create_document_with_value("doc 2", class_code, prop_code, ["150<"])
        doc_5 = self._create_document_with_value("doc 2", class_code, prop_code, ["<=150"])

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        self._set_values(classification_data, prop_code, ['>150'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_3, doc_4, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['=">150"'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_3, doc_4, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['="<150"'])
        self._search_document(
            classification_data, [doc_2], [doc_0, doc_1, doc_3, doc_4, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['<150'])
        self._search_document(
            classification_data, [doc_2], [doc_0, doc_1, doc_3, doc_4, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['15<0'])
        self._search_document(
            classification_data, [doc_3], [doc_0, doc_1, doc_2, doc_4, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['150<'])
        self._search_document(
            classification_data, [doc_4], [doc_0, doc_1, doc_2, doc_3, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['<=150'])
        self._search_document(
            classification_data, [doc_5], [doc_0, doc_1, doc_2, doc_3, doc_4, doc_not_to_be_found]
        )

    def test_text_search_label_with_spaces(self):
        class_code = "TEST_CLASS_ENUM_LABELS_WITH_SPACES"
        prop_code = "TEST_CLASS_ENUM_LABELS_WITH_SPACES_TEST_PROP_ENUM_LABELS_WITH_SPACES"

        doc_not_to_be_found = self._create_document_with_value("other doc", class_code, prop_code,
                                                               ["other test text"])
        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, ["1"])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, ["2"])
        doc_3 = self._create_document_with_value("doc 2", class_code, prop_code, ["3"])

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        self._set_values(classification_data, prop_code, ['Wert 1'])
        self._search_document(
            classification_data, [doc_1], [doc_0, doc_2, doc_3, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['Wert 2'])
        self._search_document(
            classification_data, [doc_2], [doc_0, doc_1, doc_3, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['Wert 3'])
        self._search_document(
            classification_data, [doc_3], [doc_0, doc_1, doc_2, doc_not_to_be_found]
        )

        self._set_values(classification_data, prop_code, ['Wert *'])
        self._search_document(
            classification_data, [doc_1, doc_2, doc_3], [doc_0, doc_not_to_be_found]
        )

    def test_class_search(self):
        class_code_1 = "TEST_CLASS_RIVET"
        class_code_2 = "TEST_CLASS_SCREW"

        doc_class_1 = self.create_document(class_code_1)
        classification_data = api.get_new_classification([class_code_1], with_defaults=False)
        api.update_classification(doc_class_1, classification_data, type_conversion=convert_from_json)

        doc_class_2 = self.create_document(class_code_2)
        classification_data = api.get_new_classification([class_code_2], with_defaults=False)
        api.update_classification(doc_class_2, classification_data, type_conversion=convert_from_json)

        doc_class_both = self.create_document(class_code_1 + ", " + class_code_2)
        classification_data = api.get_new_classification([class_code_1, class_code_2], with_defaults=False)
        api.update_classification(doc_class_both, classification_data, type_conversion=convert_from_json)

        self._timeout()

        classification_data = api.get_new_classification([class_code_1], with_defaults=False)
        self._search_document(
            classification_data, [doc_class_1, doc_class_both], [doc_class_2]
        )

        classification_data = api.get_new_classification([class_code_2], with_defaults=False)
        self._search_document(
            classification_data, [doc_class_2, doc_class_both], [doc_class_1]
        )

        classification_data = api.get_new_classification([class_code_1, class_code_2], with_defaults=False)
        self._search_document(
            classification_data, [doc_class_both], [doc_class_1, doc_class_2]
        )

        classification_data = api.get_new_classification(["TEST_CLASS_ARTICLE"], with_defaults=False)
        self._search_document(
            classification_data, [doc_class_1, doc_class_2, doc_class_both], []
        )

        classification_data = api.get_new_classification(
            ["TEST_CLASS_ARTICLE", "TEST_CLASS_UNITS"], with_defaults=False
        )
        self._search_document(
            classification_data, [], [doc_class_1, doc_class_2, doc_class_both],
        )


    def test_search_partial_index_update(self):

        def search_for_classification(class_code, prop_code, find_nothing=False):
            # no search value set, search only with assigned class ...
            if class_code:
                classification_data = api.get_new_classification([class_code], with_defaults=False)
            else:
                classification_data = api.create_additional_props([prop_code])

            self._set_values(classification_data, prop_code, ['test text 1'])
            if find_nothing:
                self._search_document(
                    classification_data, [], [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found]
                )
            else:
                self._search_document(
                    classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
                )
            self._set_values(classification_data, prop_code, [' test text 1 '])
            if find_nothing:
                self._search_document(
                    classification_data, [], [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found]
                )
            else:
                self._search_document(
                    classification_data, [doc_1], [doc_0, doc_2, doc_12, doc_not_to_be_found]
                )

            self._set_values(classification_data, prop_code, ['test text*'])
            if find_nothing:
                self._search_document(
                    classification_data, [], [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found]
                )
            else:
                self._search_document(
                    classification_data, [doc_1, doc_2, doc_12], [doc_0, doc_not_to_be_found]
                )
            self._set_values(classification_data, prop_code, ['test text%'])
            if find_nothing:
                self._search_document(
                    classification_data, [], [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found]
                )
            else:
                self._search_document(
                    classification_data, [doc_1, doc_2, doc_12], [doc_0, doc_not_to_be_found]
                )
            self._set_values(classification_data, prop_code, ['test text ?'])
            if find_nothing:
                self._search_document(
                    classification_data, [], [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found]
                )
            else:
                self._search_document(
                    classification_data, [doc_1, doc_2], [doc_0, doc_not_to_be_found]
                )

            self._set_values(classification_data, prop_code, ['="test text 1" OR ="test text 2"'])
            if find_nothing:
                self._search_document(
                    classification_data, [], [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found]
                )
            else:
                self._search_document(
                    classification_data, [doc_1, doc_2], [doc_0, doc_12, doc_not_to_be_found]
                )

            self._set_values(classification_data, prop_code, ['test text 1 \or 2'])  # pylint: disable=W1401
            if find_nothing:
                self._search_document(
                    classification_data, [], [doc_0, doc_1, doc_2, doc_12, doc_not_to_be_found]
                )
            else:
                self._search_document(
                    classification_data, [doc_12], [doc_0, doc_1, doc_2, doc_not_to_be_found]
                )

        initial_class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        initial_prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_not_to_be_found = self._create_document_with_value(
            "other doc", initial_class_code, initial_prop_code, ["other test text"]
        )
        doc_0 = self._create_document_with_value(
            "doc 0", initial_class_code, initial_prop_code, [None]
        )
        doc_1 = self._create_document_with_value(
            "doc 1", initial_class_code, initial_prop_code, ["test text 1"]
        )
        doc_2 = self._create_document_with_value(
            "doc 2", initial_class_code, initial_prop_code, ["test text 2"]
        )
        doc_12 = self._create_document_with_value(
            "doc 12", initial_class_code, initial_prop_code, ["test text 1 or 2"]
        )

        addtl_prop_code = "TEST_PROP_TYPE"
        classification_data = api.create_additional_props([addtl_prop_code])
        api.update_additional_props(doc_0, classification_data)
        classification_data["properties"][addtl_prop_code][0]["value"] = "test text 1"
        api.update_additional_props(doc_1, classification_data)
        classification_data["properties"][addtl_prop_code][0]["value"] = "test text 2"
        api.update_additional_props(doc_2, classification_data)
        classification_data["properties"][addtl_prop_code][0]["value"] = "test text 1 or 2"
        api.update_additional_props(doc_12, classification_data)
        classification_data["properties"][addtl_prop_code][0]["value"] = "doc_not_to_be_found"
        api.update_additional_props(doc_not_to_be_found, classification_data)

        search_for_classification(initial_class_code, initial_prop_code)
        search_for_classification(None, addtl_prop_code)

        addtl_class_code = "TEST_CLASS_ARTICLE"
        addtl_class_prop_code = "TEST_CLASS_ARTICLE_TEST_PROP_ITEM_NUMBER"
        classification_data = api.get_new_classification([addtl_class_code])
        api.update_classification(doc_0, classification_data, full_update_mode=False)
        classification_data["properties"][addtl_class_prop_code][0]["value"] = "test text 1"
        api.update_classification(doc_1, classification_data, full_update_mode=False)
        classification_data["properties"][addtl_class_prop_code][0]["value"] = "test text 2"
        api.update_classification(doc_2, classification_data, full_update_mode=False)
        classification_data["properties"][addtl_class_prop_code][0]["value"] = "test text 1 or 2"
        api.update_classification(doc_12, classification_data, full_update_mode=False)
        classification_data["properties"][addtl_class_prop_code][0]["value"] = "other test text"
        api.update_classification(doc_not_to_be_found, classification_data, full_update_mode=False)

        search_for_classification(initial_class_code, initial_prop_code)
        search_for_classification(None, addtl_prop_code)
        search_for_classification(addtl_class_code, addtl_class_prop_code)

        classification_data = {
            "assigned_classes": [],
            "deleted_classes": [addtl_class_code],
            "properties": {}
        }
        api.update_classification(doc_0, classification_data, full_update_mode=False)
        api.update_classification(doc_1, classification_data, full_update_mode=False)
        api.update_classification(doc_2, classification_data, full_update_mode=False)
        api.update_classification(doc_12, classification_data, full_update_mode=False)
        api.update_classification(doc_not_to_be_found, classification_data, full_update_mode=False)

        search_for_classification(initial_class_code, initial_prop_code)
        search_for_classification(None, addtl_prop_code)
        search_for_classification(addtl_class_code, addtl_class_prop_code, find_nothing=True)

        classification_data = {
            "assigned_classes": [],
            "deleted_properties": [addtl_prop_code],
            "properties": {}
        }
        api.update_classification(doc_0, classification_data, full_update_mode=False)
        api.update_classification(doc_1, classification_data, full_update_mode=False)
        api.update_classification(doc_2, classification_data, full_update_mode=False)
        api.update_classification(doc_12, classification_data, full_update_mode=False)
        api.update_classification(doc_not_to_be_found, classification_data, full_update_mode=False)

        search_for_classification(initial_class_code, initial_prop_code)
        search_for_classification(None, addtl_prop_code, find_nothing=True)
        search_for_classification(addtl_class_code, addtl_class_prop_code, find_nothing=True)
    
    def test_complext_empty_search(self):
        class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"

        doc_0 = self._create_document_with_value("doc 0", class_code, prop_code, [None])
        doc_1 = self._create_document_with_value("doc 1", class_code, prop_code, [""])
        doc_2 = self._create_document_with_value("doc 2", class_code, prop_code, ["ABC"])
        doc_3 = self._create_document_with_value("doc 3", class_code, prop_code, ["CDE"])

        classification_data = api.get_new_classification([class_code], with_defaults=False)

        self._set_values(classification_data, prop_code, ['=""'])
        self._search_document(
            classification_data, [doc_0, doc_1], [doc_2, doc_3]
        )

        self._set_values(classification_data, prop_code, ['="" OR ="ABC"'])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2], [doc_3]
        )

        self._set_values(classification_data, prop_code, ['="" OR !="ABC"'])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_3], [doc_2]
        )


        self._set_values(classification_data, prop_code, ['(="" OR ="ABC" OR ="CDE")'])
        self._search_document(
            classification_data, [doc_0, doc_1, doc_2, doc_3], []
        )

        self._set_values(classification_data, prop_code, ['!=""'])
        self._search_document(
            classification_data, [doc_2, doc_3], [doc_0, doc_1]
        )

        self._set_values(classification_data, prop_code, ['!="" OR ="ABC"'])
        self._search_document(
            classification_data, [doc_2, doc_3], [doc_0, doc_1]
        )
        self._set_values(classification_data, prop_code, ['="ABC" OR !=""'])
        self._search_document(
            classification_data, [doc_2, doc_3], [doc_0, doc_1]
        )

        self._set_values(classification_data, prop_code, ['!="" AND !="ABC"'])
        self._search_document(
            classification_data, [doc_3], [doc_0, doc_1, doc_2]
        )
        self._set_values(classification_data, prop_code, ['!="ABC" AND !=""'])
        self._search_document(
            classification_data, [doc_3], [doc_0, doc_1, doc_2]
        )

