# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module units

This is the documentation for the units module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
from collections import defaultdict
from cdb import ue
from cdb import ElementsError
from cdb import sqlapi
from cdb.objects.core import Object
from cdb.objects import references
from cdb.objects import expressions
from cdb.objects import ByID
from cdb.platform import gui
from cs.classification import tools


LOG = logging.getLogger(__name__)

fUnit = expressions.Forward("cs.classification.units.Unit")

_ureg = None
CS_UNITS_CURRENCY_DIMENSIONALITY = '[currency]'


def get_unit_registry():
    import pint
    global _ureg
    if _ureg is None:
        _ureg = pint.UnitRegistry()
        register_addtl_units(_ureg)
    return _ureg


def register_addtl_units(ureg):

    ureg.define('pct = 0.01*count')
    ureg.define('permill = 0.001*count')

    # Note: normally it is not required to define new *derived* units in code - they can simply be configured
    # in the "Physical Units" catalog in CDB. However new *base* units like EUR must be defined to register
    # their dimensionality with pint.
    ureg.define('EUR = ' + CS_UNITS_CURRENCY_DIMENSIONALITY)

    # The reason why the derived currencies are still defined in code below is that the "symbol" (the right
    # hand side of the expression passed to the define call below) is defined as unique constraint in the
    # Physical Units catalog in CDB, so that it is not possible to configure multiple derived units with the
    # same symbol (like "1 * EUR" in this case).
    for currency in [
        'CAD', 'CHF', 'CNY', 'GBP', 'JPY', 'RUB', 'TRY', 'USD'
    ]:
        ureg.define('{} = 1 * EUR'.format(currency))


class Unit(Object):
    __maps_to__ = "cs_unit"
    __classname__ = "cs_unit"

    CompatibleUnits = references.Reference_N(fUnit, fUnit.dimensionality == fUnit.dimensionality)

    @classmethod
    def get_pint_dimensionality(cls, symbol):
        import pint
        try:
            one = get_unit_registry().Quantity(symbol)
            return str(one.dimensionality)
        except Exception: # pylint: disable=W0703
            raise ue.Exception('cs_unit_not_defined')

    def set_dimensionality(self, ctx):
        self.dimensionality = Unit.get_pint_dimensionality(self.symbol)

    def set_fields_readonly(self, ctx):
        ctx.set_readonly('symbol')

    def clear_unit_cache(self, ctx):
        UnitCache.clear()

    def check_usage(self, ctx):
        sql_stmt_template = "count(unit_object_id) FROM %s WHERE unit_object_id = '%s'"
        for table in ['cs_property', 'cs_property_value', 'cs_object_property_value']:
            sql_stmt = sql_stmt_template % (table, self.cdb_object_id)
            result = sqlapi.SQLselect(sql_stmt)
            if sqlapi.SQLinteger(result, 0, 0) > 0:
                raise ue.Exception("cs_classification_err_unit_delete")

    event_map = {
        (('delete'), 'pre'): 'check_usage',
        (('create', 'copy'), 'pre'): 'set_dimensionality',
        (('modify'), 'pre_mask'): 'set_fields_readonly',
        (('create', 'copy', 'delete'), 'post'): 'clear_unit_cache',
    }


