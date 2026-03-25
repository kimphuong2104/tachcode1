# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import collections
import datetime
import gc
import logging
import os
import re
import sys
import uuid
from html import unescape

import cdbwrapc
from cdb import sqlapi, typeconversion, ue, util
from cdb.dberrors import DBError
from cdb.lru_cache import lru_cache
from cdb.objects import ByID, fields
from cdb.objects.cdb_file import CDB_File
from cdb.objects.core import ClassRegistry
from cdb.objects.expressions import Expression, Literal, MultiLiteral
from cdb.platform import mom
from cdb.platform.gui import (BrowserAttribute, CDBCatalog, CDBCatalogContent,
                              ColorDefinition, Languages, PythonColumnProvider)
from cdb.platform.mom.fields import DDField, IsoLangList
from cdb.platform.olc import StateDefinition
from cdbwrapc import I18nCatalogEntry, unescape_string
from cs.classification.object_classification import ClassificationData
from cs.classification.classes import ClassPropertyValuesView
from cs.metrics.qualitycharacteristics import (ObjectQualityCharacteristic,
                                               QCDefinition)
from cs.tools.semanticlinks import LinkGraphConfig, SemanticLink

#
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
LOG = logging.getLogger(__name__)
__qc_fulfillment_def = None
__qc_targetstatus_lut__ = None

RQM_DEFAULT_LINK_GRAPH_CONFIGURATION = "RQMSemanticLinkGraph"


def is_ctx_from_web(ctx):
    try:
        return bool(int(ctx.sys_args.uses_web_ui))
    except (KeyError, AttributeError, TypeError, ValueError):
        return False


def get_rqm_linkgraph_url(root_object_id):
    config = LinkGraphConfig.KeywordQuery(name=RQM_DEFAULT_LINK_GRAPH_CONFIGURATION)[0].cdb_object_id
    return "/cs-tools-semanticlinks-linkgraph/?config_id=%s&root=%s&radius=1" % (config,
                                                                                 root_object_id)


class TriStateBoolCatalog(CDBCatalog):

    # workaround for E042949
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        from cdb import util
        result = []
        result.append(I18nCatalogEntry("1", util.get_label("cdbrqm_yes")))
        result.append(I18nCatalogEntry("0", util.get_label("cdbrqm_no")))
        return result


class AttrTypeCatalog(CDBCatalog):

    def handleSelection(self, selected_objects):
        # We can't handle multiple objects
        if len(selected_objects) > 1:
            return
        if selected_objects:
            selected_object = selected_objects[0]
        else:
            selected_object = None
        if selected_object is not None:
            affected_fields = BrowserAttribute.KeywordQuery(katalog=self.getCatalogName(),
                                                            attrib="mapped_classname")
            if selected_object.cdb_classname == 'cdbdd_predefined_field':
                pre_attr = DDField.ByKeys(classname=selected_object.predefined_field_clsname,
                                          field_name=selected_object.predefined_field_name)
                if pre_attr is not None:
                    for field in affected_fields:
                        self.setValue(field.maskenfeld_attrib, pre_attr.mapped_classname.lower())

            elif selected_object.cdb_classname == 'cdbdd_virtual_field':
                for field in affected_fields:
                    self.setValue(field.maskenfeld_attrib, selected_object.virtual_field_type.lower())
            else:
                for field in affected_fields:
                    value = selected_object.mapped_classname.lower()
                    if hasattr(selected_object, 'content_type') and selected_object.content_type == "XHTML":
                        value = selected_object.content_type.lower()
                    self.setValue(field.maskenfeld_attrib, value)


def _get_color_definition(status, objektart):
    coldef = ColorDefinition.ByState(status, objektart)
    if coldef is not None and not coldef.CheckAccess("read"):
        coldef = None
    return coldef


def _load_globals(force_reload=False):
    global __qc_fulfillment_def
    if __qc_fulfillment_def is None or force_reload:
        qcd = QCDefinition.ByKeys(identifier="TF")
        if qcd is not None:
            __qc_fulfillment_def = qcd
        else:
            __qc_fulfillment_def = None


def get_state_txt(status, objektart):
    required_state = StateDefinition.ByKeys(statusnummer=status,
                                            objektart=objektart)
    if not required_state:
        LOG.error('Invalid status (%s) or objektart (%s)', status, objektart)
        raise ValueError()
    return required_state.StateText['']


def isValidFloat(val, valid_range=None):
    try:
        fval = float(val)
        if valid_range is not None and len(valid_range) == 2:
            if fval < valid_range[0] or fval > valid_range[1]:
                return False
        return True
    except (TypeError, ValueError):
        return False


def getQCFulfillmentDef(force_reload=False):
    _load_globals(force_reload)
    return __qc_fulfillment_def


def isValidFulfillmentDef(qcd):
    if qcd is not None:
        return qcd.status == qcd.VALID.status
    else:
        return False


def activateFulfillmentDef():
    qcd = getQCFulfillmentDef()
    if qcd and qcd.CheckAccess('qc_state_change') and not qcd.status == qcd.VALID.status:
        qcd.ChangeState(qcd.VALID.status)


def deactivateFulfillmentDef():
    qcd = getQCFulfillmentDef()
    if qcd and qcd.CheckAccess('qc_state_change') and not qcd.status == qcd.CREATED.status:
        qcd.ChangeState(qcd.CREATED.status)


def getFulfillmentQC(obj):
    if obj is not None and hasattr(obj, 'cdb_object_id'):
        obj_id = obj.cdb_object_id
    else:
        return None
    qcd = getQCFulfillmentDef()
    if qcd is not None and obj_id:
        args = {"cdbf_object_id": obj_id,
                "cdbqc_def_object_id": qcd.cdb_object_id}
        qc = ObjectQualityCharacteristic.ByKeys(**args)
        if qc is not None and qc.CheckAccess("read"):
            return qc
        else:
            return None


def _get_fulfillment_state(obj):
    qc = getFulfillmentQC(obj)
    if qc and qc.target_fulfillment is not None:
        return qc.target_fulfillment


def getTrafficLight(obj):
    fulfillment = _get_fulfillment_state(obj)
    if fulfillment is not None:
        if fulfillment == get_target_processor_status_enum_identifier("not_given"):  # default empty traffic light
            color = 3
        elif fulfillment == get_target_processor_status_enum_identifier("green"):
            color = 0  # green traffic light
        elif fulfillment == get_target_processor_status_enum_identifier("yellow"):
            color = 1  # orange/yellow traffic light
        elif fulfillment == get_target_processor_status_enum_identifier("red"):
            color = 2  # red traffic light
    else:
        color = 3  # not given if no fulfillment state exists
    return color


def createQC(**kwargs):
    """
    kwargs should at least have:

    cdbf_object_id (cdb_object_id of Object for which the QC should be created)
    classname (classname of the object for which the QC should be created)
    """
    definition = None
    qc = None
    if "cdbqc_def_object_id" not in kwargs.keys():
        definition = getQCFulfillmentDef()
        kwargs.update({"cdbqc_def_object_id": definition.cdb_object_id})
    if '__force_creation__' not in kwargs:
        qc = ObjectQualityCharacteristic.ByKeys(**kwargs)
    if qc is None or '__force_creation__' in kwargs:
        if '__force_creation__' in kwargs:
            del kwargs['__force_creation__']
        kwargs.update(ObjectQualityCharacteristic.MakeChangeControlAttributes())
        if "cdbqc_def_object_id" in kwargs.keys() and definition is None:
            definition = QCDefinition.ByKeys(kwargs["cdbqc_def_object_id"])
        if definition:
            kwargs.update(subject_id=definition.subject_id,
                          subject_type=definition.subject_type,
                          target_value=definition.default_target_value
                          if 'target_value' not in kwargs else kwargs['target_value'])
        qc = ObjectQualityCharacteristic.Create(**kwargs)
    return qc


