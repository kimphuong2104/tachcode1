#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module posting_updater

This is the documentation for the posting_updater module.
"""

from __future__ import absolute_import

import logging

import six
from cdb import rte, sig
from cdb.platform import mom
from cdb.storage.index import errors, updaters
from cdb.storage.index.object_updater import ObjectUpdater

from cs.activitystream.objects import Comment, Posting

__all__ = ["PostingUpdater", "CommentUpdater"]
__docformat__ = "restructuredtext en"

log = logging.getLogger(__name__)


class PostingUpdater(ObjectUpdater):
    """Update Enterprise-Search index for postings.
    The updater append the indexable comment attributes.
    """

    def __init__(self, job_id, cdb_object_id, is_deleted):
        posting = Posting.ByKeys(cdb_object_id)
        if posting:
            is_deleted = is_deleted or posting.is_deleted
        else:
            is_deleted = True
        super(PostingUpdater, self).__init__(job_id, cdb_object_id, is_deleted)

    def _collect_attributes(self):
        # Retrieve the posting
        posting = Posting.ByKeys(self._cdb_object_id)
        if posting:
            # Call super's method to collect the posting's attributes if posting has to index:
            if posting.GetClassDef().is_indexed():
                super(PostingUpdater, self)._collect_attributes()
            # iterate the comments
            for comment in posting.AllComments:
                object_handle = mom.getObjectHandleFromObjectID(
                    comment.cdb_object_id, True
                )
                if not object_handle:
                    msg = "No object found for cdb_object_id %s" % comment.cdb_object_id
                    raise errors.ObjectNotFound(
                        msg, self._job_id, comment.cdb_object_id
                    )
                cdef = object_handle.getClassDef()
                if cdef.is_indexed():
                    for att in self._search_engine.get_attributes_to_index(
                        cdef.getClassname()
                    ):
                        fdname = att.field_name
                        self._add_field(
                            att.ranking_fac,
                            object_handle[fdname],
                            cdef.getAttributeDefinition(fdname).getContentType(),
                        )
            # Also update the date: use last_comment_date for sorting
            if posting.last_comment_date:
                self._index_job._date = (  # pylint: disable=protected-access
                    six.text_type(
                        posting.last_comment_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                    )
                )


class CommentUpdater(PostingUpdater):
    """Class to update comment data in the fulltext index."""

    def __init__(self, job_id, cdb_object_id, is_deleted):
        """
        Create a new index job to update a posting which includes the comment.
        """
        log.debug("CommentUpdater: Creating CommentUpdater for %s", cdb_object_id)
        self._comment_id = None
        comment = Comment.ByKeys(cdb_object_id)
        if not is_deleted:
            if comment:
                if comment.is_deleted:
                    # Index just this comment as delete (remove from index)
                    is_deleted = True
                else:
                    # We reset the cdb_object_id to the object *owning*
                    # the given comment object. TES will then write the
                    # correct relationship to the index:
                    cdb_object_id = comment.posting_id
            else:
                log.error(
                    "CommentUpdater: Can't find cdbblog_comment %s. "
                    "Considering object deleted",
                    cdb_object_id,
                )
                is_deleted = True
        else:
            if comment:
                cdb_object_id = comment.posting_id
                is_deleted = False  # Update posting
        super(CommentUpdater, self).__init__(job_id, cdb_object_id, is_deleted)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _add_updater_to_index():
    """
    The Index Updater Methods need to be added on startup.
    """
    iuf = updaters.IndexUpdaterFactory()
    iuf.add_updater("cdbblog_comment", CommentUpdater)
    iuf.add_updater("cdbblog_posting", PostingUpdater)
