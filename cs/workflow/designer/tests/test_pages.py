#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import json
import mock
from mock import patch
from cdb import testcase
from cdb.elink.wsgi import ScriptRequest
from cdb.elink.engines.chameleon.engine import _OpHelper
from cs.workflow.briefcases import Briefcase
from cs.workflow.designer import nanoroute
from cs.workflow.designer import pages
from cs.workflow.processes import Process
from cs.workflowtest import WFTestFixture


def setup_module():
    testcase.run_level_setup()


class DummyApplication(object):
    def getURLPaths(self):
        return {
            "approot": "/APPROOT/",
        }

    def getOptions(self):
        return {
            "operations": _OpHelper,
        }


class DummyRequest(object):
    def __init__(self, form_data=None):
        self.charset = None
        self.form_data = form_data or {}

    def get_form_data(self):
        return self.form_data


class PageTestCase(object):
    def get_page(self):
        self.maxDiff = None
        page = self.__page__()
        page.application = DummyApplication()
        return page

    def get_page_posted_json(self, posted_json, value):
        page = self.get_page()
        posted_json.return_value = value
        return page

    def get_page_request(self, request, form_data):
        page = self.get_page()
        request.return_value = DummyRequest(form_data)
        return page


class DesignerPageTestCase(testcase.RollbackTestCase, PageTestCase):
    __page__ = pages.DesignerPage

    def test_render(self):
        page = self.get_page()
        result = page.render(None, "CDB_PROCESS_ID")
        # extension_resources order differs depending on nosetests params...
        ext_resources = set([
            json.dumps(x)
            for x in result["extension_resources"]
        ])
        self.assertEqual(
            ext_resources,
            set([
                '{"css": "cs.workflowtest.workflow_designer_extension/'
                'simple_task_extension.css", "js": "cs.workflowtest.'
                'workflow_designer_extension/simple_task_extension.js"}',
                '{"css": "cs.workflow.designer.parameter_extension/'
                'parameter_extension.css", "js": "cs.workflow.designer.'
                'parameter_extension/parameter_extension.js"}'
            ])
        )
        del result["extension_resources"]
        self.assertEqual(
            result,
            {
                "app_url": "/APPROOT/app/CDB_PROCESS_ID",
                "template_url": "/APPROOT/templates/",
                "resposible_roles_url": "/APPROOT/get_roles",
                "responsible_catalog_url": "/APPROOT/responsibles",
                "form_template_catalog_url": "/APPROOT/form_templates",
                "operation_catalog_url": "/APPROOT/operations",
                "constraints_catalog_url": "/APPROOT/constraints",
                "filters_catalog_url": "/APPROOT/filters",
                "conditions_catalog_url": "/APPROOT/conditions",
                "project_catalog_url": "/APPROOT/projects",
                "worfklow_template_catalog_url": (
                    "/APPROOT/workflow_templates"
                ),
                "cdb_process_id": "CDB_PROCESS_ID",
                "task_title_placeholder": u'Zum Editieren klicken',
            }
        )


class AppDataTestCase(testcase.RollbackTestCase):
    def test_render(self):
        result = pages.AppData().render(None)
        self.assertEqual(list(result.keys()), ["result"])
        self.assertEqual(
            json.loads(result["result"]),
            {
                "processId": "",
                "iface": "cs-workflow-designer-no-process",
            }
        )


class ProcessDataTestCase(testcase.RollbackTestCase):
    def test_render(self):
        self.assertEqual(
            pages.ProcessData().render(None),
            {
                "result": None,
            }
        )


class TemplateProviderTestCase(testcase.RollbackTestCase):
    def test__add_caching_headers(self):
        "response includes caching headers"
        template_provider = mock.MagicMock(
            spec=pages.TemplateProvider,
            __cache_expires__=1,
        )
        request = mock.MagicMock(spec=ScriptRequest)

        today = pages.datetime.date(2020, 5, 14)

        with patch.object(pages.datetime, "date") as date:
            date.today.return_value = today
            self.assertIsNone(
                pages.TemplateProvider._add_caching_headers(
                    template_provider,
                    request,
                )
            )

        request.add_extra_header.assert_has_calls([
            mock.call("Cache-Control", "public, max-age=86400"),
            mock.call("Expires", "Fri, 15 May 2020 00:00:00 GMT"),
            mock.call("Pragma", ""),
        ])
        self.assertEqual(
            request.add_extra_header.call_count,
            3
        )

    def test__render(self):
        "_add_caching_headers is called"
        template_provider = mock.MagicMock(
            spec=pages.TemplateProvider,
            application=mock.MagicMock(),
        )
        request = mock.MagicMock(spec=ScriptRequest)
        self.assertIsNone(
            pages.TemplateProvider._render(
                template_provider,
                request,
            )
        )
        template_provider._add_caching_headers.assert_called_once_with(
            request,
        )

    def test_render_without_app(self):
        template_provider = pages.TemplateProvider()

        with self.assertRaises(IndexError):
            template_provider._render(None)

        template_provider._virtualpath = ["", "A", "", "B", ""]

        with self.assertRaises(AttributeError):
            template_provider._render(DummyRequest())

    def test_render(self):
        template_provider = pages.TemplateProvider()

        with self.assertRaises(AttributeError):
            template_provider.render(None)

        template_provider._router_handled = "X"

        self.assertEqual(
            template_provider.render(None),
            "X"
        )


