# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import logging

from cdb import ElementsError, auth, sqlapi, util
from cdb.objects import Forward, Object, Reference_1, Reference_N
from cdb.platform import gui, mom
from cdb.tools import getObjectByName
from cdbwrapc import CDBClassDef
from cs.platform.web.rest.support import values_from_rest_key

from cs.pcs.projects.common.lists.helpers import (
    _generateDisplayConfig,
    _generateListItems,
)
from cs.pcs.projects.data_sources import DataSource

# Forward declarations
fListConfig = Forward(__name__ + ".ListConfig")
fListConfig2DataProvider = Forward(__name__ + ".ListConfig2DataProvider")
fListDataProvider = Forward(__name__ + ".ListDataProvider")
fListItemConfig = Forward(__name__ + ".ListItemConfig")
fListItemConfigEntry = Forward(__name__ + ".ListItemConfigEntry")
fDisplayType = Forward(__name__ + ".DisplayType")


class ListConfig(Object):
    __classname__ = __maps_to__ = "cs_list_config"
    HETEROGENOUS = "### heterogenous ###"

    ListDataProviderReference = Reference_N(
        fListConfig2DataProvider,
        fListConfig2DataProvider.list_cfg_object_id == fListConfig.cdb_object_id,
        order_by="sort_order",
    )

    def combineDisplayConfigsAndListOfItems(self, request, restKey=None):
        """
        :param request: HTTP request
        :type request: request

        :param restKey: restKey of the context object,
                        e.g. a project or project_task

        :returns: display_configs, list_items, rolename, error_message
        :rtype: tuple (dict, list, basestring, basestring)

        Combines display configurations and list items for all data providers.

        Display configurations are returned as the first tuple element
        ``display_configs`` and are indexed by the configuration IDs.

        List items are returned as the second tuple element ``list_items``.

        .. warning ::

            If an error occurs at runtime, an error message is generated and
            the method returns early. The return value will be incomplete.
        """
        errorMsg = ""
        rolenames = set()
        dict_of_display_configs = {}
        combined_list_of_items = []

        AllListDataProvider = [
            provRef.ListDataProvider for provRef in self.ListDataProviderReference
        ]

        for provider in AllListDataProvider:
            (
                display_config_id,
                display_config,
                list_of_items,
                isError,
                _,
            ) = provider.generateDisplayConfigAndListItems(
                request,
                restKey,
            )
            # if an error occurred in one of the dataproviders
            if isError:
                errorMsg = util.get_label(
                    "cs.pcs.projects.common.lists.list.config_error_data_provider"
                ).format(provider.name)
                return dict_of_display_configs, combined_list_of_items, None, errorMsg

            dict_of_display_configs.update({display_config_id: display_config})
            combined_list_of_items += list_of_items

            rolenames.add(provider.rolename)

        if len(rolenames) == 0:
            rolename = None
        elif len(rolenames) == 1:
            rolename = rolenames.pop()
        else:
            rolename = self.HETEROGENOUS

        return dict_of_display_configs, combined_list_of_items, rolename, errorMsg

    def generateListJSON(self, request, restKey=None):
        """
        :param request: HTTP request
        :type request: request

        :param restKey: restKey of the context object,
                        e.g. a project or project_task


        :returns: Data required by the frontend to render lists using this
            configuration.
        :rtype: dict

        .. rubric :: Example return value

        .. code-block :: python

            {
                "title": "List Config's Label",
                "items": [],
                "displayConfigs": {},
                "configError": "",
            }

        """
        (
            dict_of_display_configs,
            list_of_items,
            rolename,
            errorMsg,
        ) = self.combineDisplayConfigsAndListOfItems(
            request,
            restKey,
        )
        return {
            "title": util.get_label(self.label_id),
            "items": list_of_items,
            "displayConfigs": dict_of_display_configs,
            "configError": errorMsg,
            "relshipName": rolename,
        }


class ListConfig2DataProvider(Object):
    __classname__ = __maps_to__ = "list_cfg2data_provider"

    ListConfig = Reference_1(fListConfig, fListConfig2DataProvider.list_cfg_object_id)
    ListDataProvider = Reference_1(
        fListDataProvider, fListConfig2DataProvider.list_data_provider_object_id
    )


