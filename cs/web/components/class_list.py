#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
App that generates a simple HTML page with links to all class overview pages.
"""

from __future__ import absolute_import
__revision__ = "$Id$"

import morepath

from collections import defaultdict

from cdb import sqlapi
from cs.platform.web import root
from cs.web.components.generic_ui import get_ui_app
from cs.web.components.generic_ui.class_view import ClassViewModel
from cs.web.components.generic_ui.detail_view import DetailViewModel
from cs.web.components.ui_support.operation_app.main import get_operation_app
from cs.web.components.ui_support.operation_app.model import ClassOperationModel


class ClassListApp(morepath.App):
    pass


@root.Internal.mount(path="class-list", app=ClassListApp)
def _mount():
    return ClassListApp()


@ClassListApp.path(path="")
class ClassListModel(object):
    def entries(self):
        rs = sqlapi.RecordSet2(sql="SELECT DISTINCT"
                               "   rest_visible_name, uk_beschriftung, cdb_module_id, classname"
                               " FROM switch_tabelle"
                               " WHERE rest_visible_name <> ''"
                               " AND rest_api_active = 1"
                               " ORDER BY cdb_module_id, rest_visible_name")
        links = defaultdict(list)
        for rec in rs:
            links[rec.cdb_module_id or None].append((rec.rest_visible_name,
                                                     rec.uk_beschriftung,
                                                     rec.classname))
        return links

ICO_DD = 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiIgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2Ij4KICA8Y2lzLW5hbWU+dHJlZTwvY2lzLW5hbWU+CiAgPHJlY3Qgb3BhY2l0eT0iMCIgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2Ii8+CiAgPHBhdGggZmlsbD0iIzk5OTk5OSIgZD0iTTEzLDExLjQ5djJjMCwwLjI4LTAuMjIsMC41LTAuNSwwLjVoLTJjLTAuMjgsMC0wLjUtMC4yMi0wLjUtMC41di0yYzAtMC4yOCwwLjIyLTAuNSwwLjUtMC41ICBIMTF2LTJIOHYyaDAuNWMwLjI4LDAsMC41LDAuMjIsMC41LDAuNXYyYzAsMC4yOC0wLjIyLDAuNS0wLjUsMC41aC0yYy0wLjI4LDAtMC41LTAuMjItMC41LTAuNXYtMmMwLTAuMjgsMC4yMi0wLjUsMC41LTAuNUg3di0ySDQgIHYyaDAuNWMwLjI4LDAsMC41LDAuMjIsMC41LDAuNXYyYzAsMC4yOC0wLjIyLDAuNS0wLjUsMC41aC0yYy0wLjI4LDAtMC41LTAuMjItMC41LTAuNXYtMmMwLTAuMjgsMC4yMi0wLjUsMC41LTAuNUgzdi0ydi0xaDR2LTIgIEg2LjVDNi4yMiw1Ljk5LDYsNS43Niw2LDUuNDl2LTJjMC0wLjI4LDAuMjItMC41LDAuNS0wLjVoMmMwLjI4LDAsMC41LDAuMjIsMC41LDAuNXYyYzAsMC4yOC0wLjIyLDAuNS0wLjUsMC41SDh2Mmg0djF2MmgwLjUgIEMxMi43OCwxMC45OSwxMywxMS4yMSwxMywxMS40OXoiLz4KPC9zdmc+'

ICO_CLASSVIEW = 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiIgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2Ij4KICA8Y2lzLW5hbWU+bGlzdDwvY2lzLW5hbWU+CiAgPHJlY3Qgb3BhY2l0eT0iMCIgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2Ii8+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGZpbGw9IiM5OTk5OTkiIGQ9Ik01LDkuNUM1LDkuNzgsNC43NywxMCw0LjUsMTBoLTIgIEMyLjIzLDEwLDIsOS43OCwyLDkuNXYtMkMyLDcuMjIsMi4yMyw3LDIuNSw3aDJDNC43Nyw3LDUsNy4yMiw1LDcuNVY5LjV6IE01LDExLjVDNSwxMS4yMiw0Ljc3LDExLDQuNSwxMWgtMiAgQzIuMjMsMTEsMiwxMS4yMiwyLDExLjV2MkMyLDEzLjc4LDIuMjMsMTQsMi41LDE0aDJDNC43NywxNCw1LDEzLjc4LDUsMTMuNVYxMS41eiBNNSwzLjVDNSwzLjIyLDQuNzcsMyw0LjUsM2gtMiAgQzIuMjMsMywyLDMuMjIsMiwzLjV2MkMyLDUuNzgsMi4yMyw2LDIuNSw2aDJDNC43Nyw2LDUsNS43OCw1LDUuNVYzLjV6IE0xNCw3LjVDMTQsNy4yMiwxMy43Nyw3LDEzLjUsN2gtN0M2LjIzLDcsNiw3LjIyLDYsNy41djIgIEM2LDkuNzgsNi4yMywxMCw2LjUsMTBoN2MwLjI3LDAsMC41LTAuMjIsMC41LTAuNVY3LjV6IE0xNCwxMS41YzAtMC4yOC0wLjIzLTAuNS0wLjUtMC41aC03QzYuMjMsMTEsNiwxMS4yMiw2LDExLjV2MiAgQzYsMTMuNzgsNi4yMywxNCw2LjUsMTRoN2MwLjI3LDAsMC41LTAuMjIsMC41LTAuNVYxMS41eiBNMTQsMy41QzE0LDMuMjIsMTMuNzcsMywxMy41LDNoLTdDNi4yMywzLDYsMy4yMiw2LDMuNXYyICBDNiw1Ljc4LDYuMjMsNiw2LjUsNmg3QzEzLjc3LDYsMTQsNS43OCwxNCw1LjVWMy41eiIvPgo8L3N2Zz4='

ICO_CREATE = 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiIgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2Ij4KICA8Y2lzLW5hbWU+Zm9ybTwvY2lzLW5hbWU+CiAgPHJlY3Qgb3BhY2l0eT0iMCIgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2Ii8+CiAgPHBhdGggZmlsbD0iIzk5OTk5OSIgZD0iTTE0LDJ2MTJIMlYySDE0IE0xNC41LDFoLTEzQzEuMjIsMSwxLDEuMjMsMSwxLjV2MTNDMSwxNC43NywxLjIyLDE1LDEuNSwxNWgxMyAgYzAuMjgsMCwwLjUtMC4yMywwLjUtMC41di0xM0MxNSwxLjIzLDE0Ljc4LDEsMTQuNSwxTDE0LjUsMXogTTEzLDQuNXYtMUMxMywzLjIyLDEyLjc4LDMsMTIuNSwzaC05QzMuMjMsMywzLDMuMjIsMywzLjV2MSAgQzMsNC43OCwzLjIzLDUsMy41LDVoOUMxMi43OCw1LDEzLDQuNzgsMTMsNC41eiBNMTIsN3YxSDRWN0gxMiBNMTIuNSw2aC05QzMuMjMsNiwzLDYuMjMsMyw2LjV2MkMzLDguNzcsMy4yMyw5LDMuNSw5aDkgIEMxMi43OCw5LDEzLDguNzcsMTMsOC41di0yQzEzLDYuMjMsMTIuNzgsNiwxMi41LDZMMTIuNSw2eiBNMTIsMTF2MUg0di0xSDEyIE0xMi41LDEwaC05QzMuMjIsMTAsMywxMC4yMywzLDEwLjV2MiAgQzMsMTIuNzcsMy4yMiwxMywzLjUsMTNoOWMwLjI4LDAsMC41LTAuMjMsMC41LTAuNXYtMkMxMywxMC4yMywxMi43OCwxMCwxMi41LDEwTDEyLjUsMTB6Ii8+Cjwvc3ZnPg=='

TEMPLATE = """<!DOCTYPE html>
<html>
    <head>
        <title>Class List</title>
        <style type="text/css">
            body {
              font-family: sans-serif
            }
            .entity a {
              vertical-align: middle;
            }
            .filtered {
              display: none;
            }
        </style>
        <script type="text/javascript">
            function onFilterContent(event) {
                const value = event.target.value.toLowerCase();
                for (const elem of document.getElementsByClassName('entity')) {
                   const matches = elem.getAttribute('data-id').toLowerCase().indexOf(value) !== -1 ||
                       elem.getAttribute('data-label').toLowerCase().indexOf(value) !== -1;

                   if (matches) {
                       elem.classList.remove('filtered');
                   } else {
                       elem.classList.add('filtered');
                   }
                }

                for (const elem of document.getElementsByClassName('module')) {
                    let shouldBeHidden = true;
                    const entities = elem.getElementsByClassName('entity');
                    for (const entity of entities) {
                        if (!entity.classList.contains('filtered')) {
                            shouldBeHidden = false;
                        }
                    }
                    if (shouldBeHidden) {
                        elem.classList.add('filtered');
                    } else {
                        elem.classList.remove('filtered');
                    }
                }
            }

            document.addEventListener('DOMContentLoaded', () => {
                const filterField = document.getElementById('filter');
                filterField.addEventListener('input', onFilterContent);
            });
        </script>
    </head>
    <body>
        <h1>REST visible classes</h1>
        <input id="filter" placeholder="filter" />
        <div id="classlist">%s</div>
    </body>