class RouterRenderTestCase(testcase.RollbackTestCase):
    def test_render_main(self):
        self.assertEqual(
            pages.render_main(None),
            {
                "label_title": u"Titel",
                "label_project": u"Projektnummer",
            }
        )

    def test_render_new_task_menu(self):
        self.assertEqual(
            pages.render_new_task_menu(None),
            {
                'heading_systemtask': u'Systemaufgabe',
                'heading': u'Aufgabe',
                'systemtask_types': [
                    {
                        'type': 'cdbwf_system_task',
                        'id': u'7f87cf00-f838-11e2-b1b5-082e5f0d3665',
                        'label': u'Information'
                    }, {
                        'type': 'cdbwf_system_task',
                        'id': u'91dd3340-ea12-11e2-8ad1-082e5f0d3665',
                        'label': u'Kopie'
                    }, {
                        'type': 'cdbwf_system_task',
                        'id': u'f16b8b40-706e-11e7-9aef-68f7284ff046',
                        'label': u'Operation ausführen'
                    }, {
                        'type': 'cdbwf_system_task',
                        'id': u'4daadbb0-e57a-11e2-9a44-082e5f0d3665',
                        'label': u'Statusänderung'
                    }, {
                        'type': 'cdbwf_system_task',
                        'id': u'2df381c0-1416-11e9-823e-605718ab0986',
                        'label': u'Untergeordneter Workflow/Schleife'
                    }, {
                        'type': 'cdbwf_system_task',
                        'id': u'a73d9cc0-ea12-11e2-baf4-082e5f0d3665',
                        'label': u'Workflow abbrechen'
                    },
                    {
                        'id': u'1dd0542d-98a9-11e9-b598-5cc5d4123f3b',
                        'label': u'Workflow abschlie\xdfen',
                        'type': 'cdbwf_system_task',
                    },
                ],
                'task_types': [
                    {
                        'extensions': [],
                        'type': 'cdbwf_task_examination',
                        'label': u'Prüfung'
                    }, {
                        'extensions': [
                            {
                                'type': u'cs_workflowtest_task_extension',
                                'label': u'Extension for Tests'
                            }
                        ],
                        'type': 'cdbwf_task_approval',
                        'label': u'Genehmigung'
                    }, {
                        'extensions': [],
                        'type': 'cdbwf_task_execution',
                        'label': u'Erledigung'
                    }
                ]
            }
        )

    def test_render_task_fields(self):
        self.assertEqual(
            pages.render_task_fields(None),
            {
                'max_duration_label': u'Max. Dauer (Tage)',
                'status_label': u'Status',
                'finish_option_label': u'Vorzeitig abschließen',
                'deadline_label': u'Fällig am'
            }
        )

    def test_render_systemtask_fields(self):
        self.assertEqual(
            pages.render_systemtask_fields(None),
            {
                'uses_global_maps_label': u'Verwendet globale Mappen'
            }
        )

    def test_render_constraints(self):
        self.assertEqual(
            pages.render_constraints(None),
            {
                'label': u'Constraint',
                'icon': '/resources/icons/byname/cdbwf_constraint/'
            }
        )

    def test_render_constraint(self):
        self.assertEqual(
            pages.render_constraint(None),
            {
                'label_invert': u'Regel invertieren'
            }
        )

    def test_render_forms(self):
        self.assertEqual(
            pages.render_forms(None),
            {
                'label': u'Formulare',
                'icon': '/resources/icons/byname/cdbwf_form/'
            }
        )

    def test_render_briefcase_links(self):
        self.assertEqual(
            pages.render_briefcase_links(None),
            {
                'label': u'Mappenzuordnung',
                'icon': '/resources/icons/byname/cdbwf_briefcase_cls/'
            }
        )

    def test_render_parallel(self):
        self.assertEqual(
            pages.render_parallel(None),
            {
                'constraint_icon': '/resources/icons/byname/cdbwf_constraint/'
            }
        )

    def test_render_task(self):
        self.assertEqual(
            pages.render_task(None),
            {
                'uses_global_maps_label': u'Verwendet globale Mappen',
                'briefcase_icon': '/resources/icons/byname/cdbwf_briefcase_cls/',
                'finish_option_label': u'Vorzeitig abschließen',
                'constraint_icon': '/resources/icons/byname/cdbwf_constraint/'
            }
        )

    def test_render_description(self):
        self.assertEqual(
            pages.render_description(None),
            {
                'label_description': u'Beschreibung'
            }
        )

    def test_render_briefcase_link_meanings(self):
        from cs.workflow.briefcases import IOType
        self.assertEqual(
            pages.render_briefcase_link_meanings(None),
            {
                'label_meaning': u'Bearbeitungsmodus',
                'meanings': IOType
            }
        )

    def test_render_parameters(self):
        self.assertEqual(
            pages.render_parameters(None),
            {
                'default_label': u'Parameter'
            }
        )


