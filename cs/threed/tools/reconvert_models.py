#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

import argparse
import collections
import logging
import time

from cdb import sqlapi
from cdb import acs
from cdb.dberrors import DBConstraintViolation
from cdb.objects import ByID
from cdb.objects import Rule

from cs.documents import Document
from cs.vp.items import Item

from cs.threed.hoops import _MODEL_RULE
from cs.threed.hoops.converter import convert_document
from cs.threed.hoops.converter import JSON_FILE_FORMAT, SCZ_FILE_FORMAT, XML_FILE_FORMAT
from cs.threed.hoops.converter.configurations import get_configurations
from cs.threed.hoops.utils import chunks

LOG = logging.getLogger("Reconversion Tool")

FILETYPES = [SCZ_FILE_FORMAT]
DOC_CHUNK_SIZE = 10
MOD_RULE = Rule.ByKeys(_MODEL_RULE)


def safe_print(*msgs):
    try:
        print(" ".join([str(msg) for msg in msgs]))
    except UnicodeEncodeError:
        pass


def convert_docs(docs, filetypes=FILETYPES, site=None):
    for doc in docs:
        if not MOD_RULE.match(doc):
            LOG.warning("%s does not match the object rule '%s'" % (doc.GetDescription(), _MODEL_RULE))
            continue
        try:
            convert_document(doc, target="threed_viewing", params={"filetypes": filetypes, "skip_markup_inval": True}, site=site)
        except Exception as e:
            LOG.error("%s: %s" % (doc.GetDescription(), e))

def get_not_converted_doc_ids(doc_ids, filetypes=FILETYPES):

    # check if configs for expected filetypes exist
    all_config_filetypes = [conf.ft_name for conf in get_configurations()]
    for ftype in filetypes:
        if ftype not in all_config_filetypes:
            raise RuntimeError("No converter config for filetype %s found" % ftype)

    expected_filetypes = filetypes
    if SCZ_FILE_FORMAT in filetypes:
        expected_filetypes.extend([JSON_FILE_FORMAT, XML_FILE_FORMAT])

    filetypes_by_doc_id = collections.defaultdict(list)

    for chunked_doc_ids in chunks(doc_ids):

        doc_condition = "cdbf_object_id IN (%s)" % (
            ", ".join(["'%s'" % oid for oid in chunked_doc_ids]))

        primary_files = sqlapi.RecordSet2(
            table="cdb_file",
            condition="cdbf_primary='1' AND %s" % doc_condition
        )
        for chuncked_primary_files in chunks(primary_files):
            derived_condition = "cdbf_derived_from IN (%s)" % (
                ", ".join(["'%s'" % pfile.cdb_object_id for pfile in chuncked_primary_files]))

            filter_condition = "%s AND %s" % (doc_condition, derived_condition)
            filtered_files = sqlapi.RecordSet2(table="cdb_file", condition=filter_condition)

            for f in filtered_files:
                filetypes_by_doc_id[f.cdbf_object_id].append(f.cdbf_type)

    # at least one file of every expected filetype must be present on the doc to count as converted
    return [doc_id for doc_id, ftypes in filetypes_by_doc_id.items() if not set(expected_filetypes).issubset(set(ftypes))]


def get_existing_jobs(obj_ids, states):
    acsqueue = acs.getQueue()
    jobs = []
    for obj_id_chunk in chunks(obj_ids):
        jobs.extend([
            job for job in acsqueue.query_jobs("src_object_id IN (%s)" % (
                ", ".join(["'%s'" % oid for oid in obj_id_chunk])
            ))
            if job.cdbmq_state in states
        ])
    return jobs


def uniqify_list(lst):
    checked = []
    for e in lst:
        if e not in checked:
            checked.append(e)
    return checked


