# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import zipfile

from cdb import testcase
from cs.tools.powerreports.xmlreportgenerator.handle_xml import XMLFile

WORKING_DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(
    WORKING_DIR, "..", "..", "..", "..", "..", "tests", "test_files"
)


class XMLFileTestCase(testcase.RollbackTestCase):
    def setUp(self):
        super(XMLFileTestCase, self).setUp()
        self.excel_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(
            os.path.join(TEST_DIR, "Anforderungsübersicht_template.xlsx")
        ) as excel_file:
            excel_file.extractall(self.excel_dir)
        self.cdbxml_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(
            os.path.join(TEST_DIR, "Anforderungsübersicht_data.xlsx.cdbxml.zip")
        ) as excel_file:
            excel_file.extractall(self.cdbxml_dir)

    def test_table_with_one_column(self):
        xml_file = os.path.join(self.excel_dir, "xl", "tables", "table2.xml")
        xml = XMLFile(xml_file)
        table_xml = xml.get_in_xml_with_keylist(
            ["table", "tableColumns", "tableColumn"]
        )
        name = ""

        self.assertEqual(len(table_xml), 1)
        self.assertIs(type(table_xml), list)

        for value in table_xml:
            name = value["name"]

        self.assertEqual(name, "Bewertungen")

    def test_table_with_one_column_without_handling(self):
        xml_file = os.path.join(self.excel_dir, "xl", "tables", "table2.xml")
        converted_xml = XMLFile(xml_file)
        table_xml_data = converted_xml.get_single_key("table")
        name = ""
        value_list = table_xml_data["tableColumns"]["tableColumn"]

        for value in value_list:
            with self.assertRaises(TypeError):
                name = value["name"]

        self.assertNotEqual(name, "Bewertungen")

    def test_table_with_more_columns(self):
        xml_file = os.path.join(self.excel_dir, "xl", "tables", "table1.xml")
        converted_xml = XMLFile(xml_file)
        table_xml = converted_xml.get_in_xml_with_keylist(
            ["table", "tableColumns", "tableColumn"]
        )

        self.assertNotEqual(len(table_xml), 1)
        self.assertIs(type(table_xml), list)

        second_column = table_xml[1]
        self.assertEqual(second_column["name"], "Beschreibung")

    def test_table_single_cells(self):
        xml_file = os.path.join(self.excel_dir, "xl", "tables", "tableSingleCells1.xml")
        converted_xml = XMLFile(xml_file)
        single_cell_xml = converted_xml.get_in_xml_with_keylist(
            ["singleXmlCells", "singleXmlCell"]
        )
        expected_second_single_cell = {"D4"}

        number = 0
        cell_values = {}
        for value_dict in single_cell_xml:
            address_second_single_cell = value_dict["r"]
            cell_values[number] = {address_second_single_cell}
            number += 1

        second_dict = cell_values[2]
        self.assertEqual(second_dict, expected_second_single_cell)

    def test_rel_file_four_relation(self):
        xml_file = os.path.join(
            self.excel_dir, "xl", "worksheets", "_rels", "sheet1.xml.rels"
        )
        converted_xml = XMLFile(xml_file)
        relationships = converted_xml.get_in_xml_with_keylist(
            ["Relationships", "Relationship"]
        )

        self.assertEqual(len(relationships), 4)
        self.assertIs(type(relationships), list)

    def test_rel_file_one_relation(self):
        xml_file = os.path.join(
            self.excel_dir, "xl", "worksheets", "_rels", "sheet2.xml.rels"
        )
        converted_xml = XMLFile(xml_file)
        relationships = converted_xml.get_in_xml_with_keylist(
            ["Relationships", "Relationship"]
        )
        value_type = ""
        expected_value_type_not = "table"

        self.assertEqual(len(relationships), 1)
        self.assertIs(type(relationships), list)

        for value in relationships:
            value_type = value["Type"].split("/")[-1]

        self.assertNotEqual(value_type, expected_value_type_not)

    def test_convert_xml_to_dict(self):
        xml_file = os.path.join(
            self.cdbxml_dir, "Anforderungsübersicht_data.xlsx.cdbxml"
        )
        xml = XMLFile(xml_file)
        converted_xml = xml.get_single_key("Root")

        expected_key = "RequirementOverview"
        expected_chapter = " 1"

        dict_key = converted_xml.keys()

        self.assertIs(type(converted_xml), dict)
        self.assertIn(expected_key, dict_key)

        list_xml = converted_xml[expected_key]["List"]
        first_req_overview = list_xml[0]

        self.assertEqual(first_req_overview["chapter"], expected_chapter)

    def tearDown(self):
        super(XMLFileTestCase, self).tearDown()
        shutil.rmtree(self.excel_dir)
        shutil.rmtree(self.cdbxml_dir)
