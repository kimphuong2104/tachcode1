#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# -*- Python -*-
#
# $Id$
#
# Copyright (c) 2001,2002 by CONTACT Software GmbH.
# All rights reserved


from cdb import ue, util
from cdb.objects import (
    Forward,
    LocalizedField,
    Object,
    Reference_1,
    Reference_Methods,
    Reference_N,
    State,
)
from cdb.objects.common import WithImage
from cdb.platform import FolderContent
from cdb.sig import connect
from cs.metrics.qcclasses import WithQualityCharacteristic
from cs.tools.powerreports import WithPowerReports

fPortfolio = Forward(__name__ + ".Portfolio")
fPortfolioFolder = Forward(__name__ + ".PortfolioFolder")
fPortfolioCategory = Forward(__name__ + ".PortfolioCategory")

fFolderContent = Forward("cdb.platform.FolderContent")


class Portfolio(Object, WithImage, WithPowerReports, WithQualityCharacteristic):
    __classname__ = "cdb_portfolio"
    __maps_to__ = "cdb_portfolio"

    Categories = Reference_N(
        fPortfolioCategory,
        fPortfolioCategory.portfolio_object_id == fPortfolio.cdb_object_id,
    )

    def _getTopFolders(self):
        if self.Categories:
            top_cat = min(self.Categories, key=lambda x: x.ebene)
            return top_cat.Folders
        else:
            return []

    TopFolders = Reference_Methods(fPortfolioFolder, lambda self: self._getTopFolders())

    Name = LocalizedField("name")

    class IN_PROCESS(State):
        status = 0

    class VALID(State):
        status = 100

    class OUTDATED(State):
        status = 200

    @classmethod
    def on_cdbbqc_portfolio_navigator_now(cls, ctx):
        ctx.url("powerscript/cs.portfolios.navigator.navigator")


class PortfolioCategory(Object, WithImage):
    __classname__ = "cdb_portfolio_category"
    __maps_to__ = "cdb_portfolio_category"

    Folders = Reference_N(
        fPortfolioFolder,
        fPortfolioFolder.category_object_id == fPortfolioCategory.cdb_object_id,
    )
    Portfolio = Reference_1(fPortfolio, fPortfolioCategory.portfolio_object_id)

    Name = LocalizedField("name")


