# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com
#
# Version:  $Id$

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import logging
import webob

from cdb.objects import ByID
from cdb.objects.core import Object
from cs.platform.web import JsonAPI
from cs.platform.web.rest import get_collection_app
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.root.main import Api as Root_Api

from cs.classification import api
from cs.classification.api import InvalidChecksumException
from cs.classification.rest import utils
from cs.classification.rest.utils import get_rest_obj_by_id


LOG = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------------------------------
# Generic REST API extension
# ----------------------------------------------------------------------------------------------------------------


class ClassificationApp(JsonAPI):
    """
    App to extend generic REST API to access (get and put) classification data e.g.

    http://localhost/api/v1/collection/document/D000000@/classification

    to get data for a given document.
    """

    def __init__(self, obj, *args, **kwargs):
        super(ClassificationApp, self).__init__(*args, **kwargs)
        self.object = obj


@GenericApp.mount(app=ClassificationApp, path="{keys}/classification")
def mount_classification_app(keys, app):
    obj = app.get_object(keys)
    return ClassificationApp(obj)


@ClassificationApp.path(path='', model=Object)
def get_object_by_keys(app):
    return app.object


class AdditionalPropertiesApp(JsonAPI):
    """
    App to extend generic REST API to access (get and put) additional property data e.g.

    http://localhost/api/v1/collection/document/D000000@/additional_properties

    to get additional property data for a given document.
    """

    def __init__(self, obj, *args, **kwargs):
        super(AdditionalPropertiesApp, self).__init__(*args, **kwargs)
        self.object = obj


@GenericApp.mount(app=AdditionalPropertiesApp, path="{keys}/additional_properties")
def mount_additional_properties_app(keys, app):
    obj = app.get_object(keys)
    return AdditionalPropertiesApp(obj)


@AdditionalPropertiesApp.path(path='', model=Object)
def additional_properties_app_get_object_by_keys(app):
    return app.object

# ----------------------------------------------------------------------------------------------------------------
# External Classification REST API
# ----------------------------------------------------------------------------------------------------------------


class ClassificationRootApp(JsonAPI):
    """
    App for external classification api. e.g.

    http://localhost/api/cs.classification/v1/

    to get data for a given cdb_object_id.
    """

    def __init__(self, *args, **kwargs):
        super(ClassificationRootApp, self).__init__(*args, **kwargs)


@Root_Api.mount(app=ClassificationRootApp, path="cs.classification/v1")
def mount_classification_root_app():
    return ClassificationRootApp()


class ClassificationRootModel(object):
    pass


@ClassificationRootApp.path(path='', model=ClassificationRootModel)
def get_classification_root(app):
    return ClassificationRootModel()


class ClassificationApiApp(JsonAPI):

    def __init__(self, *args, **kwargs):
        super(ClassificationApiApp, self).__init__(*args, **kwargs)


@ClassificationRootApp.mount(app=ClassificationApiApp, path="classification")
def mount_classification_api_app():
    return ClassificationApiApp()


@ClassificationApiApp.path(path='{object_id}', model=Object)
def classification_get_object_by_id(object_id, app):
    return get_rest_obj_by_id(object_id)


class AdditionalPropertiesApiApp(JsonAPI):

    def __init__(self, *args, **kwargs):
        super(AdditionalPropertiesApiApp, self).__init__(*args, **kwargs)


@ClassificationRootApp.mount(app=AdditionalPropertiesApiApp, path="additional_properties")
def mount_additional_properties_api_app():
    return AdditionalPropertiesApiApp()


@AdditionalPropertiesApiApp.path(path='{object_id}', model=Object)
def additional_properties_get_object_by_id(object_id, app):
    return get_rest_obj_by_id(object_id)

# ----------------------------------------------------------------------------------------------------------------


@ClassificationApp.json(model=Object, request_method="GET")
@ClassificationApiApp.json(model=Object, request_method="GET")
def get_object_classification(model, request):
    """
    Get classification data for given object id. The result is filtered by the read rights of the classes and
    catalog properties that the current session has.

    Supported URL parameters:

    - pad_missing_values ([0, 1], default=1): fills the property data with empty values
    - with_assigned_classes ([0, 1], default=1): returns also the assigned classes
    - with_metadata ([0, 1], default=0): returns also the class and properties metadata

    :return:
        Classification data dict "assigned_classes" and "metadata" are optional keys depending on the
        url parameter values:

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

    :Examples:

        Get classification data with assigned_classes, properties with padded values:

        - http://localhost/api/cs.classification/v1/classification/<cdb_object_id>
        - http://localhost/api/v1/collection/<cdb_classname>/<keys>/classification

        Get classification data with assigned_classes, properties with padded values and metadata:

        - http://localhost/api/cs.classification/v1/classification/<cdb_object_id>?with_metadata=1
        - http://localhost/api/v1/collection/<cdb_classname>/<keys>/classification?with_metadata=1

        Get property values only:

        - http://localhost/api/cs.classification/v1/classification/<cdb_object_id>?pad_missing_values=0&with_assigned_classes=0
        - http://localhost/api/v1/collection/<cdb_classname>/<keys>/classification?pad_missing_values=0&with_assigned_classes=0
    """

    if model is None or not model.CheckAccess("read"):
        raise webob.exc.HTTPForbidden

    url_params = request.params
    pad_missing_properties = '1' == url_params.get('pad_missing_values', '1')
    with_assigned_classes = '1' == url_params.get('with_assigned_classes', '1')
    with_metadata = '1' == url_params.get('with_metadata', '0')

    result = api.get_classification(
        model,
        pad_missing_properties=pad_missing_properties,
        with_assigned_classes=with_assigned_classes,
        with_metadata=with_metadata,
        check_rights=True
    )
    return utils.ensure_json_serialiability(result)


