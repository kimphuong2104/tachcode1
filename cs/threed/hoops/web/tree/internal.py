# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Internal app for the tree in the threed cockpit
"""
import collections
import urllib

from webob import exc

from cdb.platform.olc import Workflow
from cdb.platform.olc import StateDefinition
from cdb.platform.mom.entities import Entity
from cdb.objects.cdb_file import CDB_File

from cs.platform.web import root
from cs.platform.web import JsonAPI
from cs.platform.web.rest.app import get_collection_app

from cs.documents import Document

from cs.vp.items import Item
from cs.vp import bom
from cs.vp.bom import bomqueries
from cs.vp.bom import search as bom_search
from cs.vp.bom.enhancement import FlatBomRestEnhancement
from cs.vp.bom.enhancement.register import BomTableScope
from cs.vp.cad import search as cad_search

from cs.threed.hoops.mapping import get_filename_set_for_bom_items


STATE_DEFINITIONS = None
BOM_ITEM_FIELDS = ["cdb_object_id", "baugruppe", "b_index", "teilenummer", "t_index", "position"]


class TreeInternal(JsonAPI):
    pass


@root.Internal.mount(app=TreeInternal, path="cs.threed.hoops.web.tree")
def _mount_internal():
    return TreeInternal()


def bom_path_to_json(path):
    result = []
    for bom_component in path:
        result.append({
            field_name: getattr(bom_component, field_name)
            for field_name in BOM_ITEM_FIELDS
            if hasattr(bom_component, field_name)
        })
    return result


def _make_bom_table_results(result, itm):
    result_with_root = [[itm] + p for p in result if p]
    return [bom_path_to_json(path) for path in result_with_root]


def _make_rest_id(request, obj):
    return urllib.parse.unquote(request.link(obj, app=get_collection_app(request)))


class TreeSearch(object):
    bom_enhancement: FlatBomRestEnhancement

    def __init__(self, cdb_object_id):
        self.item = Item.ByKeys(cdb_object_id=cdb_object_id)

        self.document = None
        if not self.item:
            self.document = Document.ByKeys(cdb_object_id=cdb_object_id)

        if not self.item and not self.document:
            raise exc.HTTPNotFound()

    def init_bom_enhancement(self, bom_enhancement, request):
        self.bom_enhancement = bom_enhancement
        self.bom_enhancement.initialize_from_request(request)

    @staticmethod
    def _get_relevant_definitions(released):
        global STATE_DEFINITIONS
        if STATE_DEFINITIONS is None:
            part_dd_class = Entity.ByKeys(classname="part")
            if not part_dd_class:
                raise RuntimeError("Cannot find data dictionary class for 'part'")
            objektart = Workflow.KeywordQuery(objclass=part_dd_class.cdb_wflow_cls).objektart
            STATE_DEFINITIONS = StateDefinition.KeywordQuery(objektart=objektart)

        released_definition_numbers = [d.statusnummer for d in STATE_DEFINITIONS if d.statusrelease == 1]
        released_definition_numbers += [
            200,  # freigegeben
            300,  # ERP freigegeben
            400,  # aus ERP
        ]

        def filter_func(definition):
            if released:
                return definition.statusnummer in released_definition_numbers
            return definition.statusnummer not in released_definition_numbers

        return filter(filter_func, STATE_DEFINITIONS)

    def _get_bom_item_paths(self, bom_item):
        def make_entry(c):
            return {
                "cdb_object_id": c.cdb_object_id,
                "position": c.position,
                "comp": c
            }

        def generate():
            def paths_to_assembly(comp):
                parents = self.parents[(comp.baugruppe, comp.b_index)]

                if parents:
                    for parent in parents:
                        for p in paths_to_assembly(parent):
                            p.append(make_entry(comp))
                            yield p
                else:
                    yield [make_entry(comp)]

            for path in paths_to_assembly(bom_item):
                yield path

        return list(generate())

    def _do_part_status_search(self, request, released=True):
        result = {}

        self.init_bom_enhancement(FlatBomRestEnhancement(BomTableScope.SEARCH), request)
        flat_bom = bomqueries.flat_bom(self.item, bom_enhancement=self.bom_enhancement)

        # the flat bom is also needed 'as saved' for the filenames
        flat_bom_as_saved = bomqueries.flat_bom(self.item)

        self.parents = collections.defaultdict(list)
        for bom_item_rec in flat_bom:
            self.parents[(bom_item_rec.teilenummer, bom_item_rec.t_index)].append(bom_item_rec)

        for definition in self._get_relevant_definitions(released):

            status_matches = [
                b for b in flat_bom if b.cdb_objektart == definition.objektart and b.status == definition.statusnummer
            ]
            status_matches_as_saved = [
                b for b in flat_bom_as_saved if b.cdb_object_id in [rec.cdb_object_id for rec in status_matches]
            ]

            ids = {_make_rest_id(request, b) for b in bom.AssemblyComponent.FromRecords(status_matches)}
            filenames = get_filename_set_for_bom_items(status_matches_as_saved)

            paths = list()
            for bom_item_rec in status_matches:
                paths.extend(self._get_bom_item_paths(bom_item_rec))

            bom_table_results = _make_bom_table_results(
                [[elem.pop("comp") for elem in path if "comp" in elem] for path in paths],
                self.item
            )

            key = (definition.statusnummer, definition.statusbez)

            if key not in result:
                result[key] = {
                    "statusNr": definition.statusnummer,
                    "statusName": definition.statusbez,
                    "color": definition.ColorDefinition.css_color,
                    "ids": ids,
                    "filenames": filenames,
                    "tableResults": bom_table_results
                }
            else:
                result[key]["ids"] = result[key]["ids"].union(ids)
                result[key]["filenames"] = result[key]["filenames"].union(filenames)
                result[key]["tableResults"].extend(bom_table_results)


        path_positions = lambda path: [comp.get("position", float("-inf")) for comp in path]

        for key, val in result.items():
            val["ids"] = list(val["ids"])
            val["filenames"] = list(val["filenames"])
            val["tableResults"].sort(key=path_positions)
            result[key] = val

        result_to_sort = result.values()
        objects = sorted(result_to_sort, key=lambda x: x.get("statusNr"))

        return {
            "objects": objects
        }

    @classmethod
    def _make_part_text_search_result(cls, request, result, itm):
        leaf_bom_item_records = [p[-1] for p in result if p]

        ids = {_make_rest_id(request, b) for b in bom.AssemblyComponent.FromRecords(leaf_bom_item_records)}

        filenames = set()
        if leaf_bom_item_records:
            leaf_bom_item_records_as_saved = bomqueries.bom_item_records(*[b.cdb_object_id for b in leaf_bom_item_records])
            filenames = get_filename_set_for_bom_items(leaf_bom_item_records_as_saved)

        bom_table_results = _make_bom_table_results(result, itm)

        return {
            "ids": list(ids),
            "filenames": list(filenames),
            "tableResults": bom_table_results
        }

    @classmethod
    def _make_document_text_search_paths(cls, request, result):
        # exclude root node from search results
        doc_paths = [p for p in result if p and len(p) > 1]

        paths = [[{"@id": _make_rest_id(request, doc)} for doc in p] for p in doc_paths]
        leaf_documents = [p[-1] for p in doc_paths]
        ids = {_make_rest_id(request, doc) for doc in leaf_documents}

        cdb_files = CDB_File.KeywordQuery(
            cdbf_object_id=[d.cdb_object_id for d in leaf_documents if d], cdbf_primary=1)
        filenames = {f.cdbf_name for f in cdb_files}

        return paths, list(ids), list(filenames)

    @classmethod
    def _make_document_text_search_result(cls, request, result):
        paths, ids, filenames = cls._make_document_text_search_paths(request, result)

        return {
            "paths": paths,
            "ids": ids,
            "filenames": filenames
        }

    def do_part_released_search(self, request):
        return self._do_part_status_search(request, released=True)

    def do_part_unreleased_search(self, request):
        return self._do_part_status_search(request, released=False)

    def do_part_text_search(self, request):
        condition = request.GET.get("condition", "")

        search = bom_search.BomSearch(self.item, condition, bom_enhancement=self.bom_enhancement)
        result = search.get_results()

        return self._make_part_text_search_result(request, result, self.item)

    def do_document_text_search(self, request):
        condition = request.GET.get("condition", "")

        search = cad_search.CadDocumentStructureSearch(self.document, condition)
        result = search.get_results()

        return self._make_document_text_search_result(request, result)

    def do_text_search(self, request):
        if self.document:
            return self.do_document_text_search(request)

        self.init_bom_enhancement(FlatBomRestEnhancement(BomTableScope.SEARCH), request)
        return self.do_part_text_search(request)


@TreeInternal.path(path="search/{cdb_object_id}", model=TreeSearch)
def _get_search_model(cdb_object_id):
    return TreeSearch(cdb_object_id)


@TreeInternal.json(model=TreeSearch, name="released_parts", request_method="POST")
def _part_unreleased_search(search_obj, request):
    return search_obj.do_part_released_search(request)


@TreeInternal.json(model=TreeSearch, name="unreleased_parts", request_method="POST")
def _part_unreleased_search(search_obj, request):
    return search_obj.do_part_unreleased_search(request)


@TreeInternal.json(model=TreeSearch, name="text", request_method="POST")
def _text_search(search_obj, request):
    return search_obj.do_text_search(request)
