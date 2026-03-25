#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
# pylint: disable=C0302

"""
This module contains Activity Stream classes.
"""

from __future__ import absolute_import

import logging

import six
from cdb import auth, constants, sig, sqlapi, transaction, ue, util
from cdb.objects import (
    ByID,
    Forward,
    LocalizedField,
    Object,
    Reference_1,
    Reference_N,
    ReferenceMethods_1,
    core,
    operations,
)
from cdb.objects.operations import operation
from cdb.objects.org import User
from cs.audittrail import (
    AuditTrailApi,
    AuditTrailDetail,
    AuditTrailDetailLongText,
    WithAuditTrail,
)

from cs.activitystream import hooks

__all__ = [
    "Posting",
    "SystemPosting",
    "UserPosting",
    "Comment",
    "Topic2Posting",
    "Subscription",
    "Channel",
    "Reaction",
]
__docformat__ = "restructuredtext en"

from webob.exc import HTTPUnprocessableEntity

log = logging.getLogger(__name__)
fPosting = Forward(__name__ + ".Posting")
fComment = Forward(__name__ + ".Comment")
fTopic2Posting = Forward(__name__ + ".Topic2Posting")
fReaction = Forward(__name__ + ".Reaction")

CACHED_STATEMENTS = {}


def paginated(records, pagesize, startpage=0):
    pos = pagesize * startpage
    while True:
        page = records[pos : pos + pagesize]
        if not page:
            break
        yield page
        pos += pagesize
        page = None


class WithLongtextAuditTrail(WithAuditTrail):
    """
    Workaround for Non-PlainText-Longtexts which are ignored by AuditTrail

    Adapted from cs.requirements.base_classes.WithRQMBase
    """

    __audit_trail_longtext__ = ""

    def add_audittrail_richtext(self, ctx, audittrail, attribute_name):
        old_text = getattr(ctx.previous_values, attribute_name, "")
        new_text = self.GetText(attribute_name)
        if old_text != new_text:
            if not audittrail:
                audittrail = self.createAuditTrail("modify")

            self.createAuditTrailLongText(
                audittrail_object_id=audittrail.audittrail_object_id,
                clsname=self.GetClassname(),
                longtext=attribute_name,
                old_text=old_text,
                new_text=new_text,
            )

    def createAuditTrailEntry(self, ctx=None):
        """
        Adds cdbblog_posting_txt to audit trail, as audit trail ignores it
        """
        audittrail = super(WithLongtextAuditTrail, self).createAuditTrailEntry(ctx)
        self.add_audittrail_richtext(ctx, audittrail, self.__audit_trail_longtext__)

    def modifyAuditTrailEntry(self, ctx):
        """
        Adds cdbblog_posting_txt to audit trail, as audit trail ignores it
        """
        audittrail = super(WithLongtextAuditTrail, self).modifyAuditTrailEntry(ctx)
        self.add_audittrail_richtext(ctx, audittrail, self.__audit_trail_longtext__)