@ClassificationApp.json(model=Object, request_method="PUT")
@ClassificationApiApp.json(model=Object, request_method="PUT")
def put_object_classification(model, request):
    """
    Update classification data for given object id. The request must contain a dictionary:

    .. code-block:: python

        {
            "assigned_classes" : [<class_codes>],
            "deleted_properties": [<CATALOG_PROPERTY_CODES>]
            "properties": {
                <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
            },
            "values_checksum": [<CHECKSUM>]
        }

    The classification data is always updated partially! Classes and additional properties that shall be
    deleted have to given explicit by using the keys 'deleted_classes' and 'deleted_properties'

    If a value checksum is part of the data dict it is compared with the persistent values. In case of
    inconsistent checksums due to concurrent modification an HTTPConflict error is thrown.

    :return: Nothing
    :rtype: `None`
    :raises: HTTPConflict in case of a checksum error and HTTPUnprocessableEntity in case of other errors

    :Examples:

        Update classification data (PUT):

        - http://localhost/api/cs.classification/v1/classification/<cdb_object_id>
        - http://localhost/api/v1/collection/<cdb_classname>/<keys>/classification

    """
    try:
        data = request.json
        api.update_classification(model, data, utils.convert_from_json, full_update_mode=False)
    except InvalidChecksumException as e:
        LOG.exception(e)
        raise webob.exc.HTTPConflict(str(e))
    except Exception as e: # pylint: disable=W0703
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))
    raise webob.exc.HTTPNoContent


@ClassificationRootApp.json(model=ClassificationRootModel, name="validate", request_method="POST")
@ClassificationRootApp.json(model=ClassificationRootModel, name="rebuild", request_method="POST")
def rebuild_object_classification(model, request):

    """
    Refresh classification data. Can be used to add  or remove classes (either put new code in 'new_classes'
    list or remove class code form 'assigned_classes' list).

    The request must contain a dictionary:

    .. code-block:: python

        {
            "assigned_classes" : [<class_codes>],
            "new_classes" : [<class_codes>],
            "properties": {
                <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
            },
            "values_checksum": [<CHECKSUM>]
        }

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

    :Examples:

        Refresh classification data (POST):

        - http://localhost/api/cs.classification/v1/rebuild


    """
    try:
        data = request.json
        return utils.ensure_json_serialiability(api.rebuild_classification(data, data.get("new_classes")))
    except Exception as e: # pylint: disable=W0703
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))


@ClassificationRootApp.json(model=ClassificationRootModel, name="new_classification", request_method="POST")
def get_new_classification(model, request):

    """
    Build a new classification data structure for given new_classes.
    If with_defaults is not given True is used, and if create_all_blocks is not given True is used.

    The request must contain a dictionary:

    .. code-block:: python

        {
            "new_classes" : [<class_codes>],
            "with_defaults": True|False,
            "create_all_blocks" : True|False
        }

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

    :Examples:

        Get new classification data (POST):

        - http://localhost/api/cs.classification/v1/new_classification


    """
    try:
        data = request.json
        return utils.ensure_json_serialiability(
            api.get_new_classification(
                data.get("new_classes"),
                with_defaults = data.get("with_defaults"),
                create_all_blocks=data.get("create_all_blocks")
            )
        )
    except Exception as e: # pylint: disable=W0703
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))


@ClassificationRootApp.json(
    model=ClassificationRootModel, name="create_additional_properties", request_method="POST"
)
def create_additional_properties(model, request):
    """
    Returns metadata and padded values for the given property codes.

    The request must contain a dictionary:

    .. code-block:: python

        {
            "property_codes" : [<property_codes>]
        }

    :return:
        A dictionary containing metadata and padded values for the given property codes.

        .. code-block:: python

            {
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                },
                "metadata": {
                    <PROPERTY_CODE> : [<PROPERTY_METADTA_DICT>]
                }
            }

    :rtype: `dict`

    :Examples:

        Create additional properties (POST):

        - http://localhost/api/cs.classification/v1/create_additional_properties
    """
    data = request.json
    result = api.create_additional_props(data.get("property_codes"))
    return utils.ensure_json_serialiability(result)


