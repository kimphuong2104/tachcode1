# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import ue
from cdb.testcase import RollbackTestCase
from cs.threed.hoops.converter.tests import common
  

class TestPartModelMapping(RollbackTestCase):
    def setUp(self):
        super(TestPartModelMapping, self).setUp()

        self.item = common.generateItem() 

    def test_3d_cockpit_on_part_with_no_model(self):
        """ If the part does not contain any model fitting the rule, an error is thrown """
        with self.assertRaises(ue.Exception):
            self.item.on_threed_cockpit_now(None)

    def test_get_3d_model_with_no_model(self):
        """ If the part does not contain any model fitting the rule, 'None' is returned """
        model = self.item.get_3d_model_document()
        self.assertEqual(model, None)

    def test_get_3d_model_with_model(self):
        """ If the part does contain a model fitting the rule, the correct model is returned """
        generatedModel = common.generateCADDocument(self.item)

        model = self.item.get_3d_model_document()
        self.assertEqual(model, generatedModel)

    def test_get_3d_model_with_multiple_models(self):
        """ If the part does contain multiple models fitting the rule, the correct model is returned """
        generatedModel = common.generateCADDocument(self.item, presets_custom={"erzeug_system": "PRC",})
        correctModel = common.generateCADDocument(self.item, presets_custom={"erzeug_system": "CatiaV5:Prod",})
        generatedModel2 = common.generateCADDocument(self.item, presets_custom={"erzeug_system": "STEP",})

        model = self.item.get_3d_model_document()
        self.assertEqual(model.cdb_object_id, correctModel.cdb_object_id)

    def test_get_3d_model_with_multiple_indexes_model(self):
        """ If the part does contain multiple indexes of a document fitting the rule, the correct model is returned """
        generated_model = common.generateCADDocument(self.item, presets_custom={"erzeug_system": "PRC"})
        model_index_a = common.generateCADDocumentIndex(self.item, generated_model)
        model_index_b = common.generateCADDocumentIndex(self.item, model_index_a)

        model = self.item.get_3d_model_document()
        self.assertEqual(model, model_index_b)