class RouterProcessTestCase(testcase.RollbackTestCase, PageTestCase):
    __process_id__ = "JSON_TEST"
    __page__ = pages.ProcessData

    def test_allowed_operations(self):
        page = self.get_page()
        self.assertEqual(
            pages.allowed_operations(page, self.__process_id__),
            {
                'after': False,
                'parallel': False,
                'loop': False,
                'before': False
            }
        )

    @patch.object(nanoroute, "posted_json")
    def test_create_task_first(self, posted_json):
        page = self.get_page_posted_json(
            posted_json,
            {
                "ttype": "system",
                "selection": [],
                "where": "wherever",
                "task_definition": "7f87cf00-f838-11e2-b1b5-082e5f0d3665",
                "parameters": {
                    "subject_id": "caddok",
                    "subject_type": "Person",
                },
            }
        )
        process = Process.ByKeys(self.__process_id__)
        self.assertEqual(len(process.AllTasks), 4)
        response = pages.create_task(page, self.__process_id__)[0]
        self.assertEqual(len(process.AllTasks), 5)
        self.assertEqual(response["iface"], "cs-workflow-graph")
        self.assertEqual(response["cdb_process_id"], self.__process_id__)

    @patch.object(nanoroute, "posted_json")
    def test_create_task_relative_to_selection(self, posted_json):
        process = Process.ByKeys(self.__process_id__)
        self.assertEqual(len(process.AllTasks), 4)

        for i, where in enumerate(["before", "after", "parallel"]):
            page = self.get_page_posted_json(
                posted_json,
                {
                    "ttype": "execution",
                    "selection": ["T00003984"],
                    "where": where,
                }
            )

            response = pages.create_task(page, self.__process_id__)[0]
            self.assertEqual(len(process.AllTasks), 5 + i)
            self.assertEqual(response["iface"], "cs-workflow-graph")
            self.assertEqual(response["cdb_process_id"], self.__process_id__)

    @patch.object(nanoroute, "posted_json")
    def test_create_task_relative_to_selection(self, posted_json):
        page = self.get_page_posted_json(
            posted_json,
            {
                "ttype": "execution",
                "where": "completion",
            }
        )

        process = Process.ByKeys(self.__process_id__)
        self.assertEqual(len(process.AllTasks), 4)
        response = pages.create_task(page, self.__process_id__)[0]
        self.assertEqual(len(process.AllTasks), 5)
        self.assertEqual(response["iface"], "cs-workflow-graph")
        self.assertEqual(response["cdb_process_id"], self.__process_id__)

    @patch.object(nanoroute, "posted_json")
    def test_create_cycle_from_selection(self, posted_json):
        process = Process.ByKeys(self.__process_id__)
        self.assertEqual(len(process.AllTasks), 4)

        page = self.get_page_posted_json(
            posted_json,
            {
                "selection": ["T00003984", "T00003989"],
            }
        )

        response = pages.create_cycle(page, self.__process_id__)[0]
        self.assertEqual(len(process.AllTasks), 3)
        self.assertEqual(response["iface"], "cs-workflow-graph")
        self.assertEqual(response["cdb_process_id"], self.__process_id__)

    @patch.object(nanoroute, "posted_json")
    def test_create_cycle(self, posted_json):
        page = self.get_page_posted_json(
            posted_json,
            {}
        )

        process = Process.ByKeys(self.__process_id__)
        self.assertEqual(len(process.AllTasks), 4)
        response = pages.create_cycle(page, self.__process_id__)[0]
        self.assertEqual(len(process.AllTasks), 4)
        self.assertEqual(response["iface"], "cs-workflow-graph")
        self.assertEqual(response["cdb_process_id"], self.__process_id__)

    @patch.object(nanoroute, "posted_json")
    def test_remove_task(self, posted_json):
        page = self.get_page_posted_json(
            posted_json,
            "T00003984"
        )

        process = Process.ByKeys(self.__process_id__)
        self.assertEqual(len(process.AllTasks), 4)
        response = pages.remove_task(page, self.__process_id__)[0]
        self.assertEqual(len(process.AllTasks), 3)
        self.assertEqual(response["iface"], "cs-workflow-graph")
        self.assertEqual(response["cdb_process_id"], self.__process_id__)

    @patch("cdb.elink.getCurrentRequest")
    def test_modify_process(self, request):
        page = self.get_page_request(
            request,
            {
                "attribute": "title",
                "value": "renamed",
            }
        )

        process = Process.ByKeys(self.__process_id__)
        self.assertEqual(process.title, "JSON Test")
        self.assertEqual(
            pages.modify_process(page, self.__process_id__),
            {"title": "renamed"}
        )
        self.assertEqual(process.title, "renamed")

    def test_start_process(self):
        page = self.get_page()
        self.assertEqual(
            pages.start_process(page, self.__process_id__),
            {
                'success': 1
            }
        )

    def test_hold_process(self):
        page = self.get_page()
        self.assertEqual(
            pages.hold_process(page, self.__process_id__),
            {
                'message': u"Der Status des Workflows ist nicht 'Umsetzung'."
            }
        )

    def test_cancel_process(self):
        page = self.get_page()
        self.assertEqual(
            pages.cancel_process(page, self.__process_id__),
            {
                'success': 1
            }
        )

    def test_dismiss_process(self):
        page = self.get_page()
        self.assertEqual(
            pages.dismiss_process(page, self.__process_id__),
            {
                'success': 1
            }
        )

    @patch.object(nanoroute, "posted_json")
    def test_create_global_briefcase(self, posted_json):
        page = self.get_page_posted_json(
            posted_json,
            {
                "name": "pelican",
                "meaning": "edit",
            }
        )
        process = Process.ByKeys(self.__process_id__)
        process.BriefcaseLinks.Delete()
        process.Reload()
        result = pages.create_global_briefcase(page, self.__process_id__)
        briefcase_id = process.BriefcaseLinks[0].briefcase_id
        self.assertEqual(
            result,
            {
                'addUrl': '/APPROOT/process/JSON_TEST/create_global_briefcase/',
                'briefcases': [
                    {
                        'addContentUrl': (
                            '/APPROOT/process/JSON_TEST/global_briefcases/{}/'
                            'add_content/'
                        ).format(briefcase_id),
                        'briefcase_id': briefcase_id,
                        'contents': [],
                        'deleteContentUrl': (
                            '/APPROOT/process/JSON_TEST/global_briefcases/{}/'
                            'delete_content/'
                        ).format(briefcase_id),
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/global_briefcases/{}/'
                            'delete/'
                        ).format(briefcase_id),
                        'icon': (
                            '/resources/icons/byname/'
                            'cdbwf_briefcase_link_obj?iotype=1'
                        ),
                        'iface': 'cs-workflow-global-briefcase',
                        'iotype': 1,
                        'meaning': 'edit',
                        'modifyUrl': (
                            '/APPROOT/process/JSON_TEST/global_briefcases/{}/'
                            'modify/'
                        ).format(briefcase_id),
                        'name': u'pelican',
                        'setMeaningUrl': (
                            '/APPROOT/process/JSON_TEST/global_briefcases/{}/'
                            'setmeaning/'
                        ).format(briefcase_id),
                    },
                ],
                'iface': 'cs-workflow-global-briefcases',
            }
        )

    @patch.object(nanoroute, "posted_json")
    def test_create_local_briefcase(self, posted_json):
        page = self.get_page_posted_json(
            posted_json,
            {
                "name": "pelican",
            }
        )
        process = Process.ByKeys(self.__process_id__)
        process.AllBriefcases.Delete()
        result = pages.create_local_briefcase(page, self.__process_id__)
        briefcase_id = process.AllBriefcases.Query(
            "briefcase_id>0"
        )[0].briefcase_id
        self.assertEqual(
            result,
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/create_local_briefcase/'
                ),
                'briefcases': [
                    {
                        'addContentUrl': (
                            '/APPROOT/process/JSON_TEST/local_briefcases/{}/'
                            'add_content/'
                        ).format(briefcase_id),
                        'briefcase_id': briefcase_id,
                        'contents': [],
                        'deleteContentUrl': (
                            '/APPROOT/process/JSON_TEST/local_briefcases/{}/'
                            'delete_content/'
                        ).format(briefcase_id),
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/local_briefcases/{}/'
                            'delete/'
                        ).format(briefcase_id),
                        'icon': (
                            '/resources/icons/byname/cdbwf_briefcase_cls?'
                        ),
                        'iface': 'cs-workflow-local-briefcase',
                        'modifyUrl': (
                            '/APPROOT/process/JSON_TEST/local_briefcases/{}/'
                            'modify/'
                        ).format(briefcase_id),
                        'name': u'pelican',
                    },
                ],
                'iface': 'cs-workflow-local-briefcases',
            }
        )

    def test_set_project(self):
        page = self.get_page()
        self.assertEqual(
            pages.set_project(page, self.__process_id__),
            None
        )


