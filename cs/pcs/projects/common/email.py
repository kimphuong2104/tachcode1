#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import logging

from cs.platform.web import get_root_url
from cs.platform.web.root.main import _get_dummy_request
from cs.platform.web.uisupport import _URL_PREFIX, get_webui_link


def get_email_links(*obj_infos):
    """
    :param obj_infos: For each object to create a link for:
        Tuple of ``cdb.objects.Object``, its link title/name
        and operation to use in the Windows client link.
    :type obj_infos: tuple

    :returns: Two lists: (Windows client links, Web UI links).
        Each link entry is a tuple of the URL and its title.

        Links are ordered exactly like ``objs_and_names``.
        Web UI links will be ``None`` if the root URL is the generic default
        (logged as "info").
    :rtype: tuple
    """
    client_win = "Client"
    client_web = "Browser"
    name_pattern = str("{} ({})")

    request = None
    root_url = get_root_url()

    if root_url and root_url.startswith(_URL_PREFIX):
        logging.info(
            "set the root URL to something else than '%s' "
            "to include web links in issue e-mail notifications",
            _URL_PREFIX,
        )
    else:
        request = _get_dummy_request(root_url)

    win_links = []
    web_links = []

    for obj, obj_name, opname in obj_infos:
        win_links.append(
            (
                obj.MakeURL(opname, plain=2),
                name_pattern.format(obj_name, client_win),
            )
        )

        if request:
            web_links.append(
                (
                    get_webui_link(request, obj),
                    name_pattern.format(obj_name, client_web),
                )
            )

    return (win_links, web_links or None)
