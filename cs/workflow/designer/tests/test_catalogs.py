#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import datetime
import json
import mock
from cdb.objects.core import Object
from cdb import sig
from cdb import testcase
from cdb.objects.org import CommonRole
from cs.shared.elink_plugins.catalog import CatalogTools
from cs.workflow.designer import catalogs


def setup_module():
    testcase.run_level_setup()


class UtilityTestCase(testcase.RollbackTestCase):
    def test_get_roles(self):
        CommonRole.Query().Update(is_org_role=0)
        CommonRole.KeywordQuery(
            role_id=["Documentation", "Engineering"]).Update(is_org_role=1)
        self.assertEqual(
            catalogs.get_roles(),
            []
        )
        self.maxDiff = None
        result = [
            x
            for x in catalogs.get_roles(cdb_process_id="JSON_TEST")
            if x[0] in ["Dokumentation", "Entwicklung"]
        ]
        result.sort(key=lambda x: x[0])
        self.assertEqual(
            result,
            [
                [
                    u'Dokumentation',
                    {
                        'subject_id': u'Documentation',
                        'subject_type': u'Common Role',
                    },
                ], [
                    u'Entwicklung',
                    {
                        'subject_id': u'Engineering',
                        'subject_type': u'Common Role',
                    },
                ],
            ]
        )

    def test_get_label_hard_fallback(self):
        "returns '?'"
        self.assertEqual(
            catalogs.get_label(lambda isolang: None),
            "?",
        )

    def test_get_label_fallback(self):
        "returns label in fallback language"
        self.assertEqual(
            catalogs.get_label(lambda isolang: "" if isolang == "" else "X"),
            "X",
        )

    def test_get_label(self):
        "returns label in login language"
        self.assertEqual(
            catalogs.get_label(lambda isolang: "Y" if isolang == "" else ""),
            "Y",
        )


class CustomizableConditionTestCase(testcase.RollbackTestCase):
    __catalog__ = catalogs.OperationCatalog
    __default__ = ["DEFAULT"]

    def _get_catalog(self):
        catalog = self.__catalog__()
        catalog.__default_conditions__ = self.__default__
        return catalog

    def setUp(self):
        super(CustomizableConditionTestCase, self).setUp()
        self.catalog = self._get_catalog()

    def tearDown(self):
        super(CustomizableConditionTestCase, self).tearDown()

    def test_default_condition(self):
        self.assertEqual(
            self.catalog._get_catalog_rules_conditions(),
            self.__default__
        )

    @mock.patch.object(sig, "emit")
    def test_custom_condition(self, emit):
        emit.return_value = lambda fqpyname: [
            "neither list nor set",
            ["CUSTOM ONE"],
            ["CUSTOM 2"],
        ]

        self.assertEqual(
            self.catalog._get_catalog_rules_conditions(),
            set(["CUSTOM ONE", "CUSTOM 2"])
        )

    def test_get_filter_condition(self):
        self.assertEqual(
            self.catalog.get_filter_condition(),
            self.catalog.__default_conditions__[0]
        )

        self.catalog.__default_conditions__ = []
        self.assertEqual(
            self.catalog.get_filter_condition(),
            "1=1"
        )

        self.catalog._get_catalog_rules_conditions = lambda: set([
            "CUSTOM ONE",
            "CUSTOM 2",
        ])

        self.assertIn(
            self.catalog.get_filter_condition(),
            set([
                "(CUSTOM ONE) OR (CUSTOM 2)",
                "(CUSTOM 2) OR (CUSTOM ONE)",
            ])
        )

        self.catalog.__join_conditions__ = "foo"
        self.assertIn(
            self.catalog.get_filter_condition(),
            set([
                "(CUSTOM ONE) foo (CUSTOM 2)",
                "(CUSTOM 2) foo (CUSTOM ONE)",
            ])
        )


