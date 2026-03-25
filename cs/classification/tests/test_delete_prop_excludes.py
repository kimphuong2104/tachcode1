# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import logging
from cs.classification.catalog import TextPropertyValue
from cs.classification.tests import utils
from cs.classification.classes import ClassProperty
from cdb import sqlapi
from cdb import util
from cdb import constants
from cdb.objects import operations

LOG = logging.getLogger(__name__)


class TestDeletedExclude(utils.ClassificationTestCase):

    def setUp(self):
        super(TestDeletedExclude, self).setUp()

    def test_delete_property_effect(self):

        class_property = ClassProperty.KeywordQuery(code="TEST_CLASS_POSITION_AND_DESCRIPTION_TEST_PROP_ENUM_SORT")[0]
        property_value = TextPropertyValue.Create(property_object_id=class_property.cdb_object_id, text_value="TEXT TEXT")
        setPreInsert = sqlapi.RecordSet2(
            "cs_property_value_exclude", "property_value_id='%s'" % property_value.cdb_object_id
        )

        assert (len(setPreInsert) == 0)
        ins = util.DBInserter("cs_property_value_exclude")
        ins.add("classification_class_id", class_property.classification_class_id)
        ins.add("class_property_id", class_property.cdb_object_id)
        ins.add("property_value_id", property_value.cdb_object_id)
        ins.add("property_id", class_property.catalog_property_id)
        ins.add("exclude", 1)
        ins.insert()
        setPostInsert = sqlapi.RecordSet2(
            "cs_property_value_exclude", "property_value_id='%s'" % property_value.cdb_object_id
        )
        assert (len(setPostInsert) == 1)
        operations.operation(
            constants.kOperationDelete,
            property_value
        )
        setPostDelete = sqlapi.RecordSet2(
            "cs_property_value_exclude", "property_value_id='%s'" % property_value.cdb_object_id
        )
        assert (len(setPostDelete) == 0)
