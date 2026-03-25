# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
This is the documentation for the cs.classification.api module.

.. warning::
    This API does **not** do permission checks, the caller functions are responsible for that.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from _collections import defaultdict
import logging

from cdb import sqlapi
from cs.classification import ClassificationException, tools

LOG = logging.getLogger(__name__)


class ConstaintsViolationException(ClassificationException):

    def __init__(self, error_messages):
        error_message = "\n".join(error_messages)
        super(ConstaintsViolationException, self).__init__(
            "cs_classification_constraint_violation", error_message
        )


class InvalidChecksumException(ClassificationException):

    def __init__(self):
        super(InvalidChecksumException, self).__init__("cs_classification_invalid_checksum")


class InvalidPropertyPathException(ClassificationException):

    def __init__(self, property_path):
        super(InvalidPropertyPathException, self).__init__(
            "cs_classification_invalid_property_path", property_path
        )


class SearchIndexException(ClassificationException):

    def __init__(self):
        super(SearchIndexException, self).__init__("cs_classification_search_index_error")


def get_classification(
    obj,
    pad_missing_properties=True,
    with_assigned_classes=True,
    with_metadata=False,
    narrowed=True,
    check_rights=False
):
    """
    Get classification data for given object.

    :param obj: the object to get the classification data for
    :param pad_missing_properties: fills the property data with empty values
    :param with_assigned_classes: adds the assigned classes to the returned dict.
        To use returned dict for update_classification with_assigned_classes has to be True!
    :param with_metadata: adds class and property metadata to the returned dict.
    :param narrowed: returns complete UI data if set to False
    :param check_rights: check the read rights on classes and catalog properties.
    :return:
        Classification data dict "assigned_classes" and "metadata" are optional keys depending on the
        parameter values:

        .. code-block:: python

            {
                "assigned_classes": [<CLASS_CODE>],
                "properties": { <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>] },
                "values_checksum": [<CHECKSUM>],
                "metadata": {
                    "classes" : {
                        <CLASS_CODE> : {
                            "class": { <CLASS_DATA> }
                            "properties": {
                                <PROPERTY_CODE>: { <PROPERTY_DATA> }
                            }
                        }
                    }
                }
            }

    :rtype: `dict`
    """

    from cs.classification.classification_data import ClassificationData

    classification = ClassificationData(obj, narrowed=narrowed, check_rights=check_rights)
    props = classification.get_classification_data()
    if pad_missing_properties:
        classification.pad_values(props, active_props_only=True)
    result = {
        "properties": props,
        "values_checksum": classification.get_classification_data_checksum()
    }
    if with_assigned_classes:
        result["assigned_classes"] = classification.get_assigned_classes(include_bases=False)
    if with_metadata:
        metadata = classification.get_classification_metadata()
        classification.remove_inactive_props(props, metadata)
        result["metadata"] = metadata
    return result


def update_classification(
    obj, data, type_conversion=None, full_update_mode=True, check_access=True, update_index=True
):
    """
    Update classification data for given object.

    If full_update_mode is True assigned classes or property values that are not part of the given data are
    deleted! Otherwise the classification data is updated partially. In this case the classes and additional
    properties that shall be deleted have to given explicit by using the keys 'deleted_classes' and
    'deleted_properties'

    If a value checksum is part of the data dict it is compared with the
    persistent values. In case of inconsistent checksums due to concurrent modification an
    InvalidChecksumException is raised.

    :param obj: the object to update the classification for
    :param data: dict with assigned classes and property data

        .. code-block:: python

            {
                "assigned_classes" : [<class_codes>],
                "deleted_classes": [<class_codes>]
                "deleted_properties": [<catalog_property_codes>]
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                },
                "ue_args": {<optional user exit data>},
                "values_checksum": [<CHECKSUM>]
            }

    :param type_conversion: optional function used for type conversion before the data is updated in
                            the database.
    :param: full_update_mode: If True, data must be provided completely. Missing properties and classes are
                              deleted. If False, data can be specified partially and only updates/inserts
                              are applied.
    :param: check_access: If True, access rights are checked. If False, no access rights are checked
                          (should be used for migrations only!).
    :param: update_index: If True, the search index is updated. If False, the search index is not updated
                          (search index must be updated later manually).
    :return: Nothing
    :rtype: `None`
    :raises: InvalidChecksumException in case of different checksums
    :raises: ConstaintsViolationException in case of contraint violations
    :raises: SearchIndexException in case errors updating the search index.
             in this case the classification is updated in the database but you need to ensure that the
             search index is updated later otherwise the search will not work properly.
    """

    from cs.classification.object_classification import ClassificationUpdater

    updater = ClassificationUpdater(obj, type_conversion=type_conversion, full_update_mode=full_update_mode)
    updater.update(data=data, check_access=check_access, update_index=update_index)


