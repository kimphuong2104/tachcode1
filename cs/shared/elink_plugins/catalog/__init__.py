#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
An eLink plugin to generate a catalog for selection.

Usage
=====
    1. Create a data provider in python to generate the data rows.


"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from math import ceil

import six

from cdb import elink
from cdb import sqlapi
from cdb.platform.gui import Table
from cdb.platform.mom import entities


class CatalogTools:

    @staticmethod
    def get_field_type(typecode):
        return "number" if typecode in (sqlapi.SQL_FLOAT, sqlapi.SQL_INTEGER) \
                        else "text"

    @staticmethod
    def get_std_table_def(table_name, table_class, searchable):
        table = Table.KeywordQuery(name=table_name).pop()
        entcls = entities.CDBClassDef(table_class)
        tabdef = entcls.getProjection(table_name, True)
        table_def = {"searchable": False,
                     "columns": []}
        visible = table.Attributes.KeywordQuery(
                            name=table_name, anzeigen=1).attribut
        for col in tabdef.getColumns():
            if not col.containsTargetAttr():
                continue
            attr_dict = {}
            attr = col.getAttribute()
            fddef = entcls.getAttributeDefinition(attr)
            if fddef:
                attr_dict["label"] = six.text_type(fddef.getLabel())
            else:
                attr_dict["label"] = ""
            attr_dict["attribute"] = attr
            attr_dict["type"] = CatalogTools.get_field_type(fddef.getSQLType())
            attr_dict["visible"] = attr in visible
            attr_dict["searchable"] = attr in searchable
            table_def["searchable"] = \
                table_def["searchable"] or attr_dict["searchable"]
            table_def["columns"].append(attr_dict)
        return table_def

    @staticmethod
    def get_search_conditions(**varkw):
        result = u"1=1"
        if "catalog_search_conditions" in varkw:
            import json
            values = []
            try:
                parsed = json.loads(varkw["catalog_search_conditions"])
                for k in parsed:
                    values.append(u"lower(%s) like '%%%s%%'" % (
                                        k, parsed[k].lower()))
            except Exception as e:
                from cdb import misc
                misc.cdblogv(
                    misc.kLogErr,
                    7,
                    "Error by parsing catalog search conditions: %s" % e)
            if values:
                result = " and ".join(values)
        return result


class ElinkCatalogBase(elink.Template):

    __html__ = """
        <metal:layout use-macro="global_plugins['catalog'].macros['open_catalog']" />"""
    __table_def__ = None

    def get_table_def(self, **varkw):
        return {}

    def get_data(self, **varkw):
        return []

    def get_catalog_title(self, **varkw):
        return None

    def get_entry_id(self, entry):
        return entry.GetObjectID()

    def _data_wrapper(self, table_def, datalist):
        new_datalist = []
        if table_def and "columns" in table_def:
            for data in datalist:
                new_data = []
                for column_def in table_def["columns"]:
                    result = {"name": column_def["attribute"],
                              "text": data.GetFormattedValue(
                                            column_def["attribute"])}
                    if column_def["type"] == "number":
                        result["value"] = getattr(data,
                                                  column_def["attribute"])
                    new_data.append(result)
                new_data.insert(0, {"name": "_description",
                                    "text": data.GetDescription()})
                new_data.insert(0, {"name": "_id",
                                    "text": self.get_entry_id(data)})
                new_datalist.append(new_data)
        return new_datalist

    def make_page(self, datalist, table_page_size, page_no):
        start = (page_no - 1) * table_page_size
        end = page_no * table_page_size
        # Paginator: (current page No., total pages)
        paginator = (page_no, int(ceil(len(datalist) * 1.0 / table_page_size)))
        return datalist[start:end], paginator

    def render(self, context, **varkw):
        from json import loads
        table_page_size = int(varkw.pop("table_page_size", "10"))
        page_no = int(varkw.pop("page_no", "1"))
        catalog_def_required = loads(varkw.pop(
                                        "catalog_def_required", "false"))
        result = {}
        result["table_page_size"] = table_page_size
        result["page_no"] = page_no
        result["catalog_def_required"] = catalog_def_required
        if result["catalog_def_required"]:
            result["catalog_title"] = self.get_catalog_title(**varkw)
        if self.__table_def__ is None:
            self.__table_def__ = self.get_table_def(**varkw)
        result["table_def"] = self.__table_def__
        result["datalist"] = []
        result["paginator"] = None
        catalog_no_data = loads(varkw.pop("catalog_no_data", "false"))
        if catalog_no_data:
            return result
        (datalist, paginator) = self.make_page(self.get_data(**varkw),
                                               table_page_size, page_no)
        from cdb.objects import Object
        try:
            if isinstance(datalist[0], Object):
                datalist = self._data_wrapper(self.__table_def__, datalist)
        except:
            pass
        result["paginator"] = paginator
        result["datalist"] = datalist
        return result


class ElinkCatalogStandard(ElinkCatalogBase):

    __catalog_table_name__ = ""
    __catalog_table_class__ = ""
    __catalog_table_searchable__ = []

    def get_table_def(self, **varkw):
        return CatalogTools.get_std_table_def(self.__catalog_table_name__,
                                              self.__catalog_table_class__,
                                              self.__catalog_table_searchable__)


class ElinkResponsibleCatalog(ElinkCatalogBase):
    """
    A role list should be provided to the autocomplete combobox::
    It should be a list of list like:
    [['<display text>', <role data>], ['<display text>', <role data>], ...]
    The 'role data' can be a dictionary or a list, it will be returned by the
    combobox if an entry is selected. The '<display text>' should be unique
    for each entry.

    In javascript, use 'plugins' in options of the catalog to config the
    'roles' variable of the plugin with a static role list, or specify an URL
    to generate data dynamically::

        ...
        var Catalog = new cdbElinkCatalog('body');
        ...
        Catalog.setupCatalog(myButton, {
            ...
            plugins: [
                {
                  name: 'responsible',
                  roles: [['Administrator', {id: 'caddok', type:'Person'}]]
                  // or:  roles: 'http://.../get_roles'
                }
            ]
        });

    """

    __html__ = """
        <metal:layout use-macro="global_plugins['catalog'].macros['responsible_catalog']" />"""
