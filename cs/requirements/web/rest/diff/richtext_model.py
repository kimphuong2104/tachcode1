# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import logging
from io import BytesIO

import lxml.etree as ET

from cdb import fls, i18n, sig, sqlapi, util
from cdb.objects.core import ByID
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.base_classes import WithRQMBase
from cs.requirements.web.rest.diff.requirements_model import RequirementsModel
from cs.requirements.richtext import RichTextModifications

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

RICHTEXT_CRITERION_DIFF_PLUGIN_ID = 'richtext'

LOG = logging.getLogger(__name__)

XSLT = u'''<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
   xmlns:diff="http://namespaces.shoobx.com/diff"
   xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
   <xsl:template match="@diff:insert-formatting">
      <xsl:attribute name="class">
         <xsl:value-of select="'insert-formatting'"/>
      </xsl:attribute>
   </xsl:template>
   <xsl:template match="diff:delete">
      <del>
         <xsl:apply-templates />
      </del>
   </xsl:template>
   <xsl:template match="diff:insert">
      <ins>
         <xsl:apply-templates />
      </ins>
   </xsl:template>
   <xsl:template match="@* | node()">
      <xsl:copy>
         <xsl:apply-templates select="@* | node()"/>
      </xsl:copy>
   </xsl:template>
</xsl:stylesheet>'''

XSLT_TEMPLATE = ET.fromstring(XSLT)