def get_new_classification(
    classes,
    with_defaults=True,
    create_all_blocks=True,
    narrowed=True,
    check_rights=False
):
    """
    Build a new classification datastructure for given new_classes.

    :param classes: list of class codes to be assigned
    :return:
        A dict containing assigned classes, property data either with or without defaults and the metadata
        for classes and all base classes is returned.

        .. code-block:: python

            {
                "assigned_classes" : [<class_codes>],
                "metadata": {
                    "classes" : {
                        <CLASS_CODE> : {
                            "class": { <CLASS_DATA> }
                            "properties": {
                                <PROPERTY_CODE>: { <PROPERTY_DATA> }
                            }
                        }
                    }
                },
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                }
            }
    :rtype: `dict`
    :raises: ClassesNotApplicableException in case of incorrect class codes
    """
    from cs.classification.classification_data import ClassificationData

    classification_data = ClassificationData(None, classes, narrowed=narrowed, check_rights=check_rights)
    properties, metadata = classification_data.get_new_classification(
        [], with_defaults=with_defaults, create_all_blocks=create_all_blocks
    )
    return {
        'properties': properties,
        'assigned_classes': classes,
        'metadata': metadata
    }


def compare_classification(left_obj_id, right_obj_id, with_metadata=False, narrowed=True, check_rights=False):
    """
    Compares the classification of two given objects. The order of multiple values for one property is not
    taken into account to calculate the differences. In this case property values can either be equal,
    only for left object or only for right object. Multivalued block properties with identifying property are
    deeply compared.

    :param left_obj_id: cdb_object id of left object
    :param right_obj_id: cdb_object id of right object
    :param with_metadata: returns also the class and properties metadata if set to True
    :param narrowed: returns complete UI data if set to False
    :return:
        A dict containing the classification differences for the given objects.

        .. code-block:: python

            {
                "assigned_classes" : [<class_codes for both objects>],
                "assigned_classes_left" : [<class_codes only for left object>],
                "assigned_classes_right" : [<class_codes only for right object>],
                "classification_is_equal": True | False,
                "metadata": {
                    "classes" : {
                        <CLASS_CODE> : {
                            "class": { <CLASS_DATA> }
                            "properties": {
                                <PROPERTY_CODE>: { <PROPERTY_DATA> }
                            }
                        }
                    }
                },
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                }
            }

        The value dict contains the key "value", if the property values are equal. The value dict contains
        the keys "value_left" and "value_right", if the property values differ. One of this keys may contain
        None in case that the value is only set for one of the given objects.
    :rtype: `dict`

    """

    from cs.classification.compare import ClassificationDataComparator

    comparator = ClassificationDataComparator(
        left_obj_id, right_obj_id, with_metadata=with_metadata, narrowed=narrowed, check_rights=check_rights
    )
    return comparator.compare()


def validate_classification(data, new_classes=None):
    LOG.warn(
        "Validate_classification is deprecated! Please use get_newclassification or rebuild_classification."
    )
    return rebuild_classification(data, new_classes)