class UnitCache(object):
    _is_initialized = False
    _units_by_oid = {}
    _units_by_dimensionality = defaultdict(list)

    @classmethod
    def _init(cls):
        if not cls._is_initialized:
            for unit in Unit.Query():
                cls._add(unit)
            cls._is_initialized = True

    @classmethod
    def clear(cls):
        cls._is_initialized = False
        cls._units_by_oid = {}
        cls._units_by_dimensionality = defaultdict(list)

    @classmethod
    def _add(cls, unit):
        label = tools.get_label('symbol_label', unit._record)
        if not label:
            label = unit.symbol
        cls._units_by_oid[unit.cdb_object_id] = {'symbol': unit.symbol,
                                                 'label': label,
                                                 'dimensionality': unit.dimensionality,
                                                 'cdb_object_id': unit.cdb_object_id}
        cls._units_by_dimensionality[unit.dimensionality].append(unit.cdb_object_id)

    @classmethod
    def _check(cls, oid):
        if oid not in cls._units_by_oid:
            unit = Unit.ByKeys(cdb_object_id=oid)
            if unit:
                cls._add(unit)
            else:
                cls._units_by_oid[oid] = None

    @classmethod
    def get_unit_info(cls, oid):
        if not oid:
            return None
        cls._init()
        cls._check(oid)
        return cls._units_by_oid[oid]

    @classmethod
    def get_unit_label(cls, oid):
        info = cls.get_unit_info(oid)
        return info["label"] if info else ""

    @classmethod
    def get_compatible_units(cls, oid):
        result = []
        unit_info = cls.get_unit_info(oid)
        if unit_info:
            return cls._units_by_dimensionality.get(unit_info['dimensionality'], [])
        return result

    @classmethod
    def check_compatibility(cls, unit1_oid, unit2_oid):
        return cls.get_unit_info(unit1_oid)["dimensionality"] == cls.get_unit_info(unit2_oid)["dimensionality"]

    @classmethod
    def get_all_units_by_id(cls):
        cls._init()
        return cls._units_by_oid

    @classmethod
    def get_all_units_by_compatibility(cls):
        cls._init()
        return cls._units_by_dimensionality

    @classmethod
    def is_currency(cls, unit_oid):
        if not unit_oid:
            return False
        unit_info = cls.get_unit_info(unit_oid)
        if unit_info and CS_UNITS_CURRENCY_DIMENSIONALITY == unit_info.get('dimensionality', ''):
            return True
        else:
            return False


def normalize_value(float_value, unit_object_id, base_unit_id, prop_code):
    import pint
    if float_value is None:
        return None
    normalized_value = float_value
    if unit_object_id and base_unit_id:
        if unit_object_id != base_unit_id:
            unit = UnitCache.get_unit_info(unit_object_id)
            base_unit = UnitCache.get_unit_info(base_unit_id)
            if unit and base_unit:
                try:
                    value = get_unit_registry().Quantity(float_value, unit["symbol"])
                    normalized_value = value.to(base_unit["symbol"]).magnitude
                except pint.UndefinedUnitError:
                    raise ue.Exception("cs_unit_not_defined")
            elif not unit:
                raise ElementsError("Cannot calculate normalized float value for property %s "
                                    "due to invalid value unit object id: %s"
                                    % (prop_code, unit_object_id))
            elif not base_unit:
                raise ElementsError("Cannot calculate normalized float value for property %s "
                                    "due to invalid default unit object id: %s"
                                    % (prop_code, base_unit_id))
    elif unit_object_id and not base_unit_id:
        LOG.error(
            "Cannot calculate normalized float value for property %s due to missing default unit.", prop_code
        )
        normalized_value = None
    elif base_unit_id and not unit_object_id:
        LOG.error(
            "Cannot calculate normalized float value for property %s due to missing value unit.", prop_code
        )
        normalized_value = None
    return normalized_value


class CompatibleUnitsCatalog(gui.CDBCatalog):

    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):

        def get_prop_id(keys):
            for key in keys:
                try:
                    prop_id = self.getInvokingDlgValue(key)
                    if prop_id:
                        return prop_id
                except KeyError:
                    # try next
                    pass
            return ''

        objs = self.getInvokingOpObjects()

        unit_object_id = None
        prop_id = get_prop_id(["property_object_id", "assigned_property_object_id", "property_id"])
        if prop_id:
            prop = ByID(prop_id)
            if prop and prop.unit_object_id:
                unit_object_id = prop.unit_object_id
        else:
            try:
                # used for class properties
                unit_object_id = self.getInvokingDlgValue("unit_object_id")
            except KeyError:
                unit_object_id = None
        self.setResultData(CompatibleUnitCatalogContent(unit_object_id, self))


class CompatibleUnitCatalogContent(gui.CDBCatalogContent):

    def __init__(self, unit_object_id, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        gui.CDBCatalogContent.__init__(self, tabdef)
        self._data = []
        if unit_object_id:
            unit = Unit.ByKeys(cdb_object_id=unit_object_id)
            if unit:
                self._data = unit.CompatibleUnits

    def getNumberOfRows(self):
        return len(self._data)

    def getRowObject(self, row):
        return self._data[row].ToObjectHandle()
