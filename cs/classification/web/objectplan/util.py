#
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Version:  $Id$
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from urllib.parse import urlencode

from cdb import cmsg


def make_create_url(dd_class, class_info):
    is_applicable = class_info["flags"][0]
    is_released = 200 == class_info["status"]
    if is_applicable and is_released:
        classification_string = '{"assigned_classes":["%s"]}' % class_info["code"]
        msg = cmsg.Cdbcmsg(dd_class, "CDB_Create", True)
        msg.add_sys_item("classification_web_ctrl", classification_string)
        return msg.eLink_url()
    else:
        return ""


def make_search_url(dd_class, class_code, uses_webui=False):
    from cs.web.components.ui_support.utils import ui_name_for_classname
    classification_string = '{"assigned_classes":["%s"]}' % class_code
    if uses_webui:
        url_parameter = {
            'search_attributes[0]': "cdb::argument.classification_web_ctrl",
            'search_values[0]': classification_string
        }
        ui_name = ui_name_for_classname(dd_class)
        url = '/info/{}?{}'.format(ui_name, urlencode(url_parameter))
        return url
    else:
        msg = cmsg.Cdbcmsg(dd_class, "CDB_Search", True)
        msg.add_sys_item("classification_web_ctrl", classification_string)
        return msg.eLink_url()