def rebuild_classification(data, new_classes=None, narrowed=True, check_rights=False):
    """
    Rebuild classification data. Can be used to add  or remove classes (either put new code in 'new_classes'
    list or remove class code form 'assigned_classes' list).

    :param data: dict with assigned classes and property data

        .. code-block:: python

            {
                "assigned_classes" : [<class_codes>],
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                },
                "values_checksum": [<CHECKSUM>]
            }

    :param new_classes: list of class codes to be assigned
    :return:
        A merged assigned classes list and a merged properties dict with padded values and a metadata dict for
        new classes is returned.

        .. code-block:: python

            {
                "assigned_classes" : [<class_codes>],
                "new_classes_metadata": {
                    "classes" : {
                        <CLASS_CODE> : {
                            "class": { <CLASS_DATA> }
                            "properties": {
                                <PROPERTY_CODE>: { <PROPERTY_DATA> }
                            }
                        }
                    }
                },
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                }
            }
    :rtype: `dict`
    :raises: ClassesNotApplicableException in case of incorrect class codes
    """

    from cs.classification.classification_data import ClassificationData

    # Thinkabout:
    # - raise exception for classes that don't exist

    properties = data.get("properties", {})
    class_codes = data.get("assigned_classes", [])

    # get catalog property codes to prevent them from being deleted
    catalog_prop_codes = set()
    if properties:
        stmt = "select code from cs_property where {}".format(
            tools.format_in_condition("code", properties.keys())
        )
        rset = sqlapi.RecordSet2(sql=stmt)
        for r in rset:
            catalog_prop_codes.add(r.code)

    # remove class props that don't belong to any of the given classes in class_codes
    if class_codes:
        valid_props = ClassificationData(None, class_codes, check_rights=check_rights).get_properties(
            include_bases=True
        )
        for prop_code in list(properties):
            if prop_code not in valid_props and prop_code not in catalog_prop_codes:
                del properties[prop_code]
    else:
        for prop_code in list(properties):
            if prop_code not in catalog_prop_codes:
                del properties[prop_code]

    # add empty property data for new classes
    new_metadata = {}
    if new_classes:
        classification_data = ClassificationData(
            None, new_classes, narrowed=narrowed, check_rights=check_rights
        )
        new_property_data, new_metadata = classification_data.get_new_classification(
            class_codes, with_defaults=True
        )
        for prop_code, val in new_property_data.items():
            if prop_code not in properties:
                properties[prop_code] = val

    data['properties'] = properties
    if new_metadata:
        data['assigned_classes'] = list(
            set(class_codes).union(set(new_metadata.get('assigned_classes', [])))
        )
    else:
        data['assigned_classes'] = class_codes

    data['new_classes_metadata'] = new_metadata['classes'] if new_metadata else {}
    if 'new_classes' in data:
        del data['new_classes']
    return data


def add_multivalue(data, property_path, create_all_blocks=True):
    """
    Add a new property value for the given property path to the given data structure.

    :param data: dict with assigned classes and property data

        .. code-block:: python

            {
                "assigned_classes" : [<class_codes>],
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                },
                "values_checksum": [<CHECKSUM>]
            }
    :param property_path: The path of the property to add the new value to. The property path is a combination
        of property codes and positions. In case of a simple multivalued property the path is the same as the
        property code e.g. "MULTIVALUED_TEXT_PROPERTY". In case of a multivalued property that is part of a
        block the path contains all property codes seperated by '/' and the position starts with 001
        e.g. "MULTIVALUED_BLOCK_PROPERTY:001/MULTIVALUED_CHILD_PROPERTY".
    :param: create_all_blocks: If True, all sub-blocks with identifying properties with autocreate are build.
    :return: the created multivalue for convenience to set the property values.
        The multivalue has already been added to the given datastructure!
    :rtype: `dict`
    :raises: InvalidPropertyPathException in case of incorrect property path

    """

    from cs.classification import util
    from cs.classification.classification_data import ClassificationData

    try:
        path_elements = property_path.split("/")
        property_values = util.get_value_list(data["properties"], path_elements)

        if property_values is None:
            raise InvalidPropertyPathException(property_path)

        class_codes = data.get("assigned_classes", [])
        classification_data = ClassificationData(None, class_codes, narrowed=True)
        values, _ = classification_data.get_new_value(property_path, create_all_blocks)

        new_multivalue = values[path_elements[-1]][0]
        property_values.append(new_multivalue)
        return new_multivalue

    except Exception: # pylint: disable=W0703
        raise InvalidPropertyPathException(property_path)


def get_applicable_classes_for_dd_class(dd_classname, deep=True, only_active=False, only_released=False):
    """
    Get a set of applicable class codes for the given data dictionary class.

    :param dd_classname: name of the data dictionary class
    :param deep: return also inherited classes or not
    :param only_active: return only active classes
    :param only_released: return only released classes
    :return: a set of applicable class codes that can be used for
             get_new_classification or rebuild_classification
    :rtype: `set`

    """

    from cs.classification import classes

    applicable_class_codes = classes.ClassificationClass.get_direct_applicable_class_codes(
        dd_classname, only_active, only_released
    )
    if deep and applicable_class_codes:
        applicable_class_codes = applicable_class_codes.union(
            classes.ClassificationClass.get_sub_class_codes(class_codes=applicable_class_codes)
        )
    return applicable_class_codes


