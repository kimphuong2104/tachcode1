#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
The Base Morepath application is intended to be used as a basis for Web UI
applications. It implements the basic functionality to generate an HTML page
with the needed <script> tags to load JavaScript libraries, and provides hooks
in the form of internal Morepath views that can (or in some cases must) be
overriden by applications (see `Morepath application overrides
<http://morepath.readthedocs.org/en/latest/app_reuse.html#application-overrides>`_).

.. attention::

   The mechanism implemented here is closely coupled to the frontend logic that
   initializes an application (see function `initialize` in the library
   `cs-web-components-base`). Any changes in one of these places may
   necessitate corresponding changes on the other side.

"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import json
import cdbwrapc
import six
from webob.exc import HTTPError

from cdb import CADDOK
from cdb import constants
from cdb import i18n
from cdb import rte
from cdb import sig
from cdb import auth
from cdb.objects import org
from cdb.util import getSysKey

# import path changed in CE 16, can be removed when cs.web is branched
try:
    from cdb.wsgi.util import GlobalStyleCache
except ImportError:
    from cdb.wsgi.static import GlobalStyleCache

from cdb.platform.gui import ToolbarDefinition
from cdb.elink import isCDBPC as isCEDesktop

from cs.platform.web import PlatformApp
from cs.platform.web import static
from cs.platform.web.util import render_file_template
from cs.platform.web.base.helpid import get_help_id_link
from cs.platform.web.rest.support import get_restlink_by_keys
from cs.platform.web.rest.classdef.main import get_classdef
from cs.platform.web.rest.i18n import WebLabels, get_i18n_app
from cs.platform.web.uisupport import get_uisupport
from cs.platform.web.uisupport import file_formats, table_export

from cs.web.components.ui_support import get_uisupport_app
from cs.web.components.ui_support.operations import (OpContextModel,
                                                     OperationInfoClass,
                                                     OperationInfo,
                                                     OperationInfoRelship,
                                                     BatchOperationInfoRelship)
from cs.web.components.ui_support.display_contexts import DisplayContextModel
from cs.web.components.ui_support.dnd_config import DropConfigurationModel
from cs.web.components.ui_support.dnd_operations import DnDOperationsModel
from cs.web.components.ui_support.errors import LogBookModel
from cs.web.components.ui_support.relships import RelshipsModel
from cs.web.components.ui_support.navigation import NavigationContent
from cs.web.components.ui_support.search_favourites import (AllSearchFavouriteCollection,
                                                            SearchFavouriteCollection,
                                                            PredefinedSearchFavourites)
from cs.web.components.ui_support.user_settings import SettingsModel
from cs.web.components.ui_support.web_search_default import SearchDefaultsModel
from cs.web.components.ui_support.ui_settings import UISettingsModel
from cs.web.components.ui_support.batchload import BatchModel, ClassdefsModel
from cs.web.components.ui_support.user_substitution import UserSubstitutionCollection
from cs.web.components.ui_support.context import Context
from cs.web.components.ui_support.thumbnail import get_thumbnail_upload
from cs.web.components.ui_support.state_colors import StateColors
from cs.web.components.ui_support.libraries import LibraryModel
from cs.web.components.ui_support.catalogs import (CatalogTypeAheadModel, CatalogSelectedValuesModel,
                                                   CatalogTableDefWithValuesModel, CatalogValueCheckModel,
                                                   CatalogQueryFormModel)

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "resources")
LAYOUT = os.path.join(TEMPLATE_PATH, "base.html")

# Hook to add customizing component globally to override
# standard CSS or JS component
GLOBAL_CUSTOMIZATION_HOOK = sig.signal()

# Hook to add customizing appSetup data globally
GLOBAL_APPSETUP_HOOK = sig.signal()

DEVMODE = CADDOK.get("WEBUI_DEBUG", "").lower() == "true"
REACT_STRICT_MODE = CADDOK.get("REACT_STRICT_MODE", "").lower() == "true"
USE_PRESIGNED_URLS = CADDOK.get("WEBUI_USE_PRESIGNED_BLOB_URL", "1") == "1"

class SettingDict(dict):
    def merge_in(self, paths, other_dict):
        if len(paths) > 0:
            curr = self
            for ppath in paths:
                curr = curr.setdefault(ppath, {})
            curr.update(other_dict)
        return self


