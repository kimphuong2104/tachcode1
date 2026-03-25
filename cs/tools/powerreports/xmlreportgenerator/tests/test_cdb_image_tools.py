import os
import urllib

import openpyxl as xl
import openpyxl.drawing.image
from mock import patch
from PIL import Image

from cdb import testcase
from cs.tools.powerreports.xmlreportgenerator import cdb_image_tools, tools

WORKING_DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(
    WORKING_DIR, "..", "..", "..", "..", "..", "tests", "test_files"
)
IMAGE_1 = "cdb://image/file:///profilbild_1.jpg"
IMAGE_PATH_WITH_BASE_NAME = os.path.join(TEST_DIR, "ReportPersons_data.xlsx")
SHEET = xl.load_workbook(
    os.path.join(TEST_DIR, "ReportPersons_template.xlsx")
).worksheets[0]
IMAGE = cdb_image_tools.get_image_to_add(IMAGE_1, IMAGE_PATH_WITH_BASE_NAME)
TEMP_IMAGE = tools.sheet_images(SHEET)[0]


class MyTestCase(testcase.RollbackTestCase):
    def test_get_image_to_add(self):
        expected_image_1 = os.path.join(
            TEST_DIR, "ReportPersons_data.xlsx.profilbild_1.jpg"
        )
        expected_image_2 = os.path.join(
            TEST_DIR, "ReportPersons_data.xlsx.profilbild_2.jpg"
        )

        expected_image_1 = Image.open(expected_image_1)
        expected_image_2 = Image.open(expected_image_2)

        expected_image_1_w = expected_image_1.width
        expected_image_1_h = expected_image_1.height
        expected_image_2_w = expected_image_2.width
        expected_image_2_h = expected_image_2.height

        expected_image_1.close()
        expected_image_2.close()

        image = cdb_image_tools.get_image_to_add(IMAGE_1, IMAGE_PATH_WITH_BASE_NAME)

        self.assertEqual(image.width, expected_image_1_w)
        self.assertEqual(image.height, expected_image_1_h)
        self.assertNotEqual(image.width, expected_image_2_w)
        self.assertNotEqual(image.height, expected_image_2_h)

    def test_change_image(self):
        old_image_width = IMAGE.width
        old_image_height = IMAGE.height

        keep_height, keep_width = False, True
        min_border_height = 0
        init_row_height = SHEET.row_dimensions[2].height

        cdb_image_tools.change_image_get_row_height(
            IMAGE,
            TEMP_IMAGE,
            keep_height,
            keep_width,
            min_border_height,
            init_row_height,
        )
        new_image_width = IMAGE.width
        new_image_height = IMAGE.height

        self.assertNotEqual(old_image_width, new_image_width)
        self.assertNotEqual(old_image_height, new_image_height)

    def test_get_row_height_width_true(self):
        keep_height, keep_width = False, True
        min_border_height = 0
        init_row_height = SHEET.row_dimensions[2].height

        new_row_height = cdb_image_tools.change_image_get_row_height(
            IMAGE,
            TEMP_IMAGE,
            keep_height,
            keep_width,
            min_border_height,
            init_row_height,
        )

        self.assertNotEqual(init_row_height, new_row_height)

    def test_get_row_height_width_false(self):
        keep_height, keep_width = True, False
        min_border_height = 0
        init_row_height = SHEET.row_dimensions[2].height

        new_row_height = cdb_image_tools.change_image_get_row_height(
            IMAGE,
            TEMP_IMAGE,
            keep_height,
            keep_width,
            min_border_height,
            init_row_height,
        )
        self.assertEqual(init_row_height, new_row_height)

    def test_get_row_height_landscape(self):
        keep_height, keep_width = True, True
        min_border_height = 0
        init_row_height = SHEET.row_dimensions[2].height

        new_row_height = cdb_image_tools.change_image_get_row_height(
            IMAGE,
            TEMP_IMAGE,
            keep_height,
            keep_width,
            min_border_height,
            init_row_height,
        )

        self.assertNotEqual(init_row_height, new_row_height)

    def test_get_row_height_portrait(self):
        table_cell_value_image_2 = "cdb://image/file:///profilbild_2.jpg"
        image = cdb_image_tools.get_image_to_add(
            table_cell_value_image_2, IMAGE_PATH_WITH_BASE_NAME
        )
        keep_height, keep_width = True, True
        min_border_height = 0
        init_row_height = SHEET.row_dimensions[2].height

        new_row_height = cdb_image_tools.change_image_get_row_height(
            image,
            TEMP_IMAGE,
            keep_height,
            keep_width,
            min_border_height,
            init_row_height,
        )

        self.assertEqual(init_row_height, new_row_height)

    def test_get_anchor_attr(self):
        center_width, center_height = False, False
        row_height = 10

        from_col, _, from_row, _ = cdb_image_tools.get_anchor_attr(
            IMAGE, TEMP_IMAGE, center_width, center_height, row_height
        )
        self.assertEqual(from_col, 0)
        self.assertEqual(from_row, 0)

    def test_http_image(self):
        cdbxml_value = (
            "cdb://image/localhost:8080/ReportPersons_data.xlsx.profilbild_1.jpg"
            " cdb:hyperlink:openfile"
        )
        test_image = os.path.join(TEST_DIR, "ReportPersons_data.xlsx.profilbild_1.jpg")
        with patch.object(
            urllib.request, "urlretrieve", return_value=(test_image, None)
        ):
            image = cdb_image_tools.get_image_to_add(
                cdbxml_value, IMAGE_PATH_WITH_BASE_NAME
            )
        self.assertEqual(type(image), openpyxl.drawing.image.Image)
        self.assertEqual(image.height, Image.open(test_image).height)
