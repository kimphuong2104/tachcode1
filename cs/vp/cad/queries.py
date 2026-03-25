# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import collections
import itertools
import uuid
import logging
import datetime as dt

from cdb import sqlapi, util, transaction
from cs.classification import solr
from cdbwrapc import CDBClassDef, build_statement

from cs.vp import utils
from cs.vp.items import Item


def flat_documents(root):
    """ Return a RecordSet of all the documents present in the document structure
        structure of the root. Computes the result efficiently making only one database query.

        The resulting records are pure teile_stamm entries, with two additional columns:
            parent_z_nummer and parent_z_index, whose purpose should be self explanatory 😁
    """

    doc_rel_keys = ["z_nummer", "z_index", "z_nummer2", "z_index2", "t_nummer2", "t_index2"]
    keys = ", ".join(["{table}" + name for name in doc_rel_keys])

    root_condition = "cdb_doc_rel.z_nummer='%s' AND cdb_doc_rel.z_index='%s'" % (
        root.z_nummer, root.z_index)
    child_condition = "doc_files.z_nummer2=cdb_doc_rel.z_nummer AND doc_files.z_index2=cdb_doc_rel.z_index"

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        length = "LEN"
    else:
        length = "LENGTH"

    QUERYSTR = """
                WITH {recursive} doc_files ({keys})
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
                SELECT DISTINCT doc_files.z_nummer as parent_z_nummer, doc_files.z_index as parent_z_index, {length}(doc_files.z_index) as length, zeichnung_v.*
                FROM doc_files
                INNER JOIN zeichnung_v
                    ON doc_files.z_nummer2=zeichnung_v.z_nummer 
                        AND doc_files.z_index2=zeichnung_v.z_index
                ORDER BY doc_files.z_nummer, doc_files.z_index, length
            """

    query = QUERYSTR.format(
        recursive=utils.sql_recursive(),
        keys=keys.format(table=""),
        doc_rel_keys=keys.format(table="cdb_doc_rel."),
        root_condition=root_condition,
        child_condition=child_condition,
        length=length
    )

    return sqlapi.RecordSet2(sql=query)


def flat_documents_dict(root):
    result = collections.defaultdict(list)

    for r in flat_documents(root):
        result[(r.parent_z_nummer, r.parent_z_index)].append(r)

    return result


class TemporaryModelResultTable:

    def __init__(self, relation):
        self._relation = relation
        self._table_name = 'cdb_cad_model_query_tmp'
        self._insert_template = "INSERT INTO %s SELECT %s"
        self._conditions_template = "'{0}', cdb_object_id, '{1}', {2} FROM {0} WHERE cdb_object_id IN({3})"

    @staticmethod
    def get_expiration_period():
        """
        :return: The expiration period for the temporary search results table, in minutes
        """

        cvex = util.get_prop("cvex")
        if cvex:
            return abs(int(cvex))
        return 1    # 2 * 60

    def insert_tmp_query_result(self, object_ids, query_id):
        """ Inserts a list of cdb_object_ids and a unique
            query id into the table
        """

        try:
            expiration_period = TemporaryModelResultTable.get_expiration_period()
            expiration_date = dt.datetime.now() + dt.timedelta(minutes=expiration_period)

            where_condition = ["'%s'" % sqlapi.quote(objid) for objid in object_ids]
            conditions = self._conditions_template.format(sqlapi.quote(self._relation),
                                                          sqlapi.quote(str(query_id)),
                                                          sqlapi.SQLdbms_date(expiration_date),
                                                          ",".join(where_condition))
            stmt = self._insert_template % (sqlapi.quote(self._table_name), conditions)
            sqlapi.SQL(stmt)
        except RuntimeError:
            logging.getLogger(__name__).exception(
                "cs.vp.cad.queries.TemporaryModelResultTable.insert_tmp_query_result(%s, %s)",
                object_ids, query_id)

    def get_conditions(self, query_id, relation_alias, tt_alias=None):
        """Returns the necessary WHERE and FROM conditions for this table so
        the kernel can use the results of the full text search to filter the
        results of the database search.
        """
        if not tt_alias:
            tt_alias = 'tt'
        conditions = ("{tt_alias}.uuid='{query_id}' and {tt_alias}.relation='{relation}' and {tt_alias}.result_object_id={relation_alias}.cdb_object_id".format(
                      tt_alias=sqlapi.quote(tt_alias), query_id=sqlapi.quote(str(query_id)),
                      relation=sqlapi.quote(self._relation), relation_alias=sqlapi.quote(relation_alias)))
        source = "{} {}".format(sqlapi.quote(self._table_name), sqlapi.quote(tt_alias))
        return conditions, source

    def fill_tmp_query_table(self, results, relation_alias, tt_alias=None):
        """
        :param results:
        :param relation_alias:
        :param tt_alias:

        :return:
        """

        self.cleanup_temp_table()

        queryid = uuid.uuid4()

        # insert_limit defines how many rows are inserted into the
        # temporary table per iteration. The limiting factor is the
        # statement length in chars, 32768. Assuming a INSERT prologue of
        # maximal 200 characters, and a repeating 56 char unit for the
        # cdb_object_id, which we assume to have a fixed length of 36 chars, we
        # get a maximal repeatable unit factor of ~ 580. We will use 500.
        insert_limit = 500
        # Integer division to determine the number of iterations
        iterations = len(results) // insert_limit + 1
        with transaction.Transaction():
            start_index = 0
            for i in range(iterations):
                end_index = min(len(results), (i + 1) * insert_limit)
                if start_index < end_index:
                    self.insert_tmp_query_result(results[start_index: end_index], queryid)
                start_index = end_index

        return self.get_conditions(queryid, relation_alias, tt_alias)

    def cleanup_temp_table(self):
        stmt = "FROM {} WHERE expiry_date < {}".format(
            sqlapi.quote(self._table_name), sqlapi.SQLdbms_date(dt.datetime.now()))
        sqlapi.SQLdelete(stmt)