class BaseApp(PlatformApp):
    """ Every Web UI application that wants to use the common framework should
        be a subclass of `BaseApp`. This application class is abstract, and is
        not mounted.
    """

    RENDERER = ("cs-web-components-base-render", "15.1.0")

    # icon_id of an Icon to be showed in tab label(only in Windows Client)
    client_favicon = ""

    def __init__(self):
        super(BaseApp, self).__init__()
        self.includes = []

    def include(self, libname, libver):
        """ Adds a dependency to this app, so that its embeddable resources will
            be embedded alongside this app.
        """
        try:
            lib = static.Registry().get(libname, libver)
            if lib not in self.includes:
                for include in self.includes:
                    if include.name == libname:
                        raise ValueError("Cannot include library %s (%s): "
                                         "Already included as version %s." %
                                         (libname, libver, include.version))
                self.includes.append(lib)
        except KeyError:
            raise ValueError("Library %s with version %s not defined" % (libname, libver))

    def render_includes(self):
        """ Generates HTML <script>tags for embedding all resources this app
            depends on.
        """
        return u"\n".join((include.render()
                           for include in self.includes))

    def update_app_setup(self, app_setup, model, request):
        """
        Provide app specific setups for frontend::

            class MyApp(BaseApp):
                def update_app_setup(self, app_setup, model, request):
                    super(MyApp, self).update_app_setup(app_setup, model, request)
                    app_setup.merge_in(["links", "my-namespace"], {
                        "someLink": "/some/link"
                    })
        """
        from cs.web.components.ui_support.outlets import OutletConfig
        us_app = get_uisupport(request)
        op_ctx_link = request.class_link(
            OpContextModel,
            {
                "context_name": "${opContextName}",
                "classname": "${classname}"
            },
            app=us_app)
        op_class_link = request.class_link(
            OperationInfoClass,
            {"classname": "${classname}"},
            app=us_app)
        op_info_link = request.class_link(
            OperationInfo,
            {
                "classname": "${classname}",
                "opname": "${operationName}"
            },
            app=us_app)
        op_relship_link = request.class_link(
            OperationInfoRelship,
            {
                "parent_classname": "${parent_classname}",
                "keys": "${keys}",
                "relship_name": "${relship_name}"
            },
            app=us_app)
        batch_op_relship_link = request.class_link(
            BatchOperationInfoRelship,
            {
                "parent_classname": "${parent_classname}",
                "keys": "${keys}",
            },
            app=us_app)
        current_user_link = get_restlink_by_keys(
            "cdb_person",
            {
                "personalnummer": auth.persno
            },
            request
        )
        class_def_link = request.class_link(
            cdbwrapc.CDBClassDef,
            {
                "class_name": "${class_name}"
            },
            app=get_classdef(request)
        )
        outlet_link = request.class_link(
            OutletConfig,
            {
                "outlet_name": "${outlet_name}",
                "class_name": "${class_name}",
                "absorb": "${absorb}"
            },
            app=us_app.child("outlet"))
        object_context = request.class_link(
            Context,
            {
                "classname": "${classname}",
                "keys": "${keys}"
            },
            app=get_uisupport(request)
        )
        state_colors_link = request.class_link(
            StateColors,
            {
                "obj_class": "${obj_class}"
            },
            app=us_app
        )
        catalog_type_ahead_link = request.class_link(
            CatalogTypeAheadModel,
            {
                "catalog_name": "${catalog_name}"
            },
            app=us_app
        )
        catalog_selected_values_link = request.class_link(
            CatalogSelectedValuesModel,
            {
                "catalog_name": "${catalog_name}",
                "extra_parameters": {"as_objects": "${as_objects}"},
            },
            app=us_app
        )
        catalog_tabular_with_values_link = request.class_link(
            CatalogTableDefWithValuesModel,
            {
                "catalog_name": "${catalog_name}",
                "extra_parameters": {"allow_multi_select": "${allow_multi_select}"},
            },
            app=us_app
        )
        catalog_value_check_link = request.class_link(
            CatalogValueCheckModel,
            {
                "catalog_name": "${catalog_name}"
            },
            app=us_app
        )
        catalog_query_form_link = request.class_link(
            CatalogQueryFormModel,
            {
                "catalog_name": "${catalog_name}"
            },
            app=us_app
        )
        table_export_link = request.class_link(
            table_export.TableExportModel,
            {},
            app=us_app
        ) if table_export else None
        drop_config_link = request.class_link(
            DropConfigurationModel,
            {
                "target_id": "${target_id}"
            },
            app=us_app
        )
        dnd_operations_link = request.class_link(
            DnDOperationsModel,
            {
                "parent_classname": "${parent_classname}",
                "keys": "${keys}",
                "relship_name": "${relship_name}"
            },
            app=us_app
        )
        libraries_target_link = request.class_link(
            LibraryModel,
            {
                "library_name": "${library_name}"
            },
            app=us_app
        )
        classdef_app = get_classdef(request)
        relship_link_template = request.class_link(RelshipsModel,
                                                   {"class_name": "${class_name}"},
                                                   app=classdef_app)

        i18_labels_link = request.class_link(WebLabels,
                                             {"isolang": i18n.default()},
                                             app=get_i18n_app(request))

        current_user = org.Person.ByKeys(auth.persno)
        try:
            enable_presigned_blob_redirect = getSysKey('enable_presigned_blob_redirect')
        except KeyError:
            enable_presigned_blob_redirect = False
        app_setup.update({
            "appSettings": {
                "usePresignedBlobRedirect": enable_presigned_blob_redirect and USE_PRESIGNED_URLS,
                "appComponent": request.view(model, name="app_component"),
                "basePath": request.view(model, name="base_path"),
                "hostUrl": request.host_url,
                # TODO rename application_title to something more appropriate (system_title?)
                "title": request.view(model, name="application_title"),
                "navBarItems": request.view(model, name="navbar_items"),
                "applicationMenuItems": json.dumps(NavigationContent("primary_master").get_entries()),
                "accountMenuItems": request.view(model, name="account_menu_items"),
                "userMenuItems": request.view(model, name="user_menu_items"),
                "passwd_op": request.view(model, name="change_pwd_menu_item"),
                "userPersno": auth.persno,
                "userFullName": auth.get_name(),
                "userUploadThumbnail": get_thumbnail_upload(current_user, request),
                "language": i18n.default(),
                "activeGUILanguages": i18n.getActiveGUILanguages(),
                "debugMode": DEVMODE,
                "hideTitleBarSearchField": request.view(model, name="hide_title_bar_search_field")
                    if cdbwrapc.OperationInfo("", "CDB_FulltextSearch") else True,
                "isCEDesktop": isCEDesktop(),
                "productName": cdbwrapc.getApplicationName(),
                # If this flag is true, the body will be fixed and
                # scrolling needs to be handled by the applications components
                # This improves scrolling behaviour of overlays.
                "renderFixedBody": False,
                "errorNotificationTimeout": SettingsModel("error_notification_timeout", "").get_setting(),
                "fileFormats": file_formats,
                "strictMode": REACT_STRICT_MODE
            },
            "formats": {
                "decimalSeparator": i18n.get_decimal_separator(),
                "groupSeparator": i18n.get_group_separator(),
                "dateTimeFormat": i18n.get_datetime_format(),
                "dateFormat": i18n.get_date_format()
            },
            "applicationConfiguration": {},
            "pluginConfiguration": {},
            "links": {
                "common": {
                    "home": "/",
                    "help": request.view(model, name="application_help_link"),
                    "attributes": "/internal/attrsettings/%s/attributegroups" %
                                  request.view(model, name="application_id"),
                    'iconBase': '/resources/icons/byname/',
                    'errorLog': request.class_link(LogBookModel, app=us_app),
                    # FIXME: a link template should not be quoted - how to tell morepath?
                    "classDefPattern": six.moves.urllib.parse.unquote(class_def_link),
                    "opContextPattern": six.moves.urllib.parse.unquote(op_ctx_link),
                    "opClassPattern": six.moves.urllib.parse.unquote(op_class_link),
                    "opInfoPattern": six.moves.urllib.parse.unquote(op_info_link),
                    "opRelshipPattern": six.moves.urllib.parse.unquote(op_relship_link),
                    "batchOpRelshipPattern": six.moves.urllib.parse.unquote(batch_op_relship_link),
                    "currentUser": six.moves.urllib.parse.unquote(current_user_link),
                    "i18nLabels": i18_labels_link,
                    "displayContextTemplate": six.moves.urllib.parse.unquote(DisplayContextModel.template_link(request)),
                    "searchFavourites": AllSearchFavouriteCollection().make_link(request),
                    "searchFavouritesTemplate":
                        six.moves.urllib.parse.unquote(SearchFavouriteCollection.template_link(request)),
                    "predefinedSearchFavouritesTemplate":
                        six.moves.urllib.parse.unquote(PredefinedSearchFavourites.template_link(request)),
                    "userSettingsTemplate": six.moves.urllib.parse.unquote(SettingsModel.template_link(request)),
                    "searchDefaultTemplate": six.moves.urllib.parse.unquote(SearchDefaultsModel.template_link(request)),
                    "uiSettings": six.moves.urllib.parse.unquote(UISettingsModel.link(request)),
                    "batchLoad": six.moves.urllib.parse.unquote(BatchModel.make_link(request)),
                    "batchloadClasses": six.moves.urllib.parse.unquote(ClassdefsModel.make_link(request)),
                    "relshipConfigurationPattern": six.moves.urllib.parse.unquote(relship_link_template),
                    "userSubstitutions": six.moves.urllib.parse.unquote(UserSubstitutionCollection.make_link(request)),
                    "outletTemplate": six.moves.urllib.parse.unquote(outlet_link),
                    "objectContext": six.moves.urllib.parse.unquote(object_context),
                    "stateColorsTemplate": six.moves.urllib.parse.unquote(state_colors_link),
                    "tableExportTemplate": six.moves.urllib.parse.unquote(table_export_link)
                        if table_export_link else None,
                    "dropConfigTemplate": six.moves.urllib.parse.unquote(drop_config_link),
                    "dndOperationsTemplate": six.moves.urllib.parse.unquote(dnd_operations_link),
                    "librariesTargetTemplate": six.moves.urllib.parse.unquote(libraries_target_link),
                    "catalogTypeAheadTemplate": six.moves.urllib.parse.unquote(catalog_type_ahead_link),
                    "catalogSelectedValuesTemplate": six.moves.urllib.parse.unquote(catalog_selected_values_link),
                    "catalogTabularWithValuesTemplate": six.moves.urllib.parse.unquote(
                        catalog_tabular_with_values_link),
                    "catalogValueCheckTemplate": six.moves.urllib.parse.unquote(catalog_value_check_link),
                    "catalogQueryFormTemplate": six.moves.urllib.parse.unquote(catalog_query_form_link),
                }
            }
        })

        # FIXME(app_inheritance): special handling for BaseErrorModel, see D082907
        if isinstance(model, BaseErrorModel):
            app_setup.update({
                "server_error": {
                    'title': model.title,
                    'explanation': model.explanation,
                    'code': model.code,
                }
            })