class ActivityEntry(Object, WithLongtextAuditTrail):
    def GetDescription(self, iso_lang=""):
        if self.is_deleted:
            return util.Labels()["cdbblog_deleted_entry"]
        return super(ActivityEntry, self).GetDescription(iso_lang)

    def deleteEntry(self):
        if isinstance(self, SystemPosting):
            raise HTTPUnprocessableEntity()
        if self.is_deleted:
            return

        kwargs = {
            "author": u"",
            "is_deleted": 1,
            self.__audit_trail_longtext__: u"",
        }
        operations.operation(
            constants.kOperationModify,
            self,
            operations.form_input(self, **kwargs),
        )

    def getRestoreAttributes(self, text_attribute=None):
        """
        Gets the data required to restore the activity entry.

        :param text_attribute: Name to rename the long text attribute to
        :return: A dict of attributes
        """
        if not self.is_deleted:
            return dict()

        if text_attribute is None:
            text_attribute = self.__audit_trail_longtext__

        def find_latest_audit_trail_details():
            audit_trail_entries = AuditTrailApi.getLatestAuditTrailEntries(
                None, self, True
            ).audittrail_object_id
            for entry in audit_trail_entries:
                audit_details = sqlapi.RecordSet2(
                    AuditTrailDetail.__classname__,
                    "audittrail_object_id='{}'".format(sqlapi.quote(entry)),
                )
                for detail in audit_details:
                    if (
                        detail.attribute_name == "is_deleted"
                        and int(detail.new_value) == 1
                    ):
                        return audit_details
            return None

        def restore_details(details):
            ret = dict()
            for detail in details:
                if detail.cdb_classname == AuditTrailDetailLongText.__classname__:
                    longtext_detail = AuditTrailDetailLongText.FromRecords([detail])[0]
                    ret[text_attribute] = longtext_detail.GetText(
                        "cdb_audittrail_longtext_old"
                    )
                elif detail.attribute_name not in core.CHCTRL:
                    ret[detail.attribute_name] = detail.old_value
            return ret

        details = find_latest_audit_trail_details()
        kwargs = restore_details(details)
        return kwargs

    def restoreEntry(self):
        kwargs = self.getRestoreAttributes()
        if not kwargs:
            return

        operations.operation(
            constants.kOperationModify,
            self,
            operations.form_input(self, **kwargs),
        )

    def modifyEntry(self, **kwargs):
        operations.operation(
            constants.kOperationModify,
            self,
            operations.form_input(self, **kwargs),
        )

    def get_reaction_ids(self):
        reactions = sqlapi.RecordSet2(
            Reaction.GetTableName(),
            "reaction_to='%s'" % sqlapi.quote(self.cdb_object_id),
            ["user_id"],
        )
        return [reaction.user_id for reaction in reactions]

    def get_reactions(self):
        return User.KeywordQuery(
            personalnummer=[reaction.user_id for reaction in self.Reactions],
            order_by="firstname",
        )


