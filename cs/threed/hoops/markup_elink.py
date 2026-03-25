# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json

from cdb import constants
from cdb import util

from cdb.objects import operations

from cs.threed.hoops import markup


RDL_CIRCLE = "Communicator.Markup.Redline.RedlineCircle"
RDL_RECTANGLE = "Communicator.Markup.Redline.RedlineRectangle"
RDL_POLYLINE = "Communicator.Markup.Redline.RedlinePolyline"
RDL_TEXT = "Communicator.Markup.Redline.RedlineText"


def get_camera_args(camera):
    camera_args = {"name": camera.get("className"),
                   "width": camera.get("width"),
                   "height": camera.get("height"),
                   "projection": camera.get("projection"),
                   "near_limit": camera.get("nearLimit"),
                   }
    position = markup.DBPoint('position', camera.get("position"))
    target = markup.DBPoint('target', camera.get("target"))
    up = markup.DBPoint('up', camera.get("up"))
    camera_args.update(position.getDBArgs())
    camera_args.update(target.getDBArgs())
    camera_args.update(up.getDBArgs())

    return camera_args


def color_args(prefix, data):
    result = {}
    for key, value in data.items():
        result[prefix + key] = value
    return result


def get_view_args(data):
    cutting_data = data.get("cuttingData", {})

    view_args = {
        "name": data.get("name"),
        "explosion_level": data.get("explodeMagnitude"),
        "edge_visibility": "1" if data.get("lineVisibility") else "0",
        "face_visibility": "1" if data.get("faceVisibility") else "0",
        "context_object_id": data.get("context_object_id"),
        "structure_pkey": data.get("structure_pkey"),
        "capping_geometry_visibility": cutting_data.get("cappingGeometryVisibility"),
        "default_visibility": "1" if data.get("defaultVisibility") else "0",
        "variant_object_id": data.get("variant_object_id"),
    }
    view_args.update(color_args("capping_face_color_", cutting_data.get("cappingFaceColor")))
    view_args.update(color_args("capping_line_color_", cutting_data.get("cappingLineColor")))

    return view_args


def get_redline_args(redline, redline_type, create=False):

    redline_args = {}

    if create:
        redline_args = {"cdb_object_id": redline.get("uniqueId")}

    if redline_type == "RedlineCircle":
        center = markup.DBPoint('center', redline.get("centerPoint"))
        point2 = markup.DBPoint('point2', redline.get("radiusPoint"))
        redline_args.update(center.getDBArgs())
        redline_args.update(point2.getDBArgs())

    elif redline_type == "RedlineRectangle":
        point1 = markup.DBPoint('point1', redline.get("point1"))
        point2 = markup.DBPoint('point2', redline.get("point2"))
        redline_args.update(point1.getDBArgs())
        redline_args.update(point2.getDBArgs())

    elif redline_type == "RedlineText":
        position = markup.DBPoint('position', redline.get("position"))
        redline_args.update({"width": redline.get("size").get("x"),
                            "height": redline.get("size").get("y")})
        redline_args.update(position.getDBArgs())
    else:
        pass  # TODO: Error message

    return redline_args


def get_cutting_plane_args(cutting_plane):
    normal = cutting_plane.get("normal", {})
    cutting_plane_args = {
        "position": cutting_plane.get("d"),
        "normal_x": normal.get("x"),
        "normal_y": normal.get("y"),
        "normal_z": normal.get("z")
    }
    return cutting_plane_args


def create_freehand_points(redline, points):
    if util.check_access("threed_hoops_point", {}, "create"):
        for index, point in enumerate(points):
            args = make_freehand_point_args(index, point, redline.get("uniqueId"))
            markup.ViewerPoint.Create(**args)


def update_freehand_points(redline, points):
    viewer_points_by_position = {
        point.position: point 
            for point in markup.ViewerPoint.KeywordQuery(markup_object_id=redline.get("uniqueId"))
        }

    for index, point in enumerate(points):
        if index in viewer_points_by_position:
            args = make_freehand_point_args(index, point, redline.get("uniqueId"))
            markup.ViewerPoint.Update(viewer_points_by_position[index], **args)


