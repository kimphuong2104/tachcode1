#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 20222 CONTACT Software GmbH
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime

from cdb.objects.operations import operation
from cs.documents import Document, DocumentCategory

from cs.pcs.projects import tasks


def generate_doc(**args):
    main_document_category = DocumentCategory.KeywordQuery(name_d="Allgemeines")[0]
    child_document_category = DocumentCategory.KeywordQuery(
        name_d="Besprechungsprotokoll"
    )[0]
    kwargs = {
        "titel": "fooDoc",
        "z_nummer": "foo",
        "z_categ1": main_document_category.categ_id,
        "z_categ2": child_document_category.categ_id,
    }
    kwargs.update(**args)
    return operation("CDB_Create", Document, **kwargs)


def generate_document_template(d, referer, **user_input):
    kwargs = {"z_nummer": d.z_nummer, "tmpl_index": ""}
    kwargs.update(**user_input)
    return operation("CDB_Create", referer, **kwargs)


def copy_project(p):
    kwargs = {
        "cdb_project_id": "bar",
    }
    return operation("CDB_Copy", p, **kwargs)


def _generate_document(index, **args):
    # constants copied from test/accepttests/steps/common.py
    doc_approve_maincategs = ("316", "144")
    doc_approve_categ = "170"

    doc_maincateg = []

    for doc_approve_maincateg in doc_approve_maincategs:
        doc_maincateg = DocumentCategory.ByKeys(doc_approve_maincateg)
        if doc_maincateg:
            break

    doc_categ = DocumentCategory.ByKeys(doc_approve_categ)

    kwargs = {
        "z_categ1": doc_maincateg.categ_id,
        "z_categ2": doc_categ.categ_id,
        "cdb_classname": "document",
        "z_art": "doc_approve",
    }
    kwargs.update(Document.MakeChangeControlAttributes())
    kwargs.update(**args)
    # ensure documents are created at different time points
    kwargs.update(
        {"cdb_cdate": datetime.datetime.now() + datetime.timedelta(minutes=index)}
    )
    return Document.Create(**kwargs)


def generate_document(index, name, status=0):
    return _generate_document(
        1,
        **{
            "z_status": status,
            "z_nummer": name + "_nummer",
            "z_index": name + "_Index",
        },
    )


def checkErrorMsg(e, doc_name):
    return (
        "Es wurde kein gültiges Dokument für Vorlagenquellen gefunden "
        + f"mit Dokumentnummer und Index: \n\n- {doc_name}_nummer/{doc_name}_Index"
        in str(e)
    )


def generate_project_task(project, **user_input):
    kwargs = {
        "cdb_project_id": project.cdb_project_id,
        "ce_baseline_id": project.ce_baseline_id,
        "task_id": "task_id",
        "task_name": "Task#1",
        "parent_task": "",
        "subject_id": "Projektmitglied",
        "subject_type": "PCS Role",
        "constraint_type": "0",
        "automatic": 0,
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", tasks.Task, **kwargs)
