# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import math
import tempfile
import os
import json
import base64

from collections import OrderedDict

from webob.exc import HTTPNotFound

from cdb import constants
from cdb import util
from cdb import ue
from cdb import sqlapi
from cdb.objects.expressions import Forward
from cdb.objects.references import ReferenceMethods_1
from cdb.objects.core import Object
from cdb.objects.references import Reference_1
from cdb.objects.references import Reference_N
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation

from cs.platform.web.rest import get_collection_app

from cs.vp.items import Item


fMeasurement = Forward(__name__ + ".Measurement")
fFaceDistanceMeasurement = Forward(__name__ + ".FaceDistanceMeasurement")
fFaceAngleMeasurement = Forward(__name__ + ".FaceAngleMeasurement")
fCircleMeasurement = Forward(__name__ + ".CircleMeasurement")
fLinearMeasurement = Forward(__name__ + ".LinearMeasurement")
fPoint2PointMeasurement = Forward(__name__ + ".Point2PointMeasurement")
fRedline = Forward(__name__ + ".Redline")
fRedlineCircle = Forward(__name__ + ".RedlineCircle")
fRedlineRectangle = Forward(__name__ + ".RedlineRectangle")
fRedlineFreehand = Forward(__name__ + ".RedlineFreehand")
fRedlineText = Forward(__name__ + ".RedlineText")
fView = Forward(__name__ + ".View")
fNodeTransform = Forward(__name__ + ".NodeTransform")
fViewerPoint = Forward(__name__ + ".ViewerPoint")
fCamera = Forward(__name__ + ".Camera")
fViewerSnapshot = Forward(__name__ + ".ViewerSnapshot")
fCuttingPlane = Forward(__name__ + ".CuttingPlane")
fLayer = Forward(__name__ + ".Layer")
fLayerItem = Forward(__name__ + ".LayerItem")
fGeometryNode = Forward(__name__ + ".GeometryNode")

fCDB_File = Forward("cdb.objects.cdb_file.CDB_File")

NORMAL_VECTOR_LENGTH = 1

class CombinedDBAttribute(object):
    def __init__(self, attribute_name, coordinates=None, coordinate_names=None,
                 default_value=0.0):
        self.attribute_name = attribute_name
        self.coordinates = coordinates if coordinates is not None else []
        self.coordinates_names = coordinate_names if coordinate_names is not None else []
        self.default_value = str(default_value)
        if self.coordinates_names is not None:
            self._init_coordinates()

    @staticmethod
    def validate(coordinate):
        return coordinate

    def _init_coordinates(self):
        cnt = 0
        for coord_name in self.coordinates_names:
            if len(self.coordinates) > cnt:
                setattr(self, coord_name, self.validate(list(self.coordinates)[cnt]))
            else:
                setattr(self, coord_name, self.default_value)
            cnt += 1

    def getDBArgs(self):
        args = {}
        for coord_name in self.coordinates_names:
            args.update({"%s_%s" % (self.attribute_name, coord_name): getattr(self, coord_name, self.default_value)
                         })
        return args


class DBPoint(CombinedDBAttribute):
    @staticmethod
    def validate(coordinate):
        try:
            result = float(coordinate)
            if math.isnan(result):
                raise ValueError
            return result
        except ValueError:
            raise util.ErrorMessage('threed_wrong_parameter_nan')

    def __init__(self, attribute_name, coordinates=None, coordinate_names=None,
                 default_value=0.0):
        if coordinate_names is not None:
            super(DBPoint, self).__init__(attribute_name, coordinates, coordinate_names,
                                          default_value)
        elif isinstance(coordinates, dict):
            # allow only certain keys
            coordinates = {k: coordinates[k] for k in coordinates if k
                           in ['x', 'y', 'z']}
            super(DBPoint, self).__init__(attribute_name, coordinates.values(),
                                          coordinates.keys(), default_value)
        else:
            super(DBPoint, self).__init__(attribute_name, coordinates,
                                          ['x', 'y', 'z'], default_value)


class DBColor(CombinedDBAttribute):
    def __init__(self, attribute_name, coordinates=None, coordinate_names=None,
                 default_value=0):
        if coordinate_names is not None:
            super(DBColor, self).__init__(attribute_name, coordinates, coordinate_names,
                                          default_value)
        elif isinstance(coordinates, dict):
            # allow only certain keys
            coordinates = {k: coordinates[k] for k in coordinates if k
                           in ['r', 'g', 'b']}
            super(DBColor, self).__init__(attribute_name, coordinates.values(),
                                          coordinates.keys(), default_value)
        else:
            super(DBColor, self).__init__(attribute_name, coordinates, ['r', 'g', 'b'],
                                          default_value)