def _add_semlinks(source, semlinks_to_create, processed_objs, dest):
    if hasattr(source, 'SemanticLinks'):
        subject_sem_links = source.SemanticLinks
        for sem_link in subject_sem_links:
            if sem_link.object_object_id not in processed_objs:
                sem_link_to_be_created = {"source": source.cdb_object_id,
                                          "subject": dest.cdb_object_id,
                                          "link_type": sem_link.link_type_object_id,
                                          "subject_clsn": dest.GetClassname(),
                                          "object_clsn": sem_link.object_object_classname,
                                          "object": sem_link.object_object_id}
                if sem_link.object_object_id in semlinks_to_create:
                    semlinks_to_create[sem_link.object_object_id].append(sem_link_to_be_created)
                else:
                    semlinks_to_create[sem_link.object_object_id] = [sem_link_to_be_created]


def _create_semlinks(dest, semlinks_to_create, processed_objs, source):
    if hasattr(source, 'SemanticLinks'):
        semlinks_created = {}
        subject_sem_links = source.SemanticLinks
        for sem_link in subject_sem_links:
            if sem_link.object_object_id in processed_objs:
                args = {"subject_object_id": dest.cdb_object_id,
                        "object_object_id": processed_objs[sem_link.object_object_id]["dest"],
                        "subject_object_classname": dest.GetClassname(),
                        "object_object_classname": processed_objs[sem_link.object_object_id]["dest_clsn"]}
                change_control_values = sem_link.MakeChangeControlAttributes()
                args.update(change_control_values)
                created_sem_link = sem_link.Copy(**args)
                semlinks_created[created_sem_link.object_object_id] = created_sem_link

        if source.cdb_object_id in semlinks_to_create:
            sem_links = semlinks_to_create[source.cdb_object_id]
            for sem_link in sem_links:
                args = {"subject_object_id": sem_link["subject"],
                        "link_type_object_id": sem_link["link_type"],
                        "object_object_id": dest.cdb_object_id,
                        "object_object_classname": dest.GetClassname(),
                        "subject_object_classname": sem_link["subject_clsn"]}
                if sem_link["subject"] in semlinks_created:
                    args.update({"mirror_link_object_id": semlinks_created[sem_link["subject"]].cdb_object_id})
                change_control_values = SemanticLink.MakeChangeControlAttributes()
                args.update(change_control_values)
                created_sem_link = SemanticLink.Create(**args)
                if sem_link["subject"] in semlinks_created:
                    pmirror = semlinks_created[sem_link["subject"]].getPersistentObject()
                    pmirror_args = {"mirror_link_object_id": created_sem_link.cdb_object_id}
                    pmirror_args.update(change_control_values)
                    pmirror.Update(**pmirror_args)
            semlinks_to_create.pop(source.cdb_object_id)


def get_last_state_protocol_entry(state_protocol_type, cdb_object_id):
    last_state_protocol_entry = None
    state_protocol_entries = state_protocol_type.KeywordQuery(cdbparentobjectid=cdb_object_id,
                                                              order_by="cdbprot_zaehler")
    if len(state_protocol_entries) > 0:
        last_state_protocol_entry = state_protocol_entries[-1]
    return last_state_protocol_entry


def _get_source_object(obj, ctx, entity=None, source_obj=None):
    src_cdb_object_id = None
    if source_obj is not None:
        return source_obj
    if ctx and ctx.dragged_obj:
        src_cdb_object_id = ctx.dragged_obj.cdb_object_id
    elif ctx and ctx.cdbtemplate:
        src_cdb_object_id = ctx.cdbtemplate["cdb_object_id"]
    elif ctx.action != "create":
        return obj
    if src_cdb_object_id is not None:
        if entity is not None:
            return entity.ByKeys(src_cdb_object_id)
        else:
            return ByID(src_cdb_object_id)
    else:
        return None


def _update_position_cache(importer, args, entity, obj=None, afterOperation=False):
    from cs.requirements import RQMSpecObject, TargetValue
    position_number_cache = importer.position_number_cache
    tree_down_context = importer.current_target_specification_tree_ctx
    if tree_down_context and 'db_only_position_cache' not in tree_down_context:
        # just init once
        if importer.specObjectsById is not None:
            reqif_cache = tree_down_context.get('reqif_cache')
            position_cache = tree_down_context.get('position_cache')
            all_db_reqif_ids = set(reqif_cache.keys())
            all_reqif_ids_to_import = set(importer.specObjectsById.keys())
            all_reqif_ids_in_booth = all_db_reqif_ids.intersection(all_reqif_ids_to_import)
            all_db_only_reqif_ids = all_db_reqif_ids.difference(all_reqif_ids_in_booth)
            only_db_object_ids = set([
                reqif_cache.get(x) for x in all_db_only_reqif_ids if x != '__empty__'
            ])
            # elements with empty reqif id are definitely only in db
            only_db_object_ids = only_db_object_ids.union(reqif_cache.get('__empty__'))
            db_only_position_cache = collections.defaultdict(dict)
            for parent_id, child_positions in position_cache.items():
                db_only_position_cache[parent_id] = set(
                    [v for (k, v) in child_positions.items() if k in only_db_object_ids]
                )
            tree_down_context['db_only_position_cache'] = db_only_position_cache

    new_position = 1
    parent_id = None
    if entity.__maps_to__ == RQMSpecObject.__maps_to__:
        parent_id = args.get(
            'parent_object_id',
            obj.parent_object_id if obj is not None else None
        )
        position_attribute_name = 'position'
    elif entity.__maps_to__ == TargetValue.__maps_to__:
        parent_id = args.get(
            'requirement_object_id',
            obj.requirement_object_id if obj is not None else None
        )
        position_attribute_name = 'pos'
    else:
        return  # Specifications do not have parents
    if parent_id is None:
        parent_id = ''  # top level elements

    if afterOperation:
        # update next position to use for this parent after op
        position_number_cache[entity.__maps_to__][parent_id] += 1
    else:
        if parent_id not in position_number_cache[entity.__maps_to__]:
            # init next position to default when not initialized yet
            position_number_cache[entity.__maps_to__][parent_id] = new_position
        # prepare operation args before the operation
        new_position_number = position_number_cache[entity.__maps_to__][parent_id]

        # ensure unique position ids but keep external sortation stable
        existent_positions = tree_down_context['db_only_position_cache'][parent_id]
        while new_position_number in existent_positions:
            position_number_cache[entity.__maps_to__][parent_id] += 1
            new_position_number = position_number_cache[entity.__maps_to__][parent_id]
        args.update({position_attribute_name: new_position_number})


def get_ue_arg_key_or_default_value(ctx, key, default_value):
    if ctx and hasattr(ctx, "ue_args"):
        if key in ctx.ue_args.get_attribute_names():
            return ctx.ue_args[key]
    return default_value


def get_target_processor_status_enum_identifier(state_name):
    from cs.metrics.targetprocessor import TargetStatus
    global __qc_targetstatus_lut__
    if __qc_targetstatus_lut__ is None:
        __qc_targetstatus_lut__ = {
            state_name: getattr(TargetStatus, state_name).value
            if hasattr(getattr(TargetStatus, state_name), 'value') else getattr(TargetStatus, state_name).index
            for state_name in ['not_given', 'green', 'yellow', 'red']
        }
    return __qc_targetstatus_lut__.get(state_name)


