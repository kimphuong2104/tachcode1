# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module showvariant

This is the documentation for the showvariant module.
"""
from __future__ import absolute_import
import logging
import os
import uuid
from cdb import misc
from cdb import util
from cdb import elink
from cdb import CADDOK
from cs.vp.variants.apps.generatorui import _getapp
from cs.wsm.variantmanagement.wsmremotecontrol import WsmRemoteControl
from cs.wsm.variantmanagement.wscsvariantctrl import WsRemoteControlCsVariants
from cs.wsm.upload_to_client import viewonclient

try:
    from cdb import client
except ImportError:
    # Seems to be CE 16
    pass

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


class WsmControlPage(elink.Resource):
    def render(self, state_id):
        logging.debug("WSMVARIANTES: Render WsmControlPage %s", state_id)
        app_state = self.application.getState(state_id)
        if app_state and app_state.generator:
            product = app_state.generator._product
            if product.CheckAccess("read"):
                self.content_type("text/vnd.contact.wsm")
                for line in app_state.wsm_ctrl:
                    self.write(line + "\n")
            else:
                self.content_type("text/plain")


def show_in_wsm(filetype, state_id, selected_row, selected_maxbom_oid=None):
    logging.debug("WSMVARIANTES:  start: show variant in wsm")
    app = _getapp()
    app.add("wsm.cdbwscall", WsmControlPage())

    state = app.getState(state_id)

    if state:
        state.wsm_ctrl = []
        generator = state.generator
        pvalues, vinfo = state.grid_data_mapping[int(selected_row)]
        product = generator._product
        # determine max bom
        maxbom = app._get_maxbom(product, selected_maxbom_oid)

        # determine filterable variant and build catia ctrl lines
        variant = app._get_filter_variant(product, vinfo)
        logging.debug("WSMVARIANTES: got variant: %s", variant)
        if variant:
            wsm_rc = WsmRemoteControl(maxbom, filetype)
            logging.debug("WSMVARIANTES: wsm_rc ok 1")
            state.wsm_ctrl = wsm_rc.get_variant_ctrl_lines(variant)
        else:
            # Try to retrieve the max bom view solution from the solver
            solution = generator.getFilterSolution(pvalues)
            if solution:
                logging.debug("WSMVARIANTES: wsm_rc ok 2")
                wsm_rc = WsmRemoteControl(maxbom, filetype)
                logging.debug("WSMVARIANTES: wsm_rc ok 2")
                state.wsm_ctrl = wsm_rc.get_ctrl_lines(product.cdb_object_id, pvalues)
            else:
                raise util.ErrorMessage("cdbvp_err_no_unique_mapping")
        return {"url": "wsm.cdbwscall?state_id=%s" % state_id}


def _isContextCdbWeb():
    appinfo = misc.CDBApplicationInfo()
    return appinfo.rootIsa(misc.kAppl_HTTPServer)


def show_in_wsm_cs_variants(erzeug_system, walk_generator, ctx):
    """
    generate hide variants xml call and uploads the file to the client
    """
    wsm_rc = WsRemoteControlCsVariants(erzeug_system, walk_generator)
    # content is binary utf-8 encoded
    content = wsm_rc.get_xml()
    fname = str(uuid.uuid4()) + ".cdbwscall"
    fpath = os.path.join(CADDOK.TEMP, fname)
    with open(fpath, "wb") as fout:
        fout.write(content)
    if _isContextCdbWeb():
        viewonclient(ctx, fpath, main_file_local_filename=fname)
    else:
        xml_clntfname = os.path.join(client.viewDir, fname)
        ctx.upload_to_client(fpath, xml_clntfname, delete_file_after_upload=1)
