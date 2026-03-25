import logging
import math
import os.path
import urllib
from urllib.parse import urlparse

import openpyxl as xl
from openpyxl.utils.units import (
    EMU_to_pixels,
    pixels_to_EMU,
    pixels_to_points,
    points_to_pixels,
)

from cs.tools.powerreports.xmlreportgenerator import tools

LOG = logging.getLogger(__name__)
FILE_PREFIX = "file:///"
CDB_PREFIX = "cdb:"
CDB_IMAGE_PREFIX = "%s//image/" % CDB_PREFIX


def get_image_attribute_values(temp_image_description):
    keep_width = True
    keep_height = False
    min_border_height = 0
    center_width = False
    center_height = False

    if temp_image_description and CDB_PREFIX in temp_image_description:
        _, attributes = temp_image_description.split(":")
        for image_attribute in attributes.split(","):
            attribute, attribute_value = image_attribute.split("=")
            if attribute == "KeepHeight" and attribute_value == "1":
                keep_height = True
            elif attribute == "KeepWidth" and attribute_value == "0":
                keep_width = False
            elif attribute == "CenterWidth" and attribute_value == "1":
                center_width = True
            elif attribute == "CenterHeight" and attribute_value == "1":
                center_height = True
            elif attribute == "MinBorderHeight":
                min_border_height = attribute_value
    else:
        LOG.warning("Template image has no alternative text.")

    return keep_width, keep_height, min_border_height, center_width, center_height


def get_image_to_add(table_cell_value, image_path_and_name):
    """
    Returns image, that has to be added in cell

    :param string table_cell_value: value of cell where image has to be added
    :param string image_path_and_name: path (temp file) where image is an first part
                                       of full image name in cdbxml zip

    Remove fixed prefix cdb://image/
    fname: relative path ; uri path ; http address

    If fname starts with 'file:///' it is relative oder uri path (1) otherwise fname is http address (2)
    (1) Get image name using removing prefix 'file:///'
        Check if image_name has ':/'
        If not: image name is relative path in cdbxml zip 'profilbild_1.jpg'
        Using image_path_and_name tempfile/TestReportPersons_Tue-15-Nov-2022-15-43-56_caddok.xlsx
        to get image from zip
        Else: is uri path like 'Z:/' or 'C:/'
    (2) Download image form http address (use any as desired)

    :return image
    """
    fname = table_cell_value.removeprefix(CDB_IMAGE_PREFIX)
    if FILE_PREFIX in fname:
        image_name = fname.removeprefix(FILE_PREFIX)
        if not os.path.isabs(image_name):
            image_path = image_path_and_name + "." + image_name
            image = xl.drawing.image.Image(image_path)
        else:
            image = xl.drawing.image.Image(image_name)
    else:
        image_name = os.path.basename(urlparse(fname).path)
        image_path, _ = urllib.request.urlretrieve(  # nosec
            fname, os.path.join(os.path.dirname(image_path_and_name), image_name)
        )
        image = xl.drawing.image.Image(image_path)

    return image


def change_image_get_row_height(
    image, temp_image, keep_height, keep_width, min_border_height, row_height
):
    """
    Changes images sizes
    Return row_height (has to be changed in 2 cases)

    :param image: cdb_image
    :param temp_image: template image
    :param bool keep_height: keep height from temp_image for image true/false
    :param bool keep_width: keep width from temp_image for image true/false
    :param int min_border_height: length of border (top/down) from row lines to image
                                  (row_height has to be changed)
    :param int row_height: current height of selected row

    Using anchors of temp_image in cell
    Getting actual height and width of temp_image INSIDE the cell (not original size) and convert to pixel
    Depending on keep_height and keep_width change set image = temp_image width / height
    Change height/width with calculated ratio to guarantee correct aspect ratio of image in cell

    If keep_width only true, change row_height to fit height of image (otherwise image is in other row)
    same if image is in landscape format and keep_height and keep_width are both true

    image width and height are changed
    :return int row_height
    """
    e2p = EMU_to_pixels
    temp_image_anchor_from = tools.anchor_from(temp_image)
    temp_image_anchor_to = temp_image.anchor.to

    temp_image_width = e2p(temp_image_anchor_to.colOff - temp_image_anchor_from.colOff)
    temp_image_height = e2p(temp_image_anchor_to.rowOff - temp_image_anchor_from.rowOff)
    img_width, img_height = get_new_image_h_w(
        image, temp_image_height, temp_image_width, keep_height, keep_width
    )

    if min_border_height != 0:
        row_height = pixels_to_points(img_height + (int(min_border_height) + 1) * 2)
    if keep_height and keep_width:
        if image.height < image.width and points_to_pixels(
            row_height
        ) < points_to_pixels(img_height):
            # if row is to small for image height and keep_width
            # has to change row height to height, otherwise image is part of next row
            row_height = pixels_to_points(img_height)
    elif keep_width and not keep_height:
        row_height = pixels_to_points(img_height)

    image.width = img_width
    image.height = img_height

    return row_height


def change_width(image, img_height):
    ratio = image.height / img_height
    img_width = image.width / ratio

    return img_width


def change_height(image, img_width):
    ratio = image.width / img_width
    img_height = image.height / ratio

    return img_height


def get_new_image_h_w(
    image, temp_image_height, temp_image_width, keep_height, keep_width
):
    if keep_height and keep_width:
        if image.height >= image.width:
            img_height = temp_image_height
            img_width = change_width(image, img_height)
        else:
            img_width = temp_image_width
            img_height = change_height(image, img_width)
    elif keep_height:
        img_height = temp_image_height
        img_width = change_width(image, img_height)
    elif keep_width:
        img_width = temp_image_width
        img_height = change_height(image, img_width)

    return img_width, img_height


def get_anchor_attr(image, temp_image, center_width, center_height, row_height):
    """
    Returns Anchor values/attributes to set image at right position in cell
    :param image: cdb_image
    :param temp_image: template image
    :param bool center_width: place image in center of column(width) true/false
    :param bool center_height: place image in center of row(height) true/false
    :param int row_height: current height of selected row

    Using anchors of temp_image in cell
    Getting column middle with from and to colOff - because width of column (from sheet)
    is based on many factors
    Getting image width and height (half for position with middle) convert pixels to
    EMU (unit of anchors)

    If center_height/center_width false set from_col/from_row = 0 and to_ attr is width/height
    For center_height = true use middle of row from row_height - row height in sheet is only in points

    :return int from_col: left offset of column x
    :return int to_col: right offset of column x
    :return int from_row: top offset of row x
    :return int to_row: bottom offset of row x
    """
    p2e = pixels_to_EMU
    from_col, to_col, from_row, to_row = None, None, None, None

    temp_image_anchor_from = tools.anchor_from(temp_image)
    temp_image_anchor_to = temp_image.anchor.to

    column_middle = (temp_image_anchor_from.colOff + temp_image_anchor_to.colOff) / 2
    row_middle = p2e(points_to_pixels(row_height)) / 2

    img_width_emu = p2e(image.width) / 2
    img_height_emu = p2e(image.height) / 2

    if center_width:
        from_col = math.ceil(column_middle - img_width_emu)
        to_col = math.floor(column_middle + img_width_emu)
    elif not center_width:
        from_col = 0
        to_col = img_width_emu * 2
    if center_height:
        from_row = math.ceil(row_middle - img_height_emu)
        to_row = math.floor(row_middle + img_height_emu)
    elif not center_height:
        from_row = 0
        to_row = img_height_emu * 2

    return from_col, to_col, from_row, to_row