class RouterTaskTestCase(testcase.RollbackTestCase, PageTestCase):
    __process_id__ = "JSON_TEST"
    __task_id__ = "T00003984"
    __page__ = pages.ProcessData

    def _get_task(self):
        task_id = self.__task_id__
        process = Process.ByKeys(self.__process_id__)
        for task in process.AllTasks.KeywordQuery(task_id=task_id):
            return task

    @patch("cdb.elink.getCurrentRequest")
    def test_modify_task(self, request):
        page = self.get_page_request(
            request,
            {
                "attribute": "title",
                "value": "sisyphos",
            }
        )
        task = self._get_task()
        self.assertEqual(task.title, "1.1")
        self.assertEqual(
            pages.modify_task(page, self.__process_id__, self.__task_id__),
            {
                "title": "sisyphos",
            }
        )
        self.assertEqual(task.title, "sisyphos")

    def test_get_responsible(self):
        page = self.get_page()
        self.assertEqual(
            pages.get_responsible(page, self.__process_id__, self.__task_id__),
            {
                'id1': u'wftest_task_owner',
                'id2': '',
                'iface': 'cs-workflow-responsible',
                'name': u'Owner, Task',
                'picture': None,
                'setResponsibleUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                    'set_responsible/'
                ),
                'subject_type': 'Person'
            }
        )

    @patch("cdb.elink.getCurrentRequest")
    def test_add_form(self, request):
        page = self.get_page_request(
            request,
            {
                "form_template_id": "dd56ac92-b7ec-11e8-b3fc-5cc5d4123f3b",
            }
        )
        task = self._get_task()
        task.BriefcaseLinks.Delete()
        task.Process.AllBriefcases.Delete()
        self.assertEqual(len(task.AllForms), 0)
        result = pages.add_form(page, self.__process_id__, self.__task_id__)
        task.Reload()
        self.assertEqual(len(task.AllForms), 1)
        form_oid = task.AllForms[0].cdb_object_id
        briefcase_id = task.BriefcaseLinks.Query(
            "briefcase_id NOT IN (0, 146, 147)"
        )[0].briefcase_id
        self.assertEqual(
            result,
            {
                'sidebar_local_briefcases': {
                    'addUrl': (
                        '/APPROOT/process/JSON_TEST/create_local_briefcase/'
                    ),
                    'briefcases': [
                        {
                            'addContentUrl': (
                                '/APPROOT/process/JSON_TEST/local_briefcases/'
                                '{}/add_content/'
                            ).format(briefcase_id),
                            'briefcase_id': briefcase_id,
                            'contents': [
                                {
                                    'content_object_id': form_oid,
                                    'deletable': True,
                                    'description': u'Testformular',
                                    'icon': (
                                        '/resources/icons/byname/cdbwf_form?'
                                    ),
                                    'iface': 'cs-workflow-briefcase-content',
                                    'operations': {
                                        'iface': (
                                            'cs-workflow-operation-dropdown'
                                        ),
                                        'oplist': [],
                                    },
                                    'url': (
                                        u'/info/form/{}'.format(form_oid)
                                    ),
                                },
                            ],
                            'deleteContentUrl': (
                                '/APPROOT/process/JSON_TEST/local_briefcases/'
                                '{}/delete_content/'
                            ).format(briefcase_id),
                            'deleteUrl': (
                                '/APPROOT/process/JSON_TEST/local_briefcases/'
                                '{}/delete/'
                            ).format(briefcase_id),
                            'icon': (
                                '/resources/icons/byname/cdbwf_briefcase_cls?'
                            ),
                            'iface': 'cs-workflow-local-briefcase',
                            'modifyUrl': (
                                '/APPROOT/process/JSON_TEST/local_briefcases/'
                                '{}/modify/'
                            ).format(briefcase_id),
                            'name': u'Testformular 1',
                        },
                    ],
                    'iface': 'cs-workflow-local-briefcases',
                },
                'task_local_briefcases': {
                    'addUrl': (
                        '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                        'link_briefcase/'
                    ),
                    'iface': 'cs-workflow-briefcase-links',
                    'links': [
                        {
                            'briefcase_id': briefcase_id,
                            'briefcase_name': u'Testformular 1',
                            'deleteUrl': (
                                '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                                'briefcaselinks/{}/delete/'.format(
                                    briefcase_id
                                )
                            ),
                            'icon': (
                                '/resources/icons/byname/'
                                'cdbwf_briefcase_link_obj?iotype=1'
                            ),
                            'iface': 'cs-workflow-briefcase-link',
                            'iotype': 1,
                            'meaning': 'edit',
                            'modifyUrl': (
                                '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                                'briefcaselinks/{}/modify/'.format(
                                    briefcase_id
                                )
                            ),
                        },
                    ],
                }
            }
        )

    def test_set_responsible(self):
        page = self.get_page()
        self.assertEqual(
            pages.set_responsible(page, self.__process_id__, self.__task_id__),
            {
                'id1': u'',
                'id2': '',
                'iface': 'cs-workflow-responsible',
                'name': u'',
                'picture': None,
                'setResponsibleUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                    'set_responsible/'
                ),
                'subject_type': u''
            }
        )

    @patch("cdb.elink.getCurrentRequest")
    def test_add_constraint(self, request):
        page = self.get_page_request(
            request,
            {
                "constraint": "03d8ab8f-22e4-11e9-97e9-68f7284ff046",
            }
        )
        task = self._get_task()
        self.assertEqual(len(task.Constraints), 0)
        result = pages.add_constraint(page, self.__process_id__, self.__task_id__)
        task.Reload()
        self.assertEqual(len(task.Constraints), 1)
        constraint_oid = task.Constraints[0].cdb_object_id
        self.assertEqual(
            result,
            {
                'addConstraintUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                    'add_constraint/'
                ),
                'constraints': [
                    {
                        'briefcase_id': '',
                        'briefcase_name': u'',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                            'constraints/{}/delete/'.format(constraint_oid)
                        ),
                        'iface': 'cs-workflow-constraint',
                        'invert_rule': 0,
                        'modifyUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                            'constraints/{}/modify/'.format(constraint_oid)
                        ),
                        'rule_name': u'Workflow abgeschlossen',
                    },
                ],
                'iface': 'cs-workflow-constraints',
            }
        )

    @patch("cdb.elink.getCurrentRequest")
    def test_link_briefcase(self, request):
        page = self.get_page_request(
            request,
            {
                "briefcase_id": 146,
            }
        )
        task = self._get_task()
        task.BriefcaseLinks.Delete()
        self.assertEqual(
            pages.link_briefcase(
                page,
                self.__process_id__,
                self.__task_id__
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                    'link_briefcase/'
                ),
                'iface': 'cs-workflow-briefcase-links',
                'links': [
                    {
                        'briefcase_id': 146,
                        'briefcase_name': u'Info',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                            'briefcaselinks/146/delete/'
                        ),
                        'icon': (
                            '/resources/icons/byname/'
                            'cdbwf_briefcase_link_obj?iotype=0'
                        ),
                        'iface': 'cs-workflow-briefcase-link',
                        'iotype': 0,
                        'meaning': 'info',
                        'modifyUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                            'briefcaselinks/146/modify/'
                        ),
                    },
                ],
            }
        )
        task.Reload()
        self.assertEqual(
            set([link.briefcase_id for link in task.Briefcases]),
            set([146])
        )

    def test_delete_briefcase_link(self):
        page = self.get_page()
        task = self._get_task()
        self.assertEqual(
            [link.briefcase_id for link in task.Briefcases],
            [147]
        )
        self.assertEqual(
            pages.delete_briefcase_link(
                page,
                self.__process_id__,
                self.__task_id__,
                147
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                    'link_briefcase/'
                ),
                'iface': 'cs-workflow-briefcase-links',
                'links': [],
            }
        )
        task.Reload()
        self.assertEqual(len(task.Briefcases), 0)

    @patch("cdb.elink.getCurrentRequest")
    def test_modify_briefcase_link(self, request):
        page = self.get_page_request(
            request,
            {
                "attribute": "extends_rights",
                "value": 1,
            }
        )
        task = self._get_task()
        self.assertEqual(task.BriefcaseLinks[0].extends_rights, 0)
        self.assertEqual(
            pages.modify_briefcase_link(
                page,
                self.__process_id__,
                self.__task_id__,
                147
            ),
            {
                'briefcase_id': 147,
                'briefcase_name': u'Testformular 1',
                'deleteUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                    'briefcaselinks/147/delete/'
                ),
                'icon': (
                    '/resources/icons/byname/'
                    'cdbwf_briefcase_link_obj?iotype=0'
                ),
                'iface': 'cs-workflow-briefcase-link',
                'iotype': 0,
                'meaning': 'info',
                'modifyUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003984/'
                    'briefcaselinks/147/modify/'
                ),
            }
        )
        task.Reload()
        self.assertEqual(task.BriefcaseLinks[0].extends_rights, 1)

    def test_modify_extension(self):
        self.skipTest("tbd: requires extended task")
        page = self.get_page()
        self.assertEqual(
            pages.modify_extension(
                page,
                self.__process_id__,
                self.__task_id__
            ),
            {}
        )