class Posting(ActivityEntry):
    """The base posting class."""

    __maps_to__ = "cdbblog_posting"
    __classname__ = "cdbblog_posting"
    __audit_trail_longtext__ = "cdbblog_posting_txt"

    def getContextObject(self):
        """
        Returns the context object of the posting as a
        `cdb.objects.Object`. The function will return
        ``None`` if there is no context object or if
        there is no `cdb.objects.Class` for the context
        object.
        """
        try:
            return ByID(self.context_object_id)
        except TypeError as exc:
            log.error("Failed to retrieve postings context object: %s", exc)

    def getAuthor(self):
        if self.is_deleted:
            return None
        return User.ByKeys(self.cdb_cpersno)

    ContextObject = ReferenceMethods_1(Object, getContextObject)

    Author = ReferenceMethods_1(User, getAuthor)

    Comments = Reference_N(
        fComment,
        fComment.in_reply_to == fPosting.cdb_object_id,
        order_by=fComment.cdb_cdate,
        access="read",
    )

    AllComments = Reference_N(
        fComment,
        fComment.posting_id == fPosting.cdb_object_id,
        order_by=fComment.cdb_cdate,
        access="read",
    )

    TopicAssignments = Reference_N(
        fTopic2Posting, fTopic2Posting.posting_id == fPosting.cdb_object_id
    )

    Reactions = Reference_N(
        fReaction,
        fReaction.reaction_to == fPosting.cdb_object_id,
    )

    def addTopic(self, topic_or_id):
        """Adds topic assignment."""
        if not isinstance(topic_or_id, six.string_types):
            topic_or_id = topic_or_id.GetObjectID()
        Topic2Posting.createMapping(self.GetObjectID(), topic_or_id)

    def commentUpdated(self, comment):
        """It updates information about the last comment."""
        self.last_comment_date = comment.cdb_mdate

    @staticmethod
    def getPostingsByTopic(topic, cnt=0, last_posting=None):
        """Looks up for postings assigned to the given topic.
        @param topic: a topic object or its cdb_object_id.
        @param cnt: how many items should be returned
        @param last_posting: a tuple of (last_comment_date, cdb_object_id)
                             of the last returned posting. Used to look
                             up the next postings older then the given one.
        """
        topic_id = topic
        if not isinstance(topic, six.string_types):
            topic_id = topic.GetObjectID()
        cond = Posting.getTopicCondition().format("'%s'" % sqlapi.quote(topic_id))
        return Posting.getPostingsByCondition(cond, cnt, last_posting)

    @staticmethod
    def _getAccessiblePostings(postings, persno=None):
        """
        Checks the ``read`` access for the objects referenced by
        `context_object_id`. Returns the reduced list
        """
        from cdb.objects import NULL
        from cdb.platform import mom

        if not persno:
            persno = auth.persno

        uuid_set = set()
        for posting in postings:
            if posting.context_object_id:
                uuid_set.add(posting.context_object_id)

        uuids = [uuid for uuid in uuid_set]
        valid_uuids = set([NULL, ""])  # No context object ==> accessible
        valid_uuids |= {
            id
            for (id, handle) in mom.getObjectHandlesFromObjectIDs(
                uuids, False, False
            ).items()
            if handle.getAccessInfo(persno).get("read", (True,))[0]
        }
        return [
            posting for posting in postings if posting.context_object_id in valid_uuids
        ]

    @staticmethod
    def getPostingOrderCondition(last_posting=None):
        """
        Generates specified sql query condition and order by expression for batches.
        Returns a tuple containing
        (batch begin condition, order by fields, order by expression).
        """
        if last_posting is None:
            tblname = Posting.GetTableName()
            # To guard a stable list during paginated checks
            newest = sqlapi.RecordSet2(
                sql=(
                    "select last_comment_date from %s where last_comment_date = "
                    " (select max(last_comment_date) from %s)"
                )
                % (tblname, tblname)
            )
            if newest:
                last_posting = (newest[0].last_comment_date, "")
            else:
                last_posting = (None, None)

        if not last_posting[0]:
            # no posting created/commented => no posting exists
            return (None, None, None)

        last_date = sqlapi.SQLdbms_date(last_posting[0])
        last_id = last_posting[1]

        if not last_id:
            cond = ("last_comment_date<={last_date}").format(last_date=last_date)
        else:
            cond = (
                "last_comment_date<{last_date} or "
                "(last_comment_date={last_date} and cdb_object_id<'{last_id}')"
            ).format(last_date=last_date, last_id=last_id)

        # DESC: both fields in descending order as later postings showed first.
        # Both field get ascending indexed(). The database can do bidirectional
        # traversal on indexes, but as compound here and not in mixed directions.
        order_by = [-Posting.last_comment_date, -Posting.cdb_object_id]
        return (cond, order_by, Posting._buildOrderBy(order_by))

    @staticmethod
    def getPostingBatchCondition(cond=None, last_posting=None):
        """
        Expands specified sql query condition with batch related information.
        Returns a tuple containing
        (query condition, order by fields, order by expression).
        """
        if not cond:
            cond = "1=1"

        (batch_start, order_by, order_by_expr) = Posting.getPostingOrderCondition(
            last_posting
        )
        if batch_start is None:
            # no batch information, find nothing
            return (None, None, None)

        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            # Add an extra subquery to move "order by" outside
            # Because MS SQL Server 2016 attempts to do sorting
            # during sub-subqueries in this case and causes performance
            # problem (E059165).
            cond = (
                "cdb_object_id in ("
                "  select cdb_object_id from {tblname} where ({cond}) and ({batch_start})"
                ") "
            ).format(
                tblname=Posting.GetTableName(),
                cond=cond,
                batch_start=batch_start,
            )
        else:
            cond = "({cond}) and ({batch_start})".format(
                cond=cond, batch_start=batch_start
            )
        return (cond, order_by, order_by_expr)

    @staticmethod
    def getPostingsByCondition(cond=None, cnt=0, last_posting=None, check_access=True):
        """
        Looks up for postings just according to the specified sql query
        condition. Returns a tupel of a list of `cdb.objects.Object` and the
        number of potentially accessible postings, which can be used to
        determine whether there are more postings or not. If the access check
        is disabled, that number would be the total number of postings.
            @param cond: used as sql 'where' condition to look up postings.
            @param cnt: how many items should be returned
            @param last_posting: a tuple of (last_comment_date, cdb_object_id)
                                 of the last returned posting. Used to look
                                 up the next postings older then the given one.
            @param check_access: Deprecated. The the ``read``-access will be
                                 always checked for all postings that contain a
                                 ``context_object_id``.
        """
        cond, order_by, order_by_expr = Posting.getPostingBatchCondition(
            cond, last_posting
        )

        if cond is None:
            # nothing to be looked up
            return ([], 0)

        if cnt < 0:
            postings = Posting._getAccessiblePostings(
                Posting.Query(cond, access="read", order_by=order_by)
            )
        else:
            records = sqlapi.RecordSet2(
                Posting.GetTableName(), cond, addtl=order_by_expr, access="read"
            )
            # To figure out whether there are more postings, collect
            # just one more piece than expected.
            # Avoid small batchs: minimal size 21
            page_size = max(cnt + 1, 21)

            # util.paginated cannot be used with access check.
            all_posts = paginated(records, page_size)
            _postings = []
            for page in all_posts:
                _postings += Posting._getAccessiblePostings(page)
                if len(_postings) > cnt:
                    # Enough pieces found(one more than required)
                    break
            postings = Posting.FromRecords(_postings)

        return ([posting for posting in postings[:cnt]], len(postings))

    @staticmethod
    def getTopicCondition(persno=None):
        """Generates the sql query condition pattern to look up postings
        assigned to specified topics.
        """
        key = "topic_condition"
        if not persno:
            persno = auth.persno

        if key not in CACHED_STATEMENTS:
            from cs.activitystream.attachment import Attachment
            from cs.sharing import Sharing

            vals = {
                "user_id": persno,
                "topic2posting": Topic2Posting.GetTableName(),
                "sharing_posting_v": "cdb_sharing_posting_v",
                "attachment": Attachment.GetTableName(),
                "subscription": Subscription.GetTableName(),
                "sharing": Sharing.GetTableName(),
            }

            conditions = [
                # posting is directly assigned to given topic
                """ SELECT t2p.posting_id
                    FROM {topic2posting} t2p
                    WHERE t2p.topic_id IN ({{0}})""".format(
                    **vals
                ),
                # posting is attached to a sharing by the user themselves
                # union
                # posting is attached to a sharing the user is subscribed to
                """ SELECT posting_id
                    FROM {sharing_posting_v} spv
                    WHERE spv.attachment_id IN ({{0}})
                    AND spv.sharing_id IN (
                        SELECT cdb_object_id
                        FROM {sharing} sharing
                        WHERE sharing.cdb_cpersno='{user_id}'
                        UNION
                        SELECT sub.channel_cdb_object_id FROM {subscription} sub
                        WHERE sub.personalnummer='{user_id}'
                    )""".format(
                    **vals
                ),
            ]

            CACHED_STATEMENTS[key] = "cdb_object_id IN ({conditions})".format(
                conditions=" UNION ".join(conditions)
            )

        return CACHED_STATEMENTS[key]

    @staticmethod
    def getNewPostingCount(cond=None, last_updated=None):
        """Looks up for new postings since latest update time.
        @param cond: used as sql 'where' condition to look up postings.
        @param last_updated: the date of last check
        """
        if not cond:
            cond = "1=1"
        if last_updated:
            last_date = sqlapi.SQLdbms_date(last_updated)
            cond = ("(%s) and last_comment_date>%s") % (cond, last_date)
        return len(Posting.Query(cond, access="read"))

    def updateLastCommentedDate(self, ctx=None):
        """Initiates the last_comment_date field of the posting object for new
        posting object.
        """
        pobj = self.getPersistentObject()
        if pobj:
            pobj.last_comment_date = self.cdb_mdate

    def addTopics(self, ctx=None):
        """
        Calls cdb.objects.Object.get_topics function to retrieve the topics
        for `self.context_object_id`.
        """
        ctxobj = self.ContextObject
        if ctxobj:  # pylint: disable=too-many-nested-blocks
            topics = ctxobj.GetActivityStreamTopics(self)
            for topic in topics:
                if topic:
                    self.addTopic(topic)
            if self.type == "insert":
                channel = ctxobj.GetClassDef().getObjectCreatedPostingChannel()
                if channel:
                    # Check whether the channel is already part of the topics
                    add = True
                    for topic in topics:
                        if topic:
                            if isinstance(topic, six.string_types):
                                if topic == channel:
                                    add = False
                                    break
                            else:
                                if topic.GetObjectID() == channel:
                                    add = False
                                    break
                    if add:
                        self.addTopic(channel)

    def openThreadPage(self, ctx):
        ctx.url("/activitystream/posting/%s" % self.cdb_object_id)

    def GetDisplayAttributes(self):
        """This method creates and returns a results dictionary, containing the
        necessary information for the html display in the client."""
        results = super(Posting, self).GetDisplayAttributes()
        results["viewurl"] = self.MakeURL("cdbblog_open_thread")
        results["attrs"].update(
            {
                "heading": "%s (%i)"
                % (
                    fComment._getClassDef().getTitle(),  # pylint: disable=protected-access
                    len(self.AllComments),
                )
            }
        )
        return results

    def getActionForSharingNotification(self):
        # Allow opening thread page from link in sharing notification
        # instead of opening information mask.
        return "cdbblog_open_thread"

    # TODO: copy Operation should not be allowed!
    event_map = {
        (("create", "copy"), "post"): (
            "updateLastCommentedDate",
            "addTopics",
        ),
        ("cdbblog_open_thread", "now"): "openThreadPage",
    }