def get_applicable_classes(obj, deep=True, only_active=False, only_released=False):
    """
    Get a set of applicable class codes for the given cdb object.

    :param obj: object to get the applicable classes for
    :param deep: return also inherited classes or not
    :param only_active: return only active classes
    :param only_released: return only released classes
    :return: a set of applicable class codes that can be used for
             get_new_classification or rebuild_classification
    :rtype: `set`

    """

    from cs.classification import util

    util.check_classification_object(obj)

    return get_applicable_classes_for_dd_class(
        obj.GetClassname(), deep=deep, only_active=only_active, only_released=only_released
    )


def get_descriptions_for_object(
    obj, class_code, languages, aggregate_parent_class_tags=False,
    decimal_seperator=None, group_seperator=None, dateformat=None
):
    """
    Get description for the persistent classification data of the given object and the given class code.

    :param class_code:
        class code
    :param languages:
        list of language codes.
    :param aggregate_parent_class_tags:
        True if the class description tag shall be combined of description tags of the base classes
    :param decimal_seperator:
        decimal seperator. if not given the decimal seperator of the session is used
    :param group_seperator:
        group seperator. if not given the group seperator of the session is used
    :param dateformat:
        dateformat. if not given the default dateformat of the session is used
    :return:
        a dictionary of class descriptions with the language as key.
        .. code-block:: python

            {
                "<lang code>": "<class_description>"
            }
    :rtype: `dict`
    """

    return get_descriptions(
        get_classification(obj), class_code, languages, aggregate_parent_class_tags,
        decimal_seperator=decimal_seperator, group_seperator=group_seperator, dateformat=dateformat
    )


def get_descriptions(
    data, class_code, languages, aggregate_parent_class_tags=False,
    decimal_seperator=None, group_seperator=None, dateformat=None
):
    """
    Create a class descriptions for all assigned classes within the given classification data.

    :param class_code:
        class code
    :param languages:
        list of language codes.
    :param aggregate_parent_class_tags:
        True if the class description tag shall be combined of description tags of the base classes
    :param decimal_seperator:
        decimal seperator. if not given the decimal seperator of the session is used
    :param group_seperator:
        group seperator. if not given the group seperator of the session is used
    :param dateformat:
        dateformat. if not given the default dateformat of the session is used
    :return:
        a dictionary of class descriptions with the language as key.

        .. code-block:: python

            {
                "<lang code>": "<class_description>"
            }

    :rtype: `dict`
    """

    class_description_tags = get_class_description_tags([class_code], languages, aggregate_parent_class_tags)[class_code]
    result = {}
    for language in languages:
        result[language] = create_class_description(
            class_description_tags[language], data, [language],
            decimal_seperator=decimal_seperator, group_seperator=group_seperator, dateformat=dateformat
        )
    return result


def get_class_description_tags(class_codes, languages=None, aggregate_parent_class_tags=False):
    """
    Get a class description tags for the given list of class codes and the given list of languages.

    :param class_codes:
        list of class codes
    :param languages:
        list of language codes. if not given the default and fallback languages of the session are used
    :param aggregate_parent_class_tags:
        True if the class description tag shall be combined of description tags of the base classes
    :return:
        a dictionary of class description tags with the given class_codes as first key and the given
        languages as second key.

        .. code-block:: python

            {
                "<class_code>" :
                {
                    "<lang code>": "<class_description_tag>"
                }
            }

    :rtype: `dict`
    """

    from cs.classification.classes import ClassificationClass

    if not languages:
        languages = tools.get_languages()

    all_class_infos = ClassificationClass.get_base_class_info_by_code(
        class_codes=class_codes, include_given=True
    )

    description_tags = {}
    if not all_class_infos:
        return description_tags

    description_cols = ",".join(["class_description_tag_" + language for language in languages])

    try:
        stmt = "select code, {} from cs_classification_class where {}".format(
            description_cols, tools.format_in_condition("code", all_class_infos.keys())
        )
        rset = sqlapi.RecordSet2(sql=stmt)
        for row in rset:
            description_tags[row.code] = {}
            for language in languages:
                description_tag = row.get("class_description_tag_" + language)
                description_tags[row.code][language] = description_tag if description_tag else u""
        result = defaultdict(dict)
        for language in languages:
            for class_code in class_codes:
                description_tag = description_tags[class_code][language]
                if aggregate_parent_class_tags:
                    parent_class_code = all_class_infos[class_code]['parent_class_code']
                    while parent_class_code:
                        description_tag = description_tags[parent_class_code][language] + description_tag
                        parent_class_code = all_class_infos[parent_class_code]['parent_class_code']
                result[class_code][language] = description_tag
        return result
    except:
        raise ValueError("invalid language given")


