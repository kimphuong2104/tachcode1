#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Analyses appinfo files of WSM documents and creates cad_variants from them.
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import six
import traceback
import logging

from lxml import etree as ET

from cdb import transaction
from cdb import constants
from cdbwrapc import SimpleArgument, Operation
from cs.vp.cad import CADVariant
from cs.wsm.result import Result, Error

from cs.wsm.pkgs.servertimingwrapper import timingWrapper, timingContext
from cs.wsm.pkgs.pkgsutils import getAppinfoContent


@timingWrapper
@timingContext("PDMPOSTPROCESSOR syncCadVariants")
def syncCadVariants(doc, files, variants):
    """
    :param doc: Document
    :param files: list of cdb_file_base-derived objects
    """
    try:
        if doc.cdb_classname != u"cdb_wsp":
            appinfo = getAppinfoContent(files)
            if not appinfo:
                return Result()

            with transaction.Transaction():
                syncFromAppinfo(doc, appinfo, variants)

        return Result()
    except Exception:
        logging.exception("syncCadVariants, unexpected error:")
        return Error(
            u"Unexpected error when creating cad variants: %s" % traceback.format_exc()
        )


def syncFromAppinfo(doc, appinfo, variants):
    """
    :param doc: Document
    :param appinfo: string containing XML
    """
    appInfoVariants = getVariantsOfAppinfo(appinfo)
    dbVariants = {v.variant_id: v for v in variants}
    deletedIds = set(dbVariants) - set(appInfoVariants)
    newIds = set(appInfoVariants) - set(dbVariants)
    modifiedIds = set(dbVariants) & set(appInfoVariants)

    # first, find variants which are not really new; only their ids have changed
    # (E058610), using the variant name which should be identical to the old id;
    # create changed variants by copy to preserve additional attributes
    changedKeyVariants = set()
    for variantId in newIds:
        variantAppinfo = appInfoVariants[variantId]
        variantName = variantAppinfo.get("name").strip()
        oldVariant = dbVariants.get(variantName)
        if oldVariant is not None:
            changedKeyVariants.add(variantId)
            copyVariant(oldVariant, variantAppinfo)

    for variantId in deletedIds:
        dbVariants[variantId].Delete()

    reallyNewIds = newIds - changedKeyVariants
    for variantId in reallyNewIds:
        createVariant(doc, appInfoVariants[variantId])

    for variantId in modifiedIds:
        modifyVariant(dbVariants[variantId], appInfoVariants[variantId])


def getVariantsOfAppinfo(content):
    """
    :param content: XML as utf-8 byte string
    :return: dict(variant id ->ElementTree Element)
    """
    variants = {}
    root = ET.fromstring(content)
    for variantElement in root.findall("variants/variant"):
        variants[variantElement.get("id").strip()] = variantElement
    return variants


def getExistingVariants(doc):
    """
    :param doc: Document
    :return: dict(variant id ->cad_variant)
    """
    variants = {}
    for variant in doc.CADVariants:
        variants[variant.variant_id] = variant
    return variants


def copyVariant(oldVariant, variantElement):
    parameters = createParameterString(variantElement)
    # allow user exits to analyse the XML describing this variant
    variantAppInfo = ET.tostring(variantElement, encoding="utf-8")
    variantAppInfo = six.ensure_str(variantAppInfo)
    args = {
        "variant_id": variantElement.get("id").strip(),
        "variant_name": variantElement.get("name"),
        "parameters": parameters,
        "cdb::argument.variant_appinfo": variantAppInfo,
        constants.kArgumentActiveIntegration: "wspmanager",
        constants.kArgumentActiveCAD: "wspmanager",
    }
    args = [SimpleArgument(k, str(v)) for k, v in six.iteritems(args)]
    op = Operation("CDB_Copy", oldVariant.ToObjectHandle(), args)
    op.run()


def createVariant(doc, variantElement):
    """
    :param variantElement: ElementTree Element representing a variant
    """
    parameters = createParameterString(variantElement)
    # allow user exits to analyse the XML describing this variant
    variantAppInfo = ET.tostring(variantElement, encoding="utf-8")
    variantAppInfo = six.ensure_str(variantAppInfo)
    args = {
        "z_nummer": doc.z_nummer,
        "z_index": doc.z_index,
        "variant_id": variantElement.get("id").strip(),
        "variant_name": variantElement.get("name"),
        "parameters": parameters,
        "cdb::argument.variant_appinfo": variantAppInfo,
        constants.kArgumentActiveIntegration: "wspmanager",
        constants.kArgumentActiveCAD: "wspmanager",
    }
    args = [SimpleArgument(k, str(v)) for k, v in six.iteritems(args)]
    op = Operation("CDB_Create", "cad_variant", args)
    op.run()


def modifyVariant(dbVariant, appinfoVariant):
    """

    :param dbVariant: cad_variant object
    :param appinfoVariant: ElementTree Element representing a variant
    """
    parameters = createParameterString(appinfoVariant)
    # allow user exits to analyse the XML describing this variant
    variantAppInfo = ET.tostring(appinfoVariant, encoding="utf-8")
    variantAppInfo = six.ensure_str(variantAppInfo)
    args = {
        "variant_name": appinfoVariant.get("name"),
        "parameters": parameters,
        "cdb::argument.variant_appinfo": variantAppInfo,
        constants.kArgumentActiveIntegration: "wspmanager",
        constants.kArgumentActiveCAD: "wspmanager",
    }
    args = [SimpleArgument(k, str(v)) for k, v in six.iteritems(args)]
    op = Operation("CDB_Modify", dbVariant.ToObjectHandle(), args)
    op.run()


def createParameterString(variantElement):
    """
    :param variantElement: ElementTree Element representing a variant
    :return: string representing the parameters of the variant
    """
    parts = {}
    for parameterElement in variantElement.findall("parameters/parameter"):
        name = parameterName(parameterElement)
        val = parameterValue(parameterElement)
        parts[name] = "%s: %s" % (name, val)
    sortedParts = [parts[name] for name in sorted(parts.keys())]
    parameters = ", ".join(sortedParts)
    maxLen = CADVariant.parameters.length
    if len(parameters) > maxLen:
        parameters = parameters[: maxLen - 3] + "..."
    return parameters


def parameterName(parameterElement):
    name = parameterElement.get("name") or parameterElement.get("id", "")
    return name


def parameterValue(parameterElement):
    valueStr = parameterElement.get("value")
    unit = parameterElement.get("unit")
    if unit:
        valueStr = "%s %s" % (valueStr, unit)
    return valueStr