@AdditionalPropertiesApp.json(model=Object, request_method="GET")
@AdditionalPropertiesApiApp.json(model=Object, request_method="GET")
def get_additional_properties(model, request):
    """
    Get additional property data for given object. Supported URL parameters:

    - with_metadata ([0, 1], default=0): returns also the properties metadata

    :return: a dict of property values. "meatdata" is an optional key depending on the given parameter values.

        .. code-block:: python

            {
                "properties": {
                    <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                },
                "metadata": {
                    <PROPERTY_CODE> : [<PROPERTY_METADTA_DICT>]
                }
            }

    :rtype: `dict`

    :Examples:

        Get additional properties (GET):

        - http://localhost/api/cs.classification/v1/additional_properties/<cdb_object_id>
        - http://localhost/api/v1/collection/<cdb_classname>/<keys>/additional_properties

        Get additional properties with metadata (GET):

        - http://localhost/api/cs.classification/v1/additional_properties/<cdb_object_id>?with_metadata=1
        - http://localhost/api/v1/collection/<cdb_classname>/<keys>/additional_properties?with_metadata=1

    """

    if model is None or not model.CheckAccess("read"):
        raise webob.exc.HTTPForbidden

    url_params = request.params
    with_metadata = '1' == url_params.get('with_metadata', '0')

    result = api.get_additional_props(
        model,
        with_metadata=with_metadata
    )
    return utils.ensure_json_serialiability(result)


@AdditionalPropertiesApp.json(model=Object, request_method="PUT")
@AdditionalPropertiesApiApp.json(model=Object, request_method="PUT")
def put_additional_properties(model, request):
    """
    Update additional properties data for given object id. The request must contain a dictionary with at
    least one of the keys set:

    .. code-block:: python

        {
            "properties": {
                <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
            },
            "deleted_properties": [<PROPERTY_CODES>]
        }

    :return: Nothing
    :rtype: `None`
    :raises: HTTPUnprocessableEntity in case of errors

    :Examples:

        Update additional properties (PUT):

        - http://localhost/api/cs.classification/v1/additional_properties/<cdb_object_id>
        - http://localhost/api/v1/collection/<cdb_classname>/<keys>/additional_properties

    """

    try:
        data = request.json
        api.update_additional_props(model, data, utils.convert_from_json)
    except InvalidChecksumException as e:
        LOG.exception(e)
        raise webob.exc.HTTPConflict(str(e))
    except Exception as e: # pylint: disable=W0703
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))
    raise webob.exc.HTTPNoContent

# ----------------------------------------------------------------------------------------------------------------


class SearchApp(JsonAPI):

    def __init__(self, *args, **kwargs):
        super(SearchApp, self).__init__(*args, **kwargs)


@ClassificationRootApp.mount(app=SearchApp, path="search")
def mount_search_app():
    return SearchApp()


class ClassificationSearch(object):
    pass


@SearchApp.path(path='', model=ClassificationSearch)
def get_search_model():
    return ClassificationSearch()


@SearchApp.json(model=ClassificationSearch, request_method="POST")
def search_object_classification(model, request):
    """
    Search for classified objects. Assigned classes list must contain class_codes to search for. Properties
    must contain the search criteria. If max_result is not given 10000 is used as default value. The default
    for with_classification is True. class_independent_property_codes are optional and have to be given for
    class independent search and must contain all catalog property codes.

    .. code-block:: python

        {
            "assigned_classes" : [<class_codes>],
            "class_independent_property_codes": [<property_codes>],
            "properties": {
                <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
            }
            "max_results": <maximal_result_size>
            "with_classification": true|false
        }

    The datastructure description for the property values can be found here: :ref:`classification_api_property_values`

    :return: list of rest representation of found objects. if called with_classification = True the classification data is injected in the rest representation with the key 'system:classification'.
    :rtype: `list`
    :raises: HTTPUnprocessableEntity in case of errors

    :Examples:

        Search (POST):

        - http://localhost/api/cs.classification/v1/search
    """

    try:
        data = request.json
        max_result = data.get("max_results", 10000)
        with_classification = data.get("with_classification", True)
        result = []
        for oid in api.search(data):
            if len(result) == max_result:
                break
            obj = ByID(oid)
            if obj and obj.CheckAccess("read"):
                rest_obj = request.view(obj, app=get_collection_app(request))
                if with_classification:
                    rest_obj['system:classification'] = utils.ensure_json_serialiability(
                        api.get_classification(obj)
                    )
                result.append(rest_obj)
        return result
    except Exception as e: # pylint: disable=W0703
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))
