# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
This module provides the search api for the C++ kernel to perform embedded classification queries
in context of CDB_Search operations.
These functions are not part of the external api!
"""

import itertools
import json

from cdb import misc, util
from cdb.storage.index.class_query import fill_tmp_table
from cdbwrapc import CDBClassDef

from cs.classification import solr


def runquery(classname, relation_alias, args):
    query = args.get("cdb::argument.classification_web_ctrl")
    misc.cdblogv(misc.kLogMsg, 7, "search_classified: %s" % query)
    if query:
        # cdb::argument.classified_search contains a json string: {"classes":[],"values":"{}"}
        d = json.loads(query)

        if "metadata" in d:
            addtl_properties = list(d["metadata"].get("addtl_properties", {}))
            assigned_classes = d["metadata"].get("assigned_classes", [])
        else:
            addtl_properties = d.get("addtl_properties", [])
            assigned_classes = d.get("assigned_classes", [])

        values = d.get("values", {})

        if not assigned_classes and not values:
            # if there are no classification search conditions skip classification search
            return ("", "")

        chunk_size = 10000
        limit = None

        mxcl = util.get_prop("mxcl")
        if mxcl and "-1" != mxcl:
            limit = abs(int(mxcl))

        solr_result_cdb_object_ids = set()
        for result in itertools.islice(
                solr.search_solr(
                    values,
                    assigned_classes,
                    addtl_properties,
                    chunk_size
                ),
                0,
                limit
        ):
            solr_result_cdb_object_ids.add(result)

        cldef = CDBClassDef(classname)
        relation = cldef.getRelation()
        conditions, source = fill_tmp_table(
            list(solr_result_cdb_object_ids), relation, relation_alias, 'tt_classified'
        ) if solr_result_cdb_object_ids else ("1=0", "")

        return conditions, source

    else:
        return ("", "")