class SystemPosting(Posting):
    """The system posting class. A system posting can only be generated by
    the system. It doesn't contain a text field for user inputs, but title
    fields in all the active languages.
    """

    __classname__ = "cdbblog_system_posting"
    __match__ = Posting.cdb_classname >= __classname__

    Title = LocalizedField("title")

    def getTitle(self, lang=""):
        """Gets the title text in specified language."""
        return self.Title[lang]

    @classmethod
    def do_create(cls, *args, **kwargs):
        """
        Uses the ``CDB_Create`` operation to create a system posting.

        :param args:
            Args parameter for the `cdb.objects.operations.operation` call

        :param kwargs:
            kwargs parameter for the `cdb.objects.operations.operation` call -
            usually the attributes of the system posting object.

        :returns:
            The created posting as `cdb.objects.Object`
        """
        try:
            result = operation(constants.kOperationNew, cls, *args, **kwargs)
            if result:
                ctx = hooks.ASChannelActionContext(result, True)
                hooks.call_channelaction_hook(ctx)
            return result
        except RuntimeError as exc:
            log.error("Failed to generate system posting: %s", exc)

    @classmethod
    def create_posting(cls, channel, title, **kwargs):
        """
        Creates a system posting. At this time
        the ``CDB_Create`` operation is used to create the object but this
        behaviour might change in the future.

        :param channel:
           The object that defines the context for the system posting or the
           ``cdb_object_id`` of this object. If it is not a string
           the object has to provide access to ``channel.cdb_object_id``.

        :param title:
            A dictionary of type {"<lang>": "<title>") that contains the
            title of the posting

        :param kwargs:
            Additional fields of the system posting.

        :returns:
            The created posting as cdb.objects.Object.
        """
        uuid = channel
        if not isinstance(uuid, six.string_types):
            uuid = channel.cdb_object_id

        if uuid:
            kwargs["context_object_id"] = uuid

        if "type" not in kwargs:
            kwargs["type"] = "update"

        if title:
            for lang, f in cls.title.getLanguageFields().items():
                val = title.get(lang)
                if val:
                    kwargs[f.name] = val
        return cls.do_create(**kwargs)


