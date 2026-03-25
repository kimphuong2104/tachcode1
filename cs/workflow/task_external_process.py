#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module task_external_process

This is the documentation for the task_external_process module.
"""

import sys

from cdb import fls
from cdb import tools
from cdb import util
from cdb.objects import Forward

from cs.workflow import tasks
from cs.workflow import briefcases
from cs.workflow import systemtasks
from cs.workflow import protocols

RUN_LOOP = "2df381c0-1416-11e9-823e-605718ab0986"
fParameterDefinition = Forward("cs.workflow.systemtasks.ParameterDefinition")
fSchemaComponent = Forward("cs.workflow.schemacomponents.SchemaComponent")


def refuse_task(task, msg):
    msg = str(msg)
    task.addProtocol(
        util.get_label("cdbwf_system_task_refused") % msg,
        protocols.MSGCANCEL
    )
    task.refuse_task(msg)


def cancel_task(task, msg):
    msg = str(msg)
    task.addProtocol(
        util.get_label("cdbwf_system_task_cancelled") % msg,
        protocols.MSGCANCEL
    )
    task.cancel_task(msg)


def close_process(task):
    """
    Close task's workflow, then complete task and discard all other new and
    running tasks of this workflow.

    For tasks, statuses are updated on DB level not API level to prevent race
    conditions because of another task becoming ready.
    """
    process = task.Process
    process.close_process()

    def _change_task_status(task, target_status):
        task.Update(
            status=target_status.status,
            cdb_status_txt=task.GetStateText(target_status),
        )

    _change_task_status(task, task.COMPLETED)
    task.addProtocol(
        str(
            util.get_label("cdbwf_process_done")
        ),
        protocols.MSGDONE
    )

    components = process.AllComponents.Query(
        fSchemaComponent.status.one_of(
            task.EXECUTION.status,
            task.NEW.status,
        )
    )
    for component in components:
        _change_task_status(component, task.DISCARDED)
        component.addProtocol(
            str(
                util.get_label("cdbwf_task_discarded")
            ) % "",
            protocols.MSGCANCEL
        )


def cancel_process(task, msg):
    """
    Cancel workflow because a system task requested it.
    """
    process = task.Process
    task.addProtocol(
        util.get_label("cdbwf_process_aborted") % msg,
        protocols.MSGCANCEL
    )
    process.cancel_process(str(msg))


def pause_process(task, msg):
    """
    Pause workflow because a system task requested it.
    """
    process = task.Process
    task.addProtocol(str(msg), protocols.MSGREFUSE)
    process.setOnhold()


def validate_parameters(task, params):
    ignored_params = set(params.keys())

    if task.task_definition_id == RUN_LOOP:
        ignored_params.update([
            "success_condition",
            "failure_condition",
        ])

    missing_pars = task.Definition.Parameters.Query(
        fParameterDefinition.name.not_one_of(*ignored_params)
    )

    if missing_pars:
        par_names = ', '.join(missing_pars.name)
        raise RuntimeError(
            "cdbwf_missing_parameters",
            task.GetDescription(),
            par_names
        )


def run_system_task_implementation(callableobj, task, contentsWithParams):
    from cs.workflow import wfqueue
    try:
        for content, params in contentsWithParams:
            validate_parameters(task, params)
            callableobj(task=task, content=content, **params)
    except systemtasks.CloseTaskAsynchronously as ex:
        # The system task implementation will take care of closing the task
        msg = str(ex)
        task.addProtocol(
            util.get_label("cdbwf_system_task_cont_async") % msg,
            protocols.MSGSYSTEM
        )
    except systemtasks.TaskRefusedException as ex:
        refuse_task(task, ex)
    except systemtasks.TaskCancelledException as ex:
        cancel_task(task, ex)
    except systemtasks.ProcessPausedException as ex:
        pause_process(task, ex)
    except systemtasks.ProcessCompletedException:
        close_process(task)
    except systemtasks.ProcessAbortedException as ex:
        cancel_process(task, ex)
    except Exception as ex:
        wfqueue.getLogger().exception(
            "system task implementation failed:\n\t%s\n\t%s\n\t%s",
            callableobj,
            task,
            contentsWithParams,
        )
        # IMPORTANT: print reason for failure on stdout;
        # this is where the parent process (wfqueue) will read it from
        print(str(ex))
        raise  # let job fail; wfqueue will pause the workflow by default
    else:
        # if no exception occured then close the task
        task.close_task()


def run(cdb_process_id, task_id):
    from cs.workflow import wfqueue
    logger = wfqueue.getLogger()
    logger.info("running system task %s:%s", cdb_process_id, task_id)
    fls.allocate_license("WORKFLOW_006")

    task = tasks.SystemTask.ByKeys(
        cdb_process_id=cdb_process_id,
        task_id=task_id,
    )
    if not task:
        logger.error("task %s:%s not found", cdb_process_id, task_id)
    elif not task.Definition:
        refuse_task(task, "cannot find system task definition\n")
    else:
        # find system task implementation
        callableobj = tools.getObjectByName(task.Definition.function_fqpyname)

        # build content dictionary
        content = {}
        contentsWithParams = []
        for mode in briefcases.IOType:
            content[mode.name] = task.getContent(mode.name)

            if task.uses_global_maps:
                content[mode.name] += task.Process.getContent(mode.name)

                # eliminate duplicates
                content[mode.name] = list(set(content[mode.name]))

        if task.task_definition_id == RUN_LOOP:
            params = {
                param.name: param.value
                for param in task.AllParameters
            }
            contentsWithParams = [[content, params]]
        else:
            # find parameters for the function call
            params = {}
            for param in task.Parameters:
                if param.name in list(params):
                    # allow value lists (multiple params with same name)
                    if not isinstance(params[param.name], list):
                        params[param.name] = [params[param.name]]
                    params[param.name].append(param.value)
                else:
                    params[param.name] = param.value

            if task.ObjectFilters:
                for rule_wrapper in task.ObjectFilters:
                    rule = rule_wrapper.Rule
                    # extend parameter dictionary with rule-specific
                    # parameters
                    ofparams = dict(params)
                    ofparams.update({
                        param.name: param.value
                        for param in task.FilterParameters[
                            rule_wrapper.cdb_object_id
                        ]
                    })

                    # filter content
                    fcontent = {
                        key: [obj for obj in value if rule.match(obj)]
                        for key, value in content.items()
                    }
                    contentsWithParams.append([fcontent, ofparams])
            else:
                contentsWithParams = [[content, params]]

        run_system_task_implementation(
            callableobj,
            task,
            contentsWithParams
        )


# Guard importing as main module
if __name__ == "__main__":
    from cs.workflow import wfqueue
    wfqueue.initialize_tool()
    args = iter(sys.argv[1:])

    cdb_process_id = next(args, "")
    task_id = next(args, "")
    run(cdb_process_id, task_id)
