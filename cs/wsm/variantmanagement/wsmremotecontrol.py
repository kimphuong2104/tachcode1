# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module wsmremotecontrol

Generating XML-Format for cdbwscall

"""
from __future__ import absolute_import
import json
from xml.etree import ElementTree

from cdb import util
from cs.vp.variants.filter import (
    ProductStructureFilter,
    get_maxbom_rating_method,
    kMaxBOMRatingMethodPredicateBased,
    kMaxBOMRatingMethodSingleProperty,
)

import six


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


class WsmRemoteControl(object):
    """
    Return XML-Infos fuer Varianten
    """

    # Example 3<?xml version="1.0"?>
    # <cdbwsinfo>
    #    <command>reduce150percent</command>
    #    <parameters>
    #       <parameter>
    #          <ptype>BO</ptype>
    #          <cadsystem>CatiaV5</cadsystem>
    #          <doc_object_id>9df32c61-754a-11e9-94c9-0021ccd84fcf</doc_object_id>
    #          <doc_name>BO-text</doc_name>
    #          <doc_filenames>Torso.CATPart?Torso2.CATPart</doc_filenames>
    #       </parameter>
    #       <parameter>
    #          <ptype>BO</ptype>
    #          <cadsystem>ProE</cadsystem>
    #          <doc_object_id>proe9df32c61-754a-11e9-94c9-0021ccd84fcf</doc_object_id>
    #          <doc_name>BO-text</doc_name>
    #          <doc_filenames>Torso.CATPart?Torso2.CATPart</doc_filenames>
    #       </parameter>
    #       <parameter>
    #         <ptype>OCCINFO</ptype>
    #         <occpath>["id1","id2"]</occpath>
    #         <occenabled>HIDE</occenabled>
    #       </parameter>

    ASSEMBLY_TYPES = {
        "CatiaV5:Prod",
        "ProE:Asmbly",
        "Unigraphics:prt",
        "SolidEdge:asm",
        "SolidWorks:asm",
        "inventor:asm",
    }

    def __init__(self, maxbom, filetype):
        self.maxbom = maxbom
        self.filetype = filetype
        self.cad_source = self.filetype.split(":")[0]

    def _add_model_parameters(self, item, parameters_el):
        """
        Add all Assembly-Type documents to paramaters Element
        """
        for doc in item.Documents.KeywordQuery(erzeug_system=self.filetype):
            param_el = ElementTree.Element("parameter")
            ptype_el = ElementTree.Element("ptype")
            ptype_el.text = "BO"
            param_el.append(ptype_el)
            cadsystem_el = ElementTree.Element("cadsystem")
            cadsystem_el.text = doc.erzeug_system.split(":")[0]
            param_el.append(cadsystem_el)
            boname_el = ElementTree.Element("doc_name")
            boname_el.text = doc.ToObjectHandle().getDesignation()
            param_el.append(boname_el)
            bo_id_el = ElementTree.Element("doc_object_id")
            bo_id_el.text = doc.cdb_object_id
            param_el.append(bo_id_el)
            filenames = [f.cdbf_name for f in doc.Files if not f.cdb_belongsto]
            filename_el = ElementTree.Element("doc_filenames")
            filename_el.text = u"?".join(filenames)
            param_el.append(filename_el)
            parameters_el.append(param_el)

    def _add_hide_information(self, occurence_id_path, active, parameters_el):
        """ """
        param_el = ElementTree.Element("parameter")
        ptype_el = ElementTree.Element("ptype")
        ptype_el.text = "OCCINFO"

        param_el.append(ptype_el)
        occpath_el = ElementTree.Element("occpath")
        occpath_el.text = json.dumps(occurence_id_path)
        param_el.append(occpath_el)

        occenabled_el = ElementTree.Element("occenabled")
        occenabled_el.text = "SHOW" if active else "HIDE"

        param_el.append(occenabled_el)
        parameters_el.append(param_el)

    def get_ctrl_lines(self, product_object_id, props):
        ctrl_lines = ['<?xml version="1.0"?>']
        root_el = ElementTree.Element("cdbwsinfo")
        command_el = ElementTree.Element("command")
        command_el.text = "reduce150percent"
        root_el.append(command_el)
        parameters_el = ElementTree.Element("parameters")
        root_el.append(parameters_el)
        self._add_model_parameters(self.maxbom, parameters_el)

        properties = list(six.iteritems(props))
        filter_ = ProductStructureFilter(
            product_object_id,
            properties,
            self.filter_bom_item_callback,
            self.filter_item_callback,
        )

        for node in filter_.walk(self.maxbom):
            occurence_id_path = []
            for bom_item in reversed(node.path):
                if not bom_item.occurence_id:
                    rating_method = get_maxbom_rating_method()
                    ratings = 0
                    if rating_method == kMaxBOMRatingMethodPredicateBased:
                        ratings = len(bom_item.VPMPredicates)
                    elif rating_method == kMaxBOMRatingMethodSingleProperty:
                        ratings = len(bom_item.VPMProperties)
                    if ratings:
                        self.handle_missing_occurence_id(node)
                    else:
                        occurence_id_path = []
                        break
                occurence_id_path.append(bom_item.occurence_id)
            if occurence_id_path:
                self._add_hide_information(
                    occurence_id_path, node.active, parameters_el
                )
        ctrl_lines.append(ElementTree.tostring(root_el))
        return ctrl_lines

    def get_variant_ctrl_lines(self, variant_obj):
        return self.get_ctrl_lines(
            variant_obj.product_object_id, variant_obj.get_property_values()
        )

    def filter_bom_item_callback(self, bom_item):
        return bom_item.cadsource == self.cad_source

    def filter_item_callback(self, _item):
        return True

    def handle_missing_occurence_id(self, node):
        u"""Builds a message as follows and raises it as util.ErrorMessage Exception:

        Fehlende CATIA Verbauungsinformation (occurence_id)
        an folgender Stuecklistenposition (Pfad ausgehend von der Top Level Baugruppe):
        Position 10: 1272782/a --> Position 40: 2333443/b -> ...

        Description of path elements (bom items) can be configured by
        cdbvp_cadctrl_err_bomitem_dtag Message.
        Leading text can be configured by cdbvp_cadctrl_err_occurence_id
        Message.
        """

        pattern = None
        from cdb.platform import gui

        m = gui.Message.ByName("cdbvp_cadctrl_err_bomitem_dtag")
        if m:
            pattern = m.Text[""]

        path = []
        for bom_item in reversed(node.path):
            if pattern:
                path.append(bom_item.ApplyDescriptionPattern(pattern))
            else:
                path.append(bom_item.GetDescription())

        raise util.ErrorMessage("cdbvp_cadctrl_err_occurence_id", " --> ".join(path))