class UserPosting(Posting):
    """The user posting class. It contains a long text field for the text input
    by the user.
    """

    __classname__ = "cdbblog_user_posting"
    __match__ = Posting.cdb_classname >= __classname__

    @classmethod
    def create_posting(
        cls,
        channel,
        txt,
        topic_ids=None,
        attachment_ids=None,
        mention_subjects=None,
        op_args=None,
        **kwargs
    ):
        """
        Creates a user posting. At this time
        the ``CDB_Create`` operation is used to create the object but this
        behaviour might change in the future. Exceptions from the create
        operation will not be catched - errors that occures during the
        mention operation will be logged and ignored.

        :param channel:
           The object that defines the context for the system posting or the
           ``cdb_object_id`` of this object. If it is not a string
           the object has to provide access to ``channel.cdb_object_id``.

        :param txt:
            The text of the posting. The format depends on the format that is
            used by the activity stream app. The format will change in the
            future so we recommend to use plain text.

        :param topic_ids:
            A list of UUIDs from the topics the posting should be assigned to.

        :param attachment_ids:
            A list of UUIDs that define the attachments of the posting. These
            are the objects linked within the posting.

        :param mention_subjects:
            A list of personal numbers (``angestellter.personalnummer``) of the
            users that are mentioned in the posting.

        :param args:
            List of `cdb.platform.mom.SimpleArgument` that will be provided
            to the kernel operation (see `cdb.objects.operations.operation`).

        :param kwargs:
            Additional attributes of the user posting class. Note that the
            values has to be typed. (see `cdb.objects.operations.operation`).

        :returns:
            The created posting as cdb.objects.Object.
        """
        uuid = channel
        if not isinstance(uuid, six.string_types) and channel:
            uuid = channel.cdb_object_id
        if uuid:
            kwargs["context_object_id"] = uuid

        # if no text is set assume the text is part of the kwargs
        if txt:
            kwargs["cdbblog_posting_txt"] = txt
        if op_args:
            result = operation(constants.kOperationNew, cls, op_args, **kwargs)
        else:
            result = operation(constants.kOperationNew, cls, **kwargs)

        if not result:
            return result

        if attachment_ids:
            from cs.activitystream.attachment import Attachment

            for attachment_id in attachment_ids:
                Attachment.addAttachment(result.cdb_object_id, attachment_id)

        if topic_ids:
            for topic_id in topic_ids:
                Topic2Posting.createMapping(result.cdb_object_id, topic_id)

        if mention_subjects:
            from cs.activitystream.mention import InvalidRecipientsError, Mention

            try:
                Mention.mentionUsers(mention_subjects, result.cdb_object_id, None)
            except InvalidRecipientsError as e:
                log.error("Error while mentioning users: %s", e)

        ctx = hooks.ASChannelActionContext(result, True)
        hooks.call_channelaction_hook(ctx)
        return result

    def GetDisplayAttributes(self):
        """This method creates and returns a results dictionary, containing the
        necessary information for the html display in the client."""
        results = super(UserPosting, self).GetDisplayAttributes()
        newattr = {}
        if self.ContextObject:
            newattr["title"] = u"%s %s" % (
                util.Labels()["cdbblog_posting_to_topic"],
                self.ContextObject.GetDescription(),
            )
        else:
            newattr["title"] = util.Labels()["cdbblog_posting_to_all"]
        results["attrs"].update(newattr)
        return results