class Measurement(Object):
    __classname__ = "threed_hoops_measurement"
    __maps_to__ = "threed_hoops_measurement"

    def get_elink_data(self):
        args = {
            "measurements": json.loads(self.GetText("threed_hoops_measurement_txt")),
            "name": self.name,
            "uniqueId": self.cdb_object_id,
            "dirty": self.dirty
        }
        return args


class View(Object):
    __classname__ = "threed_hoops_view"
    __maps_to__ = "threed_hoops_view"

    ViewRedlines = Reference_N(fRedline, fRedline.view_object_id == fView.cdb_object_id)

    ViewCamera = Reference_1(fCamera,
                             fCamera.cdb_object_id == fView.camera_object_id)

    ViewCuttingPlanes = Reference_N(fCuttingPlane,
                                    fCuttingPlane.view_object_id == fView.cdb_object_id)

    SnapshotFile = Reference_1(fCDB_File, fCDB_File.cdbf_object_id == fView.cdb_object_id,
                               fCDB_File.cdbf_type == "THREED_SNAPSHOT")

    VisibilityExceptions = Reference_N(
        fGeometryNode,
        fGeometryNode.parent_object_id == fView.cdb_object_id,
        fGeometryNode.relationship == "visibilityExceptions"
    )

    HiddenNodes = Reference_N(
        fGeometryNode,
        fGeometryNode.parent_object_id == fView.cdb_object_id,
        fGeometryNode.relationship == "hiddenNodes"
    )

    TransparentNodes = Reference_N(
        fGeometryNode,
        fGeometryNode.parent_object_id == fView.cdb_object_id,
        fGeometryNode.relationship == "transparentNodes"
    )

    NodeTransforms = Reference_N(
        fNodeTransform,
        fNodeTransform.context_object_id == fView.cdb_object_id
    )

    def on_threed_cockpit_now(self, ctx):
        url = self.get_view_url()
        return ue.Url4Context(url)

    def get_view_url(self):
        part = Item.ByKeys(cdb_object_id=self.context_object_id)
        if part is not None:
            doc = part.get_3d_model_document()
            if doc is None:
                raise HTTPNotFound()

            return "/cs-threed-hoops-web-cockpit/%s?part=%s&view=%s" % (
                doc.cdb_object_id,
                self.context_object_id,
                self.cdb_object_id
            )
        else:
            return "/cs-threed-hoops-web-cockpit/%s?view=%s" % (
                self.context_object_id,
                self.cdb_object_id
            )

    def get_elink_data(self, request=None):
        def color_args(prefix):
            return {
                coord: getattr(self, prefix + coord)
                for coord in ["r", "g", "b"]
            }

        node_transforms = dict()
        for nodeTransform in self.NodeTransforms:
            node_transforms.update(nodeTransform.get_elink_data())

        visibilities_str = util.text_read("threed_hoops_view_visibilities", ['view_object_id'], [self.cdb_object_id])
        visibilities = json.loads(visibilities_str) if visibilities_str else {}

        normal_keys = ["normal_x", "normal_y", "normal_z"]
        ordered_cutting_sections = OrderedDict([(x, {"planes": []}) for x in (normal_keys + ["normal_face"])])

        for cutting_plane in self.ViewCuttingPlanes:
            section_key = "normal_face"

            # if one the the dimensions of cutting_plane_vector equals NORMAL_VECTOR_LENGTH exactly,
            # the cutting plane corresponds to the cutting section for that dimension
            cutting_plane_vector = [cutting_plane[key] for key in normal_keys]
            if NORMAL_VECTOR_LENGTH in cutting_plane_vector:
                section_key = normal_keys[cutting_plane_vector.index(NORMAL_VECTOR_LENGTH)]

            ordered_cutting_sections[section_key]["planes"].append(cutting_plane.get_elink_data())

        args = {"uniqueId": self.cdb_object_id,
                "camera": self.ViewCamera.get_elink_data(uniqueId=self.cdb_object_id),
                "name": self.name,
                "dirty": self.dirty,
                "explodeMagnitude": self.explosion_level,
                "lineVisibility": True if self.edge_visibility == 1 else False,
                "faceVisibility": True if self.face_visibility == 1 else False,
                "markup": [
                    redline.get_elink_data()
                    for redline in self.ViewRedlines
                ],
                "cuttingData": {
                    "cappingFaceColor": color_args("capping_face_color_"),
                    "cappingLineColor": color_args("capping_line_color_"),
                    "cappingGeometryVisibility": self.capping_geometry_visibility,
                    "pickable": True,
                    "cuttingSections": list(ordered_cutting_sections.values()),
                },
                "hiddenNodes": visibilities.get("hiddenNodes", []),
                "transparentNodes": visibilities.get("transparentNodes", []),
                "nodeTransforms": node_transforms,
                "context_object_id": self.context_object_id,
                "snapshot": self._get_snapshot_url(request),
                "defaultVisibility": True if self.default_visibility == 1 else False,
                "visibilityExceptions": visibilities.get("visibilityExceptions", []),
                "variant_object_id": self.variant_object_id,
                }
        return args

    def _get_snapshot_url(self, request):
        if request is None:
            return ""
        else:
            api_link = request.link(self, app=get_collection_app(request))
            return "%s/files/%s" % (api_link, self.SnapshotFile.cdb_object_id) \
                if self.SnapshotFile is not None else ""

    def delete_all(self):
        for redline in self.ViewRedlines:
            redline.delete_all()
        for cutting_plane in self.ViewCuttingPlanes:
            cutting_plane.Delete()

        # delete visibilities
        util.text_write("threed_hoops_view_visibilities", ['view_object_id'], [self.cdb_object_id], "")

        for node_trans in self.NodeTransforms:
            node_trans.Delete()
        if hasattr(self, "ViewCamera"):
            self.ViewCamera.Delete()
        long_text = self.GetText('threed_hoops_view_txt')
        if long_text and long_text != '':
            self.DeleteText('threed_hoops_view_txt')
        self.Delete()

    def save_snapshot(self, base64snapshot):
        if base64snapshot is None:
            return

        tmp_fh = tempfile.NamedTemporaryFile(delete=False)
        tmp_fh_name = tmp_fh.name

        tmp_fh.write(base64.b64decode(base64snapshot))
        tmp_fh.close()

        if self.SnapshotFile is not None:
            operation(constants.kOperationDelete, self.SnapshotFile)

        CDB_File.NewFromFile(self.cdb_object_id,
                             tmp_fh_name,
                             primary=True,
                             additional_args=dict(cdbf_type='THREED_SNAPSHOT',
                                                  cdbf_name='snapshot.png'))
        if os.path.isfile(tmp_fh_name):
            os.unlink(tmp_fh_name)


