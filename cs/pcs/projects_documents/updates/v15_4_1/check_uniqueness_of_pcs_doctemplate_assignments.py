#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import argparse
import logging

from cdb import constants, sqlapi, transaction, util
from cdb.platform.mom.constraints import DDConstraint
from cdb.platform.mom.entities import Entity
from cdb.platform.mom.fields import DDField
from cs.documents import Document

from cs.pcs.projects_documents import AbstractTemplateDocRef

classes = AbstractTemplateDocRef.__subclasses__()
field_len = 20
constraint_removed = "z_index"


def get_tablename(cls):
    return cls.__table_name__


def get_classname(cls):
    return cls._getClassname()  # pylint: disable=protected-access


def get_sql_attr(qry_res):
    try:
        return sqlapi.SQLstring(qry_res, 0, 0)
    except IndexError:
        return ""


def get_class_desc(cls, lang="uk"):
    stmt = "{0}_ueberschrift from {1} where classname='{2}'"
    qry_res = sqlapi.SQLselect(
        stmt.format(lang, get_tablename(Entity), get_classname(cls))
    )
    return get_sql_attr(qry_res)


def get_field_desc(cls, field_name):
    stmt = "label_en from {0} where classname='{1}' and field_name='{2}'"
    qry_res = sqlapi.SQLselect(
        stmt.format(get_tablename(DDField), get_classname(cls), field_name)
    )
    return get_sql_attr(qry_res)


def get_constraint_fields(cls):
    stmt = "{0} from {1} where classname='{2}'"
    qry_res = sqlapi.SQLselect(
        stmt.format("fields_info", get_tablename(DDConstraint), get_classname(cls))
    )
    constraints = [s.strip() for s in get_sql_attr(qry_res).split(",")]
    try:
        constraints.remove(constraint_removed)
    except Exception:
        logging.exception(
            "constraints.remove('%s') failed for constraints '%s'",
            constraint_removed,
            constraints,
        )
    return constraints


def pad_txt(txt):
    txt = str(txt)
    if len(txt) > field_len:
        return txt[:field_len]
    else:
        return txt + (" " * (field_len - len(txt)))


def get_line(lst):
    result = ""
    for el in lst:
        result += pad_txt(el)
    result += "\n"
    return result


def gen_pretty_txt(entries, table_cols):
    result = ""
    for e in entries:
        result += get_line([e[f] for f in table_cols])
    return result


def _get_duplicates(cls):
    con_flds = get_constraint_fields(cls)
    stmt = "SELECT COUNT(*) AS count, {0} FROM {1} GROUP BY {0} HAVING COUNT(*) > 1"
    return (
        con_flds,
        sqlapi.RecordSet2(sql=stmt.format(", ".join(con_flds), cls.GetTableName())),
    )


def get_cls_info(cls):
    con_flds, rs = _get_duplicates(cls)
    result = get_line(["Number"] + [get_field_desc(cls, f) for f in con_flds])
    if rs:
        result += gen_pretty_txt(rs, ["count"] + con_flds)
    else:
        result += "No matching records found\n"
    return result


def _count():
    txt2print = "The following records do not match the future uniqueness rules:\n"
    for cls in classes:
        txt2print += "\n"
        txt2print += f"Templates of {get_class_desc(cls.__referer_cls__)}\n"
        txt2print += get_cls_info(cls)
    print(txt2print)