def _solr_query(query):
    """
    Executes a classification query against SOLR.

    :param query: The classification query structure.
    :return: A list of cdb_object_ids of objects which match the query.
    """

    if query:
        addtl_properties = query.get("addtl_properties", [])
        assigned_classes = query.get("assigned_classes", [])
        values = query.get("values", {})

        if not assigned_classes and not values:
            # if there are no classification search conditions skip classification search
            return None

        chunk_size = 10000
        limit = None

        mxcl = util.get_prop("mxcl")
        if mxcl and "-1" != mxcl:
            limit = abs(int(mxcl))

        results = list(itertools.islice(
            solr.search_solr(
                values,
                assigned_classes,
                addtl_properties,
                chunk_size
            ),
            0,
            limit
        ))

        return results

    return None


def classified_parts_query(classname, relation_alias, query):
    """
    Adopted from cs.classification.kernel_query.py
    Adds the objects which match the classification query condition to a temporary table.

    :param classname: The CDB class name of the objects to search for.

    :param relation_alias: The SQL alias for the table name to use in the generated query

    :param query: A dict containing the classification query data.
                  Requires at least an "assigned_classes", an "addtl_properties" and a "values" entry.

    :return: A tuple with two elements:
             The first one is a condition which can be used in a query against the temporary table
             (similar to
             "tt_classified.uuid='...' and tt_classified.relation='part_v' and
             tt_classified.cdb_object_id=ts.cdb_object_id'),
             the second one is a table alias which can be used in the FROM part of the query to join
             the temporary table (like "ftrquery tt_classified")
    """

    solr_result = _solr_query(query)
    if solr_result is not None:
        cldef = CDBClassDef(classname)
        relation = cldef.getRelation()
        query_result_table = TemporaryModelResultTable(relation)
        result = query_result_table.fill_tmp_query_table(solr_result, relation_alias, 'tt_classified')\
            if solr_result else None

        return result

    return None


def model_query_including_variant_parts(classname, relation_alias, query, whereStmt):
    """
    Adopted from cs.classification.kernel_query.py
    Adds the model objects which have CAD variants which have parts which match the classification query
    condition to a temporary table.

    :param classname: The CDB class name of the objects to search for.

    :param relation_alias: The SQL alias for the table name to use in the generated query

    :param query: A dict containing the classification query data.
                  Requires at least an "assigned_classes", an "addtl_properties" and a "values" entry.

    :param whereStmt: The WHERE statement for the part related attributes

    :return: A tuple with two elements:
             The first one is a condition which can be used in a query against the temporary table
             (similar to
             "tt_classified.uuid='...' and tt_classified.relation='part_v' and
             tt_classified.cdb_object_id=ts.cdb_object_id'),
             the second one is a table alias which can be used in the FROM part of the query to join
             the temporary table (like "ftrquery tt_classified")

             Returns None if no classification query shall be performed at all.
             Returns ("1=0", "") to indicate that the classification query did not find any matches.
             Note that in this case, the ftrquery table might not have been created at all, especially for
             the first query!
    """

    solr_result = _solr_query(query)
    if solr_result is not None:
        # Note: If required, one_of() creates multiple "IN" queries concatenated with "OR" to overcome
        #       the limit for a single "IN" query.
        #       However, depending on the database system, the  query might still run into a limit when a
        #       large list of cdb_object_ids is returned by the solr query. On Oracle, this is more than
        #       65535 elements.
        #       Nevertheless, this should be theoretical only:
        #       * If such a large number of results is returned by SOLR, the classification query is just not
        #         specific enough
        #       * In any case, the number of results returned by the solr query can be limited through the
        #         "mxcl" system property

        # Note: one_of returns "(1=0)" if the list is empty.
        solrCond = str(Item.cdb_object_id.one_of(*solr_result))
        solrCond = solrCond.replace("(cdb_object_id", "(ts.cdb_object_id")
        if whereStmt:
            whereStmt = whereStmt + " AND " + solrCond
        else:
            whereStmt = solrCond

    if not whereStmt:
        whereStmt = "(1=1)"

    # LEFT OUTER JOIN also includes models which do not have a part assigned
    stmt = """
    SELECT model.cdb_object_id
    FROM zeichnung model
    LEFT OUTER JOIN teile_stamm ts ON (ts.teilenummer=model.teilenummer AND ts.t_index=model.t_index)
    WHERE {ws}

UNION ALL

    SELECT model.cdb_object_id
    FROM zeichnung model
    JOIN cad_variant cv ON (cv.z_nummer=model.z_nummer AND cv.z_index=model.z_index)
    LEFT OUTER JOIN teile_stamm ts ON (ts.teilenummer=cv.teilenummer AND ts.t_index=cv.t_index)
    WHERE {ws}""".format(ws=whereStmt)

    # Fill the temporary table with model cdb_object_ids
    results = sqlapi.RecordSet2(sql=stmt)
    results = [x.cdb_object_id for x in results]
    cldef = CDBClassDef(classname)
    relation = cldef.getRelation()

    query_result_table = TemporaryModelResultTable(relation)
    result = query_result_table.fill_tmp_query_table(results, relation_alias, 'tt_classified')\
        if results else ("1=0", "")

    return result


