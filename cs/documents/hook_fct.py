# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module contains operation hook functions of the cs.documents package
"""

# pylint: disable=bad-continuation

__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []


from cdb.platform.gui import Message
from cdb.platform.mom.entities import CDBClassDef
from cs.documents import Document, DocumentCategory


def check_category_name_uniqueness(hook_cfg, hook_ctx):
    cdef = CDBClassDef("cdb_doc_categ")
    visible_names = []
    for adef in cdef.getMultiLangAttributeDefs():
        if adef.getName() == "name":
            visible_names = [a.getName() for a in adef.getLanguageAttributeDefs(True)]
            break
    parent_id = hook_ctx.get_value("parent_id")
    for c in DocumentCategory.KeywordQuery(  # pylint: disable=too-many-nested-blocks
        parent_id=parent_id
    ):
        categ_id = hook_ctx.get_value("categ_id")
        if c.categ_id != categ_id:
            for lang, field in DocumentCategory.name.getLanguageFields().items():
                my_val = hook_ctx.get_value(field.name)
                if my_val and my_val == c[field.name]:
                    # Check if the user has a chance to change the item
                    if field.name in visible_names:
                        parent_name = ""
                        if c.ParentCategory:
                            parent_name = c.ParentCategory.name
                        hook_ctx.add_error(
                            Message.GetMessage(
                                "cdb_konfstd_020", lang, my_val, parent_name
                            )
                        )
                    else:
                        hook_ctx.set_value(field.name, "")


def handle_filechanges_cdbm2attributes(changes):
    """
    Powerscript-Hook that is configured to be part of the
    ``WSMUploadFiles`` hook. The implementation is used to
    look if a change leads to the modification of the
    ``cdb_m2...`` attributes of a document.
    """

    def _is_relevant(file_change):
        return (
            file_change.action
            in (
                "modify",
                "create",
            )
            and Document.IsRelevantForLastFileModification(file_change.obj)
        )

    def _do_update(doc, file_changes):
        m2date = doc.cdb_m2date
        persno = None
        for fc in file_changes:
            if _is_relevant(fc):
                fmdate = fc.obj.cdb_mdate
                if fmdate and (m2date is None or fmdate > m2date):
                    m2date = fmdate
                    persno = fc.obj.cdb_mpersno
        if persno:
            doc.Update(cdb_m2date=m2date, cdb_m2persno=persno)

    primary_file_changes = False
    # We do not use the relation parameter because this can
    # lead to an unnecessary SQL-Statement if there are no primary files
    all_uuids = changes.getParentObjectUUIDs()

    for uuid in all_uuids:
        for fc in changes.getChangedFiles(uuid):
            if _is_relevant(fc):
                primary_file_changes = True
                break
    if not primary_file_changes:
        return

    affected_documents = changes.getParentObjectsByClass(Document)
    for doc in affected_documents:
        _do_update(doc, changes.getChangedFiles(doc))
