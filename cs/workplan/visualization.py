#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import dotlib, util
from cs.platform.web import uisupport


def cswp_workplan_visualization(workplan, orientation="horizontal"):
    """Creates a .svg file visualizing the work plan using graphviz-dotlib
    (inspired by method 'on_cdb_package_show_dependencies_now' in packages.py)
    """
    graph = dotlib.Graph(
        "%s %s" % (util.get_label("cswp_workplan_label"), workplan.workplan_name)
    )
    # sequences oriented from left to right
    if orientation == "horizontal":
        graph.write("rankdir=LR")
    # graph.write("ranksep=equally") # separates nodes equally
    # definition of node/edge style
    graph.write('id="workplan"')
    graph.write("edge [color=darkgray]")
    graph.write("splines=ortho")
    graph.write(
        "node [color=darkgray, shape=record, style=filled, "
        'fontname="Source Sans Pro", fontsize="10", fillcolor=white]'
    )
    # placing
    # definition of font style
    graph.write('fontsize="10"')
    graph.write('fontname="Source Sans Pro"')
    graph.write(
        'label = "%s %s"'
        % (util.get_label("cswp_workplan_label"), workplan.workplan_name)
    )
    graph.write(
        'tooltip= "%s (%s)\n\n%s: %s \n\n%s: %s - %s" '
        % (
            workplan.workplan_name,
            workplan.workplan_id,
            util.get_label("cswp_description_label"),
            workplan.description,
            util.get_label("cswp_lotsize_label"),
            workplan.lot_size_from,
            workplan.lot_size_to,
        )
    )
    graph.write('labelloc="t"')
    # graph.write('URL = "%s"' % (uisupport.get_ui_link(None, workplan)))
    # add standard Task List and consequently all task lists
    _task_list_bundle_visualization(graph, workplan.RootTaskList, orientation)
    # graph.write('{rank="min"; start}')
    graph.close()
    return graph


def _task_list_bundle_visualization(graph, task_list, orientation):
    # Open cluster subgraph
    # graph.write("subgraph cluster_%s_bundle {" % task_list.task_list_id)
    # graph.write("color = invis")
    # graph.write('smoothing = "avg_dist"')
    # graph.write("clusterrank=local")
    # create main task list
    first_task, last_task = _task_list_visualization(graph, task_list, orientation)

    # Add all task_lists refering to the task_list into the given cluster
    for referer_task_list in task_list.RefererTaskLists:
        first, last = _task_list_bundle_visualization(
            graph, referer_task_list, orientation
        )
        graph.write(
            "s_%s_%s -> %s [weight=1]"
            % (
                referer_task_list.reference_task_list,
                referer_task_list.start_task,
                first,
            )
        )
        graph.write(
            "%s -> e_%s_%s [weight=1]"
            % (
                last,
                referer_task_list.reference_task_list,
                referer_task_list.return_task,
            )
        )
    # Close cluster subgraph
    # graph.write("}")
    return first_task, last_task


def _task_list_visualization(graph, task_list, orientation):
    # Open cluster subgraph
    graph.write("subgraph cluster_%s {" % task_list.task_list_id)
    graph.write('fontcolor = "%s"' % task_list.task_list_type_color())
    # graph.write('style = filled')
    graph.write('color = "%s"' % task_list.task_list_type_color())
    graph.write("style = filled")
    graph.write('fillcolor = "%s"' % task_list.task_list_type_color_light())
    graph.write(
        'label = "%s: %s"' % (task_list.task_list_type_name(), task_list.task_list_name)
    )
    graph.write(
        'tooltip= "%s (%s)\n\n%s: %s \n\n%s: %s - %s" '
        % (
            task_list.task_list_name,
            task_list.task_list_id,
            util.get_label("cswp_description_label"),
            task_list.description,
            util.get_label("cswp_lotsize_label"),
            task_list.lot_size_from,
            task_list.lot_size_to,
        )
    )
    graph.write('URL = "%s"' % (uisupport.get_ui_link(None, task_list)))
    predecessor = ""
    if task_list.task_list_type == "standard":
        graph.write(
            'start[shape = circle, label = "%s", color="%s", fontsize="10"]'
            % (util.get_label("cswp_start_label"), task_list.task_list_type_color())
        )
        predecessor = "start"

    first_task = ""
    last_task = ""

    # add all tasks of the task list one after the other
    for task in sorted(
        task_list.MainTasks, key=lambda x: x.task_position
    ):  # task_list.Tasks:
        successor, predecessor = _task_visualization(
            graph, task, predecessor, orientation
        )
        if first_task == "":
            first_task = successor
        last_task = predecessor
    if first_task == "":
        graph.write("%s [shape=point, style = invis]" % (task_list.task_list_id))
        first_task = task_list.task_list_id
        last_task = task_list.task_list_id

    if task_list.task_list_type == "standard":
        graph.write(
            'end[shape = doublecircle, label = "%s", color="%s", fontsize="10"]'
            % (util.get_label("cswp_end_label"), task_list.task_list_type_color())
        )
        graph.write("%s -> %s [weight=2]" % (predecessor, "end"))

    # close main task list
    graph.write("}")

    return first_task, last_task