def strip_tags(xhtml):
    import re
    matcher = re.compile('<[^<]+?>')
    try:
        text = matcher.sub('', xhtml)
    except UnicodeDecodeError as e:
        LOG.exception(e)
        LOG.error('UnicodeDecodeError: %s', xhtml.encode('base64'))
        raise
    return unescape(text)


def get_content_types_by_classname(classname):
    import cdbwrapc
    cdef = cdbwrapc.CDBClassDef(classname)
    if cdef:
        return {adef.getName(): adef.getContentType() for adef in cdef.getAttributeDefs()}
    else:
        return None


def get_short_title_from_richtext(field_length, richtext):
    from cs.requirements.richtext import RichTextModifications
    richtext = RichTextModifications.remove_variables(xhtml_text=richtext)
    first_line = richtext.split('</xhtml:div>')[0]
    first_line = first_line.split('<xhtml:br/>')[0]
    cleartext = strip_tags(first_line)
    if cleartext:
        if len(cleartext) <= field_length:
            return cleartext
        else:
            return cleartext[:field_length - 3].rstrip() + "..."
    return ""


def createUniqueIdentifier():
    """
    Creates a unique identifier string based on python's UUID generation.

    As the ReqIF Schema requests ID fields with data type xsd:ID these IDs
    have to be start with an underscore or alphabetic character but not with
    a digit. Therefore the function returns the generated UUID with a special
    alphabetic prefix.

    Examples:
    >>> createUniqueIdentifier()[:4] # check first 4 characters are the prefix
    'cdb-'

    >>> import re
    >>> p=re.compile('([cdb-]{4}[\\w\\d]{8}-[\\w\\d]{4}-[\\w\\d]{4}-[\\w\\d]{4}-[\\w\\d]{12})')
    >>> m = p.match(createUniqueIdentifier())
    >>> len(m.group())                # check regex match length
    40
    """
    return 'cdb-%s' % uuid.uuid4()


def update_url_query_args(url, query_args):
    from urllib import parse
    parsed_url = urllib.parse.urlparse(url)
    query = parsed_url.query
    url_parts = list(parsed_url)
    query = dict(urllib.parse.parse_qsl(query))
    query.update(query_args)
    query = urlencode(query)
    url_parts[4] = query
    new_url = urllib.parse.urlunparse(url_parts)
    return new_url


def cleanup_file_path(file_path, logger=None):
    if os.path.isfile(file_path):
        if sys.platform == 'win32':
            error_classes = (OSError, WindowsError)  # NOSONAR
        else:
            error_classes = (OSError)
        try:
            os.remove(file_path)
            return True
        except error_classes as e:
            if logger is not None:
                logger.exception(e)
            return False


def date_to_str(dt):
    if isinstance(dt, datetime.date):
        return typeconversion.to_legacy_date_format(dt)
    return dt


@lru_cache()
def get_audittrail_config_for_rqm():
    from cs.audittrail import AuditTrailConfigField
    from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
    return {
        clsn: [
            x.field_name for x in AuditTrailConfigField.KeywordQuery(classname=clsn)
        ] for clsn in
        [
            RQMSpecification.__classname__, RQMSpecObject.__classname__, TargetValue.__classname__
        ]
    }


APPLICATION_LANGUAGES_LIST_ID = '1eca06cf-3033-11e5-89a4-f0def133d0a6'


@lru_cache()
def get_language_list(language_list_id=None):
    if language_list_id is None:
        language_list_id = APPLICATION_LANGUAGES_LIST_ID
    languages = []
    language_list = IsoLangList.ByKeys(cdb_object_id=language_list_id)
    if language_list:
        languages = set(language_list.iso_languages.split(','))
    else:
        languages = set()
    return languages