def _get_idx_to_remove(z_nummer, indizes, sortCriteria):
    """
    Returns all indexes to be remove
    (A) If a non-obsolete document does not exist, all assignments are removed except the assignment to the
        most recent obsolete index.
    (B) If exactly one non-obsolete document exists, the assignments to all obsolete documents are removed.
    (C) If more than one non-obsolete document exists, all assignments are removed except the assignment to
        the most recent non-obsolete index.
    """
    # All index of a document number in configured order
    docs = Document.KeywordQuery(
        z_nummer=z_nummer, z_index=indizes, order_by=sortCriteria
    )
    # All *obsolete* index of a document number in configured order
    obsolete_docs = [doc.z_index for doc in docs if doc.cdb_obsolete == 1]
    # All *non-obsolete* index of a document number in configured order
    non_obsolete_docs = [doc.z_index for doc in docs if not doc.cdb_obsolete]

    result = set()
    # (A)
    if len(non_obsolete_docs) == 0:
        # Remove the most recent obsolete index
        obsolete_docs.pop()
        # Add the remaining index to the list of index to be removed
        result = set(obsolete_docs)
    # (B)
    elif len(non_obsolete_docs) == 1:
        result = set(obsolete_docs)
    # (C)
    elif len(non_obsolete_docs) > 1:
        # Remove the most recent non-obsolete index
        non_obsolete_docs.pop()
        # Add the remaining index to the list of index to be removed
        result = set(obsolete_docs)
        result = result.union(set(non_obsolete_docs))
    return result


def remove_duplicates(do_remove=False):
    """
    For duplicate assignments this function removes the assignments that
    are marked as obsolete. If all templates are marked as obsolete the newest
    index will be kept.
    """
    sortCriteria = (
        util.PersonalSettings().getValueOrDefault(
            constants.kVersioningIndexOrderDoc,
            "",
            "z_index",  # default if setting is not defined
        )
        or "z_index"
    )  # if setting is empty string

    for cls in classes:
        print(f"\nRemove Template assignments of {get_class_desc(cls.__referer_cls__)}")
        txt = ""
        con_flds, rs = _get_duplicates(cls)
        if rs:
            with transaction.Transaction():
                for r in rs:
                    conditions = {fld: r[fld] for fld in con_flds}
                    candidates = cls.KeywordQuery(**conditions)
                    remove = _get_idx_to_remove(
                        r["z_nummer"], candidates.z_index, sortCriteria
                    )
                    removed = []
                    for candidate in candidates:
                        if candidate.z_index in remove:
                            if do_remove:
                                candidate.Delete()
                            removed.append(candidate.z_index)
                        else:
                            # Might be a duplicate if the key was not there
                            remove.add(candidate.z_index)
                    if removed:
                        ridx = ", ".join([idx if idx else "''" for idx in removed])
                        txt += get_line([ridx] + [r[fld] for fld in con_flds])

                if txt:
                    txt = (
                        get_line(
                            ["Removed Indizes"]
                            + [get_field_desc(cls, f) for f in con_flds]
                        )
                        + txt
                    )
                    print(txt)
        else:
            print("No duplicates found")


if __name__ == "__main__":
    desc = (
        "cs.pcs 15.4.1 does not allow the assignment of "
        "multiple versions of a document as a template to a project, task, "
        "checklist or checklist item. "
        "This script helps to make existing data compatible with the new database schema."
    )

    parser = argparse.ArgumentParser(description=desc)

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--count",
        action="store_true",
        help="Number of assignments of a document as a template are displayed, "
        "if the assignments are not compatible with the new database schema",
        default=False,
    )

    group.add_argument(
        "--show",
        action="store_true",
        help="Assignments of a document as a template that are removed from the database "
        "are only displayed, not really removed. "
        "The assignment of the most recent non-obsolete index remains unchanged. "
        "If a non-obsolete index does not exist, the assignment of the most recent "
        "obsolete index remains unchanged.",
        default=False,
    )

    group.add_argument(
        "--remove",
        action="store_true",
        help="Assignments of a document as a template are really removed from the database. "
        "The assignment of the most recent non-obsolete index remains unchanged. "
        "If a non-obsolete index does not exist, the assignment of the most recent "
        "obsolete index remains unchanged.",
        default=False,
    )

    try:
        args = parser.parse_args()
        if args.count:
            _count()
        elif args.show:
            remove_duplicates(do_remove=False)
            print(
                "\n***** It's just a preview. Use --remove to write the changes to the database. *****\n"
            )
        elif args.remove:
            remove_duplicates(do_remove=True)
            print(
                "\nChanges have been written to the database. Use --count to check the success of "
                "the action.\n"
            )
        else:
            parser.print_help()
    except argparse.ArgumentTypeError as e:
        print(f"ERROR: {e}")
