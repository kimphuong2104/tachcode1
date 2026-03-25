# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Module reports

This is the documentation for the reports module.
"""

from __future__ import unicode_literals

from cdb import cmsg
from cdb import i18n
from cdb import sqlapi
from cdb import ue, util
from cdb.platform import gui, mom
from cdb.elink import isCDBPC
import logging

from cdb.objects import ByID
from cs.requirements import RQMSpecification, RQMSpecObject
from cs.requirements import exceptions, rqm_utils
from cs.requirements.classes import RequirementPriority, RequirementCategory
from cs.tools import powerreports as PowerReports
from cs.tools.semanticlinks import SemanticLinkType, LinkGraphConfig, SemanticLink

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ["SpecificationOverview",
           "RequirementHeader",
           "RequirementOverview"]

LOG = logging.getLogger(__name__)


def get_richtext_caches(record_set, specification_object_id):
    from cs.requirements.richtext import RichTextModifications
    record_ids = [r.cdb_object_id for r in record_set]
    variable_values_by_id = RichTextModifications.get_variable_values_by_id(
        record_ids, specification_object_id
    )
    long_text_cache = rqm_utils.get_long_text_cache(RQMSpecObject, record_ids)
    return long_text_cache, variable_values_by_id


def get_richtext_attribute_values_from_record(record, long_text_cache=None, variable_values_by_id=None):
    from cs.requirements.richtext import RichTextModifications
    attribute_values = {}
    for k in ['cdbrqm_spec_object_desc_de', 'cdbrqm_spec_object_desc_en']:
        if long_text_cache is not None:
            attribute_values[k] = long_text_cache.get(k, {}).get(record.cdb_object_id, '')
        else:
            attribute_values[k] = util.text_read(
                k,
                ["cdb_object_id"],
                [record.cdb_object_id]
            )
    try:
        modifications = RichTextModifications.get_variable_modified_attribute_values(
            objs=record,
            attribute_values=attribute_values,
            from_db=True,
            raise_for_empty_value=True,
            variable_values_by_id=variable_values_by_id
        )
        attribute_values.update(modifications)
    except exceptions.MissingVariableValueError as e:
        obj = ByID(record.cdb_object_id)
        raise ue.Exception(
            "just_a_replacement", 
            "Missing variable value for %s on object %s" % (
                e.variable_id, obj.GetDescription()
            )
        )
    return {
        k: rqm_utils.strip_tags(v) for (k, v) in attribute_values.items()
    }


def add_richtext_descriptions_to_report_data(attribute_values, report_data):
    text_de = attribute_values.get("cdbrqm_spec_object_desc_de")
    if not text_de:
        text_de = attribute_values.get("cdbrqm_spec_object_desc_en")
    text_en = attribute_values.get("cdbrqm_spec_object_desc_en")
    if not text_en:
        text_en = attribute_values.get("cdbrqm_spec_object_desc_de")
    report_data["desc_long_de"] = text_de
    report_data["desc_long_en"] = text_en


class RequirementOverview(PowerReports.CustomDataProvider):
    """ Data provider for requirement structure with hierarchy information """
    CARD = PowerReports.N
    CALL_CARD = PowerReports.CARD_1

    XSDSchemaItems = {"cdbxml_level": (sqlapi.SQL_INTEGER,
                                       "computed"),
                      "chapter": (sqlapi.SQL_CHAR,
                                  RQMSpecObject.__maps_to__),
                      "act_value": (sqlapi.SQL_FLOAT,
                                    RQMSpecObject.__maps_to__),
                      "is_defined": (sqlapi.SQL_CHAR,
                                     RQMSpecObject.__maps_to__),
                      "source": (sqlapi.SQL_CHAR,
                                 RQMSpecObject.__maps_to__),
                      "authors": (sqlapi.SQL_CHAR,
                                  RQMSpecObject.__maps_to__),
                      "ext_specobject_id": (sqlapi.SQL_CHAR,
                                            RQMSpecObject.__maps_to__),
                      "req_hyperlink": (sqlapi.SQL_CHAR,
                                        RQMSpecObject.__maps_to__),
                      "desc_long_de": (sqlapi.SQL_CHAR,
                                       RQMSpecObject.__maps_to__),
                      "desc_long_en": (sqlapi.SQL_CHAR,
                                       RQMSpecObject.__maps_to__),
                      "req_rating": (sqlapi.SQL_CHAR, ''),  # New field for rating value
                      "req_comment": (sqlapi.SQL_CHAR, ''),  # New field for comment
                      "req_rating_int2ext": (sqlapi.SQL_CHAR, ''),
                      # New field for rating value (communicate int -> ext)
                      "req_comment_int2ext": (sqlapi.SQL_CHAR, '')  # New field for comment (communicate int -> ext)
                      }

    def __init__(self, *args, **kwargs):
        super(RequirementOverview, self).__init__(*args, **kwargs)
        name_ml_fields = self.get_filtered_language_fields(RQMSpecObject.__maps_to__, 'name_')
        for field_name in name_ml_fields:
            self.XSDSchemaItems[field_name] = (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__)

        priority_ml_name_fields = self.get_filtered_language_fields(RequirementPriority.__maps_to__, 'ml_name_')
        for field_name in priority_ml_name_fields:
            self.XSDSchemaItems['priority_' + field_name] = (sqlapi.SQL_CHAR, RequirementPriority.__maps_to__)
        category_ml_name_fields = self.get_filtered_language_fields(RequirementCategory.__maps_to__, 'ml_name_')
        for field_name in category_ml_name_fields:
            self.XSDSchemaItems['category_' + field_name] = (sqlapi.SQL_CHAR, RequirementCategory.__maps_to__)
        discipline_ml_name_fields = self.get_filtered_language_fields('cdbrqm_req_discipline', 'ml_name_')
        for field_name in discipline_ml_name_fields:
            self.XSDSchemaItems['discipline_' + field_name] = (sqlapi.SQL_CHAR, RequirementCategory.__maps_to__)

    @classmethod
    def get_filtered_language_fields(cls, rel, base_name):
        # default filter to de, en for higher performance, can be customized
        field_names = i18n.iso_columns(rel, base_name)
        return [field_names.get(lang) for lang in field_names.keys() if lang in ['de', 'en']]

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        for attr, (sqlType, _tableName) in self.XSDSchemaItems.items():
            schema.add_attr(attr, sqlType)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        """
            Gets hierarchical requirement data depending on DBMS type
        """
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang", i18n.default())
        # Get list of top level requirements
        if isinstance(parent_result, PowerReports.ReportData):
            obj = parent_result.getObject()
            obj.Reload()
            specification_object_id = None
            if isinstance(obj, RQMSpecification):
                specification_object_id = obj.cdb_object_id
            elif isinstance(obj, RQMSpecObject):
                specification_object_id = obj.specification_object_id
            else:
                return []

        db_type = sqlapi.SQLdbms()
        return self._getResults(
            self.getHierarchicalStructure(obj, db_type),
            specification_object_id=specification_object_id
        )

    def getHierarchicalStructure(self, obj, db_type):
        """
            Specific Hierarchical Query to determine requirement hierarchy,
            customized for this report

            :param obj: First requirement to get data from
        """
        if isinstance(obj, RQMSpecification) or isinstance(obj, RQMSpecObject):
            msRecursiveCTEQuery = """
            WITH Hierarchical (cdb_object_id, {name_ml_fields}, specobject_id,
                               chapter, priority, category,
                               discipline, is_defined,
                               ext_specobject_id,
                               cdbxml_level, path,
                               act_value, 
                               weight, parent_object_id,
                               sortorder)
            AS (
                SELECT r1.cdb_object_id, {name_ml_fields_r1}, r1.specobject_id,
                       r1.chapter, r1.priority, r1.category,
                       r1.discipline, r1.is_defined,
                       r1.ext_specobject_id,
                       0 as cdbxml_level,
                       CAST(r1.cdb_object_id as nvarchar(4000)) as path, r1.act_value, 
                       r1.weight, r1.parent_object_id, r1.sortorder
                FROM cdbrqm_spec_object_v r1
                WHERE r1.parent_object_id='{parent_object_id_r1}'
                    AND r1.specification_object_id='{specification_object_id_r1}'
                UNION ALL
                SELECT r2.cdb_object_id, {name_ml_fields_r2}, r2.specobject_id,
                       r2.chapter, r2.priority, r2.category,
                       r2.discipline, r2.is_defined,
                       r2.ext_specobject_id,
                       cdbxml_level + 1,
                       CAST((h.path + r2.cdb_object_id) as nvarchar(4000)) as path, r2.act_value,
                       r2.weight, r2.parent_object_id, r2.sortorder
                FROM cdbrqm_spec_object_v r2
                INNER JOIN Hierarchical h ON h.cdb_object_id = r2.parent_object_id
               )
            SELECT
                h.*, {priority_ml_name_fields_p},
                {category_ml_name_fields_c}, {discipline_ml_name_fields_d}
            FROM Hierarchical h
                LEFT JOIN cdbrqm_req_prio p ON h.priority=p.priority
                LEFT JOIN cdbrqm_requirement_category c ON h.category=c.name
                LEFT JOIN cdbrqm_req_discipline d ON h.discipline=d.name
            ORDER BY h.sortorder
            """
            oracleRecursiveCTEQuery = """
            WITH Hierarchical (cdb_object_id, {name_ml_fields}, specobject_id,
                               chapter, priority, category,
                               discipline, is_defined,
                               ext_specobject_id,
                               cdbxml_level, path,
                               act_value, 
                               weight, parent_object_id,
                               sortorder)
            AS (
                SELECT r1.cdb_object_id, {name_ml_fields_r1}, r1.specobject_id,
                       r1.chapter, r1.priority, r1.category,
                       r1.discipline, r1.is_defined,
                       r1.ext_specobject_id,
                       0 as cdbxml_level,
                       r1.cdb_object_id as path, r1.act_value,
                       r1.weight, r1.parent_object_id, r1.sortorder
                FROM cdbrqm_spec_object_v r1
                WHERE r1.parent_object_id='{parent_object_id_r1}'
                    AND r1.specification_object_id='{specification_object_id_r1}'
                UNION ALL
                SELECT r2.cdb_object_id, {name_ml_fields_r2}, r2.specobject_id,
                       r2.chapter, r2.priority, r2.category,
                       r2.discipline, r2.is_defined,
                       r2.ext_specobject_id,
                       cdbxml_level + 1,
                       h.path || r2.cdb_object_id as path, r2.act_value,
                       r2.weight, r2.parent_object_id, r2.sortorder
                FROM cdbrqm_spec_object_v r2
                INNER JOIN Hierarchical h ON h.cdb_object_id = r2.parent_object_id
               )
            SELECT
                h.*, {priority_ml_name_fields_p},
                {category_ml_name_fields_c}, {discipline_ml_name_fields_d}
            FROM Hierarchical h
                LEFT JOIN cdbrqm_req_prio p ON h.priority=p.priority
                LEFT JOIN cdbrqm_requirement_category c ON h.category=c.name
                LEFT JOIN cdbrqm_req_discipline d ON h.discipline=d.name
            ORDER BY h.sortorder
            """
            pgRecursiveCTEQuery = """
            WITH RECURSIVE Hierarchical (cdb_object_id, {name_ml_fields}, specobject_id,
                               chapter, priority, category,
                               discipline, is_defined,
                               ext_specobject_id,
                               cdbxml_level, path,
                               act_value, 
                               weight, parent_object_id,
                               sortorder)
            AS (
                SELECT r1.cdb_object_id, {name_ml_fields_r1}, r1.specobject_id,
                       r1.chapter, r1.priority, r1.category,
                       r1.discipline, r1.is_defined,
                       r1.ext_specobject_id,
                       0 as cdbxml_level,
                       r1.cdb_object_id::varchar as path, r1.act_value,
                       r1.weight, r1.parent_object_id, r1.sortorder
                FROM cdbrqm_spec_object_v r1
                WHERE r1.parent_object_id='{parent_object_id_r1}'
                    AND r1.specification_object_id='{specification_object_id_r1}'
                UNION ALL
                SELECT r2.cdb_object_id, {name_ml_fields_r2}, r2.specobject_id,
                       r2.chapter, r2.priority, r2.category,
                       r2.discipline, r2.is_defined,
                       r2.ext_specobject_id,
                       cdbxml_level + 1,
                       h.path || r2.cdb_object_id as path, r2.act_value,
                       r2.weight, r2.parent_object_id, r2.sortorder
                FROM cdbrqm_spec_object_v r2
                INNER JOIN Hierarchical h ON h.cdb_object_id = r2.parent_object_id
               )
            SELECT
                h.*, {priority_ml_name_fields_p},
                {category_ml_name_fields_c}, {discipline_ml_name_fields_d}
            FROM Hierarchical h
                LEFT JOIN cdbrqm_req_prio p ON h.priority=p.priority
                LEFT JOIN cdbrqm_requirement_category c ON h.category=c.name
                LEFT JOIN cdbrqm_req_discipline d ON h.discipline=d.name
            ORDER BY h.sortorder
            """
            if db_type == sqlapi.DBMS_MSSQL:
                query_fmt_str = msRecursiveCTEQuery
            elif db_type == sqlapi.DBMS_POSTGRES:
                query_fmt_str = pgRecursiveCTEQuery
            else:
                query_fmt_str = oracleRecursiveCTEQuery
            name_ml_fields = self.get_filtered_language_fields(RQMSpecObject.__maps_to__, 'name_')
            priority_ml_name_fields = self.get_filtered_language_fields(RequirementPriority.__maps_to__, 'ml_name_')
            category_ml_name_fields = self.get_filtered_language_fields(RequirementCategory.__maps_to__, 'ml_name_')
            discipline_ml_name_fields = self.get_filtered_language_fields('cdbrqm_req_discipline', 'ml_name_')
            RecursiveCTEQuery = query_fmt_str.format(
                name_ml_fields=",".join(name_ml_fields),
                name_ml_fields_r1=",".join(["r1.{}".format(x) for x in name_ml_fields]),
                name_ml_fields_r2=",".join(["r2.{}".format(x) for x in name_ml_fields]),
                parent_object_id_r1=obj.cdb_object_id if isinstance(obj, RQMSpecObject) else "",
                specification_object_id_r1=obj.specification_object_id if isinstance(obj, RQMSpecObject) else obj.cdb_object_id,
                priority_ml_name_fields_p=",".join(["p.{0} priority_{0}".format(x) for x in priority_ml_name_fields]),
                category_ml_name_fields_c=",".join(["c.{0} category_{0}".format(x) for x in category_ml_name_fields]),
                discipline_ml_name_fields_d=",".join(["d.{0} discipline_{0}".format(x) for x in discipline_ml_name_fields])
            )
            record_set = sqlapi.RecordSet2(sql=RecursiveCTEQuery)
            LOG.debug(RecursiveCTEQuery)
            return record_set
        return []

    def _getResults(self, record_set, specification_object_id):
        results = PowerReports.ReportDataList(self)
        cdb_object_ids = [record.cdb_object_id for record in record_set]
        classification_cache = rqm_utils.load_classification_cache_by_id(cdb_object_ids)
        long_text_cache, variable_values_by_id = get_richtext_caches(record_set, specification_object_id)
        for record in record_set:
            attribute_values = get_richtext_attribute_values_from_record(
                record, long_text_cache, variable_values_by_id
            )
            rd = PowerReports.ReportData(self, record)
            rd["req_hyperlink"] = self \
                .MakeURLWithoutObj("cdbrqm_spec_object",
                                   "cdbrqm_spec_object",
                                   "CDB_ShowObject",
                                   0,
                                   record.specobject_id,
                                   {"cdb_object_id": record.cdb_object_id})
            rd["is_defined"] = 'x' if rd["is_defined"] == 1 else ' '
            rd["chapter"] = " " + rd["chapter"]
            add_richtext_descriptions_to_report_data(attribute_values, report_data=rd)
            rd["cdbxml_level"] = int(record.cdbxml_level)
            rd["req_comment_int2ext"] = classification_cache.get(
                record.cdb_object_id, {}
            ).get('RQM_RATING_RQM_COMMENT_EXTERN', [{}])[0].get('value', '')
            rd["req_rating_int2ext"] = classification_cache.get(
                record.cdb_object_id, {}
            ).get('RQM_RATING_RQM_RATING_VALUE', [{}])[0].get('value', {}).get(self.cdbxml_report_lang, {}).get(
                'text_value', '')
            results.append(rd)
            rs = sqlapi.RecordSet2("cdbrqm_target_value_v",
                                   "requirement_object_id = '%s'" % record.cdb_object_id)
            def safe_pos(value):
                try:
                    return int(value)
                except ValueError:
                    if isinstance(value, str) and "." in value:
                        return int(float(value))
                    raise

            for r in rs:
                rt = PowerReports.ReportData(self, r)
                rt["req_hyperlink"] = self \
                    .MakeURLWithoutObj("cdbrqm_target_value",
                                       "cdbrqm_target_value",
                                       "CDB_ShowObject",
                                       0,
                                       r.targetvalue_id,
                                       {"cdb_object_id": r.cdb_object_id})
                rt["chapter"] = rd["chapter"] + "." + str(safe_pos(r.pos) + 1)
                text_de = rqm_utils.strip_tags(
                    util.text_read("cdbrqm_target_value_desc_de",
                                   ["cdb_object_id"],
                                   [r.cdb_object_id]))
                if not text_de:
                    text_de = rqm_utils.strip_tags(
                        util.text_read("cdbrqm_target_value_desc_en",
                                       ["cdb_object_id"],
                                       [r.cdb_object_id]))
                text_en = rqm_utils.strip_tags(
                    util.text_read("cdbrqm_target_value_desc_en",
                                   ["cdb_object_id"],
                                   [r.cdb_object_id]))
                if not text_en:
                    text_en = rqm_utils.strip_tags(
                        util.text_read("cdbrqm_target_value_desc_de",
                                       ["cdb_object_id"],
                                       [r.cdb_object_id]))
                rt["desc_long_de"] = text_de
                rt["desc_long_en"] = text_en
                rt["is_defined"] = 'x' if rd["is_defined"] == 1 else ' '
                rt["cdbxml_level"] = int(record.cdbxml_level + 1)
                rt["act_value"] = r.act_value
                rt["category_de"] = "Akzeptanzkriterium"
                rt["category_en"] = "Acceptance Criterion"
                results.append(rt)
        return results

    def MakeURLWithoutObj(self, class_name, relation, operation,
                          interactive, text_to_display, search_cond):
        """ Creates a cdb URL without instantiating the object it refers to """
        url = cmsg.Cdbcmsg(class_name, operation, interactive)
        for key in search_cond.keys():
            url.add_item(key, relation, search_cond[key])
        if isCDBPC():
            string = url.cdbwin_url()
        else:
            string = url.eLink_url()
        return "%s cdb:texttodisplay:%s" % (string, text_to_display)


class RequirementHeader(PowerReports.CustomDataProvider):
    """ Data provider for requirement header information """
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD, 'cdbrqm_spec_object')
        schema.add_attr("top_req_act_val", sqlapi.SQL_FLOAT)
        schema.add_attr("req_hyperlink", sqlapi.SQL_CHAR)
        schema.add_attr("specification_name", sqlapi.SQL_CHAR)
        schema.add_attr("specification_revision", sqlapi.SQL_CHAR)
        schema.add_attr("desc_de", sqlapi.SQL_CHAR)
        schema.add_attr("desc_en", sqlapi.SQL_CHAR)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportData(self, parent_result.getObject())
        req = parent_result.getObject()
        if isinstance(req, RQMSpecObject):
            result["top_req_act_val"] = req.act_value
        result["req_hyperlink"] = PowerReports.MakeReportURL(req)
        result["specification_name"] = req.Specification.name
        result["specification_revision"] = req.Specification.revision
        attribute_values = get_richtext_attribute_values_from_record(req)
        add_richtext_descriptions_to_report_data(attribute_values, report_data=result)
        return result


class SpecificationOverview(PowerReports.CustomDataProvider):
    """ Data provider for RQMSpecification header information """
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD, 'cdbrqm_specification')
        schema.add_attr("subject_name", sqlapi.SQL_CHAR)
        schema.add_attr("fulfillment_degree", sqlapi.SQL_FLOAT)
        schema.add_attr("RQMSpecification_hyperlink", sqlapi.SQL_CHAR)
        schema.add_attr("project_name", sqlapi.SQL_CHAR)
        schema.add_attr("product_code", sqlapi.SQL_CHAR)
        schema.add_attr("status_name_de", sqlapi.SQL_CHAR)
        schema.add_attr("status_name_en", sqlapi.SQL_CHAR)
        schema.add_attr("description", sqlapi.SQL_CHAR)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportData(self, parent_result.getObject())
        specification = parent_result.getObject()
        result["project_name"] = specification.project_name
        result["product_code"] = specification.product_code
        result["status_name_de"] = specification.joined_status_name_de
        result["status_name_en"] = specification.joined_status_name_en
        qc = rqm_utils.getFulfillmentQC(specification)
        result["fulfillment_degree"] = qc.act_value if qc is not None else ""
        result["RQMSpecification_hyperlink"] = PowerReports.MakeReportURL(specification)
        result["description"] = specification.GetText("cdbrqm_specification_txt")
        return result


class RequirementLinksHeader(PowerReports.CustomDataProvider):
    """ Data provider for the Header of RQMSRequirement Semantic Links """
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_N

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        schema.add_attr('links', sqlapi.SQL_CHAR)
        schema.add_attr('objects', sqlapi.SQL_CHAR)
        schema.add_attr('links2', sqlapi.SQL_CHAR)
        schema.add_attr('objects2', sqlapi.SQL_CHAR)
        schema.add_attr('links3', sqlapi.SQL_CHAR)
        schema.add_attr('objects3', sqlapi.SQL_CHAR)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        rr = PowerReports.ReportData(self)
        rr["links"] = source_args["links"] if source_args["links"] else util.get_label("all")
        rr["objects"] = source_args["object_names"] if source_args["object_names"] else util.get_label("all")
        rr["links2"] = source_args["links2"] if source_args["links2"] else util.get_label("all")
        rr["objects2"] = source_args["object_names2"] if source_args["object_names2"] else util.get_label("all")
        rr["links3"] = source_args["links3"] if source_args["links3"] else util.get_label("all")
        rr["objects3"] = source_args["object_names3"] if source_args["object_names3"] else util.get_label("all")
        return rr


class RequirementLinks(PowerReports.CustomDataProvider):
    """ Data provider for RQMSRequirement Semantic Links """
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_N

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        schema.add_attr('subj_desc', sqlapi.SQL_CHAR)
        schema.add_attr('obj_desc', sqlapi.SQL_CHAR)
        schema.add_attr('linktype_name', sqlapi.SQL_CHAR)
        schema.add_attr('status', sqlapi.SQL_CHAR)
        schema.add_attr('cdbxml_level', sqlapi.SQL_INTEGER)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportDataList(self)
        config = LinkGraphConfig.KeywordQuery(name="RQMSemanticLinkGraph")[0]
        c1 = source_args["types"]
        l1 = source_args["links"]
        f1 = {}
        if c1:
            f1["classes"] = c1.split(";")
        if l1:
            f1["links"] = l1.split("/")

        c2 = source_args["types2"]
        l2 = source_args["links2"]
        f2 = {}
        if c2:
            f2["classes"] = c2.split(";")
        if l2:
            f2["links"] = l2.split("/")

        c3 = source_args["types3"]
        l3 = source_args["links3"]
        f3 = {}
        if c3:
            f2["classes"] = c3.split(";")
        if l3:
            f3["links"] = l3.split("/")

        f = [f1, f2, f3]

        for o in parent_result:
            subj = o.getObject()

            rr = PowerReports.ReportData(self)
            visited = []
            edges = []

            def getReferences(node, ignore_contains, view, filter, reverse=False):
                """ node is the source object """
                objs = []
                if not filter:
                    filter = ""
                if reverse:
                    if ignore_contains:
                        objects = sqlapi.RecordSet2("cdb_semantic_link_v",
                                                    "object_object_id='%s' %s" % (
                                                        node.cdb_object_id, filter),
                                                    access="read")
                    else:
                        objects = sqlapi.RecordSet2(view,
                                                    "object_object_id='%s' %s" % (
                                                        node.cdb_object_id, filter),
                                                    access="read")
                    for link in objects:
                        if link is not None and link.subject_object_id:
                            subject = ByID(link.subject_object_id)
                            if subject is not None and subject.CheckAccess("read"):
                                objs.append({'obj': subject, 'via': link})
                else:
                    if ignore_contains:
                        subject = sqlapi.RecordSet2("cdb_semantic_link_v",
                                                    "subject_object_id='%s' %s" % (
                                                        node.cdb_object_id, filter),
                                                    access="read")
                    else:
                        subject = sqlapi.RecordSet2(view,
                                                    "subject_object_id='%s' %s" % (
                                                        node.cdb_object_id, filter),
                                                    access="read")
                    for link in subject:
                        if link is not None and link.object_object_id:
                            obj = ByID(link.object_object_id)
                            if obj is not None and obj.CheckAccess("read"):
                                objs.append({'obj': obj, 'via': link})
                return objs

            def walk(node, radius, ignore_contains, view, filtermap):
                filter = ""
                if node not in visited and radius < 3:
                    if "links" in filtermap[radius]:
                        filter += " and linktype_name in ('{links}')".format(
                            links="','".join(filtermap[radius]["links"]))
                    if "classes" in filtermap[radius]:
                        filter += " and object_object_classname in ('{}')".format(
                            "','".join(filtermap[radius]["classes"]))
                    radius += 1
                    next_node = getReferences(node, ignore_contains, view, filter)
                    for n in next_node:
                        if (node, n['obj']) not in edges and (n['obj'], node) not in edges:
                            rd = PowerReports.ReportData(self)
                            rd["obj_desc"] = PowerReports.MakeReportURL(n['obj'])
                            rd["subj_desc"] = PowerReports.MakeReportURL(node)
                            rd["linktype_name"] = n['via'].linktype_name
                            status = getattr(n['obj'], "act_value",
                                             getattr(n['obj'], "joined_status_name", ""))
                            rd["status"] = status
                            rd["cdbxml_level"] = int(radius)
                            result.append(rd)
                            edges.append((node, n['obj']))
                            if n['obj'] not in visited:
                                walk(n['obj'], radius, ignore_contains, view, filtermap)

                    next_node = getReferences(node, ignore_contains, view, filter, reverse=True)
                    for n in next_node:
                        if (node, n['obj']) not in edges and (n['obj'], node) not in edges:
                            rd = PowerReports.ReportData(self)
                            rd["subj_desc"] = PowerReports.MakeReportURL(n['obj'])
                            rd["obj_desc"] = PowerReports.MakeReportURL(node)
                            rd["linktype_name"] = n['via'].linktype_name
                            status = getattr(node, "act_value",
                                             getattr(node, "joined_status_name", ""))
                            rd["status"] = status
                            rd["cdbxml_level"] = int(radius)
                            edges.append((n['obj'], node))
                            if n['obj'] not in visited:
                                walk(n['obj'], radius, ignore_contains, view, filtermap)

            if config.view_name:
                walk(subj, radius=0,
                     ignore_contains=config.ignore_contains,
                     view=config.view_name,
                     filtermap=f)
            else:
                walk(subj, radius=0,
                     ignore_contains=True,
                     view=None,
                     filtermap=f)
        return result


class CatalogSemanticObjectsContent(gui.CDBCatalogContent):
    def __init__(self, catalog):
        tabdefname = "cdb_class_brows_flat"
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        gui.CDBCatalogContent.__init__(self, tabdef)
        self.data = None
        self._initData()

    def _initData(self):
        if self.data is None:
            sls = SemanticLinkType.Query("invalid = 0").Execute()
            clnames = list(set(
                sls.subject_object_classname + sls.object_object_classname))
            self.data = sqlapi.RecordSet2("switch_tabelle", "classname in ('%s')" % "','".join(clnames))

    def getNumberOfRows(self):
        return len(self.data)

    def getRowObject(self, row):
        self._initData()
        keys = mom.SimpleArgumentList()
        for keyname in self.cdef.getKeyNames():
            keys.append(mom.SimpleArgument(keyname, self.data[row][keyname]))
        return mom.CDBObjectHandle(self.cdef, keys, False, True)


class CatalogSemanticObjects(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):
        self.setResultData(CatalogSemanticObjectsContent(self))


class MissingRequirementLinksHeader(PowerReports.CustomDataProvider):
    """ Dataprovider for the Header of missing RQMSRequirement Semantic Links """
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1
    XSDSchemaItems = {
          "mapped_discipline_en": (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__),
          "missing_rep_weight": (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__),
          "mapped_priority_en": (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__),
          "mapped_category_en": (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__),
          "mapped_discipline_de": (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__),
          "mapped_priority_de": (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__),
          "mapped_category_de": (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__),
          "missing_rep_parent_object_id": (sqlapi.SQL_CHAR, ""),
          "specification_object_id": (sqlapi.SQL_CHAR, RQMSpecObject.__maps_to__),
          "links": (sqlapi.SQL_CHAR, ""),
          "objects": (sqlapi.SQL_CHAR, "")
    }

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        for attr, (sqlType, _tableName) in self.XSDSchemaItems.items():
            schema.add_attr(attr, sqlType)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        rr = PowerReports.ReportData(self)
        rr["links"] = source_args["links"]
        rr["objects"] = source_args["object_names"]
        if "missing_rep_priority" in source_args and source_args["missing_rep_priority"]:
            priority = RequirementPriority.ByKeys(source_args["missing_rep_priority"])
            if priority:
                localized_fields = priority.GetLocalizedValues("ml_name")
                for lang, val in localized_fields.items():
                    if val is not None:
                        rr["mapped_priority_" + lang] = val
        for k, v in source_args.items():
            if k in ["types", "links",
                     "cdbxml_rep_exec_type",
                     "cdbxml_report_format",
                     "cdbxml_report_lang"]:
                continue
            else:
                rr[k] = v
        if rr["missing_rep_parent_object_id"]:
            rr["missing_rep_parent_object_id"] = PowerReports.MakeReportURL(RQMSpecObject.ByKeys(rr["missing_rep_parent_object_id"]))
        obj = parent_result.getObject()
        obj.Reload()
        if isinstance(obj, RQMSpecification):
            rr["specification_object_id"] = PowerReports.MakeReportURL(obj)
        elif isinstance(obj, RQMSpecObject):
            rr["specification_object_id"] = PowerReports.MakeReportURL(obj.Specification)
        return rr


class MissingRequirementLinks(RequirementOverview):
    """ Dataprovider for the Header of missing RQMSRequirement Semantic Links """
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        for attr, (sqlType, _tableName) in self.XSDSchemaItems.items():
            schema.add_attr(attr, sqlType)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        """
            Gets hierarchical requirement data depending on DBMS type
        """
        if isinstance(parent_result, PowerReports.ReportData):
            obj = parent_result.getObject()
            obj.Reload()
            return self._getReportData(obj, source_args)
        return PowerReports.ReportDataList(self)

    def _getReportData(self, obj, source_args):
        results = PowerReports.ReportDataList(self)

        classes = source_args["types"]
        links = source_args["links"]
        if not (classes or links):
            return results

        f = {"classes": classes.split(";"),
             "links": links.split("/")}

        query = {}
        has_additional_source_args = False
        dialog_field_prefix = "missing_rep_"
        for k, v in source_args.items():
            if k.startswith(dialog_field_prefix) and v:
                has_additional_source_args = True
                # dialog fields have to be dialog_field_prefix + attribute name
                query[k.replace(dialog_field_prefix, "")] = v

        preqs = []
        rs = self.getHierarchicalStructure(obj, sqlapi.SQLdbms())
        if has_additional_source_args:
            filtered_column_list = None
            for r in rs:
                if filtered_column_list is None:
                    filtered_column_list = [c for c in query if c in r]
                if not filtered_column_list:
                    preqs = rs
                    LOG.warning("Failed to filter view for columns: %s", [c for c in query if c not in r])
                    break
                found = False
                for k, v in query.items():
                    if k in r and str(r[k]) == str(v):
                        found = True
                if found:
                    preqs.append(r)
        else:
            preqs = rs
        specification_object_id = (
            obj.specification_object_id if hasattr(obj, 'specification_object_id') else obj.cdb_object_id
        )
        long_text_cache, variable_values_by_id = get_richtext_caches(
            record_set=rs, specification_object_id=specification_object_id
        )
        for req in preqs:
            query_links = "subject_object_id = '%s'" % req.cdb_object_id
            if classes:
                query_links += " and object_object_classname in ('%s')" % "','".join(f["classes"])
            if links:
                query_links += " and linktype_name in ('%s')" % "','".join(f["links"])
            sls = sqlapi.RecordSet2("cdb_semantic_link_v", query_links, access="read")
            if not sls:
                rd = PowerReports.ReportData(self, req)
                rd["req_hyperlink"] = self.MakeURLWithoutObj("cdbrqm_spec_object",
                                                             "cdbrqm_spec_object",
                                                             "CDB_ShowObject",
                                                             0,
                                                             req.specobject_id,
                                                             {"cdb_object_id": req.cdb_object_id})
                rd["is_defined"] = 'x' if rd["is_defined"] == 1 else ' '
                rd["chapter"] = " " + rd["chapter"]
                attribute_values = get_richtext_attribute_values_from_record(
                    record=req, long_text_cache=long_text_cache, variable_values_by_id=variable_values_by_id
                )
                add_richtext_descriptions_to_report_data(attribute_values, report_data=rd)
                results.append(rd)
        return results