@BaseApp.path(path="")
class BaseModel(object):
    """ The Morepath model class all descendents of `BaseApp` must either use
        directly, or through a derived class.
    """

    def __init__(self):
        self._applications = None
        self._account_links = None
        self._user_menu = None
        self._change_pwd_op = None

    def _get_opinfo(self, op, request, ui_support_app=None):
        if not ui_support_app:
            ui_support_app = get_uisupport_app(request)
        url = cdbwrapc.build_tag_string(op.get_url(), None, "")
        op_link = url.replace("\"", "")
        op_name = op.get_opname()
        icons = op.get_icon_urls()
        op_icon = "/" + icons[0] if icons else ""
        op_info = None
        if not op_link:
            op_info = request.view(op, app=ui_support_app)
            op_link = "/cdbgate/byname/opname/%s/batch" % (op_name)
            # Give a hint we run in Web
            op_link += "?%s=1" % (six.moves.urllib.parse.quote(constants.kArgumentUsesWebUI))
        return {
            "link": op_link,
            "opInfo": op_info,
            "imageName": op_icon,
            "imageSrc": op_icon,
            "title": op.get_label(),
            "presentation_id": op.get_render_comp_id()
        }

    def fillApplicationsList(self, toolbar, request):
        """
        Helper function to determine the list of applications
        assigned to ``toolbar``
        """
        result = []
        toolbar = ToolbarDefinition(toolbar)
        if toolbar:
            ui_support_app = get_uisupport_app(request)
            for op in toolbar.get_operations():
                result.append(self._get_opinfo(op, request, ui_support_app))
        return result

    def get_account_menu(self, request):
        """
        Determine the list of applications that should be available directly
        from the users's account menu. The default implementation adds all operations
        that are defined in the Toolbar named ``webui_account``.
        """
        if self._account_links is None:
            self._account_links = []
            try:
                self._account_links = self.fillApplicationsList("webui_account", request)
            except AttributeError:
                pass
        return self._account_links

    def get_user_menu(self, request):
        """
        A function that retrieves a list of items assigned
        to the user menu.
        """
        if self._user_menu is None:
            self._user_menu = []
            try:
                self._user_menu = self.fillApplicationsList("webui_user_menu", request)
            except AttributeError:
                pass
        return self._user_menu

    def get_change_pwd_op(self, request):
        """
        A function that retrieves the information for the operation that
        is used to change the password
        """
        if self._change_pwd_op is None:
            self._change_pwd_op = {}
            try:
                passwd_op = cdbwrapc.OperationInfo("", "CDB_ChangePassword")
                if passwd_op:
                    self._change_pwd_op = self._get_opinfo(passwd_op, request)
            except AttributeError:
                pass
        return self._change_pwd_op if self._change_pwd_op else None


