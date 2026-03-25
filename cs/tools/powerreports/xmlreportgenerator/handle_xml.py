import logging
from collections import defaultdict

import lxml.etree as et  # nosec
from lxml.etree import XMLSyntaxError  # nosec

LOG = logging.getLogger(__name__)


class XMLFile(object):
    def __init__(self, filename):
        self.filename = filename
        self._xml = None

    @property
    def xml(self):
        """
        Load xml file
        Remove namespaces {...} for better handling later
        :return dict xml: dictionary of the xml from the given file
        """
        if not self._xml:
            etree_parse = et.iterparse(self.filename)  # pylint: disable=I1101
            try:
                for _, element in etree_parse:
                    element.tag = element.tag[element.tag.find("}") + 1 :]
                self._xml = self.xml_as_dict(etree_parse.root)
            except XMLSyntaxError as ex:
                LOG.error(ex, exc_info=True)
                raise Exception(  # pylint: disable=W0719
                    "There have been syntax errors in the xml file. "
                    "Please contact your administrator."
                )

        return self._xml

    def get_in_xml_with_keylist(self, keys):
        """
        getIn (like immutualjs) dict
        get in dict for every key in key

        if get_in is not list convert to list

        :return list get_in: list with dicts (values of last key)
        """
        get_data = self.xml.get(keys[0])
        keys = keys[1:]
        for key_idx in keys:
            get_data = get_data.get(key_idx)
            if key_idx == keys[-1] and type(get_data) is not list:
                get_data = [get_data]

        return get_data

    def get_single_key(self, key):
        key_data = self.xml[key]
        return key_data

    def xml_as_dict(self, xml_etree):
        """
        Returns xml element tree as dictionary
        based on: https://stackoverflow.com/questions/2148119/how-to-convert-an-xml-string-to-a-dictionary

        :return dict xml: similar to xmltodict package
        """
        xml = {xml_etree.tag: {} if xml_etree.attrib else None}
        children = list(xml_etree)
        if children:
            default = defaultdict(list)
            for dict_child in map(self.xml_as_dict, children):
                for key, value in dict_child.items():
                    default[key].append(value)
            xml = {
                xml_etree.tag: {
                    key: value[0] if len(value) == 1 else value
                    for key, value in default.items()
                }
            }
        if xml_etree.attrib:
            xml[xml_etree.tag].update(
                (key, value) for key, value in xml_etree.attrib.items()
            )

        return xml