class Comment(ActivityEntry):
    """The comment class. A comment must be a reply to a posting or another
    comment.
    """

    __maps_to__ = "cdbblog_comment"
    __classname__ = "cdbblog_comment"
    __audit_trail_longtext__ = "cdbblog_comment_txt"

    def getAuthor(self):
        if self.is_deleted:
            return None
        return User.ByKeys(self.cdb_cpersno)

    Posting = Reference_1(fPosting, fComment.posting_id)

    ReplyTo = Reference_1(fComment, fComment.in_reply_to)

    Author = ReferenceMethods_1(User, getAuthor)

    Comments = Reference_N(
        fComment, fComment.in_reply_to == fComment.cdb_object_id, access="read"
    )

    Reactions = Reference_N(
        fReaction,
        fReaction.reaction_to == fComment.cdb_object_id,
    )

    def updatePosting(self, ctx=None):
        """Tells the posting object that this comment is just created."""
        if self.Posting:
            self.Posting.commentUpdated(self)

    def _handle_es_update(self, ctx):
        """The system is about to delete the object.
        Need to create an index job (Enterprise-Search) now,
        because the DBEventListener normally used for this
        is called after the object is deleted in the database.
        This won't work because the index system needs to find
        the owner of a comment object in order to update the index.
        """
        try:
            if self.Posting:
                from cdb.storage.index.tesjobqueue import TESJobQueue

                TESJobQueue.enqueue(
                    self.Posting.cdb_object_id, self.Posting.GetTableName(), None, None
                )
        except Exception:  # pylint: disable=W0703
            log.exception("Error creating index job for %s", self.cdb_object_id)

    def preventCommentOnDeleted(self, ctx):
        """
        User Exit to prevent comments on deleted postings. Will raise ue.Exception if
        a comment is attempted on a deleted posting.
        """
        valid_reply_to = bool(self.in_reply_to and not self.ReplyTo.is_deleted)
        if self.Posting.is_deleted and not valid_reply_to:
            raise ue.Exception("Cannot comment on deleted posting")

    event_map = {
        ("create", "pre"): "preventCommentOnDeleted",
        ("create", "post"): "updatePosting",
        ("delete", "post"): "_handle_es_update",
    }