class ResponsiblePersonTestCase(testcase.RollbackTestCase):
    def test___getitem__(self):
        x = catalogs.ResponsiblePerson()
        x.__dict__.update({
            "foo": "bar",
            "nuttin": None,
            "empty": "",
        })
        self.assertEqual(x.foo, "bar")
        self.assertEqual(x["foo"], "bar")
        self.assertEqual(x.nuttin, None)
        self.assertEqual(x["nuttin"], None)
        self.assertEqual(x.empty, "")
        self.assertEqual(x["empty"], "")

        with self.assertRaises(AttributeError):
            _ = x.unknown

        self.assertEqual(x["unknown"], "")

    def test_match(self):
        x = catalogs.ResponsiblePerson()
        x.__dict__.update({
            "foo": "bar",
            "nuttin": None,
            "empty": "",
        })

        # only str values are supported
        with self.assertRaises(AttributeError):
            x.match({"nuttin": "whatever"})

        # but first mismatch terminates immediately
        self.assertEqual(
            x.match({"foo": "bart", "nuttin": "whatever"}),
            False
        )

        self.assertEqual(
            x.match({"foo": "bar", "empty": " "}),
            False
        )
        self.assertEqual(
            x.match({"foo": "bar", "empty": ""}),
            True
        )


class ResponsibleCatalogTestCase(testcase.RollbackTestCase):
    def test_get_table_def(self):
        x = catalogs.ResponsibleCatalog()
        self.assertEqual(
            x.get_table_def(),
            {
                'columns': [
                    {
                        'attribute': u'subject_name',
                        'label': u'Rolle/Person',
                        'searchable': True,
                        'type': 'text',
                        'visible': True,
                    }, {
                        'attribute': u'description',
                        'label': u'Beschreibung',
                        'searchable': True,
                        'type': 'text',
                        'visible': True,
                    }, {
                        'attribute': u'subject_type',
                        'label': u'Typ',
                        'searchable': True,
                        'type': 'text',
                        'visible': True,
                    }, {
                        'attribute': u'order_by',
                        'label': u'',
                        'searchable': False,
                        'type': 'text',
                        'visible': False,
                    }, {
                        'attribute': u'subject_id',
                        'label': u'Rolle/Person',
                        'searchable': False,
                        'type': 'text',
                        'visible': False,
                    }, {
                        'attribute': u'cdb_project_id',
                        'label': u'Projekt',
                        'searchable': False,
                        'type': 'text',
                        'visible': False,
                    },
                ],
                'searchable': True,
            }
        )

    def test_get_catalog_title(self):
        x = catalogs.ResponsibleCatalog()
        self.assertEqual(
            x.get_catalog_title(),
            u"Verantwortliche"
        )

    def test__wrap_person(self):
        x = catalogs.ResponsibleCatalog()
        person = {
            "personalnummer": "horst",
            "name": "Evers",
        }
        self.maxDiff = None
        self.assertEqual(
            x._wrap_person(person).__dict__,
            {
                "subject_id": "horst",
                "description": "Evers",
                "subject_type": "Person",
                "subject_name": "Evers",
                "order_by": "1",
            }
        )

    def test__extract_person_from_role(self):
        x = catalogs.ResponsibleCatalog()
        role = CommonRole.ByKeys("Administrator")
        result_caddok = {
            'description': u'Administrator',
            'order_by': '1',
            'subject_id': u'caddok',
            'subject_name': u'Administrator',
            'subject_type': 'Person',
        }
        result_vendorsupport = {
            'description': u'Vendor Support',
            'order_by': '1',
            'subject_id': u'vendorsupport',
            'subject_name': u'Vendor Support',
            'subject_type': 'Person',
        }
        self.assertEqual(
            [
                result.__dict__
                for result in x._extract_person_from_role(role, {})
            ],
            [result_caddok, result_vendorsupport]
        )
        self.assertEqual(
            [
                result.__dict__
                for result in x._extract_person_from_role(
                    role,
                    {"subject_id": "caddok"}
                )
            ],
            [result_caddok]
        )

    def test_get_data(self):
        x = catalogs.ResponsibleCatalog()
        self.maxDiff = None
        self.assertEqual(
            x.get_data(),
            []
        )

        def strip_oid(data_entry):
            result = data_entry.__dict__
            result["_oid"] = result["_oid"][:3]
            return result

        self.assertEqual(
            [
                strip_oid(result)
                for result in x.get_data(
                    cdb_process_id="JSON_TEST",
                    catalog_search_conditions='{"subject_id": "caddok"}'
                )
            ],
            [
                {
                    '_record': {
                        u'subject_name_tr': u'Administrator',
                        u'subject_type': u'Person',
                        u'subject_name_ja': u'Administrator',
                        u'cdb_project_id': u'',
                        u'description_fr': u'Administrator',
                        u'description_de': u'Administrator',
                        u'order_by': 1,
                        u'subject_id': u'caddok',
                        u'subject_name_en': u'Administrator',
                        u'description_pl': u'Administrator',
                        u'description_ja': u'Administrator',
                        u'subject_name_es': u'Administrator',
                        u'description_pt': u'Administrator',
                        u'description_tr': u'Administrator',
                        u'subject_name_ko': u'Administrator',
                        u'subject_name_cs': u'Administrator',
                        u'description_cs': u'Administrator',
                        u'subject_name_pt': u'Administrator',
                        u'description_en': u'Administrator',
                        u'subject_name_pl': u'Administrator',
                        u'description_es': u'Administrator',
                        u'description_it': u'Administrator',
                        u'subject_name_it': u'Administrator',
                        u'subject_name_de': u'Administrator',
                        u'subject_name_zh': u'Administrator',
                        u'subject_name_fr': u'Administrator',
                        u'description_ko': u'Administrator',
                        u'description_zh': u'Administrator',
                    },
                    '_dirty': False,
                    '_need_insert': False,
                    '_is_deleted': False,
                    '_refcache': {},
                    '_ctx': None,
                    '_modified': False,
                    '_obj_handle': None,
                    '_fields': {u'subject_id': u'caddok', u'subject_name_de': u'Administrator', u'subject_type': u'Person'},
                    '_oid': 'OID',
                },
            ]
        )
        self.assertEqual(
            [
                result.__dict__
                for result in x.get_data(
                    cdb_process_id="JSON_TEST",
                    catalog_plugin_conditions=(
                        '{"subject_type": "Common Role",'
                        '"subject_id": "Administrator"}'
                    ),
                )
            ],
            [
                {
                    'description': u'Administrator',
                    'order_by': '1',
                    'subject_id': u'caddok',
                    'subject_name': u'Administrator',
                    'subject_type': 'Person',
                }, {
                    'subject_id': u'vendorsupport',
                    'subject_type': 'Person',
                    'order_by': '1',
                    'description': u'Vendor Support',
                    'subject_name': u'Vendor Support',
                },
            ]
        )

    def test_render(self):
        x = catalogs.ResponsibleCatalog()
        self.maxDiff = None
        self.assertEqual(
            x.render(None),
            {
                'paginator': (1, 0),
                'datalist': [],
                'catalog_def_required': False,
                'table_def': {
                    'columns': [
                        {
                            'attribute': u'subject_name',
                            'type': 'text',
                            'visible': True,
                            'searchable': True,
                            'label': u'Rolle/Person',
                        }, {
                            'attribute': u'description',
                            'type': 'text',
                            'visible': True,
                            'searchable': True,
                            'label': u'Beschreibung',
                        }, {
                            'attribute': u'subject_type',
                            'type': 'text',
                            'visible': True,
                            'searchable': True,
                            'label': u'Typ',
                        }, {
                            'attribute': u'order_by',
                            'type': 'text',
                            'visible': False,
                            'searchable': False,
                            'label': u'',
                        }, {
                            'attribute': u'subject_id',
                            'type': 'text',
                            'visible': False,
                            'searchable': False,
                            'label': u'Rolle/Person',
                        }, {
                            'attribute': u'cdb_project_id',
                            'type': 'text',
                            'visible': False,
                            'searchable': False,
                            'label': u'Projekt',
                        },
                    ],
                    'searchable': True,
                },
                'table_page_size': 10,
                'page_no': 1,
            }
        )

    def test_make_responsible_id(self):
        x = catalogs.ResponsibleCatalog()

        with self.assertRaises(TypeError):
            x.make_responsible_id(None)

        with self.assertRaises(KeyError):
            x.make_responsible_id({
                "subject_type": "NO ID",
            })

        self.assertEqual(
            x.make_responsible_id({
                "subject_type": "\\TY..P,E",
                "subject_id": " <I @/'!$=D\n",
            }),
            "_TY_P_E_I_D_"
        )

    def test__data_wrapper(self):
        x = catalogs.ResponsibleCatalog()
        table_def = x.get_table_def()
        self.maxDiff = None

        with self.assertRaises(KeyError):
            x._data_wrapper(
                table_def,
                [{"subject_type": "NO_ID"}]
            )

        self.assertEqual(
            x._data_wrapper(table_def, []),
            []
        )
        self.assertEqual(
            x._data_wrapper(
                table_def,
                [
                    {
                        "subject_type": "TYPE",
                        "subject_id": "ID1",
                        "subject_name": "1",
                        "description": "one",
                        "order_by": "1",
                        "cdb_project_id": "",
                    },
                    {
                        "subject_type": "TYPE",
                        "subject_id": "ID2",
                        "subject_name": "2",
                        "description": "two",
                        "order_by": "1",
                        "cdb_project_id": "",
                    },
                ]
            ),
            [
                [
                    {'text': 'TYPE_ID1', 'name': '_id'},
                    {'text': '', 'name': '_description'},
                    {'text': '1', 'name': u'subject_name'},
                    {'text': 'one', 'name': u'description'},
                    {'text': 'TYPE', 'name': u'subject_type'},
                    {'text': '1', 'name': u'order_by'},
                    {'text': 'ID1', 'name': u'subject_id'},
                    {'text': '', 'name': u'cdb_project_id'},
                ], [
                    {'text': 'TYPE_ID2', 'name': '_id'},
                    {'text': '', 'name': '_description'},
                    {'text': '2', 'name': u'subject_name'},
                    {'text': 'two', 'name': u'description'},
                    {'text': 'TYPE', 'name': u'subject_type'},
                    {'text': '1', 'name': u'order_by'},
                    {'text': 'ID2', 'name': u'subject_id'},
                    {'text': '', 'name': u'cdb_project_id'},
                ],
            ]
        )


