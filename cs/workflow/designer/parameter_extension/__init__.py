#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
To create customized parameter extensions of system task for
Workflow Designer, the following steps are recommended:

1. Create a Python module and two folders ``resources`` and ``chrome``:

        - customer
            - parameter_extension
                - __init__.py
                - resources
                - chrome

2. Put the javascript and css resources into 'resources'
3. Put the html templates into the 'chrome' folder
4. Register the resources in the module:

   .. code-block :: python

        import os
        import sys
        from cs.workflow.designer.parameter_extension import router

        # get the existing resources
        extension_resources = router.handle_request(
            None,
            ["extension_resources"]
        )

        # append new resources, should be a dictionary contains
        # 'css' and 'js' pointing to the resource files
        # with the URL path relative to `options.localres_base` of an eLink
        # application, or empty if unnecessary.
        # See `cs.workflow.designer.parameter_extension.get_parameter_extension_resources`
        extension_resources["resources"].append(
            {
                "css": css filepath,
                "js": js_filepath,
            }

        @router.resource("extension_resources")
        def get_parameter_extension_resources(page):
            return extension_resources

5. Register the view template in the module:

    .. code-block :: python

        CHROME_PATH = os.path.join(
            os.path.split(
                os.path.abspath(
                    __file__.decode(
                        sys.getfilesystemencoding()
                    )
                )
            )[0],
            "chrome"
        )

        # register template file under certain file name
        # the url must be constructed as templates/<obvt file name>
        @router.resource("templates/parameter_custom_view.obvt")
        def render_parameter_custom_view(page):
            # return the folder path, the file name and a dictionary,
            # which should be used as returned data from an
            # `elink.Template.render` method for the template rendering
            return (
                CHROME_PATH,
                "parameter_custom_view.obvt",
                {"some_variable_used_in_template": "some value"},
            )

6. Register the data handler to read, modify and delete parameter data:

    .. code-block :: python

        # get data, see `cs.workflow.designer.parameter_extension.get_parameters_generate_info`
        # for more information
        def get_parameter_custom(page, task, readonly=False):
            ...

        # modify data, see `cs.workflow.designer.parameter_extension.modify_parameters_generate_info`
        # for more information
        def modify_parameter_custom(page, task):
            # get value from submitted form
            some_variable = page.get_form_data("some_variable", None)
            ...

        # delete parameter, optional.
        # If missing the default handler will be used to delete all parameters
        # of that task
        def delete_parameter_custom(page, task):
            ...

        # register data getter/setter, using "parameter_extensions/<identifier>" form
        # currently use the task.Definition.name as identifier
        @router.resource("parameter_extensions/custom")
        def parameter_custom_handler(page):
            return {
                "getter": get_parameter_custom,
                "setter": modify_parameter_custom,
                "deleter": delete_parameter_custom,  # optional
                "label": "label/meaning of parameters for this custom task",
            }

7. Make sure that this module will be imported/loaded at start up.
8. Optionally, include a custom catalog:

    8.1 Add the following code to your parameter_extension.py file:

        .. code-block :: python

            class CustomCatalog(catalog.ElinkCatalogStandard):
                pass  # see catalog.ElinkCatalogStandard for details

            from cs.workflow.designer import REGISTER_CATALOG
            from cs.workflow.designer import WorkflowDesigner

            @sig.connect(REGISTER_CATALOG)
            def register_catalogs(callback):
                callback("my_custom_catalog_url", CustomCatalog)

            # replace existing modification of extension resources
            fully_qualified_catalog_url = "".join([
                WorkflowDesigner.getModuleURL(),
                "my_custom_catalog_url",
            ])
            extension_resources["resources"].append({
                "catalogs": [{
                    "url": fully_qualified_catalog_url,
                    "id": "my_custom_catalog_id",
                }],
                "css": css_filepath,
                "js": js_filepath,
            })

    8.2 Make sure your .obvt file includes a button to open the catalog:

        .. code-block :: html

            <a class="btn btn-mini parameter-action">
                <img src="${options.plugins}catalog/catalog.png" data-if="!readonly" />
            </a>
            <div class="parameter-custom text-ellipsis" title="{my_param}">{my_param}</div>
            <div class="no-float"></div>

    8.3 Make sure your obviel.view (in :file:`parameter_extensions.js`) handles the catalog in its render
    method (see :file:`StatusChange.js` for an example).

        .. code-block :: javascript

            this.el.find('.rule-action').off('click').on(
                'click',
                function() {
                    $(this).trigger('openObjectFilterCatalog');
                }
            )
            .off('objectFilterSelected')
            .on(
                'objectFilterSelected',
                function(ev, data) {
                    if (data.result.length && data.result[0].name) {
                        self.el.trigger(
                            'parameterChanged',
                            {
                                target_state: self.obj.target_state,
                                cdb_object_id: self.obj.cdb_object_id,
                                rule_wrapper_oid: data.result[0].cdb_object_id,
                                rule_name: data.result[0].name.text
                            }
                        );
                    }
                }
            );

        The event `openObjectFilterCatalog` is triggered when the catalog button
        is clicked. When an entry is selected from the catalog, the
        event `objectFilterSelected` is triggered.


    8.4 Meanwhile you can setup the catalog (in :file:`catalogs.js`) by adding the code in setupCatalogs() function as:

        .. code-block :: javascript

            _setupCatalog(
                'wf-designer-objectfilters',
                'objectFilterSelected',
                'openObjectFilterCatalog'
            );

        .. code-block :: javascript

            function _setupCatalog(catalogID, selectedEvent, openEvent, getData, plugins) {
                const catalogButton = window.$(
                    `${CATALOG_BUTTON_SELECTOR}${catalogID}]`
                );
                const setupData = {
                    plugins: plugins ? plugins(catalogButton) : [],
                    selected: function(result, rows) {
                        catalogButton.data(CATALOG_TRIGGER)
                            .trigger(selectedEvent, {
                                result: result,
                                rows: rows
                            });
                        catalogButton.data(CATALOG_TRIGGER, null);
                    },
                    getData: getData ? getData : function() {
                        return {};
                    },
                    mainTableOnly: true,
                    localFilter: false
                };
                Catalog.setupCatalog(
                    catalogButton,
                    setupData
                );
                _openCatalogOnEvent(
                    designer,
                    openEvent,
                    catalogButton
                );
            }

"""


import os


from cdb import util
from cdb.objects import ByID
from cs.workflow.designer import router

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# use of decode is intentional, do not modify
FILE = __file__
CHROME_PATH = os.path.join(os.path.split(os.path.abspath(FILE))[0], "chrome")

# ========================
# register javascript, css
# ========================
extension_resources = router.handle_request(
                None, ["extension_resources"])
extension_resources["resources"].append(
           dict(css=u"%s/parameter_extension.css" % __name__,
                js=u"%s/parameter_extension.js" % __name__))


@router.resource("extension_resources")
def get_parameter_extension_resources(page):
    """This returns a list to allow the customized parameter extensions
    appending their css and javascript resources. The entry should be a
    dictionary contains 'css' and 'js' pointing to the resource files
    with the URL path relative to `options.localres_base` of an eLink
    application.
    """
    return extension_resources


# ================
# Information task
# ================
# register template file under certain file name
# the url must be constructed as templates/<obvt file name>
@router.resource("templates/parameter_generate_info.obvt")
def render_parameter_generate_info(page):
    # return the folder path, the file name and the data,
    # which should be used as return value from an
    # `elink.Template.render` method used to render the template
    return (CHROME_PATH, "parameter_generate_info.obvt", {})


def get_parameters_generate_info(page, task, readonly=False):
    """Retun a list of parameters for given task.

        :param page: current elink page as a instance of class
                     `cs.workflow.designer.pages.ProcessData`
        :param task: the current system task object
        :param readonly: whether it is currently in readonly mode
    """
    from cs.workflow.designer.json_data import clean_text
    para = dict(iface="cs-workflow-parameter-generate-info",
                readonly=readonly)
    subject_ids = task.Parameters.KeywordQuery(name="subject_id")
    para["subject_id"] = clean_text(subject_ids[0].value) \
        if subject_ids else ""
    subject_types = task.Parameters.KeywordQuery(name="subject_type")
    para["subject_type"] = clean_text(subject_types[0].value) \
        if subject_types else ""
    para["mapped_subject_name"] = para["subject_id"]
    cond = "subject_id='%s' and subject_type='%s'" % (
        para["subject_id"], para["subject_type"])
    subjdata = task.Process.GetSubjectCandidates(cond)
    if subjdata:
        para["mapped_subject_name"] = subjdata[0].GetSubjectName()
    para["subject_title"] = "%s(%s, %s)" % (
        para["mapped_subject_name"], para["subject_id"], para["subject_type"])
    return [para]


def modify_parameters_generate_info(page, task):
    """Modify the parameter data of given task.

        :param page: current elink page as a instance of class
                     `cs.workflow.designer.pages.ProcessData`
        :param task: the current system task object
    """
    subject_id = page.get_form_data("subject_id", None)
    subject_type = page.get_form_data("subject_type", None)
    # TOOD: need ModifyParameter() api
    task.AllParameters.Delete()
    task.AddParameters(subject_id=subject_id, subject_type=subject_type)


# register data getter/setter, using "parameter_extensions/<identifier>" form
# currently use the task.Definition.name as identifier
@router.resource("parameter_extensions/Information")
def parameter_generate_info_handler(page):
    return {"getter": get_parameters_generate_info,
            "setter": modify_parameters_generate_info,
            "label": util.Labels()["cdbwf_parameter_receivers"]}


# ==================
# Status Change task
# ==================
# register template file
@router.resource("templates/parameter_status_change.obvt")
def render_parameter_status_change(page):
    return (CHROME_PATH, "parameter_status_change.obvt", {})


def get_parameters_status_change(page, task, readonly=False):
    from cs.workflow.designer.json_data import clean_text
    result = []
    for taskpara in task.AllParameters.KeywordQuery(name="target_state"):
        if taskpara.rule_name:
            rule_wrapper = ByID(taskpara.rule_name)

            if not rule_wrapper:
                raise RuntimeError(
                    "missing rule_wrapper '{}'".format(taskpara.rule_name)
                )

            rule_wrapper_oid = rule_wrapper.cdb_object_id
            rule_name = rule_wrapper.name
        else:
            rule_wrapper_oid = ""
            rule_name = ""

        result.append({
            "iface": "cs-workflow-parameter-status-change",
            "readonly": readonly,
            "target_state": clean_text(taskpara.value),
            "rule_wrapper_oid": clean_text(rule_wrapper_oid),
            "rule_name": clean_text(rule_name),
            "cdb_object_id": taskpara.cdb_object_id,
        })
    if not readonly:
        # new parameter form
        result.append({
            "iface": "cs-workflow-parameter-status-change",
            "readonly": readonly,
            "rule_wrapper_oid": "",
            "rule_name": "",
            "target_state": "",
            "cdb_object_id": "",
        })
    return result


def modify_parameters_status_change(page, task):
    cdb_object_id = page.get_form_data("cdb_object_id", None)
    target_state = page.get_form_data("target_state", None)
    rule_wrapper_oid = page.get_form_data("rule_wrapper_oid", None)
    para = task.AllParameters.KeywordQuery(cdb_object_id=cdb_object_id)
    if para:
        para[0].ModifyParameter(
            rule_name=rule_wrapper_oid,
            value=target_state
        )
    else:
        task.AddParameters(
            rule_name=rule_wrapper_oid,
            target_state=target_state
        )


def delete_parameters_status_change(page, task):
    cdb_object_id = page.get_form_data("cdb_object_id", None)
    para = task.AllParameters.KeywordQuery(cdb_object_id=cdb_object_id)
    if para:
        para[0].DeleteParameter()


@router.resource("parameter_extensions/Statuswechsel")
def parameter_status_change_handler(page):
    return {
        "getter": get_parameters_status_change,
        "setter": modify_parameters_status_change,
        "deleter": delete_parameters_status_change,
        "label": util.Labels()["cdbwf_parameter_targetstatus"],
        "parameter_list_class": "wf-parameters-status-change",
    }


# ==================
# Run Operation task
# ==================
# register template file
@router.resource("templates/parameter_run_operation.obvt")
def render_parameter_run_operation(page):
    return (CHROME_PATH, "parameter_run_operation.obvt", {})


def get_parameters_run_operation(page, task, readonly=False):
    """Retun a list of parameters for given task.

        :param page: current elink page as a instance of class
                     `cs.workflow.designer.pages.ProcessData`
        :param task: the current system task object
        :param readonly: whether it is currently in readonly mode
    """
    from cs.workflow.designer.json_data import clean_text
    para = dict(
        iface="cs-workflow-parameter-run-operation",
        readonly=readonly
    )
    names = task.Parameters.KeywordQuery(name="operation_name")
    para["operation_name"] = clean_text(names[0].value) if names else "-"
    para["icon"] = clean_text(task.get_system_task_icon())
    return [para]


def modify_parameters_run_operation(page, task):
    """Modify the parameter data of given task.

        :param page: current elink page as a instance of class
                     `cs.workflow.designer.pages.ProcessData`
        :param task: the current system task object
    """
    # TOOD: need ModifyParameter() api
    task.AllParameters.Delete()
    task.AddParameters(
        operation_name=page.get_form_data("operation_name", None)
    )


@router.resource("parameter_extensions/RunOperation")
def parameter_run_operation_handler(page):
    return {
        "getter": get_parameters_run_operation,
        "setter": modify_parameters_run_operation,
        "label": util.Labels()["cdbwf_parameter_opname"],
    }


# ==================
# Subworkflow/Loop
# ==================
@router.resource("templates/parameter_run_loop.obvt")
def render_parameter_run_loop(page):
    return (CHROME_PATH, "parameter_run_loop.obvt", {})


def get_parameters_run_loop(page, task, readonly=False):
    """Retun a list of parameters for given task.

        :param page: current elink page as a instance of class
                     `cs.workflow.designer.pages.ProcessData`
        :param task: the current system task object
        :param readonly: whether it is currently in readonly mode
    """
    from cs.workflow.designer.json_data import clean_text
    para = {
        "iface": "cs-workflow-parameter-run-loop",
        "readonly": readonly,
        "template_process_id": "",
        "max_cycles": "1",
    }
    params = task.Parameters
    for param in params:
        if param.name in para and param.value:
            para[param.name] = param.value
    para["current_cycle"] = (
        task.CurrentCycle.current_cycle
        if task.CurrentCycle
        else 1
    )
    para["icon"] = clean_text(task.get_system_task_icon())
    return [para]


def modify_parameters_run_loop(page, task):
    """Modify the parameter data of given task.

        :param page: current elink page as a instance of class
                     `cs.workflow.designer.pages.ProcessData`
        :param task: the current system task object
    """
    max_cycles = task.AllParameters.KeywordQuery(name='max_cycles')
    if max_cycles:
        max_cycles[0].ModifyParameter(value=page.get_form_data("max_cycles", 1))
    else:
        task.AddParameters(max_cycles=page.get_form_data("max_cycles", 1))


@router.resource("parameter_extensions/Schleife")
def parameter_run_loop_handler(page):
    return {
        "getter": get_parameters_run_loop,
        "setter": modify_parameters_run_loop,
        "label": util.Labels()["cdbwf_parameter_max_cycles"],
    }
