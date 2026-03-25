#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

import six
import os
import sys

from cdb.acs import acslib

if sys.platform == "win32":
    from cs.office.acsplugins.office import pdfconverter


log = acslib.log

cPlgInRevision = "$Revision$"[11:-2]
cPlgInLocation = os.path.dirname(__file__)
cPlgInName = "msoffice"
cSetup = None
Conversions = {}


def initPlgIn():
    """Initializing of the plugin - also see the "null" plugin."""
    global cSetup, Conversions
    log("initing plugin %s\n" % cPlgInName)
    cSetup = acslib.getPluginsSetup(cPlgInName)
    Conversions = cSetup["Conversions"]


def testPlgIn():
    """Test of configuration and environment - also see the "null" plugin."""
    log("testing configuration of plugin %s\n" % cPlgInName)
    if cSetup.get("ResultTypes") is None:
        raise Exception("ResultTypes not defined")
    targets = set()
    for val in six.itervalues(Conversions):
        targets.update(val)
    for t in targets:
        if cSetup["ResultTypes"].get(t) is None:
            raise Exception("No result filetype defined for target '%s'" % t)
    return True


def HandleJob(job):
    """Execute the conversion - also see the "null" plugin."""
    global log

    # All functions called by this handle should use the log of the job
    log = job.log

    if sys.platform != "win32":
        log("Job was cancelled! The execution is only possible on a WIN32 platform.\n")
        return 1

    # Set up environment and configuration
    testPlgIn()

    # Check out source file
    src_file = job.get_file()
    if src_file is None:
        log("Could not get source file\n")
        return 1
    srcFPName = job.checkout_file(src_file)

    # Set destination file name
    src_root = os.path.splitext(srcFPName)[0]
    dstFPName = src_root + '.pdf'

    # Use pdfconverter.conf from $CADDOK_BASE/etc. If the file does not exist,
    # pdfconverter.conf from $CADDOK_HOME will be used.
    cfgfile = None

    # Check if the owner of the file is a document. If so, determine the
    # document keys for the PDF converter
    owner_doc = job.get_document()
    if owner_doc:
        z_nummer = owner_doc.z_nummer
        z_index = owner_doc.z_index
    else:
        z_nummer = None
        z_index = None

    # Get conversion user login (undefined when running "testplg")
    conversion_user_login = getattr(job, "cdbmq_enquser", "").split("@")[0]

    # Convert the document/file
    retVal = pdfconverter.convert(srcFPName, cfgfile, z_nummer, z_index, dstFPName, log,
                                  job.src_object_id, conversion_user_login, job)

    # Evaluate conversion return code
    if int(retVal) != pdfconverter.kSuccess:
        error_desc = pdfconverter.get_error_desc(int(retVal))
        log("Received error from converter tool: return code %s\n%s\n" % (retVal, error_desc))
        log("For details take a look at: %s\n" % job._workdir)
        return 1

    # Check if destination file exists at all
    if not (os.path.isfile(dstFPName)):
        log("Missing result of conversion\n")
        return 1

    # Pass conversion to the server
    result_type = cSetup["ResultTypes"].get(job.target, 'Acrobat')
    job.store_file(src_file, dstFPName, result_type)

    return 0