class CatalogTestCase(testcase.RollbackTestCase):
    def _get_data_args(self, **kwargs):
        search = json.dumps(kwargs)
        return {
            "catalog_search_conditions": search,
        }

    def _get_data(self, catalog, **kwargs):
        return catalog.get_data(**self._get_data_args(**kwargs))


class ConstraintCatalogTestCase(CatalogTestCase):
    def test_get_data(self):
        x = catalogs.ConstraintCatalog()
        data = self._get_data(x, name="Workflow abgeschlossen")
        self.assertEqual(
            set(data.name_de),
            set([
                u"Workflow abgeschlossen",
                u"Übergeordneter Workflow abgeschlossen",
            ])
        )

    def test_get_table_def(self):
        x = catalogs.ConstraintCatalog()
        self.assertEqual(
            x.get_table_def(),
            {
                'columns': [
                    {
                        'attribute': u'name',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'Name',
                    }, {
                        'attribute': u'description',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'Beschreibung',
                    },
                ],
                'searchable': True,
            }
        )

    def test__data_wrapper(self):
        x = catalogs.ConstraintCatalog()
        table_def = x.get_table_def()
        data = self._get_data(x, name="Workflow abgeschlossen")

        result = x._data_wrapper(table_def, data)
        self.assertEqual(
            set([x["name"] for x in result[0]]),
            set(["_id", "_description", "name", "description"])
        )

        names = set()

        for x in result:
            for y in x:
                if y["name"] == "name":
                    names.add(y["text"])

        self.assertEqual(
            names,
            set([
                u'Workflow abgeschlossen',
                u'Übergeordneter Workflow abgeschlossen',
            ])
        )