def model_query_with_classified_parts(classname, relation_alias, query):
    """
    Adopted from cs.classification.kernel_query.py
    Adds the model objects which have primary parts assigned which match the classification query
    condition to a temporary table.

    :param classname: The CDB class name of the objects to search for.

    :param relation_alias: The SQL alias for the table name to use in the generated query

    :param query: A dict containing the classification query data.
                  Requires at least an "assigned_classes", an "addtl_properties" and a "values" entry.

    :return: A tuple with two elements:
             The first one is a condition which can be used in a query against the temporary table
             (similar to
             "tt_classified.uuid='...' and tt_classified.relation='part_v' and
             tt_classified.cdb_object_id=ts.cdb_object_id'),
             the second one is a table alias which can be used in the FROM part of the query to join
             the temporary table (like "ftrquery tt_classified")

             Returns None if no classification query shall be performed at all.
             Returns ("1=0", "") to indicate that the classification query did not find any matches.
             Note that in this case, the ftrquery table might not have been created at all, especially for
             the first query!
    """

    # The size of the list which is returned can be limited through the "mxcl" property
    solr_result = _solr_query(query)
    if solr_result is not None:
        # Note: If required, one_of() creates multiple "IN" queries concatenated with "OR" to overcome
        #       the limit for a single "IN" query.
        #       However, depending on the database system, the  query might still run into a limit when a
        #       large list of cdb_object_ids is returned by the solr query. On Oracle, this is more than
        #       65535 elements.
        #       Nevertheless, this should be theoretical only:
        #       * If such a large number of results is returned by SOLR, the classification query is just not
        #         specific enough
        #       * In any case, the number of results returned by the solr query can be limited through the
        #         "mxcl" system property
        stmt = """
        SELECT model.cdb_object_id
        FROM zeichnung model
        JOIN teile_stamm ts ON (ts.teilenummer=model.teilenummer AND ts.t_index=model.t_index)
        WHERE {}""".format(Item.cdb_object_id.one_of(*solr_result))
        stmt = stmt.replace("(cdb_object_id", "(ts.cdb_object_id")

        # Fill the temporary table with model cdb_object_ids
        results = sqlapi.RecordSet2(sql=stmt)
        results = [x.cdb_object_id for x in results]
        cldef = CDBClassDef(classname)
        relation = cldef.getRelation()

        query_result_table = TemporaryModelResultTable(relation)
        result = query_result_table.fill_tmp_query_table(results, relation_alias, 'tt_classified')\
            if results else ("1=0", "")

        return result

    return "", ""


def create_part_condition(attr):
    """
    Creates name/value pairs for the part search attributes (which can be used in ctx.ignore_in_query)
    and the final condition for the part query which can be used in a WHERE statement.

    :param attr: A dictionary of search criterias as entered by the user
    :return: A tuple with (partQuery, whereStmt) where the partQuery is a dictionary with all
    """

    # Get all attributes which are joined to "model" through the "Part" join
    modelCls = CDBClassDef("model")
    joinedPartAttrs = {"t_index", "teilenummer"}
    joinedPartAttrs.update({a.getName()
                            for a in modelCls.getJoinedAttributeDefs(join_name="Part")})

    # Get all search criteria related to parts
    partQuery = {key: attr[key] for key in attr.keys() if key in joinedPartAttrs}

    # create the WHERE condition for part related search criterias which are not empty

    # TODO: What is the meaning of the first parameter??
    whereStmt = ""
    partCond = [build_statement("ts", "ts." + name, cond) for name, cond in partQuery.items() if
                cond]
    if partCond:
        whereStmt = " AND ".join(partCond)

    return partQuery.keys(), whereStmt
