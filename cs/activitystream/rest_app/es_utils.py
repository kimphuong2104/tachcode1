# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import auth, sqlapi
from cdb.objects.org import User
from cdb.storage.index.queries import ESQueryHelper
from cdb.storage.index.standard_query import StandardQuery

from cs.activitystream import DEFAULT_POSTING_COUNT
from cs.activitystream.objects import Posting, UserPosting


class PersonESQueryHelper(ESQueryHelper):
    PAGE_SIZE = 7

    def get_results(self, cnt):
        import math

        page_no = int(math.ceil(cnt * 1.0 / self.PAGE_SIZE)) - 1

        self.get_page(page_no)

        hits = [oid for page in self._page_cache for oid in page][:cnt]
        cond = User.cdb_object_id.one_of(*[hit.get_object_id() for hit in hits])
        order_expr = "ORDER BY name ASC"
        records = sqlapi.RecordSet2(
            table=User.GetTableName(), condition=cond, addtl=order_expr
        )
        return User.FromRecords(records), self.curr_total


class PostingESQuery(StandardQuery):
    """Model for searching activities via ES. Rewrite sorting parameter."""

    def _add_parm_sorting(self, dest):
        """Adds strings to the list dest defining
        the sort parameters of the query.
        """
        dest.append("sort=cdb_date%20desc,object_id%20desc")

    def _add_parm_filters(self, dest):
        """Adds strings to the list dest defining
        the filter parameters of the query.
        """
        super(PostingESQuery, self)._add_parm_filters(dest)
        if self._date_filter:
            dest.append("fq=cdb_date:" + self._date_filter)

    def set_posting_since(self, since):
        self._date_filter = "[%s%sTO%s*]" % (
            since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "%20",
            "%20",
        )


class PostingESQueryHelper(ESQueryHelper):
    PAGE_SIZE = DEFAULT_POSTING_COUNT

    def get_postings(self, cnt, order_by_expr):
        import math

        to_page = int(math.ceil(cnt * 1.0 / self.PAGE_SIZE)) - 1
        # generate the page cache by querying target page
        self.get_page(to_page)
        # flatten the hits of all required pages
        hits = [oid for page in self._page_cache for oid in page][:cnt]
        cond = Posting.cdb_object_id.one_of(*[hit.get_object_id() for hit in hits])
        # All access check done, just do the query
        records = sqlapi.RecordSet2(
            table=Posting.GetTableName(),
            condition=cond,
            addtl=order_by_expr,
        )
        return Posting.FromRecords(records), self.curr_total


class PostingQueryFilter(object):
    def __init__(self, stmt, addtl):
        self._stmt = stmt
        self._addtl = addtl
        self._relation_name = UserPosting.GetTableName()

    def __call__(self, cdb_object_ids, maxelems):
        """
        Returns a list with object_ids for which the objects
          - fulfill the condition (WHERE clause) given to the ctor
          - and the currently logged-on user is granted read access.

        Overridden to fit the current usage and respect sorting.
        """
        result = []
        if cdb_object_ids:
            cond = "((cdb_object_id IN (%s)) AND (%s))" % (
                ",".join(["'%s'" % objid for objid in cdb_object_ids]),
                self._stmt,
            )
            result = self._check_postings(cond)
        return result

    def _check_postings(self, cond):
        candidates = sqlapi.RecordSet2(
            table=self._relation_name,
            condition=cond,
            addtl=self._addtl,
            access="read",
            access_persno=auth.persno,
        )
        # also check access of references
        return [
            r.cdb_object_id
            for r in (
                Posting._getAccessiblePostings(  # pylint: disable=protected-access
                    candidates
                )
            )
        ]


class PostingCollectionQueryFilter(PostingQueryFilter):
    def __call__(self, cdb_object_ids, maxelems):
        result = []
        if cdb_object_ids and self._stmt:
            # combine other search conditions
            sql = self._stmt.format(
                hits="cdb_object_id in (%s)"
                % (",".join(["'%s'" % objid for objid in cdb_object_ids]))
            )
            # should be maximum PAGE_SIZE
            oids = [r.cdb_object_id for r in sqlapi.RecordSet2(sql=sql)]
            result = self._check_postings(Posting.cdb_object_id.one_of(*oids))
        return result