class FilterCatalogTestCase(CatalogTestCase):
    def test_get_data(self):
        x = catalogs.FilterCatalog()
        data = self._get_data(x, name_de='Test "OK"')
        self.assertEqual(
            data.name_de,
            ['Test "OK"']
        )

    def test_get_table_def(self):
        x = catalogs.FilterCatalog()
        self.assertEqual(
            x.get_table_def(),
            {
                'columns': [
                    {
                        'attribute': u'name',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'Name',
                    }, {
                        'attribute': u'description',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'Beschreibung',
                    },
                ],
                'searchable': True,
            }
        )

    def test__data_wrapper(self):
        x = catalogs.FilterCatalog()
        table_def = x.get_table_def()
        data = self._get_data(x, name_de='Test "OK"')
        self.maxDiff = None
        self.assertEqual(
            x._data_wrapper(table_def, data),
            [
                [
                    {
                        'text': u'771a44f0-2498-11e9-8ab2-68f7284ff046',
                        'name': '_id',
                    }, {
                        'text': '',
                        'name': '_description',
                    }, {
                        'text': u'Test "OK"',
                        'name': u'name',
                    }, {
                        'text': u'',
                        'name': u'description',
                    },
                ]
            ]
        )


class ConditionCatalogTestCase(CatalogTestCase):
    def test_get_data(self):
        x = catalogs.ConditionCatalog()
        data = self._get_data(x, name_de="Durchlauf abgeschlossen")
        self.assertEqual(
            data.name_de,
            ["Durchlauf abgeschlossen"]
        )

    def test_get_table_def(self):
        x = catalogs.ConditionCatalog()
        self.assertEqual(
            x.get_table_def(),
            {
                'columns': [
                    {
                        'attribute': u'name',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'Name',
                    }, {
                        'attribute': u'description',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'Beschreibung',
                    },
                ],
                'searchable': True,
            }
        )

    def test__data_wrapper(self):
        x = catalogs.ConditionCatalog()
        table_def = x.get_table_def()
        data = self._get_data(x, name_de="Durchlauf abgeschlossen")
        self.maxDiff = None
        self.assertEqual(
            x._data_wrapper(table_def, data),
            [
                [
                    {
                        'text': u'60fd3480-1eed-11e9-a6c4-68f7284ff046',
                        'name': '_id',
                    }, {
                        'text': '',
                        'name': '_description',
                    }, {
                        'text': u'Durchlauf abgeschlossen',
                        'name': u'name',
                    }, {
                        'text': str(
                            'Erfüllt, wenn ein Durchlauf im Status '
                            '"Abgeschlossen" beendet wurde.'
                        ),
                        'name': u'description',
                    },
                ]
            ]
        )