class PortfolioFolder(Object, WithImage, WithQualityCharacteristic, WithPowerReports):
    __classname__ = "cdb_portfolio_folder"
    __maps_to__ = "cdb_portfolio_folder"

    SubFolders = Reference_N(
        fPortfolioFolder,
        fPortfolioFolder.parent_object_id == fPortfolioFolder.cdb_object_id,
    )
    Category = Reference_1(fPortfolioCategory, fPortfolioFolder.category_object_id)
    Parent = Reference_1(fPortfolioFolder, fPortfolioFolder.parent_object_id)
    Portfolio = Reference_1(fPortfolio, fPortfolioCategory.portfolio_object_id)

    FolderContents = Reference_N(
        fFolderContent, fFolderContent.cdb_folder_id == fPortfolioFolder.cdb_object_id
    )

    Name = LocalizedField("name")

    class IN_PROCESS(State):
        status = 0

    class VALID(State):
        status = 100

    class OUTDATED(State):
        status = 200

    @classmethod
    def _get_category(cls, parent):
        """
        Return the category (i.e. its object_id) one level deeper as
        parent.Category
        """
        expr = (PortfolioCategory.portfolio_object_id == parent.portfolio_object_id) & (
            PortfolioCategory.ebene > parent.Category.ebene
        )
        next_cats = PortfolioCategory.Query(expr)
        if not next_cats:
            raise ue.Exception("cdbvp_portfolio_leaves")

        cat = min(next_cats, key=lambda x: x.ebene)
        return cat.cdb_object_id

    def fill_fields(self, ctx):
        """
        Wenn ein Ordner im Kontext der Beziehung cdb_portfolio_folder2childern angelegt
        wird, muss das Feld category_object_id im UE vorbelegt werden.
        """
        if ctx.relationship_name == "cdb_portfolio_folder2childern":
            self.category_object_id = PortfolioFolder._get_category(self.Parent)

            if ctx.mode == "pre_mask":
                ctx.set("portfolio_object_id", self.Parent.portfolio_object_id)

    def check_parent(self, ctx):
        """
        Das Parent eines Portfolio-Ordners muss ein Element
        aus einer oberen Kategorie sein
        """
        if self.Parent and self.category_object_id != self._get_category(self.Parent):
            raise ue.Exception("cdbvp_portfolio_parent_ebene")
        if (
            not self.Parent
            and self.category_object_id
            != min(self.Portfolio.Categories, key=lambda x: x.ebene).cdb_object_id
        ):
            raise ue.Exception("cdbvp_portfolio_top_level_category")

    def set_category(self, ctx):
        if not self.Category:
            if self.Parent:
                self.category_object_id = PortfolioFolder._get_category(self.Parent)
            elif ctx.relationship_name == "cdb_portfolio2top_folders":
                cats = self.Portfolio.Categories
                if cats:
                    self.category_object_id = min(
                        cats, key=lambda x: x.ebene
                    ).cdb_object_id

    def set_child_category(self, ctx):
        if ctx.changed_item == "parent_object_id":
            if self.Parent:
                self.category_object_id = self._get_category(self.Parent)
                ctx.set("category_object_id", self._get_category(self.Parent))

    def set_position(self, ctx=None):
        self.position = util.nextval("cdb_portfolio_position", 10)

    def on_cdb_portfolio_move_up_now(self, ctx):
        expr = (
            (PortfolioFolder.category_object_id == self.category_object_id)
            & (PortfolioFolder.parent_object_id == self.parent_object_id)
            & (PortfolioFolder.position < self.position)
        )
        pres = PortfolioFolder.Query(expr)
        if not pres:
            raise ue.Exception("cdbvp_portfolio_folder_top_position")

        pre = max(pres, key=lambda x: x.position)
        tmp = pre.position
        pre.position = self.position
        self.position = tmp

    def on_cdb_portfolio_move_down_now(self, ctx):
        expr = (
            (PortfolioFolder.category_object_id == self.category_object_id)
            & (PortfolioFolder.parent_object_id == self.parent_object_id)
            & (PortfolioFolder.position > self.position)
        )
        pres = PortfolioFolder.Query(expr)
        if not pres:
            raise ue.Exception("cdbvp_portfolio_folder_bottom_position")

        succ = min(pres, key=lambda x: x.position)
        tmp = succ.position
        succ.position = self.position
        self.position = tmp

    # Needed for quality characteristics
    def _get_childern_values(self, qc):
        result = 0
        def_id = qc.Definition.cdb_object_id
        for fold in self.SubFolders:
            qcs = fold.ObjectQualityCharacteristics.KeywordQuery(
                cdbqc_def_object_id=def_id
            )
            if qcs:
                new_qc = qcs[0]
                new_qc.Association.ComputationRule.compute(new_qc)
                if new_qc.act_value:
                    result += new_qc.act_value
        return result

    def set_portfolio_object_id(self, ctx):
        self.portfolio_object_id = self.Category.portfolio_object_id

    def check_name(self, ctx):
        from cdb import i18n

        for iso in i18n.getActiveGUILanguages():
            if self["name_%s" % iso]:
                f = PortfolioFolder.Query(
                    "{iso}='{name_iso}' and parent_object_id='{parent_object_id}'"
                    " and portfolio_object_id='{portfolio_object_id}'".format(
                        iso="name_%s" % iso,
                        name_iso=self["name_%s" % iso],
                        parent_object_id=self.parent_object_id,
                        portfolio_object_id=self.portfolio_object_id,
                    )
                )
                if f and f[0].cdb_object_id != self.cdb_object_id:
                    raise ue.Exception("portfolio_folder_name_exists", iso)

    event_map = {
        (("create"), ("pre_mask", "pre")): "fill_fields",
        (("create", "modify", "copy"), ("pre")): ("check_parent", "check_name"),
        (("create", "copy"), "pre_mask"): ("set_position", "set_category"),
        (("create", "copy", "modify"), "dialogitem_change"): "set_child_category",
        (("create", "copy"), "pre"): "set_portfolio_object_id",
    }


@connect(FolderContent, "create", "post")
def force_uniqueness(self, ctx):
    if ctx.relationship_name == "cdb_portfolio_folder2folder_content":
        self_folder = PortfolioFolder.ByKeys(cdb_object_id=self.cdb_folder_id)

        condition = (FolderContent.cdb_content_id == self.cdb_content_id) & (
            FolderContent.cdb_folder_id != self.cdb_folder_id
        )
        the_others = FolderContent.Query(condition)
        for other in the_others:
            other_folder = PortfolioFolder.ByKeys(cdb_object_id=other.cdb_folder_id)
            if other_folder and other_folder.Portfolio == self_folder.Portfolio:
                other.Delete()