def get_all_doc_ids_to_convert():
    threed_master_model_exist = True
    all_valid_doc_ids = []

    try:
        ordered_master_models = sqlapi.RecordSet2(table="threed_master_model", addtl="ORDER BY cdb_mdate DESC")
    except DBConstraintViolation:
        threed_master_model_exist = False
        safe_print("Database table 'threed_master_model' not found, skipping master model conversion")

    if (threed_master_model_exist):
        remaining_master_models = ordered_master_models
        doc_ids_by_master_model_oid = collections.OrderedDict().fromkeys(
            [m.cdb_object_id for m in ordered_master_models])

        doc_ids = []
        for chunked_master_models in chunks(remaining_master_models):
            docs = Document.KeywordQuery(cdb_object_id=[m.context_object_id for m in chunked_master_models])
            doc_ids.extend([doc.cdb_object_id for doc in docs])

        for mast_mod in remaining_master_models:
            if mast_mod.context_object_id in doc_ids:
                doc_ids_by_master_model_oid[mast_mod.cdb_object_id] = mast_mod.context_object_id

        remaining_master_models = [mod for mod in remaining_master_models if mod.context_object_id not in doc_ids]

        # get the docs from all items with a master model
        itms = []
        for chunked_master_models in chunks(remaining_master_models):
            itms.extend(Item.KeywordQuery(cdb_object_id=[m.context_object_id for m in chunked_master_models]))

        docs_by_item_id = Item.get_3d_model_documents(itms)
        doc_ids_by_item_id = {key: doc.cdb_object_id for key, doc in docs_by_item_id.items() if doc}

        item_ids = doc_ids_by_item_id.keys()
        for mast_mod in remaining_master_models:
            if mast_mod.context_object_id in item_ids:
                doc_ids_by_master_model_oid[mast_mod.cdb_object_id] = doc_ids_by_item_id[mast_mod.context_object_id]

        remaining_master_models = [
            mod for mod in remaining_master_models if mod.context_object_id not in item_ids]

        # the documents for some master model context objects cannot be determined
        if remaining_master_models:
            safe_print("For some objects no related model could be found. See log for details.")
            for mast in remaining_master_models:
                obj = ByID(mast.context_object_id)
                if obj:
                    LOG.warning("For %s no model could be found" % obj.GetDescription())
                else:
                    LOG.warning("For ID: '%s' no context object could be found" % mast.context_object_id)

        # filter out the docs that dont exist for some reason
        all_valid_doc_ids = [doc_id for doc_id in doc_ids_by_master_model_oid.values() if doc_id]

    # additionally get all docs containing a `3DC:PRC` file
    prc_doc_id_recs = sqlapi.RecordSet2(
        sql="SELECT cdb_object_id FROM zeichnung WHERE cdb_object_id IN (SELECT cdbf_object_id FROM cdb_file WHERE cdbf_type='3DC:PRC')")
    all_valid_doc_ids.extend([rec.cdb_object_id for rec in prc_doc_id_recs])

    unique_doc_ids = uniqify_list(all_valid_doc_ids)

    # filter down to docs that have not been converted in a previous run and preserve order
    unconverted_docs = get_not_converted_doc_ids(unique_doc_ids)
    doc_ids_to_convert = [doc_id for doc_id in unique_doc_ids if doc_id in unconverted_docs]

    return doc_ids_to_convert


def run(args):
    safe_print("Getting models for conversion")
    doc_ids_to_convert = get_all_doc_ids_to_convert()

    safe_print("Starting conversions")

    remaining_doc_ids_cnt = len(doc_ids_to_convert)
    for doc_id_chunk in chunks(doc_ids_to_convert, max_size=DOC_CHUNK_SIZE):

        safe_print("%d / %d conversions remaining..." % (remaining_doc_ids_cnt, len(doc_ids_to_convert)))
        remaining_doc_ids_cnt = remaining_doc_ids_cnt - len(doc_id_chunk)

        docs_to_convert = Document.KeywordQuery(cdb_object_id=doc_id_chunk)
        convert_docs(docs_to_convert, site=args.site)

        while True:
            current_jobs = get_existing_jobs(doc_id_chunk, states=["P", "W"])
            if current_jobs:
                time.sleep(DOC_CHUNK_SIZE) # tie the check interval to the chunk size
            else:
                break

    failed_jobs = get_existing_jobs(doc_ids_to_convert, states=["F"])
    if failed_jobs:
        safe_print("There are failed jobs. Please check the queue.")

    safe_print("Finished conversions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Script for reconverting existing models')
    parser.add_argument('--site', help='cdbmq_site used for all conversions', default=None)
    args = parser.parse_args()
    run(args)