class FilteredLanguagesCatalogContent(CDBCatalogContent):
    """ Catalog which provides a list languages filtered by a language list """

    def __init__(self, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        self.language_list_id = catalog.language_list_id
        self.filtered_languages = None
        self._load_filtered_languages()

    def _load_filtered_languages(self):
        if self.filtered_languages is None:
            self._languages_in_list = get_language_list(self.language_list_id)
            self.filtered_languages = Languages.KeywordQuery(iso_code=self._languages_in_list)

    def handlesI18nEnumCatalog(self):
        return True

    def getNumberOfRows(self):
        return len(self.filtered_languages)

    def getRowObject(self, row):
        self._load_filtered_languages()
        keys = mom.SimpleArgumentList()
        for keyname in self.cdef.getKeyNames():
            keys.append(mom.SimpleArgument(keyname, self.filtered_languages[row][keyname]))
        return mom.CDBObjectHandle(self.cdef, keys, False, True)


class FilteredLanguagesCatalog(CDBCatalog):

    def __init__(self, language_list_id):
        CDBCatalog.__init__(self)
        self.language_list_id = language_list_id

    def init(self):
        self.setResultData(FilteredLanguagesCatalogContent(self))


class ApplicationLanguagesCatalog(FilteredLanguagesCatalog):

    def __init__(self):
        FilteredLanguagesCatalog.__init__(self, APPLICATION_LANGUAGES_LIST_ID)


@lru_cache()
def get_diff_tag_for_classname(classname):
    from cdb.platform.gui import Message
    from cdb.objects.core import parse_raw
    dtag = ""
    msg = Message.ByKeys('{}_diff_dtag'.format(classname))
    if msg:
        dtag = msg.Text['']
        dtag = parse_raw(dtag)
    if not dtag:
        dtag = '%(system:description)s'  # take the normal object description if nothing special is configured
    return dtag


class _AttributeAccessor:

    def __init__(self, clazz, obj_dict):
        self.clazz = clazz
        self.obj_dict = obj_dict

    def __getitem__(self, name):
        if name == 'system:description':
            return self.obj_dict[name]
        fd = self.clazz.GetFieldByName(name)
        if isinstance(fd, fields.MultiLangAttributeDescriptor):
            fd = fd.getLanguageField()
        v = self.obj_dict[name]
        return v if v is not None else u""


class DescriptionColumnProvider(PythonColumnProvider):
    @staticmethod
    def getColumnDefinitions(classname, query_args):
        return [
            {
                'column_id': "description",
                'data_type': 'text',
                'label': util.get_label('cdbrqm_diff_description_column_label'),
            }
        ]

    @staticmethod
    def getColumnData(classname, table_data):
        result = []
        if classname is not None:
            return result
        for row_dict in table_data:
            clazz = ClassRegistry().findByClassname(row_dict['system:classname'])
            desc_pattern = get_diff_tag_for_classname(row_dict['system:classname'])
            result.append({
                'description': desc_pattern % _AttributeAccessor(clazz, row_dict)
            })
        return result


class DiffIndicatorColumnProvider(PythonColumnProvider):

    @staticmethod
    def getColumnDefinitions(classname, query_args):
        return [
            {
                'column_id': "diff_indicator",
                'data_type': 'icon',
            }
        ]


def get_long_text_cache(entity, cdb_object_ids):
    cache = collections.defaultdict(dict)
    for table_name in entity.GetTextFieldNames():
        stmt = 'SELECT * FROM {table_name} WHERE {condition} ORDER BY cdb_object_id, zeile'
        stmt = stmt.format(
            table_name=table_name, condition=entity.cdb_object_id.one_of(*cdb_object_ids))
        rs2 = sqlapi.RecordSet2(sql=stmt)
        for row in rs2:
            cdb_object_id = row['cdb_object_id']
            if cdb_object_id not in cache[table_name]:
                cache[table_name][cdb_object_id] = row['text']
            else:
                cache[table_name][cdb_object_id] += row['text']
    unescape_strings_cache = collections.defaultdict(dict)
    for table_name in cache:
        for cdb_object_id in cache[table_name]:
            unescape_strings_cache[table_name][cdb_object_id] = unescape_string(
                cache[table_name][cdb_object_id]
            )
    cache = None
    return unescape_strings_cache


def load_classification_cache(cdb_object_ids):
    res, _ = ClassificationData.load_data(
        object_ids=cdb_object_ids,
        narrowed=True,
        request=None,
        calc_checksums=False
    )
    return res


def load_classification_cache_by_id(cdb_object_ids):
    classification_cache = {}
    oid_pos = 0
    classification_data = load_classification_cache(list(cdb_object_ids))
    for oid in cdb_object_ids:
        classification_cache[oid] = classification_data[oid_pos]
        oid_pos += 1
    return classification_cache


def get_file_obj_cache_by_object_id(cdbf_object_ids):
    file_obj_ids = CDB_File.Query(
        CDB_File.cdbf_object_id.one_of(*cdbf_object_ids)
    ).cdb_object_id
    file_objs = [
        CDB_File._FromObjectHandle(v) for (v) in mom.getObjectHandlesFromObjectIDs(
            file_obj_ids, True, True
        ).values()
    ]
    result = collections.defaultdict(list)
    for f in file_objs:
        result[f.cdbf_object_id].append(f)
    return result


class RQMHierarchicals(object):

    @classmethod
    def _update_sortorder_ORACLE(cls, obj):
        HierarchicalMerge = """
            MERGE INTO cdbrqm_spec_object s
            USING
            (
                SELECT
                    so.cdb_object_id, so.sortorder_new, so.chapter_new
                FROM (
                    SELECT
                           ROWNUM rownr, LEVEL stufe, SYS_CONNECT_BY_PATH(LPAD(TO_CHAR(position), 5, 0), '/') sortorder_new,
                           LTRIM(SYS_CONNECT_BY_PATH(position, '.'), '.') chapter_new,
                           cdb_object_id, parent_object_id, specification_object_id, sortorder, position
                    FROM   cdbrqm_spec_object
                    START WITH specification_object_id = '{specification_object_id}' AND parent_object_id in ('',chr(1))
                    CONNECT BY NOCYCLE parent_object_id = PRIOR cdb_object_id
                    ORDER BY sortorder_new
                  ) so, cdbrqm_spec_object ts
                WHERE ts.cdb_object_id = so.cdb_object_id
                ORDER BY sortorder_new
            ) h
            ON(s.cdb_object_id = h.cdb_object_id)
            WHEN MATCHED THEN UPDATE SET
            s.sortorder = h.sortorder_new,
            s.chapter = h.chapter_new
            """.format(specification_object_id=obj.cdb_object_id)
        sqlapi.SQL(HierarchicalMerge)

    @classmethod
    def _update_sortorder_MSSQL(cls, obj):
        RecursiveCTEUpdate = """
            WITH Hierarchical
            AS (
                SELECT so.cdb_object_id, so.sortorder,
                        RIGHT('00000' + CAST(position AS varchar(max)),5) AS sortorder_new,
                        CAST(ROW_NUMBER() OVER (ORDER BY position) AS varchar(max)) AS chapter_new
                FROM   cdbrqm_spec_object so
                WHERE specification_object_id = '{specification_object_id}' AND parent_object_id = ''
                UNION ALL
                SELECT so.cdb_object_id, so.sortorder,
                        h.sortorder_new + CAST('/' AS varchar(max)) +
                                   RIGHT('00000' + CAST(so.position AS varchar(max)),5) AS sortorder_new,
                        h.chapter_new + CAST('.' AS varchar(max)) +
                                   CAST(ROW_NUMBER() OVER (ORDER BY position) AS varchar(max)) AS chapter_new
                FROM   cdbrqm_spec_object AS so
                INNER JOIN Hierarchical AS h ON h.cdb_object_id = so.parent_object_id
                )
            UPDATE so SET sortorder = h.sortorder_new, chapter = h.chapter_new
            FROM cdbrqm_spec_object so
            JOIN Hierarchical h ON h.cdb_object_id = so.cdb_object_id
            WHERE specification_object_id = '{specification_object_id}'
            """.format(specification_object_id=obj.cdb_object_id)
        sqlapi.SQL(RecursiveCTEUpdate)

    @classmethod
    def _update_sortorder_SQLITE(cls, obj):
        RecursiveUpdate = """
            WITH RECURSIVE hierarchical(cdb_object_id, parent_object_id, sortorder_new, chapter_new)
            AS (
                SELECT sp.cdb_object_id, sp.parent_object_id, SUBSTR('00000' || CAST(sp.position AS text), -5, 5),
                position AS chapter_new
                FROM cdbrqm_spec_object sp
                WHERE sp.specification_object_id = '{specification_object_id}' AND sp.parent_object_id = ''
                UNION ALL
                SELECT sc.cdb_object_id, sc.parent_object_id, sortorder_new || '/' ||
                    SUBSTR('00000' || CAST(sc.position AS text), -5, 5),
                    chapter_new || '.' || sc.position AS chapter_new
                FROM cdbrqm_spec_object sc
                JOIN hierarchical ON hierarchical.cdb_object_id = sc.parent_object_id
                )
            UPDATE cdbrqm_spec_object SET sortorder = (
                SELECT sortorder_new FROM hierarchical WHERE cdbrqm_spec_object.cdb_object_id = hierarchical.cdb_object_id
            ), chapter = (
                SELECT chapter_new FROM hierarchical WHERE cdbrqm_spec_object.cdb_object_id = hierarchical.cdb_object_id
            )
            WHERE specification_object_id = '{specification_object_id}'
            """.format(specification_object_id=obj.cdb_object_id)
        sqlapi.SQL(RecursiveUpdate)

    @classmethod
    def _update_sortorder_POSTGRES(cls, obj):
        RecursiveUpdate = """
                WITH RECURSIVE hierarchical(cdb_object_id, parent_object_id, sortorder_new, chapter_new)
                AS (
                    SELECT sp.cdb_object_id, sp.parent_object_id, RIGHT(CONCAT('00000' || sp.position), 5),
                    CAST(sp.position AS varchar) AS chapter_new
                    FROM cdbrqm_spec_object sp
                    WHERE sp.specification_object_id = '{specification_object_id}' AND sp.parent_object_id = ''
                    UNION ALL
                    SELECT sc.cdb_object_id, sc.parent_object_id, sortorder_new || '/' ||
                        RIGHT(CONCAT('00000' || sc.position), 5),
                        chapter_new || '.' || CAST(sc.position AS varchar) AS chapter_new
                    FROM cdbrqm_spec_object sc
                    JOIN hierarchical ON hierarchical.cdb_object_id = sc.parent_object_id
                    )
                UPDATE cdbrqm_spec_object SET sortorder = (
                    SELECT sortorder_new FROM hierarchical WHERE cdbrqm_spec_object.cdb_object_id = hierarchical.cdb_object_id
                ), chapter = (
                    SELECT chapter_new FROM hierarchical WHERE cdbrqm_spec_object.cdb_object_id = hierarchical.cdb_object_id
                )
                WHERE specification_object_id = '{specification_object_id}'
                """.format(specification_object_id=obj.cdb_object_id)
        sqlapi.SQL(RecursiveUpdate)

    @classmethod
    def update_sortorder(cls, obj):
        DBDependentUpdate = {
            sqlapi.DBMS_ORACLE: cls._update_sortorder_ORACLE,
            sqlapi.DBMS_MSSQL: cls._update_sortorder_MSSQL,
            sqlapi.DBMS_SQLITE: cls._update_sortorder_SQLITE,
            sqlapi.DBMS_POSTGRES: cls._update_sortorder_POSTGRES
        }
        DBType = sqlapi.SQLdbms()
        # due to E036143
        try:
            DBDependentUpdate.get(DBType, cls._update_sortorder_SQLITE)(obj)
        except DBError as ex:
            if ex.code != 1:
                raise ex

    @classmethod
    def _getObjectIdsRecursiveQuery_SQLITE(cls, cdb_object_id):
        return """WITH RECURSIVE hierarchical(cdb_object_id)
                AS (
                    SELECT sp.cdb_object_id
                    FROM cdbrqm_spec_object sp
                    WHERE cdb_object_id = '{cdb_object_id}'
                    UNION ALL
                    SELECT sc.cdb_object_id
                    FROM cdbrqm_spec_object sc
                    JOIN hierarchical ON hierarchical.cdb_object_id = sc.parent_object_id
                    )
                SELECT cdb_object_id, 'RQMSpecObject' AS classname FROM hierarchical
                UNION
                SELECT cdb_object_id, 'RQMTargetValue' AS classname FROM cdbrqm_target_value
                WHERE requirement_object_id IN (SELECT cdb_object_id FROM hierarchical)""".format(
            cdb_object_id=cdb_object_id)

    @classmethod
    def _getObjectIdsRecursiveQuery_MSSQL(cls, cdb_object_id):
        return """WITH Hierarchical
                AS (
                    SELECT so.cdb_object_id
                    FROM   cdbrqm_spec_object so
                    WHERE cdb_object_id = '{cdb_object_id}'
                    UNION ALL
                    SELECT so.cdb_object_id
                    FROM   cdbrqm_spec_object AS so
                    INNER JOIN Hierarchical AS h ON h.cdb_object_id = so.parent_object_id
                    )
                SELECT cdb_object_id, 'RQMSpecObject' AS classname FROM Hierarchical
                UNION
                SELECT cdb_object_id, 'RQMTargetValue' AS classname FROM cdbrqm_target_value
                WHERE requirement_object_id IN (SELECT cdb_object_id FROM Hierarchical)""".format(
            cdb_object_id=cdb_object_id)

    @classmethod
    def _getObjectIdsRecursiveQuery_ORACLE(cls, cdb_object_id):
        return """WITH Hierarchical (cdb_object_id)
                AS (
                    SELECT so.cdb_object_id
                    FROM   cdbrqm_spec_object so
                    WHERE cdb_object_id = '{cdb_object_id}'
                    UNION ALL
                    SELECT so.cdb_object_id
                    FROM   cdbrqm_spec_object so
                    INNER JOIN Hierarchical h ON h.cdb_object_id = so.parent_object_id
                    )
                SELECT cdb_object_id, 'RQMSpecObject' AS classname FROM Hierarchical
                UNION
                SELECT cdb_object_id, 'RQMTargetValue' AS classname FROM cdbrqm_target_value
                WHERE requirement_object_id IN (SELECT cdb_object_id FROM Hierarchical)""".format(
            cdb_object_id=cdb_object_id)

    @classmethod
    def getObjectIdsRecursive(cls, obj):
        # get the object ids of the objects below obj

        def _get_recursive_ids(query):
            rs = sqlapi.RecordSet2(sql=query)
            values = {}
            for r in rs:
                values[r.cdb_object_id] = r.classname
            return values

        DBDependentSelect = {
            sqlapi.DBMS_ORACLE: cls._getObjectIdsRecursiveQuery_ORACLE,
            sqlapi.DBMS_MSSQL: cls._getObjectIdsRecursiveQuery_MSSQL,
            sqlapi.DBMS_SQLITE: cls._getObjectIdsRecursiveQuery_SQLITE
        }
        DBType = sqlapi.SQLdbms()
        object_ids = []
        # due to E036143
        try:
            object_ids += _get_recursive_ids(
                DBDependentSelect.get(
                    DBType,
                    cls._getObjectIdsRecursiveQuery_SQLITE
                )(
                    obj.cdb_object_id
                )
            )
        except DBError as ex:
            if ex.code != 1:
                raise ex
        return object_ids

    @classmethod
    def _tree_down_context_ORACLE(cls):
        cte = """WITH hierarchical(
            cdb_object_id,
            parent_object_id,
            specobject_id,
            sortorder,
            is_leaf,
            position,
            reqif_id,
            ce_baseline_object_id,
            ce_baseline_origin_id
        ) AS
        (
            SELECT
                spec_object.cdb_object_id,
                spec_object.parent_object_id,
                spec_object.specobject_id,
                spec_object.sortorder,
                CASE WHEN EXISTS (
                        SELECT 42
                        FROM cdbrqm_spec_object so
                        WHERE spec_object.cdb_object_id=so.parent_object_id
                    )
                THEN 0
                ELSE 1
                END,
                spec_object.position,
                spec_object.reqif_id,
                spec_object.ce_baseline_object_id,
                spec_object.ce_baseline_origin_id
            FROM
                cdbrqm_spec_object spec_object
            WHERE
                spec_object.specification_object_id = '{specification_object_id}' AND
                spec_object.parent_object_id IN ({spec_object_parent_object_id_in})
            UNION ALL
            SELECT
                spec_object_2.cdb_object_id,
                spec_object_2.parent_object_id,
                spec_object_2.specobject_id,
                spec_object_2.sortorder,
                CASE WHEN EXISTS (
                        SELECT 42
                        FROM cdbrqm_spec_object so
                        WHERE spec_object_2.cdb_object_id=so.parent_object_id
                    )
                THEN 0
                ELSE 1
                END,
                spec_object_2.position,
                spec_object_2.reqif_id,
                spec_object_2.ce_baseline_object_id,
                spec_object_2.ce_baseline_origin_id
            FROM cdbrqm_spec_object spec_object_2
            JOIN hierarchical ON spec_object_2.parent_object_id=hierarchical.cdb_object_id ORDER BY sortorder
        )
        SELECT
            cdb_object_id,
            parent_object_id,
            specobject_id,
            sortorder,
            is_leaf,
            position,
            reqif_id,
            ce_baseline_object_id,
            ce_baseline_origin_id
        FROM hierarchical WHERE {spec_object_filter_condition} ORDER by sortorder"""
        return cte

    @classmethod
    def _tree_down_context_MSSQL(cls):
        return cls._tree_down_context_base(recursive=False)
    
    @classmethod
    def _tree_down_context_postgres(cls):
        return cls._tree_down_context_base(recursive=True)

    @classmethod
    def _tree_down_context_base(cls, recursive=False):
        cte = """WITH %s hierarchical(
            cdb_object_id,
            parent_object_id,
            specobject_id,
            sortorder,
            is_leaf,
            position,
            reqif_id,
            ce_baseline_object_id,
            ce_baseline_origin_id
        ) AS
        (
        SELECT
            spec_object.cdb_object_id,
            spec_object.parent_object_id,
            spec_object.specobject_id,
            spec_object.sortorder,
                CASE WHEN EXISTS (
                        SELECT 42
                        FROM cdbrqm_spec_object so
                        WHERE spec_object.cdb_object_id=so.parent_object_id
                    )
                THEN 0
                ELSE 1
                END,
            spec_object.position,
            spec_object.reqif_id,
            spec_object.ce_baseline_object_id,
            spec_object.ce_baseline_origin_id
        FROM
            cdbrqm_spec_object spec_object
        WHERE
            spec_object.specification_object_id = '{specification_object_id}' AND
            spec_object.parent_object_id = '{spec_object_parent_object_id}'
        UNION ALL
        SELECT
            spec_object_2.cdb_object_id,
            spec_object_2.parent_object_id,
            spec_object_2.specobject_id,
            spec_object_2.sortorder,
            CASE WHEN EXISTS (
                    SELECT 42
                    FROM cdbrqm_spec_object so
                    WHERE spec_object_2.cdb_object_id=so.parent_object_id
                )
            THEN 0
            ELSE 1
            END,
            spec_object_2.position,
            spec_object_2.reqif_id,
            spec_object_2.ce_baseline_object_id,
            spec_object_2.ce_baseline_origin_id
        FROM cdbrqm_spec_object spec_object_2
        JOIN hierarchical h ON spec_object_2.parent_object_id=h.cdb_object_id
        )
        SELECT
            cdb_object_id,
            parent_object_id,
            specobject_id,
            sortorder,
            is_leaf,
            position,
            reqif_id,
            ce_baseline_object_id,
            ce_baseline_origin_id
        FROM hierarchical WHERE {spec_object_filter_condition} ORDER by sortorder""" % ("RECURSIVE" if recursive else "")
        return cte

    @classmethod
    def get_tree_down_context(
            cls, specification, parent_object=None, return_objects=True,
            spec_object_ids=None,  # caller needs to ensure that parent ids are also inside this list
            with_file_cache=False,
            with_semantic_link_cache=False  # only where the objects are subject
    ):
        from cs.requirements import RQMSpecObject, TargetValue
        DBDependentQuery = {
            sqlapi.DBMS_ORACLE: cls._tree_down_context_ORACLE,
            sqlapi.DBMS_MSSQL: cls._tree_down_context_MSSQL,
            sqlapi.DBMS_SQLITE: cls._tree_down_context_MSSQL,
            sqlapi.DBMS_POSTGRES: cls._tree_down_context_postgres
        }
        DBType = sqlapi.SQLdbms()
        cte = DBDependentQuery.get(DBType, cls._tree_down_context_MSSQL)()
        qry = cte.format(
            specification_object_id=specification.cdb_object_id,
            spec_object_parent_object_id=parent_object.cdb_object_id if parent_object else '',
            spec_object_parent_object_id_in="'{}'".format(
                parent_object.cdb_object_id) if parent_object else "'',chr(1)",
            spec_object_filter_condition="1=1 AND {}".format(
                RQMSpecObject.cdb_object_id.one_of(*spec_object_ids)
            ) if isinstance(spec_object_ids, list) else "1=1"
        )
        rs2 = sqlapi.RecordSet2(sql=qry)
        ids = []
        for row in rs2:
            ids.append(
                {
                    'cdb_object_id': row['cdb_object_id'],
                    'parent_object_id': row['parent_object_id'],
                    'is_leaf': row['is_leaf'],
                    'position': row['position'],
                    'reqif_id': row['reqif_id'],
                    'ce_baseline_object_id': row['ce_baseline_object_id'],
                    'ce_baseline_origin_id': row['ce_baseline_origin_id']
                }
            )

        spec_object_ids = []
        target_value_ids = []
        target_value_parent_ids = []
        position_cache = collections.defaultdict(dict)
        file_cache = collections.defaultdict(list)
        semantic_link_cache = collections.defaultdict(list)
        file_obj_cache = {}
        file_obj_ids = []
        reqif_cache = {'__empty__': set()}
        ce_baseline_object_id_cache = {}
        ce_baseline_origin_id_cache = {}
        missing_ce_baseline_object_ids = False
        ref_ids = set()
        ref_ids.add(specification.cdb_object_id)
        for x in ids:
            spec_object_id = x.get('cdb_object_id')
            spec_object_ids.append(spec_object_id)
            ref_ids.add(spec_object_id)
            if x.get('is_leaf'):
                target_value_parent_ids.append(x.get('cdb_object_id'))
            if x.get('reqif_id'):
                reqif_cache[x.get('reqif_id')] = x.get('cdb_object_id')
            else:
                reqif_cache['__empty__'].add(x.get('cdb_object_id'))
            if x.get('position', None) is not None:
                position_cache[x.get('parent_object_id')][x.get('cdb_object_id')] = x.get('position')
            if x.get('ce_baseline_object_id'):
                ce_baseline_object_id_cache[x.get('cdb_object_id')] = x.get('ce_baseline_object_id')
            if x.get('ce_baseline_origin_id'):
                ce_baseline_origin_id_cache[x.get('cdb_object_id')] = x.get('ce_baseline_origin_id')
            else:
                missing_ce_baseline_object_ids = True
        stmt = """SELECT cdb_object_id, ce_baseline_object_id FROM cdbrqm_target_value
            WHERE %s ORDER BY pos, targetvalue_id"""
        stmt = stmt % TargetValue.requirement_object_id.one_of(*target_value_parent_ids)
        for tv in sqlapi.RecordSet2(sql=stmt):
            ce_baseline_object_id_cache[tv.get('cdb_object_id')] = tv.get('ce_baseline_object_id')
            ce_baseline_origin_id_cache[tv.get('cdb_object_id')] = tv.get('ce_baseline_origin_id')
            target_value_ids.append(tv.get('cdb_object_id'))
            ref_ids.add(tv.get('cdb_object_id'))

        if with_file_cache:
            if return_objects:
                file_obj_ids = CDB_File.Query(
                    CDB_File.cdbf_object_id.one_of(*ref_ids)
                ).cdb_object_id
                file_obj_cache = {
                    k: CDB_File._FromObjectHandle(v) for (k, v) in mom.getObjectHandlesFromObjectIDs(
                        file_obj_ids, True, True
                    ).items()
                }
            stmt = "SELECT cdb_object_id, cdbf_object_id FROM %s WHERE %s"
            stmt = stmt % (CDB_File.__maps_to__, CDB_File.cdbf_object_id.one_of(*ref_ids))
            for record in sqlapi.RecordSet2(sql=stmt):
                if return_objects:
                    file_cache[record.get('cdbf_object_id')].append(
                        file_obj_cache.get(
                            record.get('cdb_object_id')
                        )
                    )
                else:
                    file_cache[record.get('cdbf_object_id')].append(record.get('cdb_object_id'))

        if with_semantic_link_cache:
            if return_objects:
                semantic_link_ids = SemanticLink.Query(
                    SemanticLink.subject_object_id.one_of(*ref_ids)
                ).cdb_object_id
                semantic_link_obj_cache = {
                    k: SemanticLink._FromObjectHandle(v) for (k, v) in mom.getObjectHandlesFromObjectIDs(
                        semantic_link_ids, True, True
                    ).items()
                }
            stmt = "SELECT cdb_object_id, subject_object_id FROM %s WHERE %s"
            stmt = stmt % (SemanticLink.__maps_to__, SemanticLink.subject_object_id.one_of(*ref_ids))
            for record in sqlapi.RecordSet2(sql=stmt):
                if return_objects:
                    semantic_link_cache[record.get('subject_object_id')].append(
                        semantic_link_obj_cache.get(
                            record.get('cdb_object_id')
                        )
                    )
                else:
                    semantic_link_cache[record.get('subject_object_id')].append(record.get('cdb_object_id'))

        if not return_objects:
            spec_object_cache = spec_object_ids
            target_value_cache = target_value_parent_ids
            spec_object_long_text_cache = None
            target_value_long_text_cache = None
            classification_cache = ref_ids
        else:
            spec_object_cache = {
                k: RQMSpecObject._FromObjectHandle(v) for (k, v) in mom.getObjectHandlesFromObjectIDs(
                    spec_object_ids, True, True
                ).items()
            }
            target_value_cache = collections.defaultdict(list)
            sorted_target_value_ids = list(TargetValue.Query(
                TargetValue.requirement_object_id.one_of(*target_value_parent_ids),
                order_by=[TargetValue.pos, TargetValue.targetvalue_id]).cdb_object_id)
            target_value_obj_cache = {
                k: TargetValue._FromObjectHandle(v) for (k, v) in mom.getObjectHandlesFromObjectIDs(
                    sorted_target_value_ids, True, True
                ).items()
            }
            for tv_oid in sorted_target_value_ids:
                tv_obj = target_value_obj_cache.get(tv_oid)
                target_value_cache[tv_obj.requirement_object_id].append(tv_obj)
                position_cache[tv_obj.requirement_object_id][tv_oid] = tv_obj.pos

            spec_object_long_text_cache = get_long_text_cache(
                RQMSpecObject, spec_object_ids
            )
            target_value_long_text_cache = get_long_text_cache(
                TargetValue, target_value_ids
            )

            classification_cache = load_classification_cache_by_id(ref_ids)

        tree_context = {
            'root': specification,
            'spec_object_cache': spec_object_cache,  # dict of spec object ids -> spec objects  / list of spec object ids
            'target_value_cache': target_value_cache,  # dict requirement_object_id -> target values / list of requirement_object_ids (spec object ids)
            'long_text_cache': {
                RQMSpecObject.__classname__: spec_object_long_text_cache,  # cache cdb_object_id -> long text value
                TargetValue.__classname__: target_value_long_text_cache,  # cache cdb_object_id -> long text value
            },
            'ids': ids,
            'classification_cache': classification_cache,
            'reqif_cache': reqif_cache,
            'position_cache': position_cache,
            'ce_baseline_object_id_cache': ce_baseline_object_id_cache,
            'ce_baseline_origin_id_cache': ce_baseline_origin_id_cache,
            'missing_ce_baseline_object_ids': missing_ce_baseline_object_ids,
            'file_cache': file_cache,
            'semantic_link_cache': semantic_link_cache
        }
        gc.collect()
        return tree_context

    @classmethod
    def get_parents(
            cls,
            obj_or_objects,
            entity=None,
            field_list=None,
            context_attr_name=None,
            parent_attr_name=None,
            id_attr_name=None,
            order_attr=None
    ):
        """ get all parent elements recursively including original objects
        ATTENTION: take care not access controlled
         """
        objs = []
        if isinstance(obj_or_objects, list):
            objs = obj_or_objects
        elif obj_or_objects:
            objs = [obj_or_objects]
        objs_are_dicts = isinstance(objs[0], dict)
        if entity is None:
            entity_classname = objs[0].GetClassname() if not objs_are_dicts else objs[0].get('classname')
            entity = ClassRegistry().findByClassname(entity_classname)
        if field_list is None:
            field_list = []
        if context_attr_name is None:
            context_attr_name = (
                getattr(entity, '__context_object_id_field__')
                if hasattr(entity, '__context_object_id_field__') else 'specification_object_id'
            )
        if id_attr_name is None:
            id_attr_name = 'cdb_object_id'
        if parent_attr_name is None:
            parent_attr_name = (
                getattr(entity, '__parent_object_id_field__')
                if hasattr(entity, '__parent_object_id_field__') else 'parent_object_id'
            )
        if parent_attr_name not in field_list:
            field_list.append(parent_attr_name)
        if id_attr_name not in field_list:
            field_list.append(id_attr_name)
        stmt = cls.get_hierarchical_statement(
            entity=entity,
            field_list=field_list,
            condition={
                context_attr_name: getattr(objs[0], context_attr_name) if not objs_are_dicts else objs[0].get(context_attr_name),
                id_attr_name: [
                    (getattr(obj, id_attr_name) if not objs_are_dicts else obj.get(id_attr_name)) for obj in objs
                ] if len(objs) > 1 else (getattr(objs[0], id_attr_name) if not objs_are_dicts else objs[0].get(id_attr_name))
            },
            join_attr=id_attr_name,
            hierarchical_join_attr=parent_attr_name,
            order_attr=order_attr,
            order_direction='DESC'
        )
        return sqlapi.RecordSet2(sql=stmt)

    @classmethod
    def get_subtree(
            cls,
            obj_or_objects,
            field_list=None,
            context_attr_name=None,
            parent_attr_name=None,
            id_attr_name=None,
            order_attr=None
    ):
        """ get all sub elements recursively including original objects
        - ATTENTION: take care not access controlled """
        objs = []
        if isinstance(obj_or_objects, list):
            objs = obj_or_objects
        elif obj_or_objects:
            objs = [obj_or_objects]
        objs_are_dicts = isinstance(objs[0], dict)
        if field_list is None:
            field_list = []
        if context_attr_name is None:
            context_attr_name = 'specification_object_id'
        if id_attr_name is None:
            id_attr_name = 'cdb_object_id'
        if parent_attr_name is None:
            parent_attr_name = 'parent_object_id'
        if parent_attr_name not in field_list:
            field_list.append(parent_attr_name)
        if id_attr_name not in field_list:
            field_list.append(id_attr_name)
        entity_classname = objs[0].GetClassname() if not objs_are_dicts else objs[0].get('classname')
        entity = ClassRegistry().findByClassname(entity_classname)
        stmt = cls.get_hierarchical_statement(
            entity=entity,
            field_list=field_list,
            condition={
                context_attr_name: getattr(objs[0], context_attr_name) if not objs_are_dicts else objs[0].get(context_attr_name),
                id_attr_name: [
                    (getattr(obj, id_attr_name) if not objs_are_dicts else obj.get(id_attr_name)) for obj in objs
                ] if len(objs) > 1 else (getattr(objs[0], id_attr_name) if not objs_are_dicts else objs[0].get(id_attr_name))
            },
            join_attr=parent_attr_name,
            hierarchical_join_attr=id_attr_name,
            order_attr=order_attr,
            order_direction='ASC'
        )
        return sqlapi.RecordSet2(sql=stmt)

    @classmethod
    def get_hierarchical_statement(
            cls, entity, field_list, condition, join_attr, hierarchical_join_attr, order_attr=None,
            order_direction=None
    ):
        if order_attr is None:
            order_attr = 'sortorder'
        if order_direction is None:
            order_direction = 'ASC'
        if order_attr not in field_list:
            field_list.append(order_attr)
        alias1 = 'alias1'
        alias2 = 'alias2'
        field_list_alias1 = ",".join(["{}.{}".format(alias1, x) for x in field_list])
        field_list_alias2 = ",".join(["{}.{}".format(alias2, x) for x in field_list])
        alias1_where_condition = " AND ".join([
            Expression(
                ' IN ' if isinstance(v, list) else '=',
                getattr(entity, k),
                MultiLiteral(getattr(entity, k), *v) if isinstance(v, list) else Literal(getattr(entity, k), v)
            ).to_string() for (k, v) in condition.items()]
        )
        base_stmt = """WITH {recursive}hierarchical (
            {field_list}
        ) AS (
            SELECT {field_list_alias1} FROM {table} {alias1} WHERE {alias1_where_condition}
            UNION ALL
            SELECT {field_list_alias2} FROM {table} {alias2}
            JOIN hierarchical h ON {alias2}.{join_attr}=h.{hierarchical_join_attr}
        )
        SELECT {field_list} FROM hierarchical ORDER BY {order_attr}
        """
        stmt = base_stmt.format(
            recursive='RECURSIVE ' if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES else '',
            table=entity.__maps_to__,
            alias1=alias1,
            alias2=alias2,
            field_list=",".join(field_list),
            field_list_alias1=field_list_alias1,
            field_list_alias2=field_list_alias2,
            alias1_where_condition=alias1_where_condition,
            join_attr=join_attr,
            hierarchical_join_attr=hierarchical_join_attr,
            order_attr=order_attr
        )
        return stmt

    @classmethod
    def walk(cls, tree_down_context, obj=None, level=0, preprocessor=None):
        if obj is not None:
            yield (level, preprocessor(obj))
        root = tree_down_context.get('root')
        children = root._tree_depth_first_next(tree_down_context, obj)
        for child in children:
            for res_lvl, res_obj in cls.walk(
                tree_down_context, child, level=level + 1, preprocessor=preprocessor
            ):
                yield res_lvl, res_obj

    @classmethod
    def update_positions(
        cls,
        clazz,  # class of elements that should be repositioned
        context_object,
        context_attribute_field_name=None,  # within above clazz
        parent_attribute_field_name=None,  # within above clazz - each different parent means another position partition
        position_attribute_field_name=None,  # within above clazz
        max_chunk_size=1000
    ):
        # rqm_utils.RQMHierarchicals.update_positions(RQMSpecObject, s)
        # rqm_utils.RQMHierarchicals.update_positions(TargetValue, s, parent_attribute_field_name='requirement_object_id', position_attribute_field_name='pos')
        if context_attribute_field_name is None:
            context_attribute_field_name = 'specification_object_id'
        if parent_attribute_field_name is None:
            parent_attribute_field_name = 'parent_object_id'
        if position_attribute_field_name is None:
            position_attribute_field_name = 'position'
        from cdb import transactions
        with transactions.Transaction():
            stmt = """
                SELECT
                    cdb_object_id,
                    {parent_attribute_field_name},
                    {position_attribute_field_name},
                    row_number() over (
                        PARTITION BY {parent_attribute_field_name}
                        ORDER BY {position_attribute_field_name}
                    ) new_position
                FROM {table}
                    WHERE {context_attribute_field_name}='{context_attribute_field_value}'
            """.format(
                parent_attribute_field_name=parent_attribute_field_name,
                position_attribute_field_name=position_attribute_field_name,
                context_attribute_field_name=context_attribute_field_name,
                context_attribute_field_value=sqlapi.quote(context_object.cdb_object_id),
                table=clazz.__maps_to__
            )
            new_positions = sqlapi.RecordSet2(sql=stmt)
            chunks = []
            i = 0
            when_then_condition = ""
            chunk_keys = []
            for new_position in new_positions:
                cdb_object_id = new_position['cdb_object_id']
                chunk_keys.append(cdb_object_id)
                position = new_position['new_position']
                when_then_condition += " WHEN cdb_object_id='{cdb_object_id}' THEN {position_attribute_field_value}".format(
                    cdb_object_id=cdb_object_id, position_attribute_field_value=int(position)
                )
                i += 1
                if i >= max_chunk_size:
                    stmt = "{table} SET {position_attribute_field_name} = CASE {when_then_condition} END WHERE {condition}".format(
                        table=clazz.__maps_to__,
                        position_attribute_field_name=position_attribute_field_name,
                        when_then_condition=when_then_condition,
                        condition=clazz.cdb_object_id.one_of(*chunk_keys)
                    )
                    chunks.append(stmt)
                    when_then_condition = ""  # clear for next chunk
                    i = 0
                    chunk_keys = []
            if when_then_condition:
                stmt = "{table} SET {position_attribute_field_name} = CASE {when_then_condition} END WHERE {condition}".format(
                    table=clazz.__maps_to__,
                    position_attribute_field_name=position_attribute_field_name,
                    when_then_condition=when_then_condition,
                    condition=clazz.cdb_object_id.one_of(*chunk_keys)
                )
                chunks.append(stmt)
            updated = 0
            for chunk in chunks:
                updated += sqlapi.SQLupdate(chunk)
            if updated != len(new_positions):
                raise AssertionError('Unable to update all positions for %s' % context_object.GetDescription())


def multireplace(str_to_replace, replacements, ignore_case=False):
    """
    Given a string and a dict, replaces occurrences of the dict keys found in the
    string, with their corresponding values. The replacements will occur in "one pass",
    i.e. there should be no clashes.

    :param str str_to_replace: string to perform replacements on
    :param dict replacements: replacement dictionary {old string: new string}
    :param bool ignore_case: whether to ignore case when looking for matches
    :rtype: str the replaced string

    """
    if not replacements:
        return str_to_replace
    # from cs/iot/twin/tools/misc.py and
    # https://gist.github.com/bgusach/a967e0587d6e01e889fd1d776c5f3729
    # If case insensitive, we need to normalize the old string so that later a replacement
    # can be found. For instance with {"HEY": "lol"} we should find a replacement for "hey",
    # "HEY", etc.
    if ignore_case:

        def normalize_old(s):
            return s.lower()

        re_mode = re.IGNORECASE

    else:

        def normalize_old(s):
            return s

        re_mode = 0

    replacements = {normalize_old(key): val for key, val in replacements.items()}
    rep_sorted = sorted(replacements, key=len, reverse=True)
    rep_escaped = map(re.escape, rep_sorted)
    pattern = re.compile("|".join(rep_escaped), re_mode)

    return pattern.sub(lambda match: replacements[normalize_old(match.group(0))], str_to_replace)


def get_classification_val(val, language=None):
    new_value = None
    if isinstance(val, dict):
        if 'value' in val:
            new_value = val.get('value')
            if isinstance(new_value, dict) and 'float_value' in new_value:
                return new_value.get('float_value')
            elif isinstance(new_value, dict) and language is not None and language in new_value:
                return new_value[language]['text_value']
    elif (
        isinstance(val, ClassPropertyValuesView) and 
        val.cdb_classname == "cs_multilang_property_value" and 
        "multilang_value_{}".format(language) in val
    ):
        return val["multilang_value_{}".format(language)]
    else:
        value_dict = val.value_dict
        if len(value_dict) == 1:
            new_value = value_dict[list(value_dict)[0]]
        else:
            if hasattr(val, 'getType') and val.getType() == 'float':
                new_value = value_dict["float_value"]
            elif 'float_value' in value_dict:
                new_value = value_dict.get('float_value')
    return new_value


def convert_enum_value_to_str(enum_val):
    if isinstance(enum_val, datetime.datetime):
        return enum_val.isoformat()
    else:
        return u"{}".format(enum_val)


def statement_count():
    stat = sqlapi.SQLget_statistics()
    return stat['statement_count']


def get_objects_to_move_data(cls, ctx, parent_reference_name):
    objs_to_move = cls.PersistentObjectsFromContext(ctx)
    parent_obj = None
    specification_object_id = None
    for obj in objs_to_move:
        if parent_obj is None:
            parent_obj = getattr(obj, parent_reference_name)
            specification_object_id = obj.specification_object_id
        if getattr(obj, parent_reference_name) != parent_obj or obj.specification_object_id != specification_object_id:
            raise ue.Exception("cdbrqm_no_pos")
    return specification_object_id, parent_obj, objs_to_move
