# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb.objects import ByID
from cdb.platform import CDBCatalog
from cdb.platform.gui import CDBCatalogContent
from cs.variants import VariabilityModel

# noinspection PyProtectedMember
from cs.vp.products import Product


class VariabilityModelContextMaxBomBrowser(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)
        self.variability_model_id = None
        self.browser_data = None

    def init(self):
        if self.getInvokingField():
            try:
                self.variability_model_id = self.getInvokingDlgValue(
                    "variability_model_id"
                )
            except KeyError:
                pass
            if (
                self.variability_model_id is not None
                and self.variability_model_id != ""
            ):
                self.browser_data = VariabilityModelContextMaxBomBrowserData(
                    self, self.variability_model_id
                )
                self.setResultData(self.browser_data)

    def allowMultiSelection(self):
        return self.kDisableMultiSelection

    def handleResultDataSelection(self, selected_rows):
        if len(selected_rows) == 1:
            sel_item = self.browser_data.items[selected_rows[0]]
            self.setValue("max_bom_id", sel_item.cdb_object_id)
            self.setValue(".max_bom_id", sel_item.cdb_object_id)


class VariabilityModelContextMaxBomBrowserData(CDBCatalogContent):
    def __init__(self, catalog, variability_model_id):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        self.items = VariabilityModel.ByKeys(variability_model_id).MaxBOMs

    def getNumberOfRows(self):
        return len(self.items)

    def getRowObject(self, row):
        return self.items[row].ToObjectHandle()


class ProductContextVariabilityModelBrowser(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)
        self.product_object_id = None
        self.browser_data = None

    def init(self):
        if self.getInvokingField():
            try:
                self.product_object_id = self.getInvokingDlgValue("product_object_id")
            except KeyError:
                pass
            if self.product_object_id is not None and self.product_object_id != "":
                self.browser_data = ProductContextVariabilityModelBrowserData(
                    self, self.product_object_id
                )
                self.setResultData(self.browser_data)

    def allowMultiSelection(self):
        return self.kDisableMultiSelection

    def handleResultDataSelection(self, selected_rows):
        if len(selected_rows) == 1:
            sel_item = self.browser_data.items[selected_rows[0]]
            self.setValue("variability_model_id", sel_item.cdb_object_id)


class ProductContextVariabilityModelBrowserData(CDBCatalogContent):
    def __init__(self, catalog, product_object_id):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        self.items = Product.ByKeys(product_object_id).VariabilityModels

    def getNumberOfRows(self):
        return len(self.items)

    def getRowObject(self, row):
        return self.items[row].ToObjectHandle()


class MaxBomVariabilityModelBrowser(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)
        self.maxbom_object_id = None
        self.browser_data = None

    def init(self):
        if self.getInvokingField():
            try:
                self.maxbom_object_id = self.getInvokingDlgValue("maxbom_object_id")
            except KeyError:
                pass
            if self.maxbom_object_id is not None and self.maxbom_object_id != "":
                self.browser_data = MaxBomVariabilityModelBrowserData(
                    self, self.maxbom_object_id
                )
                self.setResultData(self.browser_data)

    def allowMultiSelection(self):
        return self.kDisableMultiSelection

    def handleResultDataSelection(self, selected_rows):
        if len(selected_rows) == 1:
            sel_item = self.browser_data.items[selected_rows[0]]
            self.setValue("variability_model_id", sel_item.cdb_object_id)


class MaxBomVariabilityModelBrowserData(CDBCatalogContent):
    def __init__(self, catalog, maxbom_object_id):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        item = ByID(maxbom_object_id)
        if item is not None:
            self.items = item.Products

    def getNumberOfRows(self):
        return len(self.items)

    def getRowObject(self, row):
        return self.items[row].ToObjectHandle()


class ThreedMasterModelFormatCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        from cs.threed.hoops.converter import SELECTABLE_CONVERSION_FORMATS

        return [each.split("_")[-1].upper() for each in SELECTABLE_CONVERSION_FORMATS]