class NodeTransform(Object):
    __classname__ = "threed_hoops_node_transforms"
    __maps_to__ = "threed_hoops_node_transforms"

    def get_elink_data(self):
        return {
            self.node_id: json.loads(self.transform)
        }

    @staticmethod
    def delete_for_context_object(context_object):
        record_set = NodeTransform.KeywordQuery(context_object_id=context_object.cdb_object_id)
        can_delete = all([n.CheckAccess("delete") for n in record_set])
        if can_delete:
            record_set.Delete()


class Camera(Object):
    __classname__ = "threed_hoops_camera"
    __maps_to__ = "threed_hoops_camera"

    def get_elink_data(self, **kwargs):
        args = {"uniqueId": self.cdb_object_id,
                "height": self.height,
                "width": self.width,
                "className": self.name,
                "projection": self.projection,
                "nearLimit": self.near_limit,
                "position": {
                    'x': self.position_x,
                    'y': self.position_y,
                    'z': self.position_z},
                "target": {
                    'x': self.target_x,
                    'y': self.target_y,
                    'z': self.target_z},
                "up": {
                    'x': self.up_x,
                    'y': self.up_y,
                    'z': self.up_z},
                }
        args.update(kwargs)

        return args


class Redline(Object):
    __classname__ = "threed_hoops_redline"
    __maps_to__ = "threed_hoops_redline"

    def get_elink_data(self):
        args = {"uniqueId": self.cdb_object_id,
                "view_object_id": self.view_object_id}
        return args

    def delete_all(self):
        if isinstance(self, RedlineText):
            long_text = self.GetText('threed_hoops_redline_text_txt')
            if long_text:
                self.DeleteText('threed_hoops_redline_text_txt')
        elif isinstance(self, RedlineFreehand):
            for point in self.RedlineFreehandPoints:
                point.Delete()
        self.Delete()


class RedlineCircle(Redline):
    __classname__ = "threed_hoops_redline_circle"
    __match__ = (fRedlineCircle.cdb_classname == "threed_hoops_redline_circle")

    def get_elink_data(self):
        args = super(RedlineCircle, self).get_elink_data()
        args.update({"className": "Communicator.Markup.Redline.RedlineCircle",
                     "centerPoint": {
                         'x': self.center_x,
                         'y': self.center_y,
                         'z': self.center_z},
                     "radiusPoint": {
                         'x': self.point2_x,
                         'y': self.point2_y,
                         'z': self.point2_z}
                     })
        return args