def create_class_description(
    class_description_tag, data,
    languages=None, decimal_seperator=None, group_seperator=None, dateformat=None
):
    """
    Create a class description based on the given class description tag and the given classification data.

    :param class_description_tag:
        the description tag
    :param data:
        classification data
    :param languages:
        language and fallback languages that are used for multilang property values
    :param decimal_seperator:
        decimal seperator. if not given the decimal seperator of the session is used
    :param group_seperator:
        group seperator. if not given the group seperator of the session is used
    :param dateformat:
        dateformat. if not given the default dateformat of the session is used
    :return:
        the created class description.
    :rtype: `str`
    """

    from cs.classification.util import create_class_description
    return create_class_description(
        class_description_tag, data["properties"],
        languages, decimal_seperator, group_seperator, dateformat
    )


def create_class_descriptions(
    data, languages=None, aggregate_parent_class_tags=False,
    decimal_seperator=None, group_seperator=None, dateformat=None
):
    """
    Create a class descriptions for all assigned classes within the given classidication data.

    :param data:
        classification data
    :param languages:
        languages to create the class descriptions for
    :param decimal_seperator:
        decimal seperator. if not given the decimal seperator of the session is used
    :param group_seperator:
        group seperator. if not given the group seperator of the session is used
    :param dateformat:
        dateformat. if not given the default dateformat of the session is used
    :return:
        a dictionary of class description tags with the given class_codes as first key and the given
        languages as second key.

        .. code-block:: python

            {
                "<class_code>" :
                {
                    "<lang code>": "<class_description>"
                }
            }

    :rtype: `dict`
    """

    from cs.classification.util import create_class_description

    assigned_classes = data["assigned_classes"]
    description_tags = get_class_description_tags(assigned_classes, languages, aggregate_parent_class_tags)

    result = defaultdict(dict)
    for assigned_class in assigned_classes:
        for language in languages:
            result[assigned_class][language] = create_class_description(
                description_tags[assigned_class][language], data["properties"],
                [language], decimal_seperator, group_seperator, dateformat
            )
    return result


def get_catalog_values(class_code, property_code, active_only, request=None):
    """
    Get the predefined property values for one property.

    :param class_code: optional class code (needed for class properties only)
    :param property_code: property code to get the values for
    :param active_only: only active or all values
    :param request: optional request object used to get link an description for objectref properties
    :return: a list of property values. Each value is a dict with the property value

        .. code-block:: python

            {
                'value': u'Blind'
            }

    :rtype: `dict`

    """

    if class_code:
        # class property
        from cs.classification import classes
        return classes.ClassPropertyValuesView.get_catalog_values(
            class_code, property_code, active_only, request
        )
    else:
        # catalog property (e.g. prop in block)
        from cs.classification import catalog
        return catalog.Property.get_catalog_values(property_code, active_only, request)


def get_all_catalog_values(
    class_codes, active_only, request=None, for_variants=False, with_normalized_values=False
):
    """
    Get the predefined property values for all properties of given classes.

    :param class_codes: list of class codes
    :param active_only: only active or all values
    :param request: optional request object used to get link an description for objectref properties
    :return: a list of property values. Each value is a dict with the property value

        .. code-block:: python

            {
                <PROPERTY_CODE>: [<PROPERTY_VALUE>]
            }

    :rtype: `dict`

    """
    from cs.classification.classification_data import ClassificationData
    class_info = ClassificationData(None, class_codes)
    return class_info.get_catalog_values(
        active_only,
        request=request,
        for_variants=for_variants,
        with_normalized_values=with_normalized_values
    )


def create_additional_props(prop_codes, check_rights=False):
    """
    Get property metdata and create property values for given property codes.

    :param prop_codes: property codes (need to be codes of catalog properties)
    :return: a dict of property metadata and property values. Each value is a dict with the property value

        .. code-block:: python

            {
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                }
                "metadata": {
                    <PROPERTY_CODE> : [<PROPERTY_METADTA_DICT>]
                }
            }

    :rtype: `dict`

    """

    from cs.classification.classification_data import ClassificationData

    classification_data = ClassificationData(None, class_codes=[], request=None, check_rights=check_rights)

    metadata = {}
    values = {}
    for prop_code in prop_codes:
        prop_value, prop_metadata = classification_data.get_new_value(prop_code)
        metadata.update(prop_metadata)
        values.update(prop_value)

    return {
        "properties": values,
        "metadata": metadata
    }


