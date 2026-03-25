# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import sqlapi
from cdb import cdbuuid
from cdb import i18n
from cdb.objects import operations, Rule, Predicate, Term
from cdb.platform.gui import Message

from cs.documents import Document

from cs.vp.items import Item
from cs.vp.cad import Model


def get_error_message(message_id, language=""):
    lang = language if language else i18n.default()
    message = Message.ByKeys(meldung_label=message_id)
    return message.Text[lang]


def generate_item(**kwargs):
    args = {
        "t_kategorie": "Baukasten"
    }
    args.update(**kwargs)

    return operations.operation(
        "CDB_Create",
        Item,
        **args
    )


def generate_cad_document(item, **kwargs):
    args = {
        "teilenummer": item.teilenummer,
        "t_index": item.t_index,
        "z_categ1": "144",  # Produkt/Teil
        "z_categ2": "177"  # CAD-Zeichnung
    }
    args.update(kwargs)

    return operations.operation(
        "CDB_Create",
        Model,
        **args
    )


def generate_document(item, **kwargs):
    args = {
        "teilenummer": item.teilenummer,
        "t_index": item.t_index,
        "z_categ1": "144",  # Produkt/Teil
        "z_categ2": "177"  # CAD-Zeichnung
    }
    args.update(kwargs)

    return operations.operation(
        "CDB_Create",
        Document,
        **args
    )


def generate_primary_file(doc, f_type, cdbf_name=None):
    return generate_file(doc, f_type, cdbf_name, cdbf_primary="1")


def generate_derived_file(doc, primary_file_id, f_type, cdbf_name=None):
    return generate_file(doc, f_type, cdbf_name, cdbf_derived_from=primary_file_id)


def generate_associated_file(doc, primary_file_id, f_type, cdbf_name=None):
    return generate_file(doc, f_type, cdbf_name, cdb_belongsto=primary_file_id)


def generate_file(doc, f_type, cdbf_name=None, **other_file_properties):
    obj_id = cdbuuid.create_uuid()
    preset = {
        "cdb_object_id": obj_id,
        "cdbf_object_id": doc.cdb_object_id,
        "cdb_classname" : "cdb_file",
        "cdbf_type": f_type,
        "cdb_wspitem_id": obj_id
    }
    preset.update(**other_file_properties)

    if cdbf_name is not None:
        preset["cdbf_name"] = cdbf_name

    query = "INTO cdb_file ({}) VALUES ('{}')".format(",".join(preset.keys()), "','".join(preset.values()))
    sqlapi.SQLinsert(query)
    return obj_id


def generate_rule(**kwargs):
    args = {
        "name": "Test rule"
    }
    args.update(kwargs)

    return operations.operation("CDB_Create", Rule, **args)


def generate_predicate(rule, fqpyname, **kwargs):
    args = {
        "predicate_name": "Test predicate",
        "name": rule.name,
        "fqpyname": fqpyname
    }
    args.update(**kwargs)

    return operations.operation("CDB_Create",
                                Predicate,
                                **args)


def generate_term(predicate, attribute, operator, expression):
    args = {
        "name": predicate.name,
        "fqpyname": predicate.fqpyname,
        "predicate_name": predicate.predicate_name,
        "attribute": attribute,
        "operator": operator,
        "expression": expression

    }

    return operations.operation("CDB_Create",
                                Term,
                                **args)