class Topic2Posting(Object):
    """The topic assignment to posting object. The topic object should has
    cdb_object_id field.
    """

    __maps_to__ = "cdbblog_topic2posting"
    __classname__ = "cdbblog_topic2posting"

    @classmethod
    def createMapping(cls, posting_id, topic_id):
        """Helper function to create topic assignment using operation routine
        to ensure calling event handler.
        """
        if posting_id and topic_id:
            operation(
                constants.kOperationNew, cls, posting_id=posting_id, topic_id=topic_id
            )

    @classmethod
    def deleteMapping(cls, posting_id, topic_id):
        if posting_id and topic_id:
            assignment = cls.KeywordQuery(posting_id=posting_id, topic_id=topic_id)
            if assignment:
                operation(constants.kOperationDelete, assignment[0])

    @classmethod
    def deleteInvalidAssignments(cls):
        """
        Deletes all entries where either the topic
        or the posting does not exist any longer.
        Returns the number of records that have been
        removed.
        """
        posting_cond = (
            "NOT EXISTS (SELECT id FROM cdb_object "
            "WHERE id = %s.posting_id)" % cls.__maps_to__
        )
        topic_cond = (
            "NOT EXISTS (SELECT id FROM cdb_object "
            "WHERE id = %s.topic_id)" % cls.__maps_to__
        )
        condition = posting_cond + " OR " + topic_cond
        rs = sqlapi.RecordSet2(cls.__maps_to__, condition=condition)
        with transaction.Transaction():
            for r in rs:
                r.delete()
        return len(rs)


class Reaction(Object):
    __maps_to__ = "cdbblog_reaction"
    __classname__ = "cdbblog_reaction"


class Subscription(Object):
    __maps_to__ = "cdbblog_subscription"
    __classname__ = "cdbblog_subscription"

    @classmethod
    def subscribeToChannel(cls, object_id, persno=""):
        """
        Generate a subscription entry
        for the user identified by `persno` or the
        active user if `persno` is ``None``.
        """
        if not persno:
            persno = auth.persno
        fields = cls.MakeChangeControlAttributes()
        fields["channel_cdb_object_id"] = object_id
        fields["personalnummer"] = persno
        Subscription.CreateNoResult(**fields)

    @classmethod
    def unsubscribeFromChannel(cls, object_id, persno=None):
        """
        Checks whether there is a subscription entry
        for the user identified by `persno` or the active
        user if `persno` is ``None``.
        If there is an entry the entry will be removed.
        """
        if not persno:
            persno = auth.persno

        subscription = Subscription.ByKeys(object_id, persno)
        if subscription:
            subscription.Delete()

    @classmethod
    def deleteInvalidSubscriptions(cls):
        """
        Deletes all subscriptions to channels that are
        no longer available. Returns the number of entries
        that have been removed.
        """
        condition = (
            "NOT EXISTS (SELECT id FROM cdb_object WHERE "
            "id = %s.channel_cdb_object_id)" % cls.__maps_to__
        )
        rs = sqlapi.RecordSet2(cls.__maps_to__, condition=condition)
        with transaction.Transaction():
            for r in rs:
                r.delete()
        return len(rs)


class Channel(Object):
    __maps_to__ = "cdbblog_channel"
    __classname__ = "cdbblog_channel"

    Title = LocalizedField("title")

    @classmethod
    def allowCreatingChannel(cls):
        return util.check_access(cls.GetTableName(), {}, "create")

    def _handle_registers(self, ctx):
        """
        The activity stream eLink-Register is only available
        for info and modify.
        In info mode we want to see only the thread.
        """
        if ctx.action != "info" and ctx.action != "modify":
            try:
                ctx.disable_registers(["cdb_elink_activitystream"])
            except Exception as exc:  # pylint: disable=W0703
                # Some context adaptors does not support disable_registers
                log.debug(
                    "Failed to disable_register(cdb_elink_activitystream): %s", exc
                )

        if ctx.action == "info":
            # Disable the data register
            ctx.disable_registers(["cdbblog_channel_reg"])
            # If cs.platform changes the register name
            # this code guarantees that the thread is the
            # active register
            ctx.set_active_register("cdb_elink_activitystream")

    event_map = {("*", "pre_mask"): "_handle_registers"}


class MQSystemPosting(Object):
    __maps_to__ = "mq_system_posting"
    __classname__ = "mq_system_posting"

    Title = LocalizedField("title")


@sig.connect(Object, any, "pre_mask")
def _handle_as_elink_register(self, ctx):
    try:
        if ctx.action != "info" and ctx.action != "modify":
            ctx.disable_registers(["cdb_elink_activitystream"])
    except Exception as exc:  # pylint: disable=W0703
        # Some context adaptors does not support disable_registers
        log.debug("Failed to disable_register(cdb_elink_activitystream): %s", exc)