class RedlineRectangle(Redline):
    __classname__ = "threed_hoops_redline_rectangle"
    __match__ = (fRedlineRectangle.cdb_classname == "threed_hoops_redline_rectangle")

    def get_elink_data(self):
        args = super(RedlineRectangle, self).get_elink_data()
        args.update({"className": "Communicator.Markup.Redline.RedlineRectangle",
                     "point1": {
                         'x': self.point1_x,
                         'y': self.point1_y,
                         'z': self.point1_z},
                     "point2": {
                         'x': self.point2_x,
                         'y': self.point2_y,
                         'z': self.point2_z}
                     })
        return args


class RedlineFreehand(Redline):
    __classname__ = "threed_hoops_redline_freehand"
    __match__ = (fRedlineFreehand.cdb_classname == "threed_hoops_redline_freehand")

    RedlineFreehandPoints = Reference_N(fViewerPoint,
                                        fViewerPoint.markup_object_id == fRedlineFreehand.cdb_object_id)

    def get_points(self):
        points = []
        for point in self.RedlineFreehandPoints:
            points.append({
                'x': point.x,
                'y': point.y,
                'z': point.z})
        return points

    def get_elink_data(self):
        args = super(RedlineFreehand, self).get_elink_data()
        args.update({"className": "Communicator.Markup.Redline.RedlinePolyline",
                     "points": self.get_points()})
        return args


class RedlineText(Redline):
    __classname__ = "threed_hoops_redline_text"
    __match__ = (fRedlineText.cdb_classname == "threed_hoops_redline_text")

    def get_elink_data(self):
        args = super(RedlineText, self).get_elink_data()
        args.update({"className": "Communicator.Markup.Redline.RedlineText",
                     "size": {
                         'x': self.width,
                         'y': self.height},
                     "position": {
                         'x': self.position_x,
                         'y': self.position_y,
                         'z': self.position_z},
                     "text": self.GetText("threed_hoops_redline_text_txt")
                     })
        return args


class CuttingPlane(Object):
    __classname__ = "threed_hoops_cutting_plane"
    __maps_to__ = "threed_hoops_cutting_plane"

    def get_elink_data(self):
        geometry = ViewerPoint\
            .KeywordQuery(markup_object_id=self.cdb_object_id, order_by="position")
        args = {
            "plane": {
                "d": self.position,
                "normal": {
                    "x": self.normal_x,
                    "y": self.normal_y,
                    "z": self.normal_z
                }
            },
            "referenceGeometry": [
                {
                    "x": point.x,
                    "y": point.y,
                    "z": point.z
                }
                for point in geometry
            ]
        }
        return args


class ViewerPoint(Object):
    __classname__ = "threed_hoops_point"
    __maps_to__ = "threed_hoops_point"

    def get_elink_data(self):
        return [self.x, self.y, self.z]


class ViewerSnapshot(Object):
    __classname__ = "threed_hoops_snapshot"
    __maps_to__ = "threed_hoops_snapshot"

    Image = ReferenceMethods_1(CDB_File, lambda self: self._get_image())

    def _get_image(self):
        files = CDB_File.KeywordQuery(cdbf_object_id=self.cdb_object_id,
                                      cdbf_primary=1)
        if len(files) > 0:
            return files[0]

    def get_elink_data(self):
        args = {"uniqueId": self.cdb_object_id,
                "name": self.name,
                "link": self.Image.MakeURL('CDB_View') if self.Image is not None else ""
                }
        return args

    @classmethod
    def on_create_document_from_snapshots_now(cls, ctx):
        from cs.threed.hoops import _checkout_and_store_files_in_wsp

        file_oids = [obj.cdb_object_id for obj in ctx.objects]
        wsp = _checkout_and_store_files_in_wsp(file_oids, ctx.dialog.title)

        # open workspace
        ctx.set_followUpOperation(constants.kOperationShowObject, op_object=wsp)


class GeometryNode(Object):
    __classname__ = "threed_hoops_geometry_node"
    __maps_to__ = "threed_hoops_geometry_node"


# -- utils --------------------------------------------------------------------

def invalidate_markup_views(doc):
    sqlapi.SQLupdate("threed_hoops_view SET dirty = '1' WHERE context_object_id = '%s'" % doc.cdb_object_id)

def invalidate_measurements(doc):
    sqlapi.SQLupdate("threed_hoops_measurement SET dirty = '1' WHERE context_object_id = '%s'" % doc.cdb_object_id)
