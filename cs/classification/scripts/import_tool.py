# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import argparse
import io
import json
import logging
import os
from collections import defaultdict
from cdb.comparch.content import ModuleContentItem
from cdb.comparch import tools
from cdb.comparch import blob_utils
from cs.classification.scripts import export_tool
from cdb import transactions
from cdb import util
from cs.classification.scripts.solr_resync import resync_schema

kDiffNone = 0
kDiffUpdate = 1
kDiffInsert = 2
kDiffDelete = 3

LOG = logging.getLogger(__name__)


class ContentItem(object):

    def __init__(self, mc_item):
        self.mc_item = mc_item

    def applyToDB(self):
        diffs, rec = self.diff()
        if rec:
            # update
            diffs = {attr: diff["NEW_VALUE"] for attr, diff in diffs.items() if "NEW_VALUE" in diff}
            if diffs:
                try:
                    rec.update(**diffs)
                except AttributeError:
                    # reduce to existing attributes and retry
                    ti = util.tables[self.mc_item.getType()]
                    attrs = ti.attrname_list().split(",")
                    for attr in list(diffs):
                        if attr not in attrs:
                            del diffs[attr]
                    if diffs:
                        rec.update(**diffs)

                return kDiffUpdate if diffs else kDiffNone
        else:
            # insert
            self.mc_item.insertIntoDB()
            return kDiffInsert
        return kDiffNone

    def diff(self):
        diffs = None
        rec = self.mc_item._getPersistentRecord()
        if rec:
            rec_data = dict(rec.items())
            # ensure that rec_data (e.g. datetime) is in the same format as the mc_item
            rec_data = tools.fromjson(tools.tojson(rec_data))
            diffs = tools._diff_attr_dicts(rec_data, self.mc_item.getAttrs())
        return diffs, rec


class ModuleContentDummy(object):

    def __init__(self):
        self.module_id = ""


class Importer(object):

    rels_with_del = ["cs_property_group_assign", "cs_class_property_group"]

    def __init__(self, exp_dir):
        self.exp_dir = exp_dir
        self.exp_filename = os.path.join(exp_dir, "data.json")
        self._stats = defaultdict(int)

    def run(self):
        with transactions.Transaction():
            self._run()

    def _run(self):
        with io.open(self.exp_filename, 'rb') as export_file:
            data = json.load(export_file)
        content_items_with_del_by_type_and_key = defaultdict(dict)
        blobs_to_import = []
        class_codes = []

        for item_type, data_dict in data.items():
            content = data_dict["CONTENT"]
            print("Processing %s entries of %s" % (len(content), item_type))
            for item_dict in content:
                mc_item = ModuleContentItem(item_type, item_dict, ModuleContentDummy())
                content_item = ContentItem(mc_item)
                if item_type in Importer.rels_with_del:
                    content_items_with_del_by_type_and_key[item_type][content_item.mc_item.key()] = content_item
                if item_type == "cdb_file":
                    blobs_to_import.append(mc_item.getAttr("cdbf_blob_id"))
                if item_type == "cs_classification_class":
                    class_codes.append(mc_item.getAttr("code"))
                action = content_item.applyToDB()
                self._stats[action] += 1

        if blobs_to_import:
            print("Importing blobs...")
            blob_utils.put_blobs_in_blobstore(self.exp_dir, blobs_to_import)

        # Delete aggregated elements of contained classes, that have been removed
        # Notes:
        # - never delete reusables like units, catalog props etc.
        # - never delete elements that have impact to stored classification data (e.g. classes, class props etc)
        exp = export_tool.Exporter(None, with_subclasses=False, classes_to_export=class_codes)
        exp.collect()
        for rel in Importer.rels_with_del:
            for obj in exp.objects_by_type[rel]:
                key = ModuleContentItem.makeKey(**obj._record.keydict())
                if key not in content_items_with_del_by_type_and_key[rel]:
                    obj.Delete()
                    self._stats[kDiffDelete] += 1

    def print_stats(self):
        print("Applied diffs: Updated %s, Inserted %s, Deleted %s" % (self._stats.get(kDiffUpdate, 0),
                                                                      self._stats.get(kDiffInsert, 0),
                                                                      self._stats.get(kDiffDelete, 0)))


def run(exp_dir):
    imp = Importer(exp_dir)
    imp.run()
    return imp


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Utility to import classification classes '
                                                 'that have been exported by export_tool')
    parser.add_argument("exp_dir", help="Export directory to import")
    args = parser.parse_args()
    imp = run(args.exp_dir)
    print("Updating search index")
    resync_schema(LOG.info)
    imp.print_stats()
    print("Export %s has been applied" % args.exp_dir)