class FormTemplateCatalogTestCase(CatalogTestCase):
    def test_get_data(self):
        x = catalogs.FormTemplateCatalog()
        data = self._get_data(x, name_en="Test Form")
        self.assertEqual(
            data.name_en,
            ["Test Form"]
        )

    def test_get_table_def(self):
        x = catalogs.FormTemplateCatalog()
        self.assertEqual(
            x.get_table_def(),
            {
                'columns': [
                    {
                        'attribute': u'joined_status_name',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Status',
                    }, {
                        'attribute': u'name',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Name',
                    }, {
                        'attribute': u'mask_name',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'Maske',
                    }, {
                        'attribute': u'cdb_cdate',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Angelegt am',
                    }, {
                        'attribute': u'cdb_mdate',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Zuletzt ge\xe4ndert am',
                    }, {
                        'attribute': u'mapped_cpersno',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Angelegt von',
                    }, {
                        'attribute': u'mapped_mpersno',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Zuletzt ge\xe4ndert von',
                    },
                ],
                'searchable': True,
            }
        )

    def test__data_wrapper(self):
        x = catalogs.FormTemplateCatalog()
        table_def = x.get_table_def()
        data = self._get_data(x, name_en="Test Form")
        self.maxDiff = None
        self.assertEqual(
            x._data_wrapper(table_def, data),
            [
                [
                    {
                        'name': '_id',
                        'text': u'dd56ac92-b7ec-11e8-b3fc-5cc5d4123f3b',
                    }, {
                        'name': '_description',
                        'text': '',
                    }, {
                        'name': u'joined_status_name',
                        'text': u'Freigegeben',
                    }, {
                        'name': u'name',
                        'text': u'Testformular',
                    }, {
                        'name': u'mask_name',
                        'text': u'wftest_form',
                    }, {
                        'name': u'cdb_cdate',
                        'text': datetime.datetime(2018, 9, 14, 9, 7, 38),
                    }, {
                        'name': u'cdb_mdate',
                        'text': datetime.datetime(2018, 9, 14, 9, 7, 47),
                    }, {
                        'name': u'mapped_cpersno',
                        'text': u'Administrator',
                    }, {
                        'name': u'mapped_mpersno',
                        'text': u'Administrator',
                    },
                ]
            ]
        )


