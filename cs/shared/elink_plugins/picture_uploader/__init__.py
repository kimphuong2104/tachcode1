#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
CDB eLink plug-in "picture uploader".
====================================

Usage:
    Follow these steps to embed picture uploader into the application:
    1. import the javascript and css resources in page template:

        <link href="${options.plugins}picture_uploader/picture_uploader.css"
              rel="stylesheet" type="text/css" />
        <script src="${options.plugins}picture_uploader/picture_uploader.js"
                type="text/javascript"></script>

    2. add following code into page template everywhere the preview image needs
       be displayed:

        <tal:previewImage
            metal:use-macro="global_plugins['picture_uploader'].macros['preview_image']"
            define="prev_img get_preview_img(obj);
                    img_url '';
                    btn_title string:Upload"/>

       The parameter `prev_img` must be given as cdb_object_id of a cdb file
       object, which can be displayed as preview image. In the example above
       it will be returned from the function get_preview_img(), which is
       implemented in this plug-in, see step#5 below for usage. The `btn_title`
       would be displayed as title of the upload button, it is optional. If an
       image should be displayed but not via preview mechanism, the complete
       url of the image should be given using parameter `img_url`, and the
       `prev_img` should not be set at the same time, e.g. to display a cdb
       object icon:

        <tal:previewImage
            metal:use-macro="global_plugins['picture_uploader'].macros['preview_image']"
            define="prev_img '';
                    img_url string:${obj.GetObjectIcon()};
                    btn_title string:Upload"/>

       There are also 2 more parameters `img_link` and `img_link_target`, which
       can be used to add a hyperlink to the image:

        <tal:previewImage
            metal:use-macro="global_plugins['picture_uploader'].macros['preview_image']"
            define="prev_img get_preview_img(obj);
                    img_url '';
                    btn_title string:Upload;
                    img_link obj.MakeURL();
                    img_link_target string:_blank"/>

       The `img_link_target` will be set as `target` attribute of a <a>-tag. In
       this example the hyperlink generated through "obj.MakeURL()" can be
       opened in a new window("_blank").

    3. add the upload form once into the page template, e.g.:

        <tal:modalupload
            metal:use-macro="global_plugins['picture_uploader'].macros['upload_modal']"
            define="modal_title string:Picture Upload;
                    modal_desc string:Upload description;
                    action_url ''">
          <metal:formHidden fill-slot="input_hidden">
            <input type="hidden" name="project_id" value=""/>
          </metal:formHidden>
        </tal:modalupload>

       The Parameter `modal_title` will be shown as title of the upload window,
       and `modal_desc` as the description text over the upload field.
       The uploading would be done by submitting a form. If `action_url` is
       given, the form data would be submit to that url, otherwise to the
       current page url. The form data must be processed there, see step#6
       below.

    4. active the plug-in in javascript, e.g.:

        var pictureUploader = new cdbElinkPictureUploader();
        // The data preparing function, it must be implemented to set the
        // required variable(s), e.g. the id of the object which the picture
        // should be attached to.
        pictureUploader.prepareModal = function(event) {
          var target = $(event.currentTarget);
          // for project image, looks up project id
          var projectId = target.closest(
              '.projecttiles, div.projectdetail.main-area.kosmodrom'
            ).data('elink-cdb_project_id');
          if(projectId !== '' && (typeof projectId !== 'undefined')){
              this.setWindowTitle(projectId);
              // fills project id in the form to be submitted
              this.popupWindow.find('input[name=project_id]').val(projectId);
          }
        //Tells cdb.elink to run uploader.
        cdb.elink.addApplication('cdb.elink.pictureuploader', pictureUploader);

    5. expose the `get_preview_img` function in powerscript(usually the template
       class) to page template if needed, e.g.:

        from cs.shared.elink_plugins.picture_uploader import PictureUploader
        ...
        class MyTemplate(elink.Template):
            def render(self, context):
                ...
                return {
                        ...
                        "get_preview_img": PictureUploader.get_preview_img,
                        ...
                        }

    6. process the form data in powerscript(usually the template class), e.g.:

        from cs.shared.elink_plugins.picture_uploader import PictureUploader
        ...
        class MyTemplate(elink.Template):

            def set_project_image(self):
                project_obj = Project.ByKeys(self.request.form_data["project_id"])
                # Using preview image mechanism(save picture as CDBFile to object).
                return PictureUploader.set_image(request,
                                                 project_obj,
                                                 max_size=220)

            def render(self, context):
                init_msg = []
                if self.request.upstreams:
                    init_msg = self.set_project_image()
                ...

       If the `max_size` is given in pixels and greater than 0, the image will
       be resized to the given size if it is originally over that.

       If the import failed, the error message would be returned from the
       `set_image` function. The caller should display the message to the user.
       If the standard page layout is used, the message can be assigend to the
       variable `elink_startup_cdb_messages`, which will be displayed
       automatically after the page reloaded, e.g.:

            def render(self, context):
                init_msg = []
                if self.request.upstreams:
                    init_msg = self.set_project_image()
                ...
                return {...
                        elink_startup_cdb_messages": init_msg,
                        ...}

    This plug-in provides almost no visual styling for the components. The
    individual styling of the preview image display and the upload form should
    be defined by the application itself. Especially the
    `div.elink-picture-preview` should be set to proper width and height.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb.objects.cdb_file import CDB_File
from cdb import elink
from cdb import util
from cdb.kernel import getFileTypesByFilename


__all__ = ["PictureUploader"]


class PictureUploader:
    @staticmethod
    def _resize_image(max_size, upstream, filetype):
        from PIL import Image
        img = Image.open("%s" % upstream)
        width, height = img.size
        if max_size > 0 and (width > max_size or height > max_size):
            if width > height:
                new_width = int(max_size)
                new_height = int((float(max_size) / float(width)) * float(height))
            else:
                new_width = int((float(max_size) / float(height)) * float(width))
                new_height = int(max_size)
            img = img.resize((new_width, new_height), Image.BICUBIC)
            upstream = upstream + "." + filetype
            img.save(upstream)
        return upstream

    @staticmethod
    def _check_image_type(filename):
        from cdb.objects.common import WithImage

        if not WithImage.isImage(filename):
            raise util.ErrorMessage("cdb_image_type")
        return True

    @staticmethod
    def set_image(request, obj, max_size=0, **kwargs):
        """
        Sets the preview image to the cdb object.
        If a file with same file type exists,
        just the new file content will be checked in, otherwise a new file
        will be created. It keeps only one primary file, which is lately
        changed.
        If the operation fails , the error message would be returned.
        """
        errmsg = []
        if hasattr(obj, "cdb_object_id") and \
           PictureUploader._check_image_type(request.upstreams[0]["filename"]):
            filename = request.upstreams[0]["filename"]
            filetype = os.path.splitext(filename)[1]
            upstream = PictureUploader._resize_image(
                        max_size,
                        request.upstreams[0]["id"],
                        filetype)
            filetype = filetype.upper().lstrip(".")

            if len(getFileTypesByFilename(filename)) == 0:
                error = "%s: %s" % (util.Labels()["cdb_import_image"], util.CDBMsg(util.CDBMsg.kFatal,
                                                                                   "cdbft_err_no_ft"))
                errmsg.append((error, "alert-error"))
            else:
                cr_args = {"cdbf_type": filetype,
                           "cdbf_name": filename}
                cr_args.update(**kwargs)
                # Keeps only ONE primary picture file
                target = None
                for cdbfile in CDB_File.GetFilesForObject(obj.cdb_object_id):
                    if cdbfile.cdbf_type.upper() == filetype:
                        target = cdbfile
                    if cdbfile.isPrimary():
                        cdbfile.cdbf_primary = 0
                try:
                    if target:
                        target.checkin_file(upstream)
                        target.cdbf_primary = 1
                    else:
                        CDB_File.NewFromFile(obj.cdb_object_id,
                                             upstream,
                                             primary=True,
                                             additional_args=cr_args)
                except Exception as e:
                    estr = "%s: %s" % (util.Labels()["cdb_import_image"], e)
                    errmsg.append((estr, "alert-error"))
                os.remove(os.path.join(upstream))
        return errmsg

    @staticmethod
    def get_preview_img(obj):
        """
        Returns the first primary file to preview.
        """
        if obj:
            files = CDB_File.GetFilesForObject(obj.GetObjectID(), primary_only=True)
            if files:
                return files[0].cdb_object_id
        return u""


class HelperApp(elink.Application):
    """
    Helper Application to provide a JSON API to check the file extensions.
    """
    def setup(self):
        self.addJSON(PictureUploader._check_image_type, "check_file_extension")


# lazy instantiation
_APP = None


def _getapp():
    global _APP
    if _APP is None:
        _APP = HelperApp()
    return _APP


def handle_request(req):
    """Shortcut to the app"""
    return _getapp().handle_request(req)