def get_additional_props(obj, with_metadata=False):
    """
    Get additional property data for given object.

    :param obj: the object to get the classification data for
    :param with_metadata: adds class and property metadata to the returned dict.
    :return: a dict of property values. "meatdata" is an optional key depending on the given parameter values.

        .. code-block:: python

            {
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                }
                "metadata": {
                    <PROPERTY_CODE> : [<PROPERTY_METADTA_DICT>]
                }
            }

    :rtype: `dict`
    """

    from cs.classification.catalog import Property
    from cs.classification.classification_data import ClassificationData

    def filter_additional_prop_values(prop_val_rec):
        assigned_prop_code = prop_val_rec.property_path.split('/')[0].split(':')[0]
        return assigned_prop_code in additional_prop_codes

    stmt = """
        SELECT * FROM  cs_object_property_value
        WHERE ref_object_id = '{obj_id}'
        ORDER BY ref_object_id, property_path""".format(
        obj_id=obj.cdb_object_id
    )
    prop_value_recs = sqlapi.RecordSet2(sql=stmt)
    if not prop_value_recs:
        data = {
            "properties": {}
        }
        if with_metadata:
            data["metadata"] = {}
        return data

    assigned_prop_codes = set(row["property_path"].split('/')[0].split(':')[0] for row in prop_value_recs)
    if with_metadata:
        catalog_props = Property.Query(Property.code.one_of(*assigned_prop_codes))
        additional_prop_codes = set(prop.code for prop in catalog_props)
    else:
        stmt = "SELECT code FROM cs_property WHERE {}".format(
            tools.format_in_condition("code", assigned_prop_codes)
        )
        additional_prop_codes = set(row["code"] for row in sqlapi.RecordSet2(sql=stmt))

    prop_value_recs.filter(filter_additional_prop_values)
    data = {
        "properties": ClassificationData._load_from_records(prop_value_recs, True, None)
    }
    if with_metadata:
        data["metadata"] = ClassificationData.get_catalog_property_metadata_for_properties(catalog_props)
    return data


def update_additional_props(obj, data, type_conversion=None):
    """
    Set additional property data for given object. New property values are created if missing or updated
    if already exising.

    :param obj: the object to update the additional property values for
    :param data: dict with additional property data (at least one of the keys has to be set)

        .. code-block:: python

            {
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                },
                "deleted_properties": [<CATALOG_PROPERTY_CODES>]
            }

    :param type_conversion: optional function used for type conversion before the data is updated in
        the database.
    :return: Nothing
    :rtype: `None`
    """

    from cs.classification.object_classification import ClassificationUpdater

    update_data = {
        "assigned_classes": [],
        "properties": data.get("properties", {}),
        "deleted_properties": data.get("deleted_properties", [])
    }
    updater = ClassificationUpdater(obj, type_conversion=type_conversion, full_update_mode=False)
    updater.update(update_data)


def search(data):
    """
    Search for classified objects. Assigned classes list must contain class_codes to search for. Properties
    must contain the search criteria.

    :param data: dict with assigned classes and property data

        .. code-block:: python

            {
                "assigned_classes" : [<class_codes>],
                "class_independent_property_codes": [<property_codes>],
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                }
            }

    :return: generator of cdb_object_ids of found objects
    :rtype: `None`
    """

    from cs.classification.solr import search_solr

    properties = data.get("properties", {})
    class_codes = data.get("assigned_classes", [])
    catalog_property_codes = data.get("class_independent_property_codes", set())
    oids = search_solr(properties, class_codes, catalog_property_codes)
    return oids


def preset_mask_data(data, ctx):
    """
    Add given classification data to dialog.

    :param data: dict with assigned classes and property data

        .. code-block:: python

            {
                "assigned_classes" : [<class_codes>],
                "class_independent_property_codes": [<property_codes>],
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                }
            }

    :param ctx: interactive operation context
    """
    tools.preset_mask_data(data, ctx)


def update_search_index(cdb_object_ids):
    """
    Update the search index for the classified object with the given object ids.

    :param cdb_object_ids: list of cdb_object_ids

    """
    from cs.classification import solr
    solr.index_object_ids(cdb_object_ids)


def add_function_to_whitelist(function_name):
    """
    Add the given function to the list of allowd functions for constraint, formula and rule expressions.

    :param function_name: name of the python function to be added in the whitelist

    """

    from cs.classification.computations import BaseTransformer
    BaseTransformer.functions.append(function_name)

