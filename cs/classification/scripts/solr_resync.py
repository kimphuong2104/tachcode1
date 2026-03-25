# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


import argparse
import datetime
import logging

from cs.classification import ObjectClassificationLog, solr
from cs.classification.solr_schema_sync import process_fields


LOG = logging.getLogger(__name__)


def reindex_objects(output_func, modified_from=None):
    output_func("Reindex objects in solr...")
    start = datetime.datetime.utcnow()
    obj_ids = ObjectClassificationLog.get_ref_object_ids_for_reindex(modified_from=modified_from)
    output_func("Updating %s objects..." % len(obj_ids))
    solr.index_object_ids(obj_ids)
    end = datetime.datetime.utcnow()
    progress_final_info = "Processing took: {}s".format((end - start).total_seconds())
    output_func(progress_final_info)


def resync_schema(output_func, chunk_size=1000):
    process_fields(
        "SELECT cdb_classname, code from cs_property",
        "SELECT cdb_classname, code from cs_class_property",
        output_func=output_func,
        chunk_size=chunk_size
    )

def valid_date(s):
    try:
        return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        try:
            return datetime.datetime.strptime(s, '%Y-%m-%d')
        except ValueError:
            msg = "Wrong date format use 'y-m-d' or 'y-m-dTh:m:s'. Your input was: {}".format(s)
            raise argparse.ArgumentTypeError(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Maintenance utility to resync the solr classification core with the system')
    parser.add_argument(
        '--schema',
        dest='resync_schema',
        default=False,
        action='store_true',
        help='resync the classification schema'
    )
    parser.add_argument(
        '--reindex',
        dest='reindex_objects',
        default=False,
        action='store_true',
        help='re-index all objects'
    )
    parser.add_argument(
        '--force',
        dest='force',
        default=False,
        action='store_true',
        help='force reindexing will override also given modified_from data'
    )
    parser.add_argument(
        '--modified_from',
        dest='modified_from',
        default=None,
        nargs='?',
        type=valid_date,
        help='re-index all objects that have been modified from this date on (y-m-d or y-m-dTh:m:s)'
    )
    parser.add_argument(
        '--quiet',
        dest='quiet',
        default=False,
        action='store_true',
        help='do not show progress information'
    )
    parser.add_argument(
        '--chunk_size',
        dest='chunk_size',
        default=100000,
        nargs='?',
        type=int,
        help='number of solr fields to be updated in one shot in case of --schema is used.'
    )

    args = parser.parse_args()
    if not args.resync_schema and not args.reindex_objects:
        parser.print_help()

    output_func = LOG.info if args.quiet else print
    if args.resync_schema:
        resync_schema(output_func, args.chunk_size)
    if args.reindex_objects:
        if args.force:
            output_func("Clear index log ...")
            ObjectClassificationLog.clear_index_dates()
            output_func("Clear index data ...")
            solr.delete_index()
            modified_from = None
        else:
            modified_from = args.modified_from
        reindex_objects(output_func, modified_from)

    solr._close_solr_connection()
