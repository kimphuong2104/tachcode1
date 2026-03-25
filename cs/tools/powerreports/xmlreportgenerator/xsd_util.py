import logging
import os
import shutil

import lxml.etree as et  # nosec
from lxml.etree import XMLSyntaxError  # nosec

from cs.tools.powerreports.xmlreportgenerator import DEBUG, tools

XMLMAPS = "xmlMaps.xml"
LOG = logging.getLogger(__name__)
XMLNS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/xmlMaps"


class XSDUtil(object):
    """
    Add XSD-Schema to template excel

    :param excel_file: an excel file (empty or template)
    :param xsd_file: xsd file (from CONTACT Elements) with schema
    :param schema_name: name of schema (name is used for xmlMaps.xml)
    """

    def __init__(self, excel_file, xsd_file, schema_name):
        self.excel_file = excel_file
        self.xsd_file = xsd_file
        self.map_name = schema_name

        self._excel_dir = None

    @property
    def excel_dir(self):
        if not self._excel_dir:
            self._excel_dir = tools.temporary_unzip_file(self.excel_file)
        return self._excel_dir

    def import_schema(self):
        """
        Checks if xmlMaps has already the schema or not

        if Excel has no xmlMaps.xml file -> add schema
        otherwise -> reload selected schema
        """
        xmlmaps_path = os.path.join(self.excel_dir, "xl", XMLMAPS)
        if not os.path.exists(xmlmaps_path):
            self.add()
        else:
            self.reload_xml_schema()

        self.clean_up()

    def reload_xml_schema(self):
        """
        Reload newest xml schema from database in excel

        First delete old xml/xsd schema in xmlMaps (save schemaid and mapid)
        Than add new schema to excel (like in add())
        """
        try:
            xsd_root = et.parse(self.xsd_file).getroot()  # pylint: disable=I1101 #nosec
        except XMLSyntaxError as ex:
            LOG.error(ex, exc_info=True)
            raise Exception(  # pylint: disable=W0719
                "There have been syntax errors in the xsd schema file. "
                "Please contact your administrator."
            )
        xmlmaps_path = os.path.join(self.excel_dir, "xl", XMLMAPS)
        xmlroot = et.parse(xmlmaps_path).getroot()  # pylint: disable=I1101 #nosec
        map_id = ""
        schema_id = ""
        for child in xmlroot:
            # use Map tag in schema to get informations
            # if schema has not CONTACT prefix will ignored
            # if multiple map schemas - last schema will be used for mapping and be replaced
            if "Map" in child.tag:
                if child.attrib["Name"].startswith("CDB_"):
                    # map id has to be the same, otherwise table und singlecells cant find connection
                    map_id = child.attrib["ID"]
                    schema_id = child.attrib["SchemaID"]
                    ns = {
                        "default": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                    }
                    schemas = xmlroot.xpath(
                        "//default:Schema[@ID='%s']" % schema_id, namespaces=ns
                    )
                    if schemas:
                        for schema in schemas:
                            xmlroot.remove(schema)
                    xmlroot.remove(child)

        map_tree = et.ElementTree(xmlroot)  # pylint: disable=I1101

        with open(xmlmaps_path, "wb") as f:
            map_tree.write(f)

        schema_root = et.Element(
            "Schema", attrib={"ID": schema_id}
        )  # pylint: disable=I1101
        schema_root.insert(0, xsd_root)

        xmlroot.insert(0, schema_root)

        map_attribute = {
            "ID": map_id,
            "Name": self.map_name,
            "RootElement": "Root",
            "SchemaID": schema_id,
            "ShowImportExportValidationErrors": "false",
            "AutoFit": "true",
            "Append": "false",
            "PreserveSortAFLayout": "true",
            "PreserveFormat": "true",
        }
        et.SubElement(xmlroot, "Map", attrib=map_attribute)  # pylint: disable=I1101

        map_tree = et.ElementTree(xmlroot)  # pylint: disable=I1101
        with open(xmlmaps_path, "wb") as f:
            map_tree.write(f)

        tools.save_excel(self.excel_file, self.excel_dir)

    def add(self):
        self.update_workbook_rels()

        schema_id = "Schema" + "1"

        schema_root = et.Element(
            "Schema", attrib={"ID": schema_id}
        )  # pylint: disable=I1101
        try:
            schema_root.insert(
                0, et.parse(self.xsd_file).getroot()  # nosec
            )  # pylint: disable=I1101
        except XMLSyntaxError as ex:
            LOG.error(ex, exc_info=True)
            raise Exception(  # pylint: disable=W0719
                "There have been syntax errors in the xsd schema file. "
                "Please contact your administrator."
            )
        map_info_root = et.Element(
            "MapInfo",  # pylint: disable=I1101
            attrib={"xmlns": XMLNS, "SelectionNamespaces": ""},
        )
        map_info_root.insert(0, schema_root)

        map_attribute = {
            "ID": "1",
            "Name": self.map_name,
            "RootElement": "Root",
            "SchemaID": schema_id,
            "ShowImportExportValidationErrors": "false",
            "AutoFit": "true",
            "Append": "false",
            "PreserveSortAFLayout": "true",
            "PreserveFormat": "true",
        }
        et.SubElement(
            map_info_root, "Map", attrib=map_attribute
        )  # pylint: disable=I1101

        map_tree = et.ElementTree(map_info_root)  # pylint: disable=I1101

        with open(os.path.join(self.excel_dir, "xl", XMLMAPS), "wb") as f:
            map_tree.write(f)

        tools.save_excel(self.excel_file, self.excel_dir)

    def update_workbook_rels(self):
        """
        Update rel file of the workbook to append xml schema

        Open rel xml file and append xmlMap as an element
        Make sure the rId of the element is not duplicated
        """
        workbook_path = os.path.join(self.excel_dir, "xl", "_rels", "workbook.xml.rels")
        workbook_rel_tree = et.parse(workbook_path)  # pylint: disable=I1101 #nosec

        elem_tag = ""
        map_ids = []
        for child in workbook_rel_tree.getroot():
            elem_tag = child.tag
            map_ids.append(child.attrib["Id"])

        map_id = 1
        while True:
            xml_map_id = "rId" + str(map_id)
            if xml_map_id in map_ids:
                map_id += 1
            else:
                break
        xml_map_attr = {"Id": xml_map_id, "Type": XML_TYPE, "Target": XMLMAPS}

        et.SubElement(
            workbook_rel_tree.getroot(), elem_tag, attrib=xml_map_attr
        )  # pylint: disable=I1101

        with open(workbook_path, "wb") as f:
            workbook_rel_tree.write(f)

    def clean_up(self):
        if DEBUG:
            LOG.info("Excel directory: %s", self.excel_dir)
        else:
            try:
                shutil.rmtree(self.excel_dir)
            except Exception as e:  # pylint: disable=W0703
                LOG.warning(
                    "Could not remove Excel directory %s (%s)",
                    self.excel_dir,
                    e,
                )
