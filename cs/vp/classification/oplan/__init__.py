#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# pylint: disable-msg=E1103,W0612
# CDB:Browse

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
from cs.documents import Document
from cs.shared.elink_plugins.picture_uploader import PictureUploader
from cs.vp import classification
from cs.vp.classification.oplan.sml import ELINK_OPLAN_TEMPLATE_NAME, Oplan
from cdb import elink
from cdb import misc
from cdb import CADDOK
from cdb import util
from cdbwrapc import OperationContext

__all__ = ["provide_file"]

_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}


def provide_file(f, location):
    """
    Checks out the file to `location` if it is not there.
    Uses a temporary file during the checkout so it ist
    suitable for the SML-Object-Plan where different
    processes might try to checkout a file at the
    same time to the same location.

    :param f:         an instance of cdb.objects.cdb_file.CDB_File
    :param location:  an instance of unicode
    """
    assert isinstance(location, str)

    if location and not os.path.exists(location):
        import tempfile
        try:
            # Use a temporary name for the file to avoid
            # conflicts between the different processes
            ntf = tempfile.NamedTemporaryFile(dir=os.path.dirname(location),
                                              delete=False)
            ntf.close()
            try:
                f.checkout_file(ntf.name)
                os.rename(ntf.name, location)
            except Exception as exc:
                misc.cdblogv(misc.kLogErr, 0, "Failed to checkout SML-File:%s to %s\n%s" % (f.cdb_object_id, f.name, str(exc)))
                location = ""
        except Exception as exc:
            # Rename might fail if an other process had the same idea
            # so if the file is there - its ok
            if not os.path.exists(location):
                misc.cdblogv(misc.kLogErr, 0, "Failed to checkout SML-File:%s\n%s" % (location, str(exc)))
                location = ""
    return location


class Picture(elink.BinaryResource):
    def _get_image_path(self, f):
        """
        Returns the directory where the images are stored.
        Creates the directory if necessary.
        """
        result = os.path.join(CADDOK.TMPDIR, "sml_icons")
        if not os.path.exists(result):
            os.mkdir(result)
        return os.path.join(result, f.cdbf_blob_id + os.path.splitext(f.cdbf_name)[1])

    def render(self):
        znr = self.request.form_data["z_nummer"]
        zix = self.request.form_data["z_index"]
        doc = Document.ByKeys(znr, zix)
        if not doc:
            msg = "Unknown document '%(z_nummer)s'-'%(z_index)s'" % (self.request.form_data)
            misc.cdblogv(misc.kLogErr, 0, msg)
            self.content_type("text/plain")
            self.write(msg.encode("utf8"))
        else:
            for f in doc.getPrimaryFiles():
                fn = provide_file(f, self._get_image_path(f))
                if fn:
                    _, ext = os.path.splitext(fn)
                    if ext in _IMAGE_TYPES:
                        with open(fn, "rb") as f:
                            data = f.read()
                        self.content_type(_IMAGE_TYPES[ext])
                        self.write(data)
                    else:
                        self.content_type("text/plain")
                        self.write("%s" % ext)


class PsetPage(elink.Template):
    __template__ = "psetinfo.html"

    def render(self, context):
        psetid = self.request.form_data.get("pset_id", "")
        ps = classification.PropertySet.ByKeys(psetid)
        if ps:
            ps.Reload()

            docs = ps.DocumentReferences.Query(
                classification.PropSetDocumentReference.purpose == "Weitere Dokumente",
                order_by=classification.PropSetDocumentReference.position
            )
            images = ps.DocumentReferences.Query(
                classification.PropSetDocumentReference.purpose.one_of("Bild in Maske/Objektplan",
                                                                       "Bild im Objektplan"),
                order_by=classification.PropSetDocumentReference.position
            )

            content = {
                'base_uri': self.request.base_uri +
                self.request.script_name + ELINK_OPLAN_TEMPLATE_NAME,
                'current': ps,
                'docs': docs,
                'get_preview_img': PictureUploader.get_preview_img,
                'images': images
            }
            return content


class CgroupPage(elink.Template):
    __template__ = "cgroupinfo.html"

    def render(self, context):
        cgroupid = self.request.form_data.get("cgroup_id", "")
        cgroup = classification.ClassificationCategory.ByKeys(cgroupid)
        if cgroup:
            cgroup.Reload()
            stmt = classification.CGDocumentReference.purpose.one_of("Bild in Maske/Objektplan",
                                                                     "Bild im Objektplan")
            content = {
                'base_uri': self.request.base_uri + self.request.script_name + ELINK_OPLAN_TEMPLATE_NAME,
                'current': cgroup,
                'docs': cgroup.DocumentReferences.Query(classification.CGDocumentReference.purpose == "Weitere Dokumente"),
                'get_preview_img': PictureUploader.get_preview_img,
                'images': cgroup.DocumentReferences.Query(stmt)
            }
            misc.cdblogv(misc.kLogMsg, 0, "%s images" % len(content['images']))
            return content


class MaskImages(elink.Template):
    """
    Class to handle SML mask images
    """
    __template__ = "maskimages.html"

    def render(self, context):
        psetid = self.request.form_data.get("pset_id", "")
        if not psetid:
            opContext = OperationContext(self.request.form_data["opContextID"])
            psetid = opContext.getArgumentValueByName('teile_stamm.sachgruppe')
        ps = classification.PropertySet.ByKeys(psetid)
        if ps:
            ps.Reload()
            context.images = []
            ps_imagesrefs = ps.DocumentReferences.Query(
                classification.PropSetDocumentReference.purpose.one_of("Bild in Maske/Objektplan",
                                                                       "Bild in Maske"),
                order_by=classification.PropSetDocumentReference.position
            )
            for ps_imagesref in ps_imagesrefs:
                if ps_imagesref.Document:
                    context.images.append(ps_imagesref)
        count_images = 1
        if context.images:
            count_images = len(context.images)
        context.max_in_row = "var max_in_row = 3"
        if count_images > 0 and count_images < 3:
            context.max_in_row = "var max_in_row = %d" % count_images
        # Proportionale Groessenaenderung
        # Das Skript wird mit dem Context übergeben, da TAL einzelne Zeichen escaped
        # hier das '>'-Zeichen
        context.jsscript = '''
          $.fn.resize=function(maxXSize, maxYSize)
          {
              if (maxXSize == undefined)
              {
                maxXSize = 200;
              }
              if (maxYSize == undefined)
              {
                maxYSize = 170;
              }
              var calcX=maxXSize,calcY=maxYSize;
              $(this).each(function()
              {
                var y=$(this).height(),x=$(this).width();
                if(x/y > maxXSize/maxYSize)
                {
                  $(this).css({width:calcX});
                }
                else
                {
                  $(this).css({height:calcY});
                }
              }
          )}; '''
        context.get_preview_img = PictureUploader.get_preview_img


@elink.using_template_engine("chameleon")
class OplanApp(elink.Application):
    def __init__(self):
        super(OplanApp, self).__init__(util.get_label("cdbsml_oplan"))
        self.add("pset", PsetPage())
        self.add("cgroup", CgroupPage())
        self.add("pic", Picture())
        self.add("maskimages", MaskImages())
        self.add(ELINK_OPLAN_TEMPLATE_NAME, Oplan())

    @classmethod
    def on_cdbsml_oplan_now(cls, ctx):
        return cls.OpenModule()


# lazy instantiation
_APP = None


def _getapp():
    global _APP
    if _APP is None:
        _APP = OplanApp()
    return _APP


def handle_request(req):
    """Shortcut to the app"""
    return _getapp().handle_request(req)
