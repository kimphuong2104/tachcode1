#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module Products
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi
from cdb import ue
from cdb.classbody import classbody
from cdb.objects import Forward, ReferenceMethods_1, ReferenceMethods_N
from cdb.objects import LocalizedField
from cdb.objects import Object, Reference_N, Reference_1, State
from cdb.objects.common import WithImage
from cdb.objects import org
from cdb.objects.org import WithSubject
from cdb.platform.mom import SimpleArguments
import cdbwrapc

from cs.actions import Action
from cs.metrics.qcclasses import WithQualityCharacteristic
from cs.portfolios import Portfolio
from cs.portfolios import PortfolioFolder
from cs.tools.powerreports import WithPowerReports
from cs.vp.variants.vptools import WithChangeLog
from cs.sharing.share_objects import WithSharing
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest import CollectionApp


# Exported objects
__all__ = []

fProduct = Forward(__name__ + ".Product")
fMaturity = Forward(__name__ + ".Maturity")
fFile = Forward("cdb.objects.cdb_file.CDB_File")
fCDB_File = Forward("cdb.objects.cdb_file.CDB_File")


class Product(WithSubject, WithImage, WithPowerReports, WithQualityCharacteristic,
              WithChangeLog, WithSharing):
    __maps_to__ = "cdbvp_product"
    __classname__ = "cdbvp_product"

    Images = Reference_N(fCDB_File,
                         fCDB_File.cdbf_object_id == fProduct.cdb_object_id)

    class INVALID(State):
        status = 300

    def setProductImagePreMask(self, ctx):
        if self.Image:
            ctx.redirect_icon("product_image", self.Image)

    @classmethod
    def on_preview_available_now(cls, ctx):
        ctx.enablePreview()

    def on_preview_now(self, ctx):
        preview_file = self.Image
        if preview_file:
            preview_file.handlePreviewCtx(ctx)
        else:
            self.Super(Product).on_preview_now(ctx)

    def _getImage(self):
        if self.Images:
            return self.Images[0]
        else:
            return None

    Image = ReferenceMethods_1(fFile, _getImage)

    ProductMaturity = Reference_1(fMaturity, fProduct.maturity)

    Name = LocalizedField("name")

    @classmethod
    def create_from_template(cls, ctx):
        """
        Create a product by selecting an template and copying it
        """
        # Get the project
        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name="cdbvp_product_template")
        else:
            product_id = ctx.catalog_selection[0]["cdb_object_id"]
            template = Product.ByKeys(product_id)
            ctx.set_followUpOperation("CDB_Copy", keep_rship_context=True, op_object=template)

    def keep_name(self, ctx):
        ctx.keep("code", ctx.object.code)

    @classmethod
    def on_cdbvp_upload_csv_to_client_now(cls, ctx):
        if "filename" in ctx.dialog.get_attribute_names():
            filename = ctx.dialog["filename"]
            ctx.file(filename)

    def createFollowUpOverview(self, ctx):
        """
        Tells `ctx` to start the follow up operation
        ``cdbpcs_product``. The follow up is only created if
        there is no pending error. Because CDB/Win starts a
        follow up on its own when performing a copy on the toplevel
        structure node, this method skips the creation of an
        additional follow up in this case.
        """
        if ctx.error != 0:
            return
        if ctx.action != "copy" or getattr(ctx.sys_args, "structurerootaction", "") != "1":
            ctx.set_followUpOperation('cdbvp_product', 1)

    event_map = {('cdbvp_create_from_template', 'now'): "create_from_template",
                 (('copy', 'modify', 'info'), 'pre_mask'): "setProductImagePreMask",
                 ('modify', 'pre'): 'keep_name',
                 (('create', 'copy'), 'post'): 'createFollowUpOverview'
                 }


class Maturity(Object):
    Name = LocalizedField("name")

    __maps_to__ = "cdbvp_maturity"
    __classname__ = "cdbvp_maturity"


@classbody
class Action(object):
    Product = Reference_1(Product, Action.product_object_id)


@classbody
class PortfolioFolder(object):
    def _getProducts(self):
        return [x for x in [Product.ByKeys(cdb_object_id=object_id)
                       for object_id in self.FolderContents.cdb_content_id] if not x is None]
    Products = ReferenceMethods_N(fProduct, _getProducts)

    def _getAllProducts(self):
        result = self.Products
        for folder in self.SubFolders:
            result += folder.AllProducts
        return result
    AllProducts = ReferenceMethods_N(fProduct, _getAllProducts)


@classbody
class Portfolio(object):
    def _getAllProducts(self):
        result = []
        for folder in self.TopFolders:
            result += folder.AllProducts
        return result
    AllProducts = ReferenceMethods_N(fProduct, lambda self: self._getAllProducts())


class ProductApp(GenericApp):
    def __init__(self):
        super(ProductApp, self).__init__("product")


@CollectionApp.mount(app=ProductApp, path="product")
def _mount_app():
    return ProductApp()


@GenericApp.defer_links(model=Product)
def _defer_item(app, _item):
    return app.child(ProductApp())


def generate_cdbvp_resp_brows():
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault
        collate = "COLLATE %s" % CollationDefault.get_default_collation()
    else:
        collate = ""

    sql_columns = []
    languages = set()

    class_def = cdbwrapc.CDBClassDef("cdb_global_role")
    for attr_def in class_def.getMultiLangAttributeDefs():
        sources = attr_def.getLanguageAttributeDefs()

        if attr_def.getName() == "description_ml":
            target_attr = "description_%s"
        elif attr_def.getName() == "name":
            target_attr = "subject_name_%s"
        else:
            target_attr = None

        if target_attr is not None:
            for lang_attr_def in sources:
                lang = lang_attr_def.getIsoLang()
                languages.add(lang)

                sql_columns.append(
                    "%s AS %s" % (lang_attr_def.getName(), target_attr % lang)
                )

    global_role_part = (
        "SELECT "
        "role_id AS subject_id, "
        "'Common Role' {collate} AS subject_type, "
        "{sql_columns}, "
        "1 AS order_by "
        "FROM cdb_global_role "
        "WHERE is_org_role = 1 "
    ).format(
        collate=collate,
        sql_columns=", ".join(sql_columns),
    )

    sql_columns = []

    for target_attr in ["description_%s", "subject_name_%s"]:
        for lang in languages:
            sql_columns.append("name AS %s" % (target_attr % lang))

    person_part = (
        "SELECT "
        "personalnummer AS subject_id, "
        "'Person' {collate} AS subject_type, "
        "{sql_columns}, "
        "3 AS order_by "
        "FROM  angestellter "
        "WHERE active_account='1' and visibility_flag='1'"
    ).format(
        collate=collate,
        sql_columns=", ".join(sql_columns),
    )

    stmt = (
        "{global_role_part} "
        "UNION "
        "{person_part}"
    ).format(
        global_role_part=global_role_part,
        person_part=person_part
    )

    return stmt

class ProductStatusProtocol(Object):
    __classname__ = "cdbvp_product_prot"
    __maps_to__ = "cdbvp_product_prot"


class ProductPart(Object):
    __classname__ = "cdbvp_product2part"
    __maps_to__ = "cdbvp_product2part"
