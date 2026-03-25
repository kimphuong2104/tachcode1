# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
import re

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


def register_widget_url(app_setup, widget_code, url):
    """
    Public API to register a widget model URL so default widgets can access it.
    Add placeholders for specific parameters, e.g. project id, to given url, that will
    be replaced in the frontend.

    :param app_setup: The app_setup to extend.
    :type app_setup: cs.web.components.base.main.SettingDict

    :param widget_code: The widget's code as used in frontend actions.
    :type widget_code: basestring

    :param url: The URL to use.
    :type url: basestring

    :raises AttributeError: If ``app_setup`` has no ``merge_in`` method.
    """
    from cs.objectdashboard.widgets.widget_rest_app import APP

    # regular expression to catch "%24%7Bsomething%7D"
    pattern = re.compile(r"%24%7B(?P<attr>[a-z_]+)%7D")
    # replace "%24%7Bsomething%7D" with "${something}"
    parsedUrl = pattern.subn(r"${\1}", url)[0]

    app_setup.merge_in([APP, "widgets", widget_code], {"url": parsedUrl})
