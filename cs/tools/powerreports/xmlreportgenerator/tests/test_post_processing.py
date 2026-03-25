import os
import shutil
import tempfile

from cdb import testcase
from cs.tools.powerreports.xmlreportgenerator import ExcelReportGenerator, tools

WORKING_DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(
    WORKING_DIR, "..", "..", "..", "..", "..", "tests", "test_files"
)


class PostProcessingTestCase(testcase.RollbackTestCase):
    def setUp(self):
        super(PostProcessingTestCase, self).setUp()
        self.test_dir = tempfile.mkdtemp()
        shutil.copy2(
            os.path.join(TEST_DIR, "VarStücklistenvergleich_cs.variants_de.xlsm"),
            self.test_dir,
        )
        shutil.copy2(
            os.path.join(TEST_DIR, "VarStücklistenvergleich_2_schema.xlsm"),
            self.test_dir,
        )

    def test_template_has_vba_signature(self):
        data = os.path.join(
            TEST_DIR,
            "Varianten-Stücklistenvergleich_Tue-06-Jun-2023-08-28-36_caddok.xlsm.cdbxml.zip",
        )
        template = os.path.join(
            self.test_dir, "VarStücklistenvergleich_cs.variants_de.xlsm"
        )

        ExcelReportGenerator(template, data).generate()
        excel_dir = tools.temporary_unzip_file(template)
        excel_xl_dir = os.path.join(excel_dir, "xl")
        excel_rel_dir = os.path.join(excel_xl_dir, "_rels")

        self.assertIn("vbaProject.bin.rels", os.listdir(excel_rel_dir))
        shutil.rmtree(excel_dir)

    def test_template_has_no_vba_signature(self):
        data = os.path.join(
            TEST_DIR,
            "Varianten-Stücklistenvergleich_Tue-06-Jun-2023-08-28-36_caddok.xlsm.cdbxml.zip",
        )
        template = os.path.join(self.test_dir, "VarStücklistenvergleich_2_schema.xlsm")

        ExcelReportGenerator(template, data).generate()
        excel_dir = tools.temporary_unzip_file(template)
        excel_xl_dir = os.path.join(excel_dir, "xl")
        excel_rel_dir = os.path.join(excel_xl_dir, "_rels")

        self.assertNotIn("vbaProject.bin.rels", os.listdir(excel_rel_dir))
        shutil.rmtree(excel_dir)

    def tearDown(self):
        super(PostProcessingTestCase, self).tearDown()
        shutil.rmtree(self.test_dir)
