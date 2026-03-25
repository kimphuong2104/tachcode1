#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import acs as cdbacs
from cdb import sqlapi
from cdb import util

from cs.documents import Document

import json

from cs.vp.cad import Model

from cs.threed.hoops.utils import chunks
from cs.threed.hoops.converter.utils import get_job_params

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

JSON_FILE_FORMAT = "Hoops:JSON"
SCZ_FILE_FORMAT = "Hoops:SCZ"
XML_FILE_FORMAT = "Hoops:XML"
PRC_FILE_FORMAT = "PRC"
PDF_FILE_FORMAT = "Acrobat"


CSCONVERT_NAME = "CSConvert"
HOOPS_CONVERTER_NAME = "HOOPS"

cSetup = None


def convert_document(doc, target=None, checkForExistingJob=True, params=None, callback=None, site=None):
    """
    Generate a Job in the ACS-Queue to create a 3D model.
    By default this converts a given document to all formats 
    existing as an active converter configuration 
    if a registered acs target name is provided.

    :param doc: The source CAD-document.
    :param target: Name of the output target.
        This needs to be registered as an acs plugin for the source filetype.
    :param checkForExistingJob: If True a job will be create in the acs queue only if
        no jobs for the same source and target format is waiting.
    :param params: A dictionary. Can be used to specify a list of target filetypes 
        with the key `filetypes` and a list of converter configurations specified via the
        `ft_name` attribute as the value. If this list is provided, the document will be
        converted with the matching configurations instead of the active ones.
    :param site: String specifying the target site for the replication.

    :return: A list with the ids of the created acs jobs.
    """

    if params is None:
        params = {}

    jobids = []

    if target is not None:
        order = cdbacs.Order(doc.cdb_object_id, target, doc.erzeug_system, callback=callback, site=site)
        job = None
        if checkForExistingJob:
            job = order.getExistingJob()
        if not job:
            job = _release_order_with_params(order, params)

        jobids.append(job.cdbmq_id)

    return jobids


def create_threed_batch_job(docs, target=None, filetypes=None, reconvert_dependencies=False):

    if target is not None:

        doc_oids = [doc.cdb_object_id for doc in docs]

        params = {
            "doc_ids": doc_oids,
            "target": target,
            "filetypes": filetypes if filetypes is not None else [],
            "reconvert_dependencies": reconvert_dependencies,
        }

        for doc in docs:
            if target_registered(doc.erzeug_system, "threed_batch"):
                order = cdbacs.Order(doc.cdb_object_id, "threed_batch", doc.erzeug_system)
                return _release_order_with_params(order, params)

    return None


def create_dependent_jobs(job, all_configs):

    params = get_job_params(job.id())

    if params is None:
        job.log("Missing job parameters. No dependent jobs will be created")
        return 0

    doc_ids = params["doc_ids"] if "doc_ids" in params.keys() else []
    target = params["target"] if "target" in params.keys() else None
    filetypes = params["filetypes"] if "filetypes" in params.keys() else []

    if not filetypes:
        filetypes = [conf.ft_name for conf in all_configs if conf.auto_convert]

    reconvert_dependencies = params["reconvert_dependencies"] if "reconvert_dependencies" in params.keys() else False

    docs = [Document.ByKeys(cdb_object_id=oid) for oid in doc_ids]

    if target is not None and filetypes:
        conversion_docs = set([])
        dependency_docs = set([])

        for doc in docs:
            if target_registered(doc.erzeug_system, target):
                conversion_docs.add(doc)

            if reconvert_dependencies:
                for dep in doc.getModelDependencies():
                    if target_registered(dep.erzeug_system, target):
                        dependency_docs.add(dep)

        if reconvert_dependencies:
            conversion_docs.update(get_reconversion_docs(dependency_docs, filetypes))

        for cd in conversion_docs:
            convert_document(cd, target=target, params={"filetypes": filetypes})

    # remove batch params
    util.text_write("threed_hoops_job_params", ['job_id'], [job.id()], "")

    return 0


def get_reconversion_docs(docs, file_types):

    reconversion_docs = set([])

    for chunked_docs in chunks(docs):

        primary_files = sqlapi.RecordSet2(
            table="cdb_file",
            condition="cdbf_primary='1' AND cdbf_object_id IN (%s)" % (", ".join(["'%s'" % doc.cdb_object_id for doc in chunked_docs]))
        )

        for chunked_primary_files in chunks(primary_files):

            doc_condition = "cdbf_object_id IN (%s)" % (", ".join(["'%s'" % doc.cdb_object_id for doc in chunked_docs]))
            filetype_condition = "cdbf_type IN (%s)" % (", ".join(["'%s'" % ftype for ftype in file_types]))
            derived_condition = "cdbf_derived_from IN (%s)" % (", ".join(["'%s'" % pfile.cdb_object_id for pfile in chunked_primary_files]))

            filter_condition = "%s AND %s AND %s" % (doc_condition, filetype_condition, derived_condition)
            filtered_files = sqlapi.RecordSet2(table="cdb_file", condition=filter_condition)

            result = Document.KeywordQuery(cdb_object_id=[f.cdbf_object_id for f in filtered_files])
            reconversion_docs.update(result)

    return reconversion_docs


def target_registered(filetype, target):
    return (target, "hoops") in cdbacs.registered_conversions(filetype)


def _release_order_with_params(order, params):
    job = order.ratify()

    params_str = json.dumps(params)
    util.text_write("threed_hoops_job_params", ['job_id'], [job.id()], params_str)

    job.start()
    return job