class BaseErrorModel(BaseModel):
    def __init__(self, title, explanation, code):
        super(BaseErrorModel, self).__init__()
        self.title = title
        if code == 404:
            self.explanation = "The page you were looking for was not found."
        else:
            self.explanation = explanation
        self.code = code


@BaseApp.html(model=HTTPError)
def handle_error(model, request):

    @request.after
    def set_status_code(response):
        response.status_code = model.code

    return request.view(BaseErrorModel(model.title, model.explanation, model.code))


@BaseApp.view(model=BaseErrorModel, name="app_component")
def error_page_component(model, request):
    return "cs-web-components-base-ErrorPage"


@BaseApp.view(model=BaseErrorModel, name="document_title", internal=True)
def error_document_title(model, request):
    return model.title


@BaseApp.html(model=BaseModel)
def get_page(model, request):
    """ This is the main function used to generate a HTML page. It includes
        all of the 3rd party JavaScript libraries, and the base components
        from the |elements| Web UI as <script> tags.

        `get_page` calls several internal Morepath views (see below), that
        can be overriden by applications to customize the generated HTML.

        **Attributes:**

          +---------------+-----------------+
          | View Name     | None            |
          +---------------+-----------------+
          | Return Type   | html            |
          +---------------+-----------------+
    """
    request.app.include("cs-font", "15.0")
    request.app.include("cs-web-components-externals", "15.2.0")
    request.app.include("cs-web-components-base", "15.1.0")
    if request.app.RENDERER:
        request.app.include(*request.app.RENDERER)

    # If we are in devmode, initialize global-style on each render call
    global_styles = os.path.basename(GlobalStyleCache.get_global_style())
    # Implementation note: the double "dumps" here serves to create a string that
    # escapes single quotes correctly, see E051834. Just using dumps once, and then
    # using ${structure: ...} in the template (as would be intuitive) will leave
    # unescaped single quotes in the generated HTML.
    widgets = {"setup": json.dumps(json.dumps(request.view(model, name="setup"))),
               "favicon": request.view(model, name="favicon"),
               "additional_head": request.view(model, name="additional_head"),
               "document_title": request.view(model, name="document_title"),
               "enable_notify_changes": json.dumps(
                   request.view(model, name="enable_notify_changes")),
               'global_styles': global_styles}
    # add global customization at the end
    sig.emit(GLOBAL_CUSTOMIZATION_HOOK)(request)
    widgets.update(includes=request.app.render_includes())
    widgets.update(body=request.view(model, name="_body"))
    return render_file_template(LAYOUT, **dict(widgets=widgets))


@BaseApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(model, request):
    """ Return the document title (the value of the title tag in html). Should
        be overriden by applications.

        **Attributes:**

          +---------------+-----------------+
          | View Name     | document_title  |
          +---------------+-----------------+
          | Return Type   | string          |
          +---------------+-----------------+
    """
    return cdbwrapc.getApplicationName()


@BaseApp.view(model=BaseModel, name="setup", internal=True)
def setup(model, request):
    """ Static data, that can be computed in the backend, is included as a JSON
        encoded object in the <head> HTML element. As in `get_page`, this
        function calls (possibly) overriden internal views to do its work.

        **Attributes:**

          +---------------+-----------------+
          | View Name     | setup           |
          +---------------+-----------------+
          | Return Type   | dictionary      |
          +---------------+-----------------+
    """
    app_setup = SettingDict()
    request.app.update_app_setup(app_setup, model, request)
    # add global customization at the end
    sig.emit(GLOBAL_APPSETUP_HOOK)(app_setup, request)
    initial_libraries = [fname.name for fname in request.app.includes]
    app_setup["initialLibraries"] = initial_libraries
    return app_setup


@BaseApp.view(model=BaseModel, name="favicon", internal=True)
def favicon(model, request):
    """ Define the icon to be schown for the application by the browser. Must
        return HTML code to be embedded in the <head> tag.

        **Attributes:**

          +---------------+-------------------+
          | View Name     | additional_head   |
          +---------------+-------------------+
          | Return Type   | html              |
          +---------------+-------------------+
    """
    cdbicon = ""
    if request.app.client_favicon:
        cdbicon = ' cdbicon="%s"' % request.app.client_favicon
    return "\n".join(
        ['<link rel="shortcut icon" href="/static/imgid/branding_web_favicon.ico"%s>' % cdbicon,
         '<link rel="icon" href="/static/imgid/branding_web_favicon.ico">',
         '<link rel="apple-touch-icon" href="/static/imgid/branding_web_app_icon.png">'])


