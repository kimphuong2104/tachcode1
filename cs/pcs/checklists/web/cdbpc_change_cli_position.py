#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json

from cdb import util
from cs.platform.web.root import Root
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel
from webob.exc import HTTPForbidden, HTTPNotFound

from cs.pcs.checklists import Checklist
from cs.pcs.checklists.web.models import ChecklistItemsModel

# MOUNT url is hard-coded in cdbpc-exclusive mask
# of operation "cdbpcs_cli_position"
MOUNT = "cs-pcs-CDBPC_ChangeCLIPosition"


class CDBPC_App(ConfigurableUIApp):
    pass


class Model(SinglePageModel):
    page_name = "cs-pcs-checklists-web-CDBPC_ChangeCLIPosition"

    def __init__(self, absorb):
        super().__init__()
        if not absorb:
            raise HTTPNotFound

        path = absorb.split("/")

        if len(path) != 2:
            raise HTTPNotFound

        checklist = Checklist.ByKeys(*path)

        if not (checklist and checklist.CheckAccess("read")):
            raise HTTPNotFound


@Root.mount(app=CDBPC_App, path=MOUNT)
def _mount_app():
    return CDBPC_App()


@CDBPC_App.path(path="", model=Model, absorb=True)
def _get_model(absorb):
    return Model(absorb)


# not called from Elements UI, just from Windows Client
def on_cdbpcs_cli_position_now(self, ctx):
    try:
        payload = json.loads(ctx.dialog.organizer)
    except ValueError as exc:
        import logging

        logging.error("ctx.dialog.organizer: %s", ctx.dialog.organizer)
        raise util.ErrorMessage("ue_fatal_error3", "CDBPC_ChangeCLIPosition") from exc

    try:
        model = ChecklistItemsModel(self.cdb_project_id, self.checklist_id)
        # pylint: disable=protected-access
        model._update_positions(payload)
    except (HTTPNotFound, HTTPForbidden) as exc:
        raise util.ErrorMessage("permission2") from exc


Checklist.on_cdbpcs_cli_position_now = on_cdbpcs_cli_position_now