class ListDataProvider(Object):
    __classname__ = __maps_to__ = "cs_list_dataprovider"

    DataSource = Reference_1(
        DataSource,
        DataSource.data_source_id == fListDataProvider.data_source_id,
        DataSource.rest_visible_name == fListDataProvider.rest_visible_name,
    )

    def get_sql_statement(self, key_names, key_values):
        """
        :raises IndexError: if lengths of `key_names` and `key_values` differ
        """
        table = self.DataSource.get_table()
        add_where = " AND ".join(
            [
                f"{key}='{sqlapi.quote(value)}'"
                for key, value in zip(key_names, key_values)
            ]
        )
        sql_stmt = (
            f"SELECT cdb_object_id, {', '.join(key_names)} "
            f"FROM {table} "
            f"WHERE {self.DataSource.get_where()} AND {add_where} "
            f"{self.DataSource.get_order_by()}"
        )
        return sql_stmt

    def _get_sql_stmt(self, rest_name, rest_key):
        if rest_key is None:
            return None

        def _validate_key_values(key_values, key_names):
            expected_length = len(key_names)

            if len(key_values) != expected_length:
                logging.error(
                    "invalid REST key for %s: '%s' (expected %s keys)",
                    rest_name,
                    rest_key,
                    expected_length,
                )
                raise ValueError

            return key_values

        if rest_name in ("project", "project_task"):
            try:
                classdef = CDBClassDef.findByRESTName(rest_name)
            except ElementsError as exc:
                logging.error("invalid REST name: '%s'", rest_name)
                raise ValueError from exc

            key_names = list(classdef.getKeyNames())
            key_values = values_from_rest_key(rest_key)

            # remove ce_baseline_id (assumed to be last primary key) from key_names
            # and key_values because lists are only shown for the current
            # head of project/task (i.e. empty baseline id)
            key_names.pop()
            key_values.pop()

            key_values = _validate_key_values(key_values, key_names)

            return self.get_sql_statement(key_names, key_values)

        return None

    def _resolveDataSourceSQL(self, restKey=None):
        """
        :param restKey: restKey of the context object,
                        e.g. a project or project_task

        :returns: ``cdb_object_id`` of each identified object and whether an
            error occurred
        :rtype: tuple (list, boolean)

        Resolves SQL-Stmt of ``self.DataSource`` and ``cdb_object_id`` of each
        identified objects.

        If the table of the ``DataSource`` and the class of the ``ListDataProvider``
        differ, this is considered an error.

        In case of an error, an empty list and ``True`` are returned.
        Otherwise, the list of ``cdb_object_ids`` and ``False`` are returned.
        """

        # Note: To check if given SQl_Stmt does find objects/records of the correct class
        # of the list config, compare DataSource Resulting_Classname and ListDataProvider ClassName

        # if table name does not match with chosen class, return empty list
        if self.DataSource.resulting_classname != self.classname:
            logging.exception(
                gui.Message.GetMessage(
                    "cdbpcs_list_ds_not_match_dp_classname",
                    self.DataSource.data_source_id,
                    self.classname,
                    self.name,
                )
            )
            return [], True

        try:
            sql_stmt = self._get_sql_stmt(
                self.DataSource.rest_visible_name,
                restKey,
            )
        except ValueError:
            return [], True

        if sql_stmt is None:
            # if DataSource is configured for sth else than project and project_task
            # this is a confguration error which needs to be logged
            logging.exception(
                gui.Message.GetMessage(
                    "cdbpcs_list_ds_rest_name_invalid",
                    self.DataSource.data_source_id,
                    self.DataSource.rest_visible_name,
                    self.name,
                )
            )
            return [], True

        # use recordset; SQL-Statement always costs the same and RecordSet is
        # lazily evaluated
        records = sqlapi.RecordSet2(sql=sql_stmt)
        # Note: Read Access is checked in function getObjectHandlesFromDataSource
        return [record.cdb_object_id for record in records], False

    def getObjectHandlesFromDataSource(self, restKey=None):
        """
        :param restKey: restKey of the context object,
                e.g. a project or project_task

        :returns: ``ObjectHandle`` for each identified object,
            the sorted list of keys, and whether an
            error occurred
        :rtype: tuple (dict, list, boolean)

        Resolves an ``ObjectHandle`` for each object provided by the
        Data Source and returns them as a dict.

        If an error occurs, an empty dict, the list of keys and ``True`` are returned.
        Otherwise, the dict of ``ObjectHandles``, the list of keys and ``False`` are returned.
        """

        object_ids, isError = self._resolveDataSourceSQL(restKey)
        handles_dict = {}
        if not isError and object_ids:
            # getObjectHandlesFromObjectIDs uses cache for not-reloading
            # data from db if not necessary. Also, check read access for
            # returned objects.
            handles_dict = mom.getObjectHandlesFromObjectIDs(object_ids, False, True)
        # only return cdb_object_ids of object handles read access is granted
        # an keep the order of object_ids
        accessible_object_ids = [
            object_id for object_id in object_ids if object_id in handles_dict
        ]

        return handles_dict, accessible_object_ids, isError

    ListItemConfig = Reference_1(
        fListItemConfig, fListDataProvider.list_item_cfg_object_id
    )

    def getObjectHandlesFromRelship(self, restkey):
        def _check_read_access_on_objhndl(objhndl):
            hasReadAccess = False
            try:
                hasReadAccess = (
                    objhndl and objhndl.getAccessInfo(auth.persno)["read"][0]
                )
            except (IndexError, AttributeError, KeyError):
                logging.exception(
                    "ListDataProvider - _check_read_access_on_objhndl: "
                    "failed to check access on object handle"
                )
            return hasReadAccess

        cdef = CDBClassDef(self.referer)
        restkeys = restkey.split("@")
        keys = mom.SimpleArgumentList()
        i = 0
        for keyname in cdef.getKeyNames():
            keys.append(mom.SimpleArgument(keyname, restkeys[i]))
            i += 1
        objhndl = mom.CDBObjectHandle(cdef, keys, False, True)
        # Only proceed if read access is granted on the object the relship
        # shall be resolved from
        hasReadAccess = _check_read_access_on_objhndl(objhndl)
        if not hasReadAccess:
            logging.warning(
                "ListDataProvider - getObjectHandlesfromRelship: "
                "user '%s' has no read access on object of class '%s' with keys '%s' "
                "or object does not exists.",
                auth.persno,
                self.referer,
                restkeys,
            )
            return {}, [], True, ""

        # Resolve the Relship
        rs_def = cdef.getRelationshipByRolename(self.rolename)
        if rs_def and rs_def.is_valid():
            objhndls = objhndl.navigate_Relship(rs_def.get_identifier())
            objhndl_dict = {}
            objids = []
            for hndl in objhndls:
                # only add handles of objects found by relship
                # if read access is granted upon them
                if _check_read_access_on_objhndl(hndl):
                    oid = hndl.cdb_object_id
                    objhndl_dict[oid] = hndl
                    objids.append(oid)
            return objhndl_dict, objids, False, rs_def.get_label()
        else:
            return {}, [], True, ""

    def generateDisplayConfigAndListItems(self, request, restKey=None):
        # pylint: disable=too-many-return-statements
        """
        :param request: HTTP request. Used for generating links.
        :type request: request

        :param restKey: restKey of the context object,
                e.g. a project or project_task

        :returns: display_config_id, display_config, list_of_items, isError
        :rtype: tuple (basestring, dict, list, boolean)

        Generates a display configuration, defining how a list item is to be
        displayed in the frontend and a list of items, each containing only the
        attributes needed to display the corresponding list entry.

        If any error occurs, the return value's last element will be ``True``
        and the first one may be empty or incomplete.
        """
        list_of_items = []

        list_item_config = self.ListItemConfig
        display_config_id = list_item_config.name

        if not list_item_config.isValid():
            logging.exception(
                gui.Message.GetMessage(
                    "cdbpcs_list_list_item_config_invalid", display_config_id
                )
            )
            return "", {}, [], True

        list_of_config_entries = list_item_config.AllListItemConfigEntries
        (
            display_config,
            dict_of_attribute_functions,
            isDisplayConfigError,
        ) = _generateDisplayConfig(list_of_config_entries, self.classname)

        if isDisplayConfigError:
            return "", {}, [], True, ""

        label = ""
        if self.data_source_id:
            (
                dict_of_matched_object_handles,
                sortedKeys,
                isErrorDataSourceEval,
            ) = self.getObjectHandlesFromDataSource(restKey)
            if isErrorDataSourceEval:
                logging.exception(
                    gui.Message.GetMessage(
                        "cdbpcs_list_err_ds_eval", self.DataSource.data_source_id
                    )
                )
                return "", {}, [], True, ""
        elif self.rolename:
            (
                dict_of_matched_object_handles,
                sortedKeys,
                isErrorRolenameEval,
                label,
            ) = self.getObjectHandlesFromRelship(restKey)
            if isErrorRolenameEval:
                logging.exception(
                    gui.Message.GetMessage("cdbpcs_list_err_ds_eval", self.rolename)
                )
                return "", {}, [], True, ""
        else:
            return "", {}, [], True, ""

        list_of_items, isListError = _generateListItems(
            display_config_id,
            dict_of_attribute_functions,
            dict_of_matched_object_handles,
            sortedKeys,
            request,
        )

        if isListError:
            return "", {}, [], True, ""

        return display_config_id, display_config, list_of_items, False, label

    def generateListJSON(self, request, restKey=None):
        """
        :param request: HTTP request
        :type request: request

        :param restKey: restKey of the context object,
                        e.g. a project or project_task


        :param restKey: restKey of the context object,
                        e.g. a project or project_task

        :returns: Data required by the frontend to render lists using this
            configuration.
        :rtype: dict

        .. rubric :: Example return value

        .. code-block :: python

            {
                "title": Relship Label",
                "items": [],
                "displayConfigs": {},
                "configError": "",
            }

        """
        (
            display_config_id,
            display_config,
            list_of_items,
            isError,
            label,
        ) = self.generateDisplayConfigAndListItems(request, restKey)

        errorMsg = ""
        # if an error occurred in one of the dataproviders, determine error msg
        if isError:
            errorMsg = util.get_label(
                "cs.pcs.projects.common.lists.list.config_error_data_provider"
            ).format(self.name)

        presets = {}
        if self.referer:
            cdef = CDBClassDef(self.referer)
            restkeys = restKey.split("@")
            i = 0
            for keyname in cdef.getKeyNames():
                presets[keyname] = restkeys[i]
                i += 1
        return {
            "title": label,
            "items": list_of_items,
            "displayConfigs": {display_config_id: display_config},
            "configError": errorMsg,
            "presets": presets,
        }


