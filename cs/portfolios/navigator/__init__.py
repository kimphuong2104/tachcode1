#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# -*- Python -*-
#
# $Id$
#
# Copyright (c) 2001,2002 by CONTACT Software GmbH.
# All rights reserved

import json

from cdb import elink, typeconversion
from cdb.objects import ByID, Rule
from cdb.platform.mom import entities
from cs.portfolios import Portfolio
from cs.shared.elink_plugins.picture_uploader import PictureUploader

MAX_IMG_SIZE = 260

VISIBLE_PORTFOLIOS_RULE = "Visible Portfolios"
VISIBLE_FOLDERS_RULE = "Visible Portfolio Folders"


class Main(elink.Template):
    __template__ = "main.html"

    __navigator_plugins__ = None
    __cdbhelpid__ = "portfolio_navigator"

    def plugin(self):
        if self.__navigator_plugins__ is None:
            from cdb import sig

            plugins = sig.emit("cs.portfolio.navigator.getplugins")()
            self.__navigator_plugins__ = sorted(plugins, key=lambda x: x[0])
        return self.__navigator_plugins__

    def get_image(self, obj):
        img_obj = ByID(obj.image_object_id)
        if img_obj:
            return PictureUploader.get_preview_img(img_obj)
        else:
            return ""

    def _get_portfolios(
        self, categories_ids, blocks, dropdown_dict, path_list, entry_point
    ):
        """get portfolios' datas"""
        dropdown_list = []

        visible_portfolios = Rule.ByKeys(VISIBLE_PORTFOLIOS_RULE)
        portfolios = visible_portfolios.Objects

        if portfolios:
            i = 1
            for portfolio in portfolios:
                if entry_point:
                    blocks[0].append((i, portfolio))
                    i += 1
                dropdown_list.append([portfolio.Name[""], portfolio.cdb_object_id])

            path_list.insert(0, "Portfolios")
            dropdown_dict["Portfolios"] = dropdown_list

        return categories_ids, blocks, dropdown_dict, path_list

    def _get_data_portfolio(
        self, categories_ids, blocks, dropdown_dict, path_list, entry_point, obj
    ):
        """get data and move up"""

        if obj.Categories:
            dropdown_list = []

            oRule = Rule.ByKeys(VISIBLE_FOLDERS_RULE)
            folders = sorted(
                [fold for fold in obj.TopFolders if oRule.match(fold)],
                key=lambda x: x.position,
            )
            i = 1
            for folder in folders:
                if entry_point:
                    blocks[0].append((i, folder))
                    i += 1

            top_cat = min(obj.Categories, key=lambda x: x.ebene)
            path_list.insert(0, top_cat.Name[""])
            folders = [folder for folder in top_cat.Folders if oRule.match(folder)]

            for folder in folders:
                dropdown_list.append([folder.Name[""], folder.cdb_object_id])

            dropdown_dict[top_cat.Name[""]] = dropdown_list

        categories_ids.insert(0, [obj.Name[""], "?cdb_object_id=" + obj.cdb_object_id])
        return self._get_portfolios(
            categories_ids, blocks, dropdown_dict, path_list, False
        )

    def _get_data_not_bottom_folder(
        self, categories_ids, blocks, dropdown_dict, path_list, entry_point, obj
    ):
        """get data and move up"""
        dropdown_list = []

        oRule = Rule.ByKeys(VISIBLE_FOLDERS_RULE)
        folders = sorted(
            [fold for fold in obj.SubFolders if oRule.match(fold)],
            key=lambda x: x.position,
        )
        if folders:
            i = 1
            for folder in folders:
                if entry_point:
                    blocks[0].append((i, folder))
                    i += 1

            path_list.insert(0, folders[0].Category.Name[""])

            for folder in folders:
                dropdown_list.append([folder.Name[""], folder.cdb_object_id])

            dropdown_dict[folders[0].Category.Name[""]] = dropdown_list
        categories_ids.insert(0, [obj.Name[""], "?cdb_object_id=" + obj.cdb_object_id])

        if obj.Parent is None:
            next_obj = obj.Category.Portfolio
            return self._get_data_portfolio(
                categories_ids, blocks, dropdown_dict, path_list, False, next_obj
            )
        else:
            next_obj = obj.Parent
            return self._get_data_not_bottom_folder(
                categories_ids, blocks, dropdown_dict, path_list, False, next_obj
            )

    def _get_data_bottom_folder(
        self, categories_ids, dropdown_dict, path_list, entry_point, obj
    ):
        """get data and move up"""

        plugins = self.plugin()
        contents = obj.FolderContents
        blocks = [[] for _i in range(len(plugins) + 1)]
        for content in obj.FolderContents:
            found = False
            for j, plugin in enumerate(plugins):
                content_obj = ByID(content.cdb_content_id)
                if content_obj._getClassname() == plugin[1].__folder_content_class__:
                    blocks[j].append((len(blocks[j]), content_obj))
                    found = True
                    break
            if not found:
                blocks[-1].append((len(blocks[-1]), ByID(content.cdb_content_id)))
        categories_ids.insert(0, [obj.Name[""], "?cdb_object_id=" + obj.cdb_object_id])

        if obj.Parent is None:
            next_obj = obj.Category.Portfolio
            return self._get_data_portfolio(
                categories_ids, blocks, dropdown_dict, path_list, False, next_obj
            )
        else:
            next_obj = obj.Parent
            return self._get_data_not_bottom_folder(
                categories_ids, blocks, dropdown_dict, path_list, False, next_obj
            )

    def _get_data(self, cdb_object_id=None):
        """
        calls recursive functions starting at current cdb_object_id provided and
        moving upwards, getting all needed data. called in render()
        EX: product -> folder -> parent folder ... -> portfolio -> all portfolios

        :return: A tuple (reached_product_level, categories_ids, blocks,
                 path_list, dropdown_dict, entry_point) with the following meaning

                 - reached_product_level:
                             boolean value showing whether a product is
                             displayed. Needed for tal:condition, since
                             the product page is slightly different than
                             folder/portfolio page
                 - categories_ids:
                             name and cdb_object_id of selected categories.
                             Needed for breadcrumb
                 - blocks:
                             [[portfolios]] or, if in bottom folder,
                             [[products], [projects],(...) [other]], where
                             [objs] is [(1, obj1),(2, obj2),.....(n, objn)]
                 - path_list:
                             names of categories. Used in breadcrumb
                 - dropdown_dict:
                             names and cdb_object_id of values to be
                             displayed in dropdown menus in breadcrumb
                 - entry_point:
                             boolean value. True only at first entry in
                             _get_data_at_level(..).
                             Needed for getting the correct blocks
        """
        path_list = []
        dropdown_dict = {}
        categories_ids = [["", ""]]
        reached_product_level = False

        obj = None
        if cdb_object_id:
            obj = ByID(cdb_object_id)
        if obj and cdb_object_id:
            if isinstance(obj, Portfolio):
                blocks = [[]]
                (
                    categories_ids,
                    blocks,
                    dropdown_dict,
                    path_list,
                ) = self._get_data_portfolio(
                    categories_ids, blocks, dropdown_dict, path_list, True, obj
                )
            else:
                oRule = Rule.ByKeys(VISIBLE_FOLDERS_RULE)
                folders = [fold for fold in obj.SubFolders if oRule.match(fold)]
                if len(folders) != 0:
                    blocks = [[]]
                    (
                        categories_ids,
                        blocks,
                        dropdown_dict,
                        path_list,
                    ) = self._get_data_not_bottom_folder(
                        categories_ids, blocks, dropdown_dict, path_list, True, obj
                    )
                else:
                    reached_product_level = True
                    (
                        categories_ids,
                        blocks,
                        dropdown_dict,
                        path_list,
                    ) = self._get_data_bottom_folder(
                        categories_ids, dropdown_dict, path_list, True, obj
                    )

        else:
            blocks = [[]]
            categories_ids, blocks, dropdown_dict, path_list = self._get_portfolios(
                categories_ids, blocks, dropdown_dict, path_list, True
            )

        return (reached_product_level, categories_ids, blocks, dropdown_dict, path_list)

    def get_class_label(self, classname):
        cls = entities.Class.ByKeys(classname=classname)
        if cls:
            return cls.Label[""]
        else:
            return ""

    @staticmethod
    def get_product_operation_names(obj_or_cls=None, **varkw):
        return [
            "CDB_ShowObject",
            "cdbvp_product",
            "cdbvp_product_view",
            "cdbrqm_value_dashboard",
            "cdbrqm_link_matrix",
            "cdbqc_obj_cockpit",
        ]

    @staticmethod
    def get_project_operation_names(obj_or_cls=None, **varkw):
        return [
            "CDB_ShowObject",
            "cdbpcs_project_overview",
            "cdbpcs_project_info",
            "CDBPCS_ProjectPlan",
            "CDBPCS_CapaChart",
            "cdbpcs_milestone_report",
            "cdbqc_obj_cockpit",
        ]

    @staticmethod
    def get_date_to_str(date, evaltime=False):
        """
        Return a string date (dd.mm.yyyy / dd.mm.yyyy hh:mm:ss) from a
        `datetime.datetime` object.
        Only if evaltime is set the returned string contains the time part.

        Returns None in case of an exception. The exception will be logged as
        error.
        """
        return typeconversion.to_legacy_date_format(date, evaltime)

    def render(self, context, cdb_object_id=None, **varkw):
        context_object = None
        # If there is only one visible portofolio, we skip the portfolio view
        if not cdb_object_id:
            visible_portfolios = Rule.ByKeys(VISIBLE_PORTFOLIOS_RULE)
            if len(visible_portfolios.Objects) == 1:
                portfolio = visible_portfolios.Objects[0]
                cdb_object_id = portfolio.cdb_object_id

        if cdb_object_id:
            context_object = ByID(cdb_object_id)
        (
            reached_product_level,
            categories_ids,
            blocks,
            dropdown_dict,
            path_list,
        ) = self._get_data(cdb_object_id)

        from cdb.util import get_label

        oLanguage = {
            "oPaginate": {
                "sFirst": get_label("cdb_portfolio_olanguage_first"),
                "sLast": get_label("cdb_portfolio_olanguage_last"),
                "sNext": get_label("cdb_portfolio_olanguage_next"),
                "sPrevious": get_label("cdb_portfolio_olanguage_previous"),
            },
            "sEmptyTable": get_label("cdb_portfolio_olanguage_empty_table"),
            "sInfo": get_label("cdb_portfolio_olanguage_info"),
            "sInfoEmpty": get_label("cdb_portfolio_olanguage_empty"),
            "sInfoFiltered": get_label("cdb_portfolio_olanguage_filtered"),
            "sLengthMenu": get_label("cdb_portfolio_olanguage_length"),
            "sZeroRecords": get_label("cdb_portfolio_olanguage_zero_records"),
            "sSearch": "",
        }

        return {
            "context_object": context_object,
            "reached_product_level": reached_product_level,
            "categories_ids": categories_ids,
            "blocks": blocks,
            "dropdown_dict": dropdown_dict,
            "path_list": path_list,
            "get_preview_img": PictureUploader.get_preview_img,
            "get_image": self.get_image,
            "get_project_operation_names": self.get_project_operation_names,
            "get_product_operation_names": self.get_product_operation_names,
            "date_to_str": self.get_date_to_str,
            "oLanguage": json.dumps(oLanguage),
            "sFilterPlaceholder": get_label("cdbqc_elink_cockpit_search"),
            "upload_action_url": "%supload"
            % (self.application.getURLPaths()["approot"]),
            "plugins": self.plugin(),
        }


class _UploadPicture(elink.Template):
    """
    Handles the picture uploading.
    """

    __html__ = "<html></html>"

    def render(self, context, cdb_object_id=None, **varkw):
        if self.request.upstreams:
            image_to = varkw.get("image_to_object", cdb_object_id)
            if image_to:
                obj = ByID(image_to)
                PictureUploader.set_image(self.request, obj, MAX_IMG_SIZE)
        return self.redirect()


@elink.using_template_engine("chameleon")
class Application(elink.Application):
    """
    Application class to start and run the eLINK application
    """

    def setup(self):
        """
        Add the page(s) to the application,
        add the JavaScript methods
        """
        self.add("", Main())
        self.add("upload", _UploadPicture())

    @classmethod
    def on_CDB_eLink_portfolio_now(cls, ctx):
        return cls.OpenModule("navigator")


navigator = elink.AppMaker(Application, "Portfolio Navigator")


def handle_request(req):
    """Shortcut to the app"""
    return navigator.handle_request(req)
