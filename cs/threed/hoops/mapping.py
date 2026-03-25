# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module provides the functionality to map between the exchange id path of a
specific node and its associated document, as well as vice versa.
"""

import logging
import collections
import os

from cdb import sqlapi

from cdb.objects.cdb_file import CDB_File

from cs.documents import Document

from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent
from cs.vp.cad import CADVariant

from cs.threed.hoops import utils

LOG = logging.getLogger(__name__)

IDENTITY_MATRIX = '1.0 0.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 0.0 1.0'


def get_filename_set_for_bom_items(bom_items: list[AssemblyComponent] | sqlapi.RecordSet2) -> set[str]:
    """
    Returns a set of filenames for a given list of bom item objects/records.
    The set of filenames might be smaller than the list of bom items, if parts do not contain a document of the hierarchy.

    @param bom_items: list of bom items
    @return: set of filenames
    """
    items_by_bom_item = AssemblyComponent.get_items_for_bom_items(bom_items)
    documents_by_item_oid = Item.get_3d_model_documents(list(items_by_bom_item.values()))
    cdb_files = CDB_File.KeywordQuery(
        cdbf_object_id=[d.cdb_object_id for d in documents_by_item_oid.values() if d], cdbf_primary=1)
    return {f.cdbf_name for f in cdb_files}


class DocumentFileMapper(object):
    def __init__(self, context_document):
        self.context_document = context_document

    def get_context_files(self, filenames):

        file_keys = ", ".join(["cdb_file." + fd.name for fd in set(CDB_File.GetTableKeys())])
        doc_rel_keys = ["z_nummer", "z_index", "z_nummer2", "z_index2"]
        keys = ", ".join(["{table}" + name for name in doc_rel_keys])

        root_condition = "cdb_doc_rel.z_nummer='%s' AND cdb_doc_rel.z_index='%s'" % (
            self.context_document.z_nummer, self.context_document.z_index)
        child_condition = "doc_files.z_nummer2=cdb_doc_rel.z_nummer AND doc_files.z_index2=cdb_doc_rel.z_index"
        filename_condition = " OR ".join(["(cdbf_name='%s')" % fname for fname in filenames])

        db_type = sqlapi.SQLdbms()
        db_specific_command = "WITH"

        if db_type == sqlapi.DBMS_POSTGRES:
            db_specific_command = "WITH RECURSIVE"

        QUERYSTR = """
            {db_specific_command} doc_files ({keys})
                AS
                (
                    SELECT {doc_rel_keys}
                        FROM cdb_doc_rel
                        WHERE {root_condition}
                    UNION ALL
                        SELECT {doc_rel_keys}
                        FROM cdb_doc_rel
                        INNER JOIN doc_files
                            ON {child_condition}
                )
            SELECT DISTINCT {file_keys}
            FROM doc_files
            LEFT JOIN zeichnung 
                ON doc_files.z_nummer2=zeichnung.z_nummer 
                    AND doc_files.z_index2=zeichnung.z_index 
                OR doc_files.z_nummer=zeichnung.z_nummer 
                    AND doc_files.z_index=zeichnung.z_index
            LEFT JOIN cdb_file
                ON cdb_file.cdbf_object_id=zeichnung.cdb_object_id
                WHERE {filename_condition}
        """

        query = QUERYSTR.format(
            db_specific_command=db_specific_command,
            keys=keys.format(table=""),
            file_keys=file_keys,
            doc_rel_keys=keys.format(table="cdb_doc_rel."),
            root_condition=root_condition,
            child_condition=child_condition,
            filename_condition=filename_condition
        )

        result = sqlapi.RecordSet2(sql=query)

        return result

    def _get_alternative_solid_works_files(self, filenames):
        """
        Fix for E075641.
        SolidWorks changed their file extensions from upper case
        to lower case in 2020. Assemblies that were upgraded might
        return the wrong casing for their sub-assemblies and parts.
        In such cases, the files are not found, even though they exist.
        This function tries to find files with the opposite casing.
        """
        extension_lookup = {
            ".SLDASM": ".sldasm",
            ".sldasm": ".SLDASM",
            ".SLDPRT": ".sldprt",
            ".sldprt": ".SLDPRT"
        }

        applicable_filenames = []
        filename_mpping = {}
        for filename in filenames:
            fname, extension = os.path.splitext(filename)
            if extension in extension_lookup.keys():
                new_name = fname + extension_lookup[extension]
                applicable_filenames.append(new_name)
                filename_mpping[new_name] = filename

        cdb_files = CDB_File.KeywordQuery(cdbf_name=applicable_filenames)
        newly_found_filenames = [filename_mpping[f.cdbf_name] for f in cdb_files if f.cdbf_name in filename_mpping]
        return cdb_files, applicable_filenames, newly_found_filenames


    def get_missing_file_names(self, files, expected_file_names):
        missing_file_names = []
        found_filenames = [f.cdbf_name for f in files]
        for filename in expected_file_names:
            if filename not in found_filenames:
                missing_file_names.append(filename)
        return missing_file_names


    def get_document_path_for_filenames(self, filenames):
        """
        Returns the document path for the given list of exchange ids. The first
        element in the resulting list always is the context document!

        @param filenames: the list of filenames with the toplevel file first
        @return: a list of cs.documents.Document instances with the head/context document first
        """
        result = []
        filenames = list(filenames)

        files_by_name = dict()
        cdb_files = CDB_File.KeywordQuery(cdbf_name=filenames)

        missing_filenames = self.get_missing_file_names(cdb_files, filenames)
        corrected_filenames_found = []
        if missing_filenames:
            #Workaround for E075641
            additional_files, corrected_filenames, corrected_filenames_found = self._get_alternative_solid_works_files(missing_filenames)
            filenames.extend(corrected_filenames)
            cdb_files.extend(additional_files)


        if len(cdb_files) > len(filenames):
            LOG.info(
                "expected to find exactly one file per filename, but found multiple."
                "restricting to document context"
            )
            cdb_files = self.get_context_files(filenames)

        if not cdb_files:
            LOG.warn(
                "expected to find exactly one file per filename, but found none."
            )

        for f in cdb_files:
            files_by_name[f.cdbf_name] = f

        documents = Document.KeywordQuery(cdb_object_id=[cdbf.cdbf_object_id for cdbf in cdb_files])
        documents_by_id = dict()
        for document in documents:
            documents_by_id[document.cdb_object_id] = document

        for filename in filenames:
            if filename not in files_by_name:
                #only throw an error if no corrected filename was found as well
                if filename not in corrected_filenames_found:
                    raise RuntimeError("filename %s does not identify a file" % filename)
                else:
                    continue

            cdb_file = files_by_name[filename]
            if cdb_file.cdbf_object_id not in documents_by_id:
                raise RuntimeError(
                    "could not find a document with object id '%s'" % cdb_file.cdbf_object_id
                )
            result.append(documents_by_id[cdb_file.cdbf_object_id])

        return result

    def get_filename_paths_for_document_paths(self, document_paths):
        """
        Gets a list of filename paths (top down) for a given list of document paths.

        The context document must be the last element of every document path list.

        @param document_paths: list of document paths with the most derived document first in every document path
        @return: list of filename paths with the name of the root element first in every filename path
        """

        flat_docs_set = set([doc for path in document_paths for doc in path])
        documents_by_id = {d.cdb_object_id: d for d in flat_docs_set}

        cdb_files = CDB_File.KeywordQuery(cdbf_object_id=documents_by_id.keys(), cdbf_primary=1)

        cdb_files_by_document_id = collections.defaultdict(list)
        for f in cdb_files:
            cdb_files_by_document_id[f.cdbf_object_id].append(f)

        filename_paths = []
        for doc_path in document_paths:

            fname_path = []
            for doc in doc_path:
                files = cdb_files_by_document_id[doc.cdb_object_id]
                if len(files) != 1:
                    raise RuntimeError("expected to find exactly 1 file for document '%s', but found: %s" % (
                        doc.GetDescription(), [f.GetDescription() for f in files]
                    ))
                fname_path.append(files[0].cdbf_name)

            filename_paths.append(fname_path)

        return filename_paths


class PartDocumentMapper(object):
    def __init__(self, context_part):
        self.context_part = context_part
        self.document_mapper = DocumentFileMapper(context_part.get_3d_model_document())

    @classmethod
    def _get_parts_for_documents(cls, documents):
        pk_statement = utils.make_item_pk_statement(documents)
        items = {(i.teilenummer, i.t_index): i for i in Item.Query(pk_statement)}

        variants = collections.defaultdict(list)
        for variant in CADVariant.Query(pk_statement):
            variants[(variant.teilenummer, variant.t_index)].append(variant)

        result = collections.defaultdict(list)

        for doc in documents:
            doc_key = (doc.z_nummer, doc.z_index)
            item_key = (doc.teilenummer, doc.t_index)
            result[doc_key].append(items[item_key])
            result[doc_key].extend(variants[item_key])

        return result

    @classmethod
    def _get_possible_bom_items(cls, items):
        """
        Returns all the bom items where the given items are in the role of the assembly
        @param items:
        @return:
        """
        pk_statement = utils.make_item_pk_statement(items, {'teilenummer': 'baugruppe', 't_index': 'b_index'})
        return AssemblyComponent.Query(pk_statement)

    def get_filename_path_for_bom_items(self, bom_items):
        """
        Returns a list of filenames (top down) for a given list of bom items (top down). The list of filenames might be
        longer than the list of bom items, if one of the parts contain more than one document of the hierarchy.

        @param bom_items: list of bom items (top down). The assembly of the first bom item must be the context part of this object
        @return: list of filenames ordered top down
        """
        import warnings
        warnings.warn(
            "`get_filename_path_for_bom_items` is deprecated. Use `get_filename_paths_for_bom_item_paths` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_filename_paths_for_bom_item_paths([bom_items])[0]

    def get_filename_paths_for_bom_item_paths(self, bom_item_paths):
        """
        Returns a list of filename paths (top down) for a given list of bom item paths (top down). 
        Each list of filenames might be longer than the corresponding list of bom items, 
        if one of the parts contain more than one document of the hierarchy.

        @param bom_items: list of bom item paths (top down).
        @return: list of filename paths (top down)
        """

        # the first document of every path should always be the one that is opened in the cockpit
        root_doc = self.context_part.get_3d_model_document()

        flat_bom_items_set = set([bom_item for path in bom_item_paths for bom_item in path])
        bom_items_by_id = {bom_item.cdb_object_id: bom_item for bom_item in flat_bom_items_set}

        items_by_bom_item = AssemblyComponent.get_items_for_bom_items(list(bom_items_by_id.values()))
        documents_by_item = Item.get_3d_model_documents(list(items_by_bom_item.values()))
        documents_by_bom_item_id = {bom_item_id: documents_by_item[item.cdb_object_id] for bom_item_id, item in items_by_bom_item.items()}

        document_paths = []
        for path in bom_item_paths:
            documents = []
            invalid = False
            if root_doc:
                documents.append(root_doc)

            for bom_item in path:
                current = documents_by_bom_item_id[bom_item.cdb_object_id]
                if current:
                    documents.append(current)
                else:
                    invalid = True

            if invalid:
                documents = []

            document_paths.append(documents)

        return self.document_mapper.get_filename_paths_for_document_paths(document_paths)

    def get_bom_item_path_for_filenames(self, filenames, transformation_matrix_path=None):
        """
        Returns a list of bom items (top down) for a given list of filenames (top down). The list of bom items might be
        shorter than the list of filenames, if one of the parts contain more than one document of the hierarchy.

        @param filenames: list of filenames (top down).
        @return: list of cs.vp.bom.AssemblyComponents. The assembly of the first bom item is the context part of this object
        """
        documents = self.document_mapper.get_document_path_for_filenames(filenames)
        result = []

        parts_for_documents = self._get_parts_for_documents(documents)

        root_doc = documents[0]
        root_doc_parts = parts_for_documents[(root_doc.z_nummer, root_doc.z_index)]
        if self.context_part not in root_doc_parts:
            raise ValueError("Part '%s' is not a part that is assigned to the root document '%s', but should" % (
                self.context_part.GetDescription(),
                root_doc.GetDescription()
            ))

        all_items = []
        for i in parts_for_documents.values():
            all_items.extend(i)
        possible_bom_items = self._get_possible_bom_items(all_items)
        bom_items_by_assembly_and_item = collections.defaultdict(list)
        for b in possible_bom_items:
            bom_items_by_assembly_and_item[(b.baugruppe, b.b_index, b.teilenummer, b.t_index)].append(b)


        # remove root trafo matrix
        if transformation_matrix_path:
            transformation_matrix_path.pop()

        top_doc = documents[0]
        for child_doc in documents[1:]:
            key = (top_doc.teilenummer, top_doc.t_index, child_doc.teilenummer, child_doc.t_index)
            bom_items = bom_items_by_assembly_and_item[key]

            if not bom_items:
                # this might happen if two documents are belonging to the same part...
                continue

            transform_to_compare = None
            if transformation_matrix_path:
                transform_to_compare = transformation_matrix_path.pop()
                if transform_to_compare is None:
                    transform_to_compare = IDENTITY_MATRIX

            if len(bom_items) > 1 and transform_to_compare is not None:

                bom_item_ids = [bom_item.cdb_object_id for bom_item in bom_items]
                possible_bom_item_occurrences = utils.get_occurrences_for_bom_item_ids(bom_item_ids)

                def _transformations_match(bom_item_occurrence, model_transformations):
                    occ_transformations = [float(trans) for trans in bom_item_occurrence["relative_transformation"].split(" ")]
                    bom_transformations = [float(trans) for trans in model_transformations.split(" ")]
                    for idx, val in enumerate(occ_transformations):
                        if not utils.isclose(val, bom_transformations[idx]):
                            return False
                    return True

                matching_bom_item_occurrences = []
                for occ in possible_bom_item_occurrences:
                    if _transformations_match(occ, transform_to_compare):
                        matching_bom_item_occurrences.append(occ)

                if not matching_bom_item_occurrences:
                    LOG.warn("No matching occurrence found. Guessing the bom item.")
                    result.append(bom_items[0])
                else:
                    if len(matching_bom_item_occurrences) > 1:
                        LOG.warn("Multiple occurrences with the same transformation found. Guessing the right one.")

                    bom_item = AssemblyComponent.ByKeys(cdb_object_id=matching_bom_item_occurrences[0].bompos_object_id)
                    if bom_item is not None:
                        result.append(bom_item)

            else:
                # there is either exactly one bom item
                # or more than one that cannot be determined via the occurrences
                # in both cases the first one found is used
                result.append(bom_items[0])

            top_doc = child_doc

        return result