class ListItemConfig(Object):
    __classname__ = __maps_to__ = "cs_list_item_config"

    AllListItemConfigEntries = Reference_N(
        fListItemConfigEntry,
        fListItemConfigEntry.list_item_cfg_object_id == fListItemConfig.cdb_object_id,
        order_by="display_order",
    )

    def _getAllPrimaryEntries(self):
        """
        :returns: "Primary" ``ListItemConfigEntry`` objects
        :rtype: list

        .. note ::

            There should only be one entry in the list returned in order for
            the ``ListItemConfig`` to be valid.
        """
        return [
            entry
            for entry in self.AllListItemConfigEntries
            if entry.layout_position == "primaryText"
        ]

    def isValid(self):
        """
        :returns: Whether the ``ListItemConfig`` is valid or not
        :rtype: bool

        A ``ListItemConfig`` is valid if

        - there is exactly one "primaryText" entry and
        - the "primaryText" entry uses the 'cs-pcs-widgets-TextRenderer'
            component
        """
        list_of_primary = self._getAllPrimaryEntries()
        if len(list_of_primary) == 1:
            return (
                list_of_primary[0].DisplayType.component
                == "cs-pcs-widgets-TextRenderer"
            )
        return False

    def getPrimaryAttribute(self):
        """
        :returns: Attribute name to be used as "primaryText" label; ``None`` if
            the ``ListItemConfig`` is invalid
        :rtype: basestring

        :raises IndexError: if no primary entry exists.
        """
        if self.isValid():
            return self._getAllPrimaryEntries()[0].content
        return None


class ListItemConfigEntry(Object):
    __classname__ = __maps_to__ = "cs_list_item_cfg_entry"

    DisplayType = Reference_1(fDisplayType, fListItemConfigEntry.display_type_object_id)

    def getDisplayTypeProperties(self):
        """
        :returns: Functions generating values indexed by property names
        :rtype: dict

        .. rubric :: Example return value

        .. code-block :: python

            {"my_property": get_my_property_values}

        :raises ImportError: if any function specified by the configuration
            cannot be imported.
        """
        python_function = getObjectByName(self.DisplayType.fqpyname)
        # call python function of DisplayType
        properties = python_function(self.content)
        return properties

    def getDisplayTypeComponent(self):
        """
        :returns: component name of the display type
        :rtype: basestring

        The component name of ``self.DisplayType`` is expected to be a fully
        qualified React component name.
        """
        return self.DisplayType.component


class DisplayType(Object):
    __classname__ = __maps_to__ = "cs_list_item_display_type"