def make_freehand_point_args(position, point, redline_id):
    return {
        "position": str(position),
        "x": point.get('x'),
        "y": point.get('y'),
        "z": point.get('z'),
        "markup_object_id": redline_id,
        }


def create_redline(redline, view_object_id):
    redline_type = get_shortened_redlining_type(redline)
    redline_args = get_redline_args(redline, redline_type, True)
    redline_args.update({"view_object_id": view_object_id})

    granted = util.check_access("threed_hoops_redline",
                                {key: str(value)  # don't ask
                                 for key, value in redline_args.items()},
                                "create")

    if granted and redline_type == "RedlineCircle":
        markup.RedlineCircle.Create(**redline_args)
    elif granted and redline_type == "RedlineRectangle":
        markup.RedlineRectangle.Create(**redline_args)
    elif granted and (redline_type == "RedlinePolyline"):
        markup.RedlineFreehand.Create(**redline_args)
        create_freehand_points(redline, redline.get("points"))
    elif granted and redline_type == "RedlineText":
        redline_obj = markup.RedlineText.Create(**redline_args)
        redline_obj.SetText("threed_hoops_redline_text_txt",
                            redline.get("text"))
    else:
        pass  # TODO: error message: no proper redline type found


def create_cutting_plane(plane, view_object_id):
    args = get_cutting_plane_args(plane.get("plane"))
    args.update({"view_object_id": view_object_id})

    granted = util.check_access("threed_hoops_cutting_plane",
                                {key: str(value)  # don't ask
                                 for key, value in args.items()},
                                "create")

    if granted:
        plane_obj = markup.CuttingPlane.Create(**args)

        geometry = plane.get("referenceGeometry")
        for point, position in zip(geometry, range(len(geometry))):
            markup.ViewerPoint.Create(
                markup_object_id=plane_obj.cdb_object_id,
                position=position,
                **point
            )


def create_view(data):
    if data.get("name") == "auto_save":
        return  # Views which are generated automatically on start of viewer will not be saved
    hwv_camera = data.get("camera")

    # Create camera object
    camera_args = get_camera_args(hwv_camera)

    granted = util.check_access("threed_hoops_camera",
                                {key: str(value)  # don't ask
                                 for key, value in camera_args.items()},
                                "create")
    if not granted:
        return

    camera = markup.Camera.Create(**camera_args)

    context_object_id = data.get("context_object_id")
    number = len(markup.View.KeywordQuery(context_object_id=context_object_id))

    if data.get("markup"):
        name = util.get_label("threed_hoops_redlining_no").format(number=number)
    else:
        name = util.get_label("threed_hoops_view_no").format(number=number)

    view_args = get_view_args(data)
    view_args.update({"name": name,
                      "cdb_object_id": data.get("uniqueId"),
                      "camera_object_id": camera.cdb_object_id})
    view_args.update(markup.View.MakeChangeControlAttributes())

    granted = util.check_access("threed_hoops_view",
                                {key: str(value)  # don't ask
                                 for key, value in view_args.items()},
                                "create")

    if granted:
        view = markup.View.Create(**view_args)

        # Create visibilities
        visibilities = {
            name: data.get(name) for name in ["visibilityExceptions", "hiddenNodes", "transparentNodes"]
        }
        visibilities_str = json.dumps(visibilities)
        util.text_write("threed_hoops_view_visibilities", ['view_object_id'], [view.cdb_object_id], visibilities_str)

        redlines = data.get("markup", [])
        for redline in redlines:
            create_redline(redline, view.cdb_object_id)

        cutting_data = data.get("cuttingData", {})
        for section in cutting_data.get("cuttingSections", []):
            for plane in section.get("planes", []):
                create_cutting_plane(plane, view.cdb_object_id)

        node_transforms = data.get("nodeTransforms", {})
        create_or_update_node_transforms(view, node_transforms)

        return {"name": view.name,
                "uniqueId": view.cdb_object_id}


