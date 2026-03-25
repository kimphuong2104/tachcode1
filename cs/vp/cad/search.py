# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb.objects import fields
from cdb import i18n

from cs.vp import utils
from cs.vp.cad import Model
from cs.vp.cad import queries

import logging

LOG = logging.getLogger(__name__)


class DocumentAttributeAccessor(object):
    def __init__(self, document_rec, ignore_errors=True):
        """"
        This attribute accessor can be used with an zeichnung_v or document_v record to access
        any kind of document attribute.

        The accessor can also be used with a zeichnung record with the following limitations:
        - Joined and virtual attributes are not accessible
        - Mapped attributes based on joined attributes don't work

        If the ignore_errors flag is true, inaccessible attributes will not lead to an error but the error with
        it's full tracback is logged. En empty string is retured as valiue is this case.
        """

        self.ignore_errors = ignore_errors
        self.document_rec = document_rec

    def _get_value(self, field_descriptor):
        if isinstance(field_descriptor, fields.MappedAttributeDescriptor):
            mapped_attr = field_descriptor.ma
            keyval = self.document_rec[mapped_attr.getReferer()]
            keyval = "" if keyval is None else "%s" % keyval
            v = mapped_attr.getValue(keyval)
        else:
            v = self.document_rec[field_descriptor.name]
        return v if v is not None else ""

    def __getitem__(self, name):
        v = ""
        try:
            field_descriptor = Model.GetFieldByName(name)
            if isinstance(field_descriptor, fields.MultiLangAttributeDescriptor):
                v = self._get_value(field_descriptor.getLanguageField())
                if not v:
                    for language in i18n.FallbackLanguages():
                        fd = field_descriptor.getLanguageField(language)
                        if fd:
                            v = self._get_value(fd)
                            if v:
                                break
            else:
                v = self._get_value(field_descriptor)
        except Exception:
            if self.ignore_errors:
                logging.exception("DocumentAttributeAccessor: Failed to access attribute %s" % name)
            else:
                raise
        return v


class CadDocumentStructureSearch(object):
    def __init__(self, root_document, condition=""):
        self.root_document = root_document
        self.condition = condition.lower()

    def get_results(self):
        result = []

        doc_node_tag = utils.get_description_tag('model_dtag')

        flat_documents = queries.flat_documents_dict(self.root_document)

        keys_searched = set()

        def search_in_structure(path, doc):
            k = (doc.z_nummer, doc.z_index)

            if k in keys_searched:
                # prevent recursion
                # TODO check for faulty data, this should not be necessary...
                return

            keys_searched.add(k)
            for child in flat_documents[k]:
                model = child
                if not isinstance(child, Model):
                    model = Model.FromRecords([child])[0]

                doc_path = path + [model]

                description = doc_node_tag % DocumentAttributeAccessor(child)
                if self.condition in description.lower():
                    result.append(doc_path)

                search_in_structure(doc_path, child)

        root_path = [self.root_document]
        if self.condition in self.root_document.GetDescription().lower():
            result.append(root_path)

        search_in_structure(root_path, self.root_document)

        return result