@BaseApp.html(model=BaseModel, name="additional_head", internal=True)
def default_additional_head(model, request):
    """ Return application specific HTML code to be embedded in the <head> tag.

        **Attributes:**

          +---------------+-------------------+
          | View Name     | additional_head   |
          +---------------+-------------------+
          | Return Type   | html              |
          +---------------+-------------------+
    """
    return ""


@BaseApp.html(model=BaseModel, name="enable_notify_changes", internal=True)
def default_enable_notify_changes(model, request):
    return False


@BaseApp.view(model=BaseModel, name="app_component", internal=True)
def get_app_component(model, request):
    """ Return the registered name of the React component that represents the
        root element for the application.
        Must be implemented for all applications.

        **Attributes:**

          +---------------+-------------------+
          | View Name     | app_component     |
          +---------------+-------------------+
          | Return Type   | string            |
          +---------------+-------------------+
    """
    return ""


@BaseApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(model, request):
    """ Return the part of the URL path (without scheme / host / port) that is
        handled by the backend. The frontend uses this information to set up
        client side routing.
        Must be implemented for all applications.

        **Attributes:**

          +---------------+-------------------+
          | View Name     | base_path         |
          +---------------+-------------------+
          | Return Type   | URL path          |
          +---------------+-------------------+
    """
    return None


@BaseApp.view(model=BaseModel, name="application_title", internal=True)
def get_application_title(model, request):
    """ Could be overriden to define a custom application title.

        **Attributes:**

          +---------------+-------------------+
          | View Name     | application_title |
          +---------------+-------------------+
          | Return Type   | string            |
          +---------------+-------------------+
    """
    return cdbwrapc.getApplicationName()


@BaseApp.view(model=BaseModel, name="navbar_items", internal=True)
def get_navbar_items(model, request):
    """ This view generates the default navbar_items of the application.
        Could be overriden to avoid rendering default nav bar items.

        See also :py:meth:`cs.web.components.base.main.get_additional_navbar_items`

        **Attributes:**

          +---------------+-------------------+
          | View Name     | navbar_items      |
          +---------------+-------------------+
          | Return Type   | json              |
          +---------------+-------------------+
    """
    navbar_items = []
    navbar_items.extend(request.view(model, name="additional_navbar_items"))
    return json.dumps(navbar_items)