class DiffRichTextAPIModel (object):

    def __init__(self, left_cdb_object_id, right_cdb_object_id):
        self.left_cdb_object_id = left_cdb_object_id
        self.right_cdb_object_id = right_cdb_object_id
        if right_cdb_object_id == "null":
            # Right element is empty
            self.left_object = ByID(self.left_cdb_object_id)
            self.right_object = None
            self.empty_element = True

        else:
            if left_cdb_object_id == "null":
                # Left element is empty
                self.left_object = None
                self.right_object = ByID(self.right_cdb_object_id)
                self.empty_element = True
            else:
                self.left_object = ByID(self.left_cdb_object_id)
                self.right_object = ByID(self.right_cdb_object_id)
                self.empty_element = False

    def check_access(self):
        if (
            (
                self.empty_element and
                self.left_object and
                self.left_object.CheckAccess('read')
            ) or
            (
                self.empty_element and
                self.right_object and
                self.right_object.CheckAccess('read')
            ) or
            (
                self.left_object and self.left_object.CheckAccess('read') and
                self.right_object and self.right_object.CheckAccess('read')
            )
        ):
            access_granted = True
        else:
            access_granted = False
        return access_granted

    @classmethod
    def fast_rich_text_diff_ids(cls, left_spec, right_spec, settings, additional_conditions=None):
        """ Searches all objects (their ids) that have different description (richtext) values
        compared to their counterpart within the given
        left and right specification object contexts.

        Per default: only requirement objects are searched,
            via settings also target values can be searched as well.
        """
        fls.allocate_license('RQM_070')
        if settings is None:
            settings = {}
        if additional_conditions is None:
            additional_conditions = {}
        languages = settings.get('languages', [])
        attributes = [
            'cdb_object_id',
            'ce_baseline_origin_id',
            'specification_object_id',
            'requirement_object_id',
            'pos'
        ]
        criterions_per_class = settings.get('criterions_per_class', {})
        entities_to_search_for = [
            x for x in [
                RQMSpecification,
                RQMSpecObject,
                TargetValue
            ] if (
                x.__maps_to__ in criterions_per_class and
                RICHTEXT_CRITERION_DIFF_PLUGIN_ID in criterions_per_class[x.__maps_to__]
            )
        ]
        changed_ids = set()
        changed_req_ids = set()
        changed_tv_ids = set()
        for entity in entities_to_search_for:
            additional_condition = additional_conditions.get(entity.__maps_to__, "1=1")
            base_condition_attr = (
                "specification_object_id" if hasattr(entity, "specification_object_id")
                else "cdb_object_id"
            )
            base_condition = str(
                getattr(entity, base_condition_attr).one_of(
                    left_spec.cdb_object_id, right_spec.cdb_object_id
                )
            )
            ids_stmt = """
            SELECT
                {columns}
            FROM {table} WHERE {condition}""".format(
                table=entity.__maps_to__,
                columns=",".join([
                    "{attr} {attr}".format(attr=attr)
                    if hasattr(entity, attr) else
                    "NULL {attr}".format(attr=attr)
                    for attr in attributes
                ]),
                condition=" AND ".join(
                    [
                        base_condition,
                        additional_condition.replace('left_side.', '').replace('right_side.', '')
                    ]
                )
            )
            ids = sqlapi.RecordSet2(sql=ids_stmt)
            left_ids = {}
            right_ids = {}
            cdb_object_ids = set()
            for record in ids:
                if record[base_condition_attr] == left_spec.cdb_object_id:
                    left_ids[record['ce_baseline_origin_id']] = (
                        record['cdb_object_id'], record['requirement_object_id'], record['pos']
                    )
                else:
                    right_ids[record['ce_baseline_origin_id']] = (
                        record['cdb_object_id'], record['requirement_object_id'], record['pos']
                    )
                cdb_object_ids.add(record['cdb_object_id'])
            text_cache = RequirementsModel.get_requirements_text_cache(
                reqs=None,
                req_ids=list(cdb_object_ids),
                languages=languages if entity != RQMSpecification else None,
                entity=entity
            )
            for left_id, left in left_ids.items():
                right = right_ids.get(left_id)  # as ce_baseline_origin_id should be the same everytime
                if right:  # if a requirement was deleted
                    right_cdb_object_id, right_requirement_object_id, _right_tv_pos = right
                    left_cdb_object_id, _left_requirement_object_id, _left_tv_pos = left
                    left_text = text_cache.get(left_cdb_object_id)
                    if left_text is not None:
                        for key, value in left_text.items():
                            if value == '':
                                left_text[key] = "<xhtml:div></xhtml:div>"
                    right_text = text_cache.get(right_cdb_object_id)
                    if right_text is not None:
                        for key, value in right_text.items():
                            if value == '':
                                right_text[key] = "<xhtml:div></xhtml:div>"
                    if left_text != right_text:
                        if right_requirement_object_id:
                            changed_tv_ids.add(right)
                            changed_req_ids.add(right_requirement_object_id)
                            changed_ids.add(right_requirement_object_id)
                        else:
                            changed_req_ids.add(right_cdb_object_id)
                        changed_ids.add(right_cdb_object_id)
        return {
            'changed_req_ids': changed_req_ids,
            'changed_tv_ids': changed_tv_ids,
            'changed_ids': changed_ids
        }

    @classmethod
    def remove_prefix(cls, text, prefix):
        return text[text.startswith(prefix) and len(prefix):]

    def process_object(self, target_desc):

        try:
            from xmldiff import formatting, main as xmldiff_main

            class HTMLFormatter(formatting.XMLFormatter):

                def render(self, result):
                    transform = ET.XSLT(XSLT_TEMPLATE)
                    result = transform(result)
                    return super(HTMLFormatter, self).render(result)

        except ImportError:
            LOG.error('Python library xmldiff is not installed')
            return {}

        # Result dictionary
        language_diff_dict = {}
        # Namespaces
        ns_diff = '{http://namespaces.shoobx.com/diff}'
        ns_xhtml = '{http://www.w3.org/1999/xhtml}'

        if not self.empty_element:
            desc_left_pre = self.left_object.GetText(target_desc) if self.left_object else "<xhtml:div></xhtml:div>"
            desc_left_pre = desc_left_pre if (desc_left_pre != "" and not isinstance(self.left_object, RQMSpecification)) else "<xhtml:div>" + desc_left_pre + "</xhtml:div>"

            desc_right_pre = self.right_object.GetText(target_desc) if self.right_object else "<xhtml:div></xhtml:div>"
            desc_right_pre = desc_right_pre if (desc_right_pre != "" and not isinstance(self.right_object, RQMSpecification)) else "<xhtml:div>" + desc_right_pre + "</xhtml:div>"

            desc_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml">' + desc_left_pre + '</xml>'
            desc_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml">' + desc_right_pre + '</xml>'
            # Obtain formatted html diff file
            formatter = HTMLFormatter(pretty_print=False)
            result = xmldiff_main.diff_texts(
                desc_left,
                desc_right,
                formatter=formatter,
                diff_options={'F': 0.8, 'ratio_mode': 'accurate'}
            )
            is_different = True
            if desc_left == desc_right:
                is_different = False

            # Parse from string
            context = ET.iterparse(BytesIO(result.encode("UTF-8")), events=("start",))

            # Flag for elements inside a table
            parent_tr = False
            root = None
            for _event, elem in context:
                if root is None:
                    root = elem
                    continue
                if elem.getparent().tag == ns_xhtml + "tr":
                    parent_tr = True
                else:
                    parent_tr = False
                if parent_tr is True and ns_diff + "delete" in elem.attrib.keys():
                    elem.attrib["style"] = 'background-color:rgb(255, 187, 187);text-decoration:line-through;'
                if ns_diff + "insert" in elem.keys():
                    elem.getparent().remove(elem)
                if ns_diff + "update-attr" in elem.keys():
                    updated_attrs = elem.attrib[ns_diff + "update-attr"]
                    for upd_atr in updated_attrs.split(";"):
                        if upd_atr != "":
                            attr_name = upd_atr.split(":")[0]
                            attr_par = self.remove_prefix(upd_atr, attr_name + ":")
                            elem.attrib[attr_name] = attr_par

            xmlstr_empty = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml">' + WithRQMBase.EMPTY_DIV + '</xml>'
            xmlstr_left = ET.tostring(root, method=RichTextModifications.DEFAULT_SERIALIZATION).decode('utf-8')

            # Repeat process for right side
            # Parse from bytes to iterparse
            context = ET.iterparse(BytesIO(result.encode("utf-8")), events=("start",))
            root = None
            parent_tr = False
            # Tables require special backend processing
            for _event, elem in context:
                if root is None:
                    root = elem
                    continue
                if elem.getparent().tag == ns_xhtml + "tr":
                    parent_tr = True
                else:
                    parent_tr = False
                if parent_tr is True and ns_diff + "insert" in elem.attrib.keys():
                    elem.attrib["style"] = 'background-color:rgb(212, 252, 199);'
                if ns_diff + "delete" in elem.keys():
                    elem.getparent().remove(elem)

            xmlstr_right = ET.tostring(root, method=RichTextModifications.DEFAULT_SERIALIZATION).decode('utf-8')

            # Replace paths for REST links
            if self.left_object:
                xhtml_left_pre = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
                    self.left_object, {target_desc: xmlstr_left}, from_db=True
                )
                if len(xhtml_left_pre) == 0:
                    xhtml_left = xmlstr_left
                else:
                    xhtml_left = xhtml_left_pre[target_desc]
            else:
                xhtml_left = xmlstr_empty
            if self.right_object:
                xhtml_right_pre = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
                    self.right_object, {target_desc: xmlstr_right}, from_db=True
                )
                if len(xhtml_right_pre) == 0:
                    xhtml_right = xmlstr_right
                else:
                    xhtml_right = xhtml_right_pre[target_desc]
            else:
                xhtml_right = xmlstr_empty

            language_diff_dict = {
                "xhtml_left": xhtml_left if is_different else None,
                "xhtml_right": xhtml_right if is_different else None,
                "xhtml_single": xhtml_right if not is_different else None
            }
        else:  # There was an empty side
            xmlstr_empty = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml">' + WithRQMBase.EMPTY_DIV + '</xml>'

            desc_left_pre = self.left_object.GetText(target_desc) if self.left_object else "<xhtml:div></xhtml:div>"
            desc_left_pre = desc_left_pre if desc_left_pre != "" else "<xhtml:div></xhtml:div>"

            desc_right_pre = self.right_object.GetText(target_desc) if self.right_object else "<xhtml:div></xhtml:div>"
            desc_right_pre = desc_right_pre if desc_right_pre != "" else "<xhtml:div></xhtml:div>"

            xmlstr_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml">' + desc_left_pre + '</xml>'
            xmlstr_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml">' + desc_right_pre + '</xml>'

            if self.left_object:
                xhtml_left_pre = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
                    self.left_object, {target_desc: xmlstr_left}, from_db=True
                )
                if len(xhtml_left_pre) == 0:
                    xhtml_left = xmlstr_left
                else:
                    xhtml_left = xhtml_left_pre[target_desc]
            else:
                xhtml_left = xmlstr_empty
            if self.right_object:
                xhtml_right_pre = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
                    self.right_object, {target_desc: xmlstr_right}, from_db=True
                )
                if len(xhtml_right_pre) == 0:
                    xhtml_right = xmlstr_right
                else:
                    xhtml_right = xhtml_right_pre[target_desc]
            else:
                xhtml_right = xmlstr_empty

            language_diff_dict = {
                "xhtml_left": "single_object",
                "xhtml_right": "single_object",
                "xhtml_single": xmlstr_left if self.left_object else xhtml_right
            }
        return language_diff_dict

    def diff(self, languages):
        fls.allocate_license('RQM_070')
        # Result dictionary
        diff_dict = {"diff_dict": {}}
        type_object = self.right_object if self.right_object else self.left_object

        if isinstance(type_object, RQMSpecification):
            req_descr_base = "cdbrqm_specification_txt"
            diff_dict["diff_dict"]["spec"] = self.process_object(req_descr_base)
        else:
            # Target language description
            req_descr_base = (
                "cdbrqm_spec_object_desc_"
                if isinstance(type_object, RQMSpecObject) else
                "cdbrqm_target_value_desc_"
            )
            for language in languages:
                if language in i18n.Languages():
                    target_desc = req_descr_base + language
                    diff_dict["diff_dict"][language] = self.process_object(target_desc)

        return diff_dict


@sig.connect(RQMSpecification, "rqm_diff_plugins", "init")
def register_diff_plugin(registry):
    registry.register_criterion([
        RQMSpecification,
        RQMSpecObject,
        TargetValue
    ], RICHTEXT_CRITERION_DIFF_PLUGIN_ID, util.get_label('web.rqm_diff.description'))


@sig.connect(RQMSpecification, "rqm_diff_plugins", "search", 'richtext')
def search(left_spec, right_spec, settings):
    return DiffRichTextAPIModel.fast_rich_text_diff_ids(left_spec, right_spec, settings)