class RouterSystemTaskTestCase(testcase.RollbackTestCase, PageTestCase):
    __process_id__ = "JSON_TEST"
    __task_id__ = "T00003987"
    __page__ = pages.ProcessData
    __condition_oid__ = "7bd6ade1-1eed-11e9-a1ce-68f7284ff046"
    __condition_name__ = "Durchlauf fehlgeschlagen"
    __condition_oid2__ = "60fd3480-1eed-11e9-a6c4-68f7284ff046"

    def _get_task(self):
        task_id = self.__task_id__
        process = Process.ByKeys(self.__process_id__)
        for task in process.AllTasks.KeywordQuery(task_id=task_id):
            # make the system task a "run loop" task
            task.Update(
                task_definition_id="2df381c0-1416-11e9-823e-605718ab0986"
            )
            return task

    def test_modify_parameter(self):
        page = self.get_page()
        self.assertEqual(
            pages.modify_parameter(
                page,
                self.__process_id__,
                self.__task_id__
            ),
            {
                'deleteUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'delete_parameter/'
                ),
                'iface': 'cs-workflow-parameters',
                'label': u'Empfänger',
                'modifyUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'modify_parameter/'
                ),
                'parameters': [
                    {
                        'iface': 'cs-workflow-parameter-generate-info',
                        'mapped_subject_name': u'None',
                        'readonly': False,
                        'subject_id': u'None',
                        'subject_title': u'None(None, None)',
                        'subject_type': u'None',
                    },
                ],
                'plist_class': '',
            }
        )

    def test_delete_parameter(self):
        page = self.get_page()
        self.assertEqual(
            pages.delete_parameter(
                page,
                self.__process_id__,
                self.__task_id__
            ),
            {
                'deleteUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'delete_parameter/'
                ),
                'iface': 'cs-workflow-parameters',
                'label': u'Empfänger',
                'modifyUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'modify_parameter/'
                ),
                'parameters': [
                    {
                        'iface': 'cs-workflow-parameter-generate-info',
                        'mapped_subject_name': '',
                        'readonly': False,
                        'subject_id': '',
                        'subject_title': '(, )',
                        'subject_type': '',
                    },
                ],
                'plist_class': '',
            }
        )

    @patch("cdb.elink.getCurrentRequest")
    def test_add_success_condition(self, request):
        page = self.get_page_request(
            request,
            {
                "success_condition": self.__condition_oid__,
                "position": "2",
            }
        )
        task = self._get_task()
        self.assertEqual(
            task.AllParameters.KeywordQuery(name="success_condition").value,
            []
        )
        self.assertEqual(
            pages.add_success_condition(
                page,
                self.__process_id__,
                self.__task_id__
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'success_condition/'
                ),
                'iface': 'cs-workflow-success-conditions',
                'success_conditions': [
                    {
                        'condition_name': u'Durchlauf fehlgeschlagen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_condition/Durchlauf fehlgeschlagen/'
                            'delete/2/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf fehlgeschlagen/'
                            'down/2/'
                        ),
                        'iface': 'cs-workflow-success-condition',
                        'position': u'2',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf fehlgeschlagen/'
                            'up/2/'
                        ),
                    },
                ],
            }
        )
        task.Reload()
        self.assertEqual(
            task.AllParameters.KeywordQuery(name="success_condition").value,
            ["2"]
        )

    @patch("cdb.elink.getCurrentRequest")
    def test_add_failure_condition(self, request):
        page = self.get_page_request(
            request,
            {
                "failure_condition": self.__condition_oid__,
                "position": "2",
            }
        )
        task = self._get_task()
        self.assertEqual(
            task.AllParameters.KeywordQuery(name="failure_condition").value,
            []
        )
        self.assertEqual(
            pages.add_failure_condition(
                page,
                self.__process_id__,
                self.__task_id__
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'failure_condition/'
                ),
                'failure_conditions': [
                    {
                        'condition_name': u'Durchlauf fehlgeschlagen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_condition/Durchlauf fehlgeschlagen/'
                            'delete/2/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf fehlgeschlagen/'
                            'down/2/'
                        ),
                        'iface': 'cs-workflow-failure-condition',
                        'position': u'2',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf fehlgeschlagen/'
                            'up/2/'
                        ),
                    },
                ],
                'iface': 'cs-workflow-failure-conditions',
            }
        )
        task.Reload()
        self.assertEqual(
            task.AllParameters.KeywordQuery(name="failure_condition").value,
            ["2"]
        )

    def test_delete_success_condition(self):
        page = self.get_page()
        task = self._get_task()
        task.AddParameters(
            rule_name=self.__condition_oid__,
            success_condition="2",
        )
        self.assertEqual(
            pages.delete_condition(
                page,
                self.__process_id__,
                self.__task_id__,
                "success_condition",
                self.__condition_name__,
                "2"
            ),
            {
                'success_conditions': [],
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'success_condition/'
                ),
                'iface': 'cs-workflow-success-conditions',
            }
        )
        task.Reload()
        self.assertEqual(
            len(task.AllParameters.KeywordQuery(name="success_condition")),
            0
        )

    def test_delete_failure_condition(self):
        page = self.get_page()
        task = self._get_task()
        task.AddParameters(
            rule_name=self.__condition_oid__,
            failure_condition="2",
        )
        self.assertEqual(
            pages.delete_condition(
                page,
                self.__process_id__,
                self.__task_id__,
                "failure_condition",
                self.__condition_name__,
                "2"
            ),
            {
                'failure_conditions': [],
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'failure_condition/'
                ),
                'iface': 'cs-workflow-failure-conditions',
            }
        )
        task.Reload()
        self.assertEqual(
            len(task.AllParameters.KeywordQuery(name="failure_condition")),
            0
        )

    def _get_conditions(self, task, condition):
        """
        {
            "rule oid 123abc": "03",
            "rule oid 123def": "05",
        }
        """
        task.Reload()
        params = task.AllParameters.KeywordQuery(
            name=condition,
            order_by="value ASC",
        )
        return {
            x.rule_name: x.value
            for x in params
        }

    def test_move_failure_condition_up(self):
        page = self.get_page()
        task = self._get_task()
        task.AddParameters(
            rule_name=self.__condition_oid2__,
            failure_condition="03",
        )
        task.AddParameters(
            rule_name=self.__condition_oid__,
            failure_condition="05",
        )
        self.assertEqual(
            pages.move_condition(
                page,
                self.__process_id__,
                self.__task_id__,
                "failure_conditions",
                self.__condition_name__,
                "up",
                "05"
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'failure_condition/'
                ),
                'failure_conditions': [
                    {
                        'condition_name': u'Durchlauf fehlgeschlagen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_condition/Durchlauf fehlgeschlagen/'
                            'delete/03/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf fehlgeschlagen/'
                            'down/03/'
                        ),
                        'iface': 'cs-workflow-failure-condition',
                        'position': u'03',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf fehlgeschlagen/'
                            'up/03/'
                        ),
                    }, {
                        'condition_name': u'Durchlauf abgeschlossen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_condition/Durchlauf abgeschlossen/'
                            'delete/05/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf abgeschlossen/'
                            'down/05/'
                        ),
                        'iface': 'cs-workflow-failure-condition',
                        'position': u'05',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf abgeschlossen/'
                            'up/05/'
                        ),
                    },
                ],
                'iface': 'cs-workflow-failure-conditions',
            }
        )
        self.assertEqual(
            self._get_conditions(task, "failure_condition"),
            {
                self.__condition_oid__: "03",
                self.__condition_oid2__: "05",
            }
        )

    def test_move_failure_condition_down(self):
        page = self.get_page()
        task = self._get_task()
        task.AddParameters(
            rule_name=self.__condition_oid__,
            failure_condition="05",
        )
        task.AddParameters(
            rule_name=self.__condition_oid2__,
            failure_condition="06",
        )
        task.Reload()
        self.assertEqual(
            pages.move_condition(
                page,
                self.__process_id__,
                self.__task_id__,
                "failure_conditions",
                self.__condition_name__,
                "down",
                "05"
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'failure_condition/'
                ),
                'failure_conditions': [
                    {
                        'condition_name': u'Durchlauf abgeschlossen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_condition/Durchlauf abgeschlossen/'
                            'delete/05/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf abgeschlossen/'
                            'down/05/'
                        ),
                        'iface': 'cs-workflow-failure-condition',
                        'position': u'05',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf abgeschlossen/'
                            'up/05/'
                        ),
                    }, {
                        'condition_name': u'Durchlauf fehlgeschlagen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_condition/Durchlauf fehlgeschlagen/'
                            'delete/06/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf fehlgeschlagen/'
                            'down/06/'
                        ),
                        'iface': 'cs-workflow-failure-condition',
                        'position': u'06',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'failure_conditions/Durchlauf fehlgeschlagen/'
                            'up/06/'
                        ),
                    },
                ],
                'iface': 'cs-workflow-failure-conditions',
            }
        )
        self.assertEqual(
            self._get_conditions(task, "failure_condition"),
            {
                self.__condition_oid2__: "05",
                self.__condition_oid__: "06",
            }
        )

    def test_move_success_condition_up(self):
        page = self.get_page()
        task = self._get_task()
        task.AddParameters(
            rule_name=self.__condition_oid__,
            success_condition="05",
        )
        task.AddParameters(
            rule_name=self.__condition_oid2__,
            success_condition="03",
        )
        self.assertEqual(
            pages.move_condition(
                page,
                self.__process_id__,
                self.__task_id__,
                "success_conditions",
                self.__condition_name__,
                "up",
                "05"
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'success_condition/'
                ),
                'iface': 'cs-workflow-success-conditions',
                'success_conditions': [
                    {
                        'condition_name': u'Durchlauf fehlgeschlagen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_condition/Durchlauf fehlgeschlagen/'
                            'delete/03/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf fehlgeschlagen/'
                            'down/03/'
                        ),
                        'iface': 'cs-workflow-success-condition',
                        'position': u'03',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf fehlgeschlagen/'
                            'up/03/'
                        ),
                    }, {
                        'condition_name': u'Durchlauf abgeschlossen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_condition/Durchlauf abgeschlossen/'
                            'delete/05/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf abgeschlossen/'
                            'down/05/'
                        ),
                        'iface': 'cs-workflow-success-condition',
                        'position': u'05',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf abgeschlossen/'
                            'up/05/'
                        ),
                    },
                ],
            }
        )
        self.assertEqual(
            self._get_conditions(task, "success_condition"),
            {
                self.__condition_oid__: "03",
                self.__condition_oid2__: "05",
            }
        )

    def test_move_success_condition_down(self):
        page = self.get_page()
        task = self._get_task()
        task.AddParameters(
            rule_name=self.__condition_oid2__,
            success_condition="06",
        )
        task.AddParameters(
            rule_name=self.__condition_oid__,
            success_condition="05",
        )
        self.assertEqual(
            pages.move_condition(
                page,
                self.__process_id__,
                self.__task_id__,
                "success_conditions",
                self.__condition_name__,
                "down",
                "05"
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                    'success_condition/'
                ),
                'iface': 'cs-workflow-success-conditions',
                'success_conditions': [
                    {
                        'condition_name': u'Durchlauf abgeschlossen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_condition/Durchlauf abgeschlossen/'
                            'delete/05/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf abgeschlossen/'
                            'down/05/'
                        ),
                        'iface': 'cs-workflow-success-condition',
                        'position': u'05',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf abgeschlossen/'
                            'up/05/'
                        ),
                    }, {
                        'condition_name': u'Durchlauf fehlgeschlagen',
                        'deleteUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_condition/Durchlauf fehlgeschlagen/'
                            'delete/06/'
                        ),
                        'downUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf fehlgeschlagen/'
                            'down/06/'
                        ),
                        'iface': 'cs-workflow-success-condition',
                        'position': u'06',
                        'upUrl': (
                            '/APPROOT/process/JSON_TEST/tasks/T00003987/'
                            'success_conditions/Durchlauf fehlgeschlagen/'
                            'up/06/'
                        ),
                    },
                ],
            }
        )
        self.assertEqual(
            self._get_conditions(task, "success_condition"),
            {
                self.__condition_oid2__: "05",
                self.__condition_oid__: "06",
            }
        )