def update_view(data, view):
    camera = view.ViewCamera if view else None

    if camera and camera.CheckAccess("save"):
        hwv_camera = data.get("camera")
        camera_args = get_camera_args(hwv_camera)
        camera.Update(**camera_args)

    if view and view.CheckAccess("save"):
        view_args = get_view_args(data)
        chctrl_args = markup.View.MakeChangeControlAttributes()
        del chctrl_args["cdb_cdate"]
        del chctrl_args["cdb_cpersno"]
        view_args.update(chctrl_args)
        if "name" in view_args and view_args.get("name") is None:
            view_args.pop("name")
        view.Update(**view_args)
        if data.get("visibilities") is not None:
            view.SetText("threed_hoops_view_txt", data.get("visibilities"))

    # FIXME: update cutting planes

    node_transforms = data.get("nodeTransforms", {})
    create_or_update_node_transforms(view, node_transforms)

    redlines_in_saved_view = data.get("markup", [])
    all_redlines_from_db = {rdl.cdb_object_id: rdl for rdl in markup.Redline.KeywordQuery(view_object_id=view.cdb_object_id)}

    def requires_update(rdl_db, rdl_view):
        className = rdl_view.get('className')
        values = []

        if className == RDL_POLYLINE:
            # Polylines do not use the regular positions of other redlinings.
            # The position is stored in individual points instead. To avoid
            # additional DB statements we assume the Polyline was updated.
            return True

        # Text uses the position paramters
        elif className == RDL_TEXT:
            pos = rdl_view["position"]
            size = rdl_view["size"]

            values = [
                (rdl_db.position_x, pos["x"]),
                (rdl_db.position_y, pos["y"]),
                (rdl_db.position_z, pos["z"]),
                (rdl_db.width, size["x"]),
                (rdl_db.height, size["y"])
            ]

        # Rectangles and Circles both use two points for their position.
        # Since both points change if you move the markup, we only check one point.
        elif className == RDL_RECTANGLE:
            pos = rdl_view["point1"]
            values = [
                (rdl_db.point1_x, pos["x"]),
                (rdl_db.point1_y, pos["y"]),
                (rdl_db.point1_z, pos["z"]), 
            ]

        elif className == RDL_CIRCLE:
            pos = rdl_view['centerPoint']
            values = [
                (rdl_db.center_x, pos["x"]),
                (rdl_db.center_y, pos["y"]),
                (rdl_db.center_z, pos["z"]), 
            ]

        # if any value differs an update is needed
        return any([v[0] != v[1] for v in values])


    for redline in redlines_in_saved_view:
        rdl = all_redlines_from_db.get(redline.get("uniqueId"), None)
        if rdl: 
            del all_redlines_from_db[redline.get("uniqueId")]
            if redline.get("className") == RDL_TEXT:
                rdl.SetText("threed_hoops_redline_text_txt", redline.get("text"))

            redline_type = get_shortened_redlining_type(redline)
            if requires_update(rdl, redline):
                if redline_type == "RedlinePolyline":
                    update_freehand_points(redline, redline.get("points"))
                else:
                    redline_args = get_redline_args(redline, redline_type, False)
                    rdl.Update(**redline_args)
        else:
            create_redline(redline, view.cdb_object_id)

    # if there are redlinings left in all_redlinings, those are no longer
    # present in the current view. Therefore, they are deleted from the database.
    # This method is called after every deletion, therefore only a maximum of one
    # redlining should be removed here
    for remaining in all_redlines_from_db.values():
        if remaining is not None:
            operations.operation(
                constants.kOperationDelete,
                remaining
            )

    # overwrite visibilities
    visibilities = {
        name: data.get(name) for name in ["visibilityExceptions", "hiddenNodes", "transparentNodes"]
    }
    visibilities_str = json.dumps(visibilities)
    util.text_write("threed_hoops_view_visibilities", ['view_object_id'], [view.cdb_object_id], visibilities_str)


def get_shortened_redlining_type(redlining):
    class_name = redlining.get("className")
    if "." in class_name:
        class_name = class_name.split(".")[-1]
    return class_name


def create_or_update_node_transforms(context_object, node_transforms):
    markup.NodeTransform.delete_for_context_object(context_object)

    for node_id, transform in node_transforms.items():
        kwargs = {
            "context_object_id": context_object.cdb_object_id,
            "node_id": node_id,
            "transform": json.dumps(transform)
        }
        granted = util.check_access("threed_hoops_view",
                                    the_keys=kwargs,
                                    access="create")
        if granted:
            markup.NodeTransform.Create(**kwargs)