def _task_visualization(graph, task, predecessor, orientation):
    if orientation == "horizontal":
        graph.write(
            '%s_%s [label = "{%s | {%s | %s}}",'
            'tooltip = "%s: %s (%s) \n\n%s: %s \n\n%s: %s \n\n%s: %s",'
            'URL = "%s", color="%s",'
            'fontsize="10", fixedsize=true, width="2"]'
            % (
                task.task_list_id,
                task.task_id,
                task.task_position,
                task.task_name
                if len(task.task_name) <= 30
                else task.task_name[0: (27 - len(str(task.task_position)))] + "...",
                task.workplace_name
                if len(task.workplace_name) <= 30
                else task.workplace_name[0 : (27 - len(str(task.task_position)))]
                + "...",
                task.task_position,
                task.task_name,
                task.task_id,
                util.get_label("cswp_description_label"),
                task.description,
                util.get_label("cswp_plant_label"),
                task.plant_name,
                util.get_label("cswp_workplace_label"),
                task.workplace_name,
                uisupport.get_ui_link(None, task),
                task.TaskList.task_list_type_color(),
            )
        )
    else:
        graph.write(
            '%s_%s [label = "%s | {%s | %s}",'
            'tooltip = "%s: %s (%s) \n\n%s: %s \n\n%s: %s \n\n%s: %s",'
            'URL = "%s", color="%s",'
            'fontsize="10", fixedsize=true, width="2"]'
            % (
                task.task_list_id,
                task.task_id,
                task.task_position,
                task.task_name
                if len(task.task_name) <= 30
                else task.task_name[0: (27 - len(str(task.task_position)))] + "...",
                task.workplace_name
                if len(task.workplace_name) <= 30
                else task.workplace_name[0 : (27 - len(str(task.task_position)))]
                + "...",
                task.task_position,
                task.task_name,
                task.task_id,
                util.get_label("cswp_description_label"),
                task.description,
                util.get_label("cswp_plant_label"),
                task.plant_name,
                util.get_label("cswp_workplace_label"),
                task.workplace_name,
                uisupport.get_ui_link(None, task),
                task.TaskList.task_list_type_color(),
            )
        )

    start = "%s_%s" % (task.task_list_id, task.task_id)
    end = "%s_%s" % (task.task_list_id, task.task_id)

    if task.RefererStartTaskTaskLists:
        graph.write(
            "s_%s_%s [shape=point, style = invis, fixedsize=false]"
            % (task.task_list_id, task.task_id)
        )
        graph.write(
            "s_%s_%s -> %s_%s [weight=2]"
            % (task.task_list_id, task.task_id, task.task_list_id, task.task_id)
        )
        start = "s_%s_%s" % (task.task_list_id, task.task_id)
        if predecessor != "":
            if predecessor == "start":
                graph.write("%s -> %s [dir=none,weight=10]" % (predecessor, start))
            else:
                graph.write("%s -> %s [dir=none,weight=2]" % (predecessor, start))

    else:
        if predecessor != "":
            graph.write("%s -> %s [weight=2]" % (predecessor, start))

    if task.RefererReturnTaskTaskLists:
        graph.write(
            "e_%s_%s [shape=point, style = invis, fixedsize=false]"
            % (task.task_list_id, task.task_id)
        )
        graph.write(
            "%s_%s -> e_%s_%s [dir=none, weight=2]"
            % (task.task_list_id, task.task_id, task.task_list_id, task.task_id)
        )
        end = "e_%s_%s" % (task.task_list_id, task.task_id)

    return start, end