</html>"""


def img(src, width=None, height=None):
    return '<img {} {} src="data:image/svg+xml;base64, {}"/>'\
        .format('width="{}"'.format(width) if width else '',
                'height="{}"'.format(height) if height else '',
                src)


def a(href, node):
    return '<a href="{}">{}</a>'.format(href, node)


def generate_html(request, links):
    ui_app = get_ui_app(request)
    op_app = get_operation_app(request)
    for module in sorted(links.keys()):
        yield '<div class="module"><h3>%s</h3><ul>' % module
        for rest_visible_name, uk_beschriftung, classname in links[module]:
            yield '<li data-label="{}" data-id="{}" class="entity">'\
                .format(uk_beschriftung, rest_visible_name)
            yield '%s (%s)' % (uk_beschriftung or '-- No label --',
                               rest_visible_name)
            try:
                dd_ui_link = request.class_link(DetailViewModel,
                                                {"rest_name": 'entity',
                                                 "keys": classname},
                                                app=ui_app)
                yield a(dd_ui_link, img(ICO_DD))
            except morepath.error.LinkError:
                pass
            try:
                class_ui_link = request.class_link(ClassViewModel,
                                                   {"rest_name": rest_visible_name},
                                                   app=ui_app)
                yield a(class_ui_link, img(ICO_CLASSVIEW))
            except morepath.error.LinkError:
                pass
            try:
                create_ui_link = request.class_link(ClassOperationModel,
                                                    {"opname": 'CDB_Create',
                                                     "clazz": classname},
                                                    app=op_app)
                yield a(create_ui_link, img(ICO_CREATE))
            except morepath.error.LinkError as e:
                print(e)
            yield '</li>'

        yield '</ul></div>'


@ClassListApp.html(model=ClassListModel)
def _html(model, request):
    return TEMPLATE % '\n'.join(generate_html(request, model.entries()))