@BaseApp.view(model=BaseModel, name="additional_navbar_items", internal=True)
def get_additional_navbar_items(model, request):
    """ This view is an extension point for navbar_items. Must be overriden
        if additional nav bar items should be provided by derived application.

        See also: :ref:`app_implementation_navbar`

        **Attributes:**

          +---------------+-------------------------+
          | View Name     | additional_navbar_items |
          +---------------+-------------------------+
          | Return Type   | json                    |
          +---------------+-------------------------+
    """
    return []


@BaseApp.view(model=BaseModel, name="account_menu_items", internal=True)
def get_account_items(model, request):
    """ Could be overriden to avoid rendering default application menu items.

        **Attributes:**

          +---------------+-------------------------+
          | View Name     | account_menu_items      |
          +---------------+-------------------------+
          | Return Type   | json                    |
          +---------------+-------------------------+
    """
    return json.dumps(model.get_account_menu(request))


@BaseApp.view(model=BaseModel, name="user_menu_items", internal=True)
def get_user_items(model, request):
    """ Could be overriden to avoid rendering default user menu items.

        **Attributes:**

          +---------------+-------------------------+
          | View Name     | user_menu_items         |
          +---------------+-------------------------+
          | Return Type   | json                    |
          +---------------+-------------------------+
    """
    return json.dumps(model.get_user_menu(request))


@BaseApp.view(model=BaseModel, name="change_pwd_menu_item", internal=True)
def get_change_pwd_item(model, request):
    """
    Could be overriden to avoid rendering the menu item to change the
    password.

        **Attributes:**

          +---------------+-------------------------+
          | View Name     | change_pwd_menu_item    |
          +---------------+-------------------------+
          | Return Type   | json                    |
          +---------------+-------------------------+
    """
    return json.dumps(model.get_change_pwd_op(request))


@BaseApp.view(model=BaseModel, name="application_id", internal=True)
def app_id(model, request):
    """
    An application identifier. This is used to retrieve attribute groups and should be overridden
    to retrieve attribute definitions like the master data group.
    """
    return "app"


@BaseApp.view(model=BaseModel, name="application_help_id", internal=True)
def app_help_id(model, request):
    """ A string representing the help id to the application specific help text.
        This will be used to generate the link to open the help text in documentation.

        Must be overriden if help page should be linked for derived application.

        **Attributes:**

          +---------------+-------------------------+
          | View Name     | application_help_id     |
          +---------------+-------------------------+
          | Return Type   | string                  |
          +---------------+-------------------------+
    """
    return ""


@BaseApp.view(model=BaseModel, name="application_help_link", internal=True)
def app_help_link(model, request):
    """ Link to application specific help.

        If the link to application specific help should not be generated in the usual way,
        as using help ID that gets returned from :py:meth:`cs.web.components.base.main.app_help_id` view, this
        `application_help_link` view should be implemented the to return the expected link.

        **Attributes:**

          +---------------+-------------------------+
          | View Name     | application_help_link   |
          +---------------+-------------------------+
          | Return Type   | link                    |
          +---------------+-------------------------+
    """
    help_id = request.view(model, name="application_help_id")
    return get_help_id_link(request, help_id) if help_id else ""


@BaseApp.view(model=BaseModel, name="hide_title_bar_search_field", internal=True)
def get_hide_title_bar_search_field(model, request):
    """ Could be overriden to hide title bar search field.

        **Attributes:**

          +---------------+-----------------------------+
          | View Name     | hide_title_bar_search_field |
          +---------------+-----------------------------+
          | Return Type   | bool                        |
          +---------------+-----------------------------+
    """
    return False


@BaseApp.view(model=BaseModel, name="_body", internal=True)
def get_special_body(model, request):
    """ Could be overriden to define special body content.
    Only for special use cases.
    """
    return None


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-web-components-base", "15.1.0",
                         os.path.join(os.path.dirname(__file__), "js", "build"))
    lib.add_file('cs-web-components-base.js')
    lib.add_file('cs-web-components-base.js.map')
    static.Registry().add(lib)

    render = static.Library("cs-web-components-base-render", "15.1.0",
                            os.path.join(os.path.dirname(__file__), "js", "build"))
    render.add_file('cs-web-components-base-render.js')
    render.add_file('cs-web-components-base-render.js.map')
    static.Registry().add(render)
