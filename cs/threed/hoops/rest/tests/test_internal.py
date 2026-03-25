# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import json

from webtest import TestApp as Client

from cdb import testcase
from cdb import constants
from cdb.objects import operations

from cs.platform.web.root import Root
from cs.platform.web.root.main import _get_dummy_request
from cs.platform.web.rest.app import get_collection_app

from cs.documents import Document

from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent


class TestInternalMapping(testcase.RollbackTestCase):
    def setUp(self):
        super(TestInternalMapping, self).setUp()

        self.client = Client(Root())

        self.filename_paths_top_down = [
            [
                "000061-1-.CATProduct",
                "000068-1-.CATProduct",
                "000065-1-.CATPart"
            ],
            [
                "000061-1-.CATProduct",
                "000077-1-.CATProduct",
                "000074-1-.CATPart"
            ]
        ]

        self.document_paths_top_down = [
            [
                Document.ByKeys(z_nummer="000061-1", z_index=""),
                Document.ByKeys(z_nummer="000068-1", z_index=""),
                Document.ByKeys(z_nummer="000065-1", z_index="")
            ],
            [
                Document.ByKeys(z_nummer="000061-1", z_index=""),
                Document.ByKeys(z_nummer="000077-1", z_index=""),
                Document.ByKeys(z_nummer="000074-1", z_index="")
            ]
        ]

        self.transformations = [
            [
                ["1.3 -1.1 1.0 0.0 -0.2 0.9 2.2 0.0 -0.3 -0.8 3.6 0.0 -5.0 21.0 1.0 1.0"],
                ["2.3 -1.1 1.0 0.0 -0.2 0.9 2.2 0.0 -0.3 -0.8 3.6 0.0 -5.0 21.0 1.0 1.0"]
            ],
            [
                ["3.3 -1.1 1.0 0.0 -0.2 0.9 2.2 0.0 -0.3 -0.8 3.6 0.0 -5.0 21.0 1.0 1.0"],
                ["4.3 -1.1 1.0 0.0 -0.2 0.9 2.2 0.0 -0.3 -0.8 3.6 0.0 -5.0 21.0 1.0 1.0"]
            ]
        ]

        self.bom_item_paths_top_down = [
            [
                AssemblyComponent.ByKeys(
                    baugruppe="000061",
                    b_index="",
                    teilenummer="000068",
                    t_index="",
                    variante="",
                    position=30,
                ),
                AssemblyComponent.ByKeys(
                    baugruppe="000068",
                    b_index="",
                    teilenummer="000065",
                    t_index="",
                    variante="",
                    position=50,
                )
            ],
            [
                AssemblyComponent.ByKeys(
                    baugruppe="000061",
                    b_index="",
                    teilenummer="000077",
                    t_index="",
                    variante="",
                    position=50,
                ),
                AssemblyComponent.ByKeys(
                    baugruppe="000077",
                    b_index="",
                    teilenummer="000074",
                    t_index="",
                    variante="",
                    position=10,
                )
            ]
        ]

        self.filenames_top_down = self.filename_paths_top_down[0]

        self.documents_top_down = self.document_paths_top_down[0]

        self.bom_items_top_down = self.bom_item_paths_top_down[0]

        self.path = [
            {
                "teilenummer": "000061", 
                "t_index": ""
            },
            {
                "baugruppe": "000061",
                "b_index": "",
                "teilenummer": "000068",
                "t_index": "",
                "variante": "",
                "position": 30,
            },
            {
                "baugruppe": "000068",
                "b_index": "",
                "teilenummer": "000065",
                "t_index": "",
                "variante": "",
                "position": 50,
            }
        ]

        self.context_part = Item.ByKeys(teilenummer="000061", t_index="")

    def setUpOccurrences(self):
        from cs.vp.bomcreator.assemblycomponentoccurrence import AssemblyComponentOccurrence

        for path_index, path in enumerate(self.bom_item_paths_top_down):
            for bom_item_index, bom_item in enumerate(path):
                operations.operation(
                    constants.kOperationNew,
                    AssemblyComponentOccurrence,
                    occurrence_id=bom_item.teilenummer,
                    reference_path=bom_item.teilenummer,
                    assembly_path=bom_item.teilenummer,
                    relative_transformation=self.transformations[path_index][bom_item_index][0],
                    bompos_object_id=bom_item.cdb_object_id
        )

    @classmethod
    def setUpClass(cls):
        super(TestInternalMapping, cls).setUpClass()

        from cs.threed.hoops.tests.utils import install_testdata
        install_testdata()

    def __get_document_url(self, view_name):
        return "/internal/cs.threed.hoops/mapping/document/%s/%s" % \
              (self.documents_top_down[0].cdb_object_id, view_name)

    def __get_bom_item_url(self, view_name):
        return "/internal/cs.threed.hoops/mapping/bom_item/%s/%s" % \
               (self.context_part.cdb_object_id, view_name)

    def test_find_documents_for_filenames(self):
        """ The API returns the documents for a given list of filenames """
        url = self.__get_document_url("for_filenames")
        response = self.client.post(url, json.dumps({
            "filenames": self.filenames_top_down
        }))

        self.assertEqual(200, response.status_int)

        expected_document_ids = [d.cdb_object_id for d in self.documents_top_down]
        received_document_ids = [d.get("cdb_object_id") for d in response.json]
        self.assertEqual(expected_document_ids, received_document_ids)

    def test_find_filename_paths_for_document_paths(self):
        """ The API returns the filename paths for a given list of document paths """
        url = self.__get_document_url("for_document_paths")
        request = _get_dummy_request()
        response = self.client.post(url, json.dumps({
            "document_url_paths": [[request.link(d, app=get_collection_app(request)) for d in path] for path in self.document_paths_top_down]
        }))

        self.assertEqual(200, response.status_int)
        self.assertEqual(self.filename_paths_top_down, [x["path"] for x in response.json])

    def test_find_filename_paths_for_bom_item_oid_paths(self):
        """ The API returns the filename paths for a given list of bom item object id paths """
        url = self.__get_bom_item_url("for_bom_item_oid_paths")
        response = self.client.post(url, json.dumps({
            "bom_item_oid_paths": [[b.cdb_object_id for b in path] for path in self.bom_item_paths_top_down]
        }))

        self.assertEqual(200, response.status_int)

        self.assertEqual(self.filename_paths_top_down, [x["path"] for x in response.json])
        self.assertEqual([[[],[]], [[],[]]], [x["transforms"] for x in response.json])

    def test_find_filename_paths_for_bom_item_paths_with_occurrences(self):
        """ The API returns the filename paths and transformations for a given list of bom item paths """
        self.setUpOccurrences()
        url = self.__get_bom_item_url("for_bom_item_oid_paths")
        response = self.client.post(url, json.dumps({
            "bom_item_oid_paths": [[b.cdb_object_id for b in path] for path in self.bom_item_paths_top_down]
        }))

        self.assertEqual(200, response.status_int)
        self.assertEqual(self.filename_paths_top_down, [x["path"] for x in response.json])
        self.assertEqual(self.transformations, [x["transforms"] for x in response.json])

    def test_get_mapping_file_link(self):
        """ The API returns the file link for the converted document """
        url = self.__get_document_url("get_mapping_file_link")
        request = _get_dummy_request()
        response = self.client.get(url)
        self.assertEqual(200, response.status_int)

    def test_find_bom_items_for_filenames(self):
        url = self.__get_bom_item_url("for_filenames")
        response = self.client.post(url, json.dumps({
            "filenames": self.filenames_top_down
        }))

        self.assertEqual(200, response.status_int)

        expected_bom_items = [b.baugruppe for b in self.bom_items_top_down]
        received_bom_items = [b.get("baugruppe") for b in response.json]
        self.assertListEqual(expected_bom_items, received_bom_items)