class OperationCatalogTestCase(CatalogTestCase):

    mocked_std_table_def = {
        'columns': [
            {
                'attribute': u'cdb_module_id',
                'type': 'text',
                'visible': True,
                'searchable': False,
                'label': u'Modul Id',
            },
            {
                'attribute': u'acl_allow',
                'type': 'text',
                'visible': True,
                'searchable': False,
                'label': u'Ben\xf6tigtes Recht',
            },
            {
                'attribute': u'menugroup',
                'type': 'number',
                'visible': True,
                'searchable': False,
                'label': u'Men\xfcgruppe',
            },
        ],
        'searchable': True,
    }

    mocked_table_def = {
        'columns': [
            {
                'attribute': u'acl_allow',
                'type': 'text',
                'visible': True,
                'searchable': False,
                'label': u'Ben\xf6tigtes Recht',
            },
            {
                'attribute': u'menugroup',
                'type': 'number',
                'visible': True,
                'searchable': False,
                'label': u'Men\xfcgruppe',
            },
        ],
        'searchable': True,
    }

    mocked_data = {}

    def test_get_data(self):
        x = catalogs.OperationCatalog()
        x.__default_conditions__ = ["1=1"]
        data = self._get_data(x, name="CDB_ShowObject")
        self.assertEqual(
            data.name,
            ["CDB_ShowObject", "CDB_ShowObjectUrl"]
        )

    @mock.patch.object(CatalogTools, "get_std_table_def")
    def test_get_table_def(self, get_std_table_def):
        get_std_table_def.return_value = self.mocked_std_table_def
        x = catalogs.OperationCatalog()
        self.assertEqual(
            x.get_table_def(),
            {
                'columns': [
                    {
                        'attribute': u'acl_allow',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Ben\xf6tigtes Recht',
                    }, {
                        'attribute': u'menugroup',
                        'type': 'number',
                        'visible': True,
                        'searchable': False,
                        'label': u'Men\xfcgruppe',
                    },
                ],
                'searchable': True,
            }
        )

    @mock.patch.object(Object, "ID")
    def test__data_wrapper(self, ID):
        ID.return_value = "TESTID"
        x = catalogs.OperationCatalog()
        table_def = self.mocked_table_def
        data = self._get_data(x, name="CDB_Create")
        self.maxDiff = None
        self.assertEqual(
            x._data_wrapper(table_def, data),
            [
                [
                    {
                        'text': 'TESTID',
                        'name': '_id',
                    }, {
                        'text': '',
                        'name': '_description',
                    }, {
                        'text': u'',
                        'name': u'acl_allow',
                    }, {
                        'text': 10,
                        'name': u'menugroup',
                    },
                ],
            ]
        )


class ProjectCatalogTestCase(CatalogTestCase):
    def test_get_data(self):
        x = catalogs.ProjectCatalog()
        data = self._get_data(x)
        self.assertEqual(
            data,
            []
        )

    def test_get_table_def(self):
        x = catalogs.ProjectCatalog()
        self.assertEqual(
            x.get_table_def(),
            {
                'columns': [],
                'searchable': True,
            }
        )

    def test_get_catalog_title(self):
        x = catalogs.ProjectCatalog()
        self.assertEqual(
            x.get_catalog_title(),
            u""
        )


