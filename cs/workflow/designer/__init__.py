#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module cs.workflow.designer.designer
"""

import json
from cdb import elink
from cdb import sig
from cs.workflow.designer import nanoroute

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

REGISTER_CATALOG = sig.signal()

LOOP_TASK_ID = "2df381c0-1416-11e9-823e-605718ab0986"


@elink.using_template_engine("chameleon")
class WorkflowDesigner(elink.Application):
    def setup(self):
        from cs.workflow.designer import pages
        self.add("", pages.DesignerPage())
        self.add("templates", pages.TemplateProvider())
        self.add("app", pages.AppData())
        self.add("process", pages.ProcessData())
        from cs.workflow.designer.catalogs import ResponsibleCatalog
        self.add("responsibles", ResponsibleCatalog())
        from cs.workflow.designer.catalogs import FormTemplateCatalog
        self.add("form_templates", FormTemplateCatalog())
        from cs.workflow.designer.catalogs import OperationCatalog
        self.add("operations", OperationCatalog())
        from cs.workflow.designer.catalogs import ConstraintCatalog
        from cs.workflow.designer.catalogs import FilterCatalog
        from cs.workflow.designer.catalogs import ConditionCatalog
        self.add("constraints", ConstraintCatalog())
        self.add("filters", FilterCatalog())
        self.add("conditions", ConditionCatalog())
        from cs.workflow.designer.catalogs import ProjectCatalog
        self.add("projects", ProjectCatalog())
        from cs.workflow.designer.catalogs import get_roles
        self.addJSON(get_roles, "get_roles")
        from cs.workflow.designer.catalogs import WorkflowTemplateCatalog
        self.add("workflow_templates", WorkflowTemplateCatalog())
        sig.emit(REGISTER_CATALOG)(self.add_extension_catalog)

    def add_extension_catalog(self, catalog_url, catalog_cls):
        """
        Extension classes can add catalogs like this:

        .. code-block:: python

            from cs.workflow.designer import REGISTER_CATALOG
            @sig.connect(REGISTER_CATALOG)
            def register_catalog(callback):
                callback("relative_catalog_url", CustomElinkCatalogStandard)

        .. warning::
            You may override standard urls by calling this method.
        """
        self.add(catalog_url, catalog_cls())

    @classmethod
    def get_designer_url(cls, process, urlroot=""):
        return "{}{}?cdb_process_id={}".format(
            urlroot,
            cls.getModuleURL(),
            process.cdb_process_id,
        )


# lazy instantiation
_APP = None


def _getapp():
    global _APP
    if _APP is None:
        _APP = WorkflowDesigner("Designer")
    return _APP


def handle_request(req):
    """Shortcut to the app"""
    return _getapp().handle_request(req)


router = nanoroute.LookUp()


# ========================
# register point for javascript, css
# ========================
@router.resource("extension_resources")
def _get_extension_resources(page):
    """This returns a list to allow the customized extensions
    appending their css and javascript resources. The entry should be a
    dictionary contains 'css' and 'js' pointing to the resource files
    with the URL path relative to `options.localres_base` of an eLink
    application.
    """
    return dict(resources=[])
