# coding: utf-8

import pprint

from cdb import sqlapi, transactions, util
from cdb.comparch import protocol

from .oid_map import CDB_OBJECT_ID_MAP


def formatDict(someDict):
    return pprint.pformat(dict(someDict), indent=4)


def getDataStmt(record):
    """convert record dict to SQL where statement, leaving out cdb_object_id"""
    return " AND ".join(
        [
            "{}={}".format(
                col, sqlapi.make_literal(util.TableInfo(record.thead.tname), col, val)
            )
            for col, val in dict(record).items()
            if col != "cdb_object_id"
        ]
    )


def getPKStmt(record):
    """convert record keydict to SQL where statement"""
    return " AND ".join(
        [
            "{}={}".format(
                col, sqlapi.make_literal(util.TableInfo(record.thead.tname), col, val)
            )
            for col, val in record.keydict().items()
        ]
    )


class RecordNotInsertedException(Exception):
    def __init__(self, record):
        super(RecordNotInsertedException, self).__init__()
        self.record = record

    def __str__(self):
        return "Record not inserted: {}".format(self.record)


class Migrater(object):
    __oid_attrs__ = ["cdb_object_id", "tclass_object_id", "column_object_id"]
    __defaults__ = {}  # static defaults
    __keep__ = []  # if new entry already exists, keep these attributes
    __transformations__ = {}  # dynamic transformations

    def _transform(self, record):
        new_values = dict(record)
        new_values.update(self.__defaults__)  # apply defaults

        # apply dynamic transformations
        for key, funcname in self.__transformations__.items():
            new_values[key] = getattr(self, funcname)(record)

        # keep important values from existing entry
        existing = self._get_existing_by_oid(record)
        if existing:
            new_values.update({k: existing[k] for k in self.__keep__})

        return sqlapi.Record(self.__table_new__, **new_values)

    def _get_existing_by_oid(self, old_record):
        for existing in sqlapi.RecordSet2(
            self.__table_new__, "cdb_object_id='{}'".format(old_record["cdb_object_id"])
        ):
            return existing

    def _translate_oids(self, record):
        result = dict(record)

        if "cdb_object_id" in list(record):
            sqlapi.SQLupdate(
                "cdb_object SET id='tmp-{0}' WHERE id='{0}'".format(
                    record["cdb_object_id"]
                )
            )

        for oid_attr in self.__oid_attrs__:
            if oid_attr in list(result):
                # use new objectid for known objects
                result[oid_attr] = CDB_OBJECT_ID_MAP.get(
                    result[oid_attr], result[oid_attr]
                )

        return result

    def _copy(self, record):
        new_record = self._transform(self._translate_oids(record))

        dupe = sqlapi.RecordSet2(self.__table_new__, getDataStmt(new_record))

        if dupe:
            # skipping record because of functional duplicate
            return dupe[0]

        existing = sqlapi.RecordSet2(self.__table_new__, getPKStmt(new_record))

        if not existing:
            if new_record.insert() == 1:
                return new_record
            else:
                raise RecordNotInsertedException(new_record)
        else:
            new_values = dict(new_record)
            if "cdb_object_id" in list(new_values):
                del new_values["cdb_object_id"]
            existing[0].update(**new_values)
            return existing[0]

    def _validate(self, old_record, new_record):
        pass  # may raise Exception, log warning...

    def _old_records(self):
        return sqlapi.RecordSet2(self.__table_old__)

    def _report(self):
        details = "\n\n".join(
            "FROM\t{}:\n{}\nTO\t{}:\n{}".format(
                self.__table_old__, formatDict(old), self.__table_new__, formatDict(new)
            )
            for old, new in self.migrated
        )
        protocol.logMessage(
            "{}: migrated {} entries".format(
                self.__class__.__name__, len(self.migrated)
            ),
            details_longtext=details,
        )

    def migrate(self):
        self.migrated = []
        with transactions.Transaction():
            for old_record in self._old_records():
                new_record = self._copy(old_record)
                self._validate(old_record, new_record)
                self.migrated.append((old_record, new_record))
        self._report()