class WorkflowTemplateCatalog(CatalogTestCase):
    def test_get_data(self):
        x = catalogs.WorkflowTemplateCatalog()
        data = self._get_data(x)
        self.assertEqual(
            set(data.is_template),
            set([u"1"])
        )
        data = self._get_data(x, cdb_process_id="TEST_TEMPLATE")
        self.assertEqual(
            data.cdb_process_id,
            ["TEST_TEMPLATE"]
        )

    def test_get_table_def(self):
        x = catalogs.WorkflowTemplateCatalog()
        self.maxDiff = None
        self.assertEqual(
            x.get_table_def(),
            {
                'columns': [
                    {
                        'attribute': u'title',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'Titel',
                    }, {
                        'attribute': u'mapped_subject_name',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Verantwortlich',
                    }, {
                        'attribute': u'cdb_process_id',
                        'type': 'text',
                        'visible': True,
                        'searchable': True,
                        'label': u'ID',
                    }, {
                        'attribute': u'cdb_project_id',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Projektnummer',
                    }, {
                        'attribute': u'mapped_categ_name',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Kategorie',
                    }, {
                        'attribute': u'mapped_org_name',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Organisationseinheit',
                    }, {
                        'attribute': u'start_date',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Start',
                    }, {
                        'attribute': u'deadline',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Fällig am',
                    }, {
                        'attribute': u'max_duration',
                        'type': 'number',
                        'visible': True,
                        'searchable': False,
                        'label': u'Max. Dauer (Tage)',
                    }, {
                        'attribute': u'joined_status_name',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Status',
                    }, {
                        'attribute': u'is_template',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Vorlage',
                    }, {
                        'attribute': u'mapped_cpersno_name',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Angelegt von',
                    }, {
                        'attribute': u'cdb_cdate',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'Angelegt am',
                    }, {
                        'attribute': u'completing_ok',
                        'type': 'number',
                        'visible': True,
                        'searchable': False,
                        'label': u'Verläuft erfolgreich',
                    }, {
                        'attribute': u'is_subworkflow',
                        'type': 'number',
                        'visible': True,
                        'searchable': False,
                        'label': u'Untergeordneter Workflow?',
                    }, {
                        'attribute': u'loop_process_id',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'ID (übergeordneter Workflow)',
                    }, {
                        'attribute': u'loop_task_id',
                        'type': 'text',
                        'visible': True,
                        'searchable': False,
                        'label': u'ID (übergeordnete Aufgabe)',
                    }, {
                        'attribute': u'current_cycle',
                        'type': 'number',
                        'visible': True,
                        'searchable': False,
                        'label': u'Durchlauf',
                    },
                ],
                'searchable': True,
            }
        )

    def test__data_wrapper(self):
        x = catalogs.WorkflowTemplateCatalog()
        table_def = x.get_table_def()
        data = self._get_data(x, cdb_process_id="TEST_TEMPLATE")
        self.maxDiff = None
        self.assertEqual(
            x._data_wrapper(table_def, data),
            [
                [
                    {
                        'text': u'ed4eda01-e90b-11e8-a2d9-68f7284ff046',
                        'name': '_id',
                    }, {
                        'text': '',
                        'name': '_description',
                    }, {
                        'text': u'Test Template',
                        'name': u'title',
                    }, {
                        'text': u'Administrator',
                        'name': u'mapped_subject_name',
                    }, {
                        'text': u'TEST_TEMPLATE',
                        'name': u'cdb_process_id',
                    }, {
                        'text': u'',
                        'name': u'cdb_project_id',
                    }, {
                        'text': u'',
                        'name': u'mapped_categ_name',
                    }, {
                        'text': u'',
                        'name': u'mapped_org_name',
                    }, {
                        'text': datetime.date(2018, 11, 15),
                        'name': u'start_date',
                    }, {
                        'text': None,
                        'name': u'deadline',
                    }, {
                        'text': None,
                        'name': u'max_duration',
                    }, {
                        'text': u'Freigegeben',
                        'name': u'joined_status_name',
                    }, {
                        'text': u'1',
                        'name': u'is_template',
                    }, {
                        'text': u'Administrator',
                        'name': u'mapped_cpersno_name',
                    }, {
                        'text': datetime.datetime(2018, 11, 15, 20, 23, 27),
                        'name': u'cdb_cdate',
                    }, {
                        'text': 1,
                        'name': u'completing_ok',
                    }, {
                        'text': 0,
                        'name': u'is_subworkflow',
                    }, {
                        'text': u'',
                        'name': u'loop_process_id',
                    }, {
                        'text': u'',
                        'name': u'loop_task_id',
                    }, {
                        'text': 0,
                        'name': u'current_cycle',
                    },
                ],
            ]
        )