class RouterBriefcaseTestCase(testcase.RollbackTestCase, PageTestCase):
    __process_id__ = "JSON_TEST"
    __global_briefcase_id__ = 0
    __briefcase_id__ = 147
    __page__ = pages.ProcessData

    def _get_global_briefcase(self):
        return Briefcase.KeywordQuery(
            cdb_process_id=self.__process_id__,
            briefcase_id=self.__global_briefcase_id__,
        )[0]

    def _get_briefcase(self):
        return Briefcase.KeywordQuery(
            cdb_process_id=self.__process_id__,
            briefcase_id=self.__briefcase_id__,
        )[0]

    @patch("cdb.elink.getCurrentRequest")
    def test_modify_briefcase(self, request):
        page = self.get_page_request(
            request,
            {
                "attribute": "name",
                "value": "renamed",
            }
        )
        briefcase = self._get_briefcase()
        self.assertEqual(briefcase.name, "Testformular 1")
        self.assertEqual(
            pages.modify_briefcase(
                page,
                self.__process_id__,
                self.__briefcase_id__
            ),
            {
                "name": "renamed",
            }
        )
        self.assertEqual(briefcase.name, "renamed")

    @patch("cdb.elink.getCurrentRequest")
    def test_set_global_briefcase_meaning(self, request):
        page = self.get_page_request(
            request,
            {
                "value": "edit",
            }
        )
        briefcase = self._get_global_briefcase()
        self.assertEqual(briefcase.Links.iotype, [0])
        self.assertEqual(
            pages.set_global_briefcase_meaning(
                page,
                self.__process_id__,
                self.__global_briefcase_id__
            ),
            {
                "iotype": 1,
                "meaning": "edit",
                "icon": (
                    "/resources/icons/byname/"
                    "cdbwf_briefcase_link_obj?iotype=1"
                ),
            }
        )
        self.assertEqual(briefcase.Links.iotype, [1])

    def test_delete_global_briefcase(self):
        page = self.get_page()
        self.assertEqual(
            pages.delete_global_briefcase(
                page,
                self.__process_id__,
                self.__briefcase_id__
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/create_global_briefcase/'
                ),
                'briefcases': [{
                    'addContentUrl': (
                        '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                        'add_content/'
                    ),
                    'briefcase_id': 0,
                    'contents': [],
                    'deleteContentUrl': (
                        '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                        'delete_content/'
                    ),
                    'deleteUrl': (
                        '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                        'delete/'
                    ),
                    'icon': (
                        '/resources/icons/byname/'
                        'cdbwf_briefcase_link_obj?iotype=0'
                    ),
                    'iface': 'cs-workflow-global-briefcase',
                    'iotype': 0,
                    'meaning': 'info',
                    'modifyUrl': (
                        '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                        'modify/'
                    ),
                    'name': u'Anh\xe4nge',
                    'setMeaningUrl': (
                        '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                        'setmeaning/'
                    ),
                }],
                'iface': 'cs-workflow-global-briefcases',
            }
        )

    def test_delete_local_briefcase(self):
        page = self.get_page()
        self._get_briefcase().Links.Delete()
        self.assertEqual(
            pages.delete_local_briefcase(
                page,
                self.__process_id__,
                self.__briefcase_id__
            ),
            {
                'addUrl': (
                    '/APPROOT/process/JSON_TEST/create_local_briefcase/'
                ),
                'briefcases': [{
                    'addContentUrl': (
                        '/APPROOT/process/JSON_TEST/local_briefcases/146/'
                        'add_content/'
                    ),
                    'briefcase_id': 146,
                    'contents': [],
                    'deleteContentUrl': (
                        '/APPROOT/process/JSON_TEST/local_briefcases/146/'
                        'delete_content/'
                    ),
                    'deleteUrl': (
                        '/APPROOT/process/JSON_TEST/local_briefcases/146/'
                        'delete/'
                    ),
                    'icon': '/resources/icons/byname/cdbwf_briefcase_cls?',
                    'iface': 'cs-workflow-local-briefcase',
                    'modifyUrl': (
                        '/APPROOT/process/JSON_TEST/local_briefcases/146/'
                        'modify/'
                    ),
                    'name': u'Info',
                }],
                'iface': 'cs-workflow-local-briefcases',
            }
        )

    @patch("cdb.elink.getCurrentRequest")
    def test_add_content_to_global_briefcase(self, request):
        test_object = WFTestFixture.ByKeys("TEST_FIXTURE")
        test_object.MakeURL(plain=2)
        page = self.get_page_request(
            request,
            {
                "cmsgs[]": [
                    test_object.MakeURL(plain=2),  # cdb://
                    "/info/cdbwf_test/TEST FIXTURE 2",
                    # "/info/{rest_name}/{rest_key}/relship/{relship}",
                    # ".../files/{file_object_id}",
                ]
            }
        )
        briefcase = self._get_global_briefcase()
        self.assertEqual(len(briefcase.Content), 0)
        self.assertEqual(
            pages.add_content_to_global_briefcase(
                page,
                self.__process_id__,
                self.__global_briefcase_id__
            ),
            {
                'addContentUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                    'add_content/'
                ),
                'briefcase_id': 0,
                'contents': [
                    {
                        'content_object_id': (
                            u'0a68595e-4239-11e8-92a7-5cc5d4123f3b'
                        ),
                        'deletable': True,
                        'description': u'TEST_FIXTURE',
                        'icon': '',
                        'iface': 'cs-workflow-briefcase-content',
                        'operations': {
                            'iface': 'cs-workflow-operation-dropdown',
                            'oplist': [],
                        },
                        'url': u'/info/cdbwf_test/TEST_FIXTURE',
                    }, {
                        'content_object_id': (
                            u'917a52f0-2956-11e9-863b-68f7284ff046'
                        ),
                        'deletable': True,
                        'description': u'TEST FIXTURE 2',
                        'icon': '',
                        'iface': 'cs-workflow-briefcase-content',
                        'operations': {
                            'iface': 'cs-workflow-operation-dropdown',
                            'oplist': [],
                        },
                        'url': u'/info/cdbwf_test/TEST~20FIXTURE~202',
                    },
                ],
                'deleteContentUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                    'delete_content/'
                ),
                'deleteUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/delete/'
                ),
                'icon': (
                    '/resources/icons/byname/'
                    'cdbwf_briefcase_link_obj?iotype=0'
                ),
                'iface': 'cs-workflow-global-briefcase',
                'iotype': 0,
                'meaning': 'info',
                'modifyUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/modify/'
                ),
                'name': u'Anhänge',
                'setMeaningUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                    'setmeaning/'
                ),
            }
        )
        self.assertEqual(len(briefcase.Content), 2)

    @patch("cdb.elink.getCurrentRequest")
    def test_delete_global_briefcase_content(self, request):
        content_oid = "0a68595e-4239-11e8-92a7-5cc5d4123f3b"
        page = self.get_page_request(
            request,
            {
                "content_object_id": content_oid,
            }
        )
        briefcase = self._get_global_briefcase()
        briefcase.AddObject(content_oid)
        self.assertEqual(len(briefcase.Content), 1)
        self.assertEqual(
            pages.delete_global_briefcase_content(
                page,
                self.__process_id__,
                self.__global_briefcase_id__
            ),
            {
                'addContentUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                    'add_content/'
                ),
                'briefcase_id': 0,
                'contents': [],
                'deleteContentUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                    'delete_content/'
                ),
                'deleteUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                    'delete/'
                ),
                'icon': (
                    '/resources/icons/byname/'
                    'cdbwf_briefcase_link_obj?iotype=0'
                ),
                'iface': 'cs-workflow-global-briefcase',
                'iotype': 0,
                'meaning': 'info',
                'modifyUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                    'modify/'
                ),
                'name': u'Anhänge',
                'setMeaningUrl': (
                    '/APPROOT/process/JSON_TEST/global_briefcases/0/'
                    'setmeaning/'
                ),
            }
        )
        briefcase.Reload()
        self.assertEqual(len(briefcase.Content), 0)

    @patch("cdb.elink.getCurrentRequest")
    def test_add_content_to_local_briefcase(self, request):
        test_object = WFTestFixture.ByKeys("TEST_FIXTURE")
        test_object.MakeURL(plain=2)
        page = self.get_page_request(
            request,
            {
                "cmsgs[]": [
                    test_object.MakeURL(plain=2),  # cdb://
                    "/info/cdbwf_test/TEST FIXTURE 2",
                    # "/info/{rest_name}/{rest_key}/relship/{relship}",
                    # ".../files/{file_object_id}",
                ]
            }
        )
        briefcase = self._get_briefcase()
        self.assertEqual(len(briefcase.Content), 0)
        self.assertEqual(
            pages.add_content_to_local_briefcase(
                page,
                self.__process_id__,
                self.__briefcase_id__
            ),
            {
                'addContentUrl': (
                    '/APPROOT/process/JSON_TEST/local_briefcases/147/'
                    'add_content/'
                ),
                'briefcase_id': 147,
                'contents': [
                    {
                        'content_object_id': (
                            u'0a68595e-4239-11e8-92a7-5cc5d4123f3b'
                        ),
                        'deletable': True,
                        'description': u'TEST_FIXTURE',
                        'icon': '',
                        'iface': 'cs-workflow-briefcase-content',
                        'operations': {
                            'iface': 'cs-workflow-operation-dropdown',
                            'oplist': [],
                        },
                        'url': u'/info/cdbwf_test/TEST_FIXTURE',
                    }, {
                        'content_object_id': (
                            u'917a52f0-2956-11e9-863b-68f7284ff046'
                        ),
                        'deletable': True,
                        'description': u'TEST FIXTURE 2',
                        'icon': '',
                        'iface': 'cs-workflow-briefcase-content',
                        'operations': {
                            'iface': 'cs-workflow-operation-dropdown',
                            'oplist': [],
                        },
                        'url': u'/info/cdbwf_test/TEST~20FIXTURE~202',
                    },
                ],
                'deleteContentUrl': (
                    '/APPROOT/process/JSON_TEST/local_briefcases/147/'
                    'delete_content/'
                    ),
                'deleteUrl': (
                    '/APPROOT/process/JSON_TEST/local_briefcases/147/delete/'
                ),
                'icon': '/resources/icons/byname/cdbwf_briefcase_cls?',
                'iface': 'cs-workflow-local-briefcase',
                'modifyUrl': (
                    '/APPROOT/process/JSON_TEST/local_briefcases/147/modify/'
                ),
                'name': u'Testformular 1',
            }
        )
        self.assertEqual(len(briefcase.Content), 2)

    @patch("cdb.elink.getCurrentRequest")
    def test_delete_local_briefcase_content(self, request):
        content_oid = "0a68595e-4239-11e8-92a7-5cc5d4123f3b"
        page = self.get_page_request(
            request,
            {
                "content_object_id": content_oid,
            }
        )
        briefcase = self._get_briefcase()
        briefcase.AddObject(content_oid)
        self.assertEqual(len(briefcase.Content), 1)
        self.assertEqual(
            pages.delete_local_briefcase_content(
                page,
                self.__process_id__,
                self.__briefcase_id__
            ),
            {
                'addContentUrl': (
                    '/APPROOT/process/JSON_TEST/local_briefcases/147/'
                    'add_content/'
                ),
                'briefcase_id': 147,
                'contents': [],
                'deleteContentUrl': (
                    '/APPROOT/process/JSON_TEST/local_briefcases/147/'
                    'delete_content/'
                ),
                'deleteUrl': (
                    '/APPROOT/process/JSON_TEST/local_briefcases/147/'
                    'delete/'
                ),
                'icon': '/resources/icons/byname/cdbwf_briefcase_cls?',
                'iface': 'cs-workflow-local-briefcase',
                'modifyUrl': (
                    '/APPROOT/process/JSON_TEST/local_briefcases/147/'
                    'modify/'
                ),
                'name': u'Testformular 1',
            }
        )
        briefcase.Reload()
        self.assertEqual(len(briefcase.Content), 0)


class RouterConstraintTestCase(testcase.RollbackTestCase, PageTestCase):
    __process_id__ = "JSON_TEST"
    __task_id__ = "T00003983"
    __constraint_oid__ = "5e6de8b2-c86a-11e8-b71d-5cc5d4123f3b"
    __page__ = pages.ProcessData

    def _get_constraint(self):
        process = Process.ByKeys(self.__process_id__)
        for constraint in process.AllConstraints.KeywordQuery(
                cdb_object_id=self.__constraint_oid__
        ):
            return constraint

    @patch("cdb.elink.getCurrentRequest")
    def test_modify_constraint(self, request):
        page = self.get_page_request(
            request,
            {
                "attribute": "invert_rule",
                "value": "0",
            }
        )
        constraint = self._get_constraint()
        self.assertEqual(constraint.invert_rule, 1)
        self.assertEqual(
            pages.modify_constraint(
                page,
                self.__process_id__,
                self.__task_id__,
                self.__constraint_oid__
            ),
            {
                'briefcase_id': '',
                'briefcase_name': u'',
                'deleteUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003983/constraints/'
                    '5e6de8b2-c86a-11e8-b71d-5cc5d4123f3b/delete/'
                ),
                'iface': 'cs-workflow-constraint',
                'invert_rule': 0,
                'modifyUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003983/constraints/'
                    '5e6de8b2-c86a-11e8-b71d-5cc5d4123f3b/modify/'
                ),
                'rule_name': u'Workflow abgeschlossen',
            }
        )
        constraint.Reload()
        self.assertEqual(constraint.invert_rule, 0)

    def test_delete_constraint(self):
        page = self.get_page()
        self.assertEqual(
            pages.delete_constraint(
                page,
                self.__process_id__,
                self.__task_id__,
                self.__constraint_oid__
            ),
            {
                'addConstraintUrl': (
                    '/APPROOT/process/JSON_TEST/tasks/T00003983/'
                    'add_constraint/'
                ),
                'constraints': [],
                'iface': 'cs-workflow-constraints',
            }
        )
