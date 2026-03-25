# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import datetime
import logging

import cdbwrapc
import isodate
from cdb import auth, sqlapi, typeconversion, util
from cdb.constants import kOperationNew
from cdb.objects import core
from cdb.objects.operations import operation
from cdb.objects.org import User
from cdb.storage.index.standard_query import StandardQuery
from cs.web.components.ui_support.navigation_modules import (
    NavigationAppViewModule,
    NavigationHomepageModule,
    NavigationModules,
    NavigationSubMenuModule,
)
from six.moves.urllib.parse import urlunparse

from cs.activitystream import APP_MOUNT_PATH, CHANNEL_OVERVIEW_PATH
from cs.activitystream.attachment import Attachment
from cs.activitystream.objects import (
    Channel,
    Comment,
    Posting,
    Reaction,
    Subscription,
    SystemPosting,
    Topic2Posting,
    UserPosting,
    paginated,
)
from cs.activitystream.rest_app import es_utils
from cs.sharing import Sharing

from .subscription_category_registry import get_registry

log = logging.getLogger(__name__)


def get_referenced_objects(posting_id, tblname, attrname, check_access="read"):
    """Get referenced objects of a posting with less sql statements.
    :param posting_id: object ID of the posting
    :param tblname: name of the table that contains the references
    :param attrname: name of attribute that contains ID of the referenced object
    :param check_access: deprecated. ``Read`` access of the referenced objects will
                         always be checked
    :return: a list of referenced objects by that posting.
    """
    result = []
    cond = "r.posting_id='%s' AND o.id=r.%s" % (sqlapi.quote(posting_id), attrname)
    tbls = "cdb_object o, %s r" % tblname
    relations = sqlapi.RecordSet2(
        sql=("SELECT distinct o.relation " "FROM %s " "WHERE %s ") % (tbls, cond)
    )

    for rel in relations:
        tname = rel.relation
        records = sqlapi.RecordSet2(
            sql=("SELECT t.* " "FROM %s, %s t " "WHERE %s " "AND t.cdb_object_id=o.id")
            % (tbls, tname, cond)
        )

        accessable = [r for r in records if util.check_access(tname, r, "read")]

        # Find the cdb.objects class for this database table
        cr = core.ClassRegistry()
        klass = cr.find(tname)
        # Build cdb.objects objects from the query result
        result += klass.FromRecords(accessable)

    return result


class WithExtraParams(object):
    __default_posting_count__ = 20

    def __init__(self, extra_parameters):
        self.extra_parameters = extra_parameters

    def _filter_posting_type(self):
        no_up = self.extra_parameters.get("userposting", "on") == "off"
        no_sp = self.extra_parameters.get("systemposting", "on") == "off"
        no_sharing = self.extra_parameters.get("sharingposting", "on") == "off"

        sp_cat = self.extra_parameters.get("sharingposting_category", "all")
        if sp_cat not in {"all", "from_me", "to_me"}:
            sp_cat = "all"

        # All postings
        if not (no_up or no_sp or no_sharing or sp_cat != "all"):
            return []
        # No postings
        if no_up and no_sp and no_sharing:
            return ["1=2"]

        posting = Posting.GetTableName()
        comment = Comment.GetTableName()
        sharing = Sharing.GetTableName()
        # Query conditions:
        # User postings
        up_cond = UserPosting._MatchExpression()  # pylint: disable=protected-access
        # Postings with comments
        comment_cond = (
            "EXISTS (SELECT * FROM {comment} "
            "        WHERE {comment}.posting_id={posting}.cdb_object_id) "
        ).format(comment=comment, posting=posting)
        # System postings
        sp_cond = SystemPosting._MatchExpression()  # pylint: disable=protected-access
        # Sharings
        sharing_cond = (
            "EXISTS (SELECT * FROM {sharing} "
            "        WHERE {sharing}.cdb_object_id={posting}.context_object_id {{addtl}}) "
        ).format(sharing=sharing, posting=posting)
        # Limit sharings to choosen category
        addtl = ""
        # Filter sharings with choosen category out
        filter_addtl = ""
        if sp_cat != "all":
            operator = "=" if sp_cat == "from_me" else "<>"
            addtl = "{sharing}.cdb_cpersno {operator} '{persno}'".format(
                sharing=sharing,
                operator=operator,
                persno=sqlapi.quote(auth.persno),
            )
            filter_addtl = " AND NOT {addtl}".format(addtl=addtl)
            addtl = " AND {addtl}".format(addtl=addtl)

        result = []
        # No user postings
        if no_up and not no_sp and not no_sharing:
            # System postings or sharings
            result = [
                " ({sp_cond} OR {sharing_cond}) ".format(
                    sp_cond=sp_cond, sharing_cond=sharing_cond.format(addtl=addtl)
                )
            ]

        # No system postings
        elif no_sp and not no_up and not no_sharing:
            # User postings or system postings with comments
            result = [
                " ({up_cond} OR {comment_cond}) ".format(
                    up_cond=up_cond, comment_cond=comment_cond
                )
            ]

        # No sharing
        elif no_sharing and not no_sp and not no_up:
            result = [
                " (NOT {sharing_cond})".format(
                    sharing_cond=sharing_cond.format(addtl="")
                )
            ]

        # Only user postings
        elif not no_up and no_sp and no_sharing:
            result = [
                " (({up_cond} OR {comment_cond}) AND NOT {sharing_cond}) ".format(
                    up_cond=up_cond,
                    comment_cond=comment_cond,
                    sharing_cond=sharing_cond.format(addtl=""),
                )
            ]

        # Only system postings
        elif not no_sp and no_up and no_sharing:
            result = [" ({sp_cond}) ".format(sp_cond=sp_cond)]

        # only sharing
        elif not no_sharing and no_sp and no_up:
            result = [
                " ({sharing_cond}) ".format(
                    sharing_cond=sharing_cond.format(addtl=addtl)
                )
            ]

        # With all postings but only some sharings
        elif sp_cat != "all":
            result = [
                " (NOT {sharing_cond}) ".format(
                    sharing_cond=sharing_cond.format(addtl=filter_addtl)
                )
            ]

        return result

    def _filter_person(self):
        person = self.extra_parameters.get("pn", "")
        no_ac = self.extra_parameters.get("author_comments", "on") == "off"
        if person:
            persno_cond = sqlapi.quote(person)
            if no_ac:
                return [
                    u" (cdb_cpersno = '%(persno)s')"
                    % {
                        "persno": persno_cond,
                    }
                ]
            else:
                comment_table = Comment.GetTableName()
                return [
                    u" (cdb_cpersno = '%(persno)s' or exists "
                    "(select * from %(ct)s where %(ct)s.posting_id=%(pt)s.cdb_object_id"
                    " and %(ct)s.cdb_cpersno = '%(persno)s'))"
                    % {
                        "persno": persno_cond,
                        "ct": comment_table,
                        "pt": Posting.GetTableName(),
                    }
                ]
        return []

    def _filter_date(self):
        date = self.extra_parameters.get("date", None)
        if date:
            try:
                posting_table = Posting.GetTableName()
                comment_table = Comment.GetTableName()
                return [
                    u" (%(cdate)s or exists"
                    "(select * from %(ct)s where %(ct)s.posting_id=%(pt)s.cdb_object_id"
                    " and %(ccdate)s))"
                    % {
                        "cdate": cdbwrapc.build_statement(
                            posting_table, "cdb_cdate", date
                        ),
                        "ct": comment_table,
                        "pt": posting_table,
                        "ccdate": cdbwrapc.build_statement(
                            comment_table, "cdb_cdate", date
                        ),
                    }
                ]
            except Exception as exc:  # pylint: disable=W0703
                log.debug("_filter_date(): %s", exc)
        return []

    def _get_posting_count(self):
        s_cnt = self.extra_parameters.get("posting_count", "")
        try:
            cnt = int(s_cnt)
        except ValueError:
            cnt = self.__default_posting_count__
        return cnt

    def _get_last_queried(self):
        last_comment_date = self.extra_parameters.get("last_comment_date", None)
        last_object_id = self.extra_parameters.get("last_object_id", None)
        last_posting = None
        if last_comment_date and last_object_id:
            try:
                last_posting = (
                    isodate.parse_datetime(last_comment_date),
                    sqlapi.quote(last_object_id),
                )
            except Exception as exc:  # pylint: disable=W0703
                log.debug("_get_last_queried: %s", exc)
        return last_posting

    def _get_since(self):
        since = self.extra_parameters.get("since", None)
        if since:
            try:
                return [
                    u"last_comment_date > %s"
                    % sqlapi.SQLdbms_date(isodate.parse_datetime(since))
                ]
            except Exception as exc:  # pylint: disable=W0703
                log.debug("_get_since: %s", exc)
        return []

    def query(self):
        search_text = self.extra_parameters.get("searchtext", "").strip()
        cnt = self._get_posting_count()
        last_posting = self._get_last_queried()
        cond = self._get_query_cond()
        if search_text:
            cond, _, order_by = Posting.getPostingBatchCondition(cond, last_posting)
            es_query = es_utils.PostingESQuery(search_text)
            es_query.set_owner_type(
                [UserPosting._getClassname()]  # pylint: disable=protected-access
            )
            since = self.extra_parameters.get("since", None)
            if since:
                es_query.set_posting_since(isodate.parse_datetime(since))
            object_filter = es_utils.PostingQueryFilter(cond, order_by)
            queryhelper = es_utils.PostingESQueryHelper(es_query, object_filter)
            result = queryhelper.get_postings(cnt, order_by)
        else:
            result = Posting.getPostingsByCondition(cond, cnt, last_posting)
        return (result[0], result[1] <= cnt)

    def add_posting(self, text):
        return operation(kOperationNew, UserPosting, cdbblog_posting_txt=text)

    def _get_all_query_conditions(self):
        cond = self._filter_posting_type()
        cond += self._filter_person()
        cond += self._filter_date()
        cond += self._get_since()
        return cond

    def _get_query_cond(self):
        raise NotImplementedError


class PostingCollection(WithExtraParams):
    def _get_all_postings_condition(self):
        if not hasattr(self, "__all_postings_conditions__ "):
            self.__all_postings_conditions__ = []
            cond = ""
            # Look up threads for current user
            persno_cond = sqlapi.quote(auth.persno)

            # These postings can be queried directly:
            # Company wide threads
            # Own discussions
            # - discussions created by current user
            # - system activities from current user and commented by someone
            self.__all_postings_conditions__.append(
                "context_object_id = ''"
                "  OR "
                "  (cdb_cpersno = '%s' AND (%s OR EXISTS ( "
                "    SELECT cdbblog_comment.posting_id FROM cdbblog_comment "
                "    WHERE cdbblog_comment.posting_id = "
                "      cdbblog_posting.cdb_object_id))) "
                % (persno_cond, UserPosting.__match__)
            )

            # These postings can be queried per sub select:
            # Threads with topics:
            # - topics subscripted
            cond = (
                "SELECT cdbblog_topic2posting.posting_id "
                "  FROM cdbblog_topic2posting "
                "  WHERE EXISTS ("
                "    SELECT 0 "
                "    FROM cdbblog_subscription "
                "    WHERE cdbblog_subscription.personalnummer = '%s' AND "
                "    cdbblog_subscription.channel_cdb_object_id = "
                "      cdbblog_topic2posting.topic_id "
                "  )" % persno_cond
            )

            # Threads that commented by current user
            cond += (
                "UNION ALL SELECT cdbblog_comment.posting_id "
                "  FROM cdbblog_comment "
                "  WHERE cdbblog_comment.cdb_cpersno = '%s' " % persno_cond
            )

            # Current user gets tagged/mentioned somewhere
            # Waiving "channel_cdb_object_id = cdbblog_posting.cdb_object_id"
            # to improve performance on MSSQL
            cond += (
                "UNION ALL SELECT cdbblog_subscription.channel_cdb_object_id "
                "  FROM cdbblog_subscription "
                "  WHERE cdbblog_subscription.personalnummer = '%s' " % persno_cond
            )

            self.__all_postings_conditions__.append("cdb_object_id in (%s)" % cond)
        return self.__all_postings_conditions__

    def _get_query_cond(self):
        cond = self._get_all_query_conditions()
        return u" and ".join(cond) if cond else "1=1"

    def query(self):
        search_text = self.extra_parameters.get("searchtext", "").strip()
        cnt = self._get_posting_count()
        last_posting = self._get_last_queried()
        filter_cond = self._get_query_cond()
        result = ([], 0)
        if search_text:
            stmt, order_by_expr = self.get_es_filter_condition(
                filter_cond, last_posting
            )
            es_query = es_utils.PostingESQuery(search_text)
            es_query.set_owner_type(
                [UserPosting._getClassname()]  # pylint: disable=protected-access
            )
            since = self.extra_parameters.get("since", None)
            if since:
                es_query.set_posting_since(isodate.parse_datetime(since))
            object_filter = es_utils.PostingCollectionQueryFilter(stmt, order_by_expr)
            queryhelper = es_utils.PostingESQueryHelper(es_query, object_filter)
            result = queryhelper.get_postings(cnt, order_by_expr)
        else:
            result = self.query_collection_postings(filter_cond, cnt, last_posting)
        return (result[0], result[1] <= cnt)

    def get_es_filter_condition(self, filter_cond, last_posting):
        batch_start, _, order_by_expr = Posting.getPostingOrderCondition(last_posting)

        if batch_start is None:
            # nothing to be looked up
            return ""

        table_conds = self._get_all_postings_condition()
        posting_table = Posting.GetTableName()
        stmt = (
            "SELECT cdb_object_id FROM {posting_table} "
            "    WHERE ({{hits}}) AND ({direct_cond}) AND ({filter_cond}) AND ({batch_start}) "
            "UNION "
            "SELECT cdb_object_id FROM {posting_table} "
            "    WHERE ({{hits}}) AND ({id_cond}) AND ({filter_cond}) AND ({batch_start}) "
        ).format(
            posting_table=posting_table,
            direct_cond=table_conds[0],
            filter_cond=filter_cond,
            batch_start=batch_start,
            id_cond=table_conds[1],
        )
        return stmt, order_by_expr

    def query_collection_postings(self, filter_cond, cnt, last_posting):
        # pylint: disable=R0914
        batch_start, order_by, order_by_expr = Posting.getPostingOrderCondition(
            last_posting
        )

        if batch_start is None:
            # nothing to be looked up
            return ([], 0)

        table_conds = self._get_all_postings_condition()
        posting_table = Posting.GetTableName()
        # only select necessary columns (possibly with database indexing)
        cols = ", ".join([field.name for field in order_by])
        if "cdb_object_id" not in cols:
            cols += ", cdb_object_id"
        sql = (
            "SELECT {cols} FROM {posting_table} "
            "    WHERE ({direct_cond}) AND ({filter_cond}) AND ({batch_start}) "
            "UNION "
            "SELECT {cols} FROM {posting_table} "
            "    WHERE ({id_cond}) AND ({filter_cond}) AND ({batch_start}) "
            "{order_by_expr} "
        ).format(
            cols=cols,
            posting_table=posting_table,
            direct_cond=table_conds[0],
            filter_cond=filter_cond,
            batch_start=batch_start,
            id_cond=table_conds[1],
            order_by_expr=order_by_expr,
        )
        records = sqlapi.RecordSet2(sql=sql)

        # To figure out whether there are more postings, collect
        # just one more piece than expected.
        # Avoid small batches: minimal size 21
        # Avoid big batches exploding sub query: maximum size 201
        page_size = min(201, max(cnt + 1, 21))

        all_posts = paginated(records, page_size)
        _postings = []
        for page in all_posts:
            oids = [r.cdb_object_id for r in page]
            # check access of postings themselves
            candidates = sqlapi.RecordSet2(
                posting_table,
                Posting.cdb_object_id.one_of(*oids),
                addtl=order_by_expr,
                access="read",
            )
            # also check access of references
            _postings += (
                Posting._getAccessiblePostings(  # pylint: disable=protected-access
                    candidates
                )
            )
            if len(_postings) > cnt:
                # Enough pieces found(one more than required)
                break
        postings = Posting.FromRecords(_postings[:cnt])
        return (postings, len(_postings))


class ChannelCollection(object):
    def query(self, list_all=False):
        if list_all:
            return [], Channel.Query(access="read")
        q_str = (
            "cdb_object_id in (select channel_cdb_object_id from %s where personalnummer='%s')"
            % (Subscription.GetTableName(), sqlapi.quote(auth.persno))
        )
        return [ToAllChannel(), SharingChannel()], Channel.Query(q_str, access="read")


class PostingComments(object):
    def __init__(self, posting):
        self.posting = posting

    def query(self):
        return self.posting.AllComments

    def add_comment(self, text):
        return operation(
            kOperationNew,
            Comment,
            cdbblog_comment_txt=text,
            posting_id=self.posting.cdb_object_id,
        )

    def add_reply_to(self, text, reply_to):
        return operation(
            kOperationNew,
            Comment,
            cdbblog_comment_txt=text,
            posting_id=self.posting.cdb_object_id,
            in_reply_to=reply_to.cdb_object_id,
        )


class ReactionModel(object):
    def add_reaction(self):
        Reaction.CreateNoResult(
            reaction_to=self.reaction_to.cdb_object_id,
            user_id=auth.persno,
            cdb_cdate=typeconversion.to_legacy_date_format(datetime.datetime.utcnow()),
        )

    def remove_reaction(self):
        try:
            Reaction.ByKeys(
                reaction_to=self.reaction_to.cdb_object_id, user_id=auth.persno
            ).Delete()
        except AttributeError:
            log.debug("Delete failed, data does not exist.")


class PostingReactionModel(ReactionModel):
    def __init__(self, posting):
        self.reaction_to = posting


class CommentReactionModel(ReactionModel):
    def __init__(self, comment):
        self.reaction_to = comment


class PostingTopics(object):
    def __init__(self, posting):
        self.posting = posting

    def query(self):
        topics = get_referenced_objects(
            self.posting.cdb_object_id, Topic2Posting.GetTableName(), "topic_id"
        )

        ctx = self.posting.ContextObject if self.posting.context_object_id else None
        if not ctx:
            ctx = ToAllChannel()
        elif ctx in topics:
            topics.remove(ctx)
        return [ctx] + topics

    def set_topics(self, topic_ids):
        current_topics = {
            t.topic_id
            for t in sqlapi.RecordSet2(
                Topic2Posting.GetTableName(),
                "posting_id='{}'".format(sqlapi.quote(self.posting.cdb_object_id)),
            )
        }
        new_topics = set(topic_ids)
        if self.posting.context_object_id:
            new_topics.add(self.posting.context_object_id)

        delete_topics = current_topics.difference(new_topics)
        create_topics = new_topics.difference(current_topics)

        for topic_id in delete_topics:
            Topic2Posting.deleteMapping(self.posting.cdb_object_id, topic_id)

        for topic_id in create_topics:
            Topic2Posting.createMapping(self.posting.cdb_object_id, topic_id)

        return bool(delete_topics or create_topics)


class Attachments(object):
    def __init__(self, entry):
        self.entry = entry

    def query(self):
        return get_referenced_objects(
            self.entry.cdb_object_id, Attachment.GetTableName(), "attachment_id"
        )

    def add_attachments(self, obj_ids):
        result = []
        for obj_id in obj_ids:
            result.append(Attachment.addAttachment(self.entry.cdb_object_id, obj_id))
        return result

    def has_attachments(self):
        return (
            len(
                Attachment.Query(
                    condition="posting_id='%s'"
                    % sqlapi.quote(self.entry.cdb_object_id),
                    access="read",
                )
            )
            > 0
        )

    def modifiable(self):
        # Should not modify existing postings. Use comment to add new attachments.
        # Only author can modify attachments.
        return not self.has_attachments() and self.entry.cdb_cpersno == auth.persno

    def set_attachments(self, obj_ids):
        current_ones = {
            att.attachment_id
            for att in sqlapi.RecordSet2(
                Attachment.GetTableName(),
                "posting_id='{}'".format(sqlapi.quote(self.entry.cdb_object_id)),
            )
        }
        new_ones = set(obj_ids)
        delete_ones = current_ones.difference(new_ones)
        create_ones = new_ones.difference(current_ones)

        for attachment_id in delete_ones:
            Attachment.deleteAttachment(self.entry.cdb_object_id, attachment_id)

        for attachment_id in create_ones:
            Attachment.addAttachment(self.entry.cdb_object_id, attachment_id)


class PostingAttachments(Attachments):
    pass


class CommentAttachments(Attachments):
    pass


class ObjectPostings(WithExtraParams):
    def __init__(self, context_id, extra_parameters):
        self.context_id = context_id
        super(ObjectPostings, self).__init__(extra_parameters)

    def _get_query_cond(self):
        cond = [
            Posting.getTopicCondition().format(("'%s'" % sqlapi.quote(self.context_id)))
        ]
        cond += self._get_all_query_conditions()
        return u" and ".join(cond)

    def add_posting(self, text):
        return operation(
            kOperationNew,
            UserPosting,
            cdbblog_posting_txt=text,
            context_object_id=self.context_id,
        )


class SubscriptionCategoryBase(object):
    order = 0

    def __init__(self, additional_condition):
        self.additional_condition = additional_condition

    @property
    def icon(self):
        return None

    @property
    def title(self):
        return ""

    def get_objects(self):
        return []


class SubscriptionCollection(object):
    def query(self):
        names = dict(
            sname=Subscription.GetTableName(),
            cname=Channel.GetTableName(),
            persno=sqlapi.quote(auth.persno),
        )
        q_str = (
            "cdb_object_id in (select %(sname)s.channel_cdb_object_id from %(sname)s where "
            "%(sname)s.personalnummer='%(persno)s' and not exists (select 1 from %(cname)s where "
            "%(sname)s.channel_cdb_object_id = %(cname)s.cdb_object_id))" % names
        )
        return [categ(q_str) for categ in get_registry().get_categories()]


class NavigationMenu(object):
    root_mount = "/" + APP_MOUNT_PATH
    channels = root_mount + "/" + CHANNEL_OVERVIEW_PATH

    @classmethod
    def link_channel(cls, channel_id):
        return urlunparse(("", "", cls.root_mount, "", "topic=" + channel_id, ""))


class Navigation(NavigationMenu):
    def get_navigation(self, req):
        root = NavigationModules()
        main_nav = NavigationHomepageModule("")
        main_nav.addAdditionalHomepageEntry(
            "web.activitystream.all", "web.activitystream.all", self.root_mount, ""
        )
        main_nav.addAdditionalHomepageEntry(
            "web.activitystream.all_channels",
            "web.activitystream.all_channels",
            self.channels,
            "",
        )
        main_nav.module_description.pop(
            0
        )  # Remove the 'search' entry as it is not used in AS
        main_nav.module_description[0]["is_default_homepage"] = True
        root.addModule(10, main_nav)

        channel_nav = NavigationChannel().get_channel_submenu(req)
        root.addModule(20, channel_nav)

        subscription_nav = NavigationSubscription().get_subscription_submenu(req)
        if subscription_nav:
            root.addModule(30, subscription_nav)

        return root


class NavigationSubmenu(NavigationMenu):
    pass


class NavigationChannel(NavigationSubmenu):
    def get_channel_submenu(self, req):
        predefined, custom = ChannelCollection().query()
        nav = NavigationAppViewModule(
            "web.activitystream.channels", req.link(NavigationChannel())
        )
        for channel in predefined:
            nav.appendAppEntry(
                channel.GetDescription(),
                self.link_channel(channel.cdb_object_id),
                "cdbblog_channel",
            )
        for channel in sorted(custom, key=lambda c: c.GetDescription()):
            nav.appendAppEntry(
                channel.title,
                self.link_channel(channel.cdb_object_id),
                "cdbblog_channel",
            )
        return nav

    def render(self, req):
        return self.get_channel_submenu(req).moduleContent()


class NavigationSubscription(NavigationSubmenu):
    def __init__(self, name=None):
        self.name = name

    def render_subscriptions(self, nav, menu_view):
        for subscription in menu_view["subscriptions"]:
            description = subscription["description"]
            link = self.link_channel(subscription["cdb_object_id"])
            object_icon = subscription["object_icon"]
            nav.appendAppEntry(
                description, description, "cdb_blog_subscription", app_link=link
            )
            nav.module_content[-1]["imageSrc"] = object_icon

    def render_subscription_collection(self, req, subscription):
        menu_view = req.view(subscription)
        if not menu_view["subscriptions"]:
            return None
        nav = NavigationSubMenuModule(
            "web.activitystream.subscriptions", req.link(NavigationSubscription())
        )
        nav.module_description["headline"] = subscription.title  # Replace label
        self.render_subscriptions(nav, menu_view)
        return nav

    def get_subscriptions(self):
        subscriptions = SubscriptionCollection().query()
        if self.name:
            return [s for s in subscriptions if s.title == self.name]
        return subscriptions

    def get_subscription_submenu(self, req):
        subscriptions = self.get_subscriptions()
        if len(subscriptions) == 1:
            # If only one subscription category exists, render it directly into the menu
            return self.render_subscription_collection(req, subscriptions[0])
        elif len(subscriptions) > 1:
            # If more than one category exists, render all categories into separate subdirectories
            submenu_module = NavigationSubMenuModule(
                "web.activitystream.subscriptions", req.link(NavigationSubscription())
            )
            for subscription in subscriptions:
                title = subscription.title
                submenu_module.appendAppEntry(
                    title,
                    title,
                    "Folder",
                    conf_link=req.link(NavigationSubscription(title)),
                )

            return submenu_module
        return None

    def render(self, req):
        submenu_module = self.get_subscription_submenu(req)
        if self.name:
            # If the menu is already a submenu, the frontend expects a NavigationModule structure
            root = NavigationModules()
            root.addModule(10, submenu_module)
            return root.frontEndModuleList()
        return submenu_module.moduleContent()


class SharingChannel(object):
    def __init__(self):
        self.cdb_object_id = "sharing"

    def GetDescription(self):
        return util.Labels()["web.share_objects.shared"]

    def GetObjectIcon(self):
        return self.GetClassIcon()

    def GetClassIcon(self):
        return Channel.GetClassIcon()

    def GetClassTitle(self):
        return (
            Channel._getClassDef().getDesignation()  # pylint: disable=protected-access
        )


class SharingCollection(WithExtraParams):
    def _get_sharing_cond(self):
        # Postings should have a sharing object as context, which is
        # - subscribed by current user
        # - or created by current user
        return (
            "context_object_id IN ("
            "  SELECT {sharing}.cdb_object_id"
            "  FROM {sharing}"
            "  WHERE {sharing}.cdb_cpersno='{pers}'"
            "    OR EXISTS ("
            "      SELECT 0"
            "      FROM {subscr}"
            "      WHERE {subscr}.channel_cdb_object_id={sharing}.cdb_object_id"
            "       and {subscr}.personalnummer='{pers}'"
            "    )"
            ")"
        ).format(
            sharing=sqlapi.quote(Sharing.GetTableName()),
            subscr=sqlapi.quote(Subscription.GetTableName()),
            pers=sqlapi.quote(auth.persno),
        )

    def _get_query_cond(self):
        cond = [self._get_sharing_cond()]
        cond += self._get_all_query_conditions()
        return u" and ".join(cond)


class ToAllChannel(object):
    def __init__(self):
        self.cdb_object_id = "to_all"

    def GetDescription(self):
        return util.Labels()["web.activitystream.to-all"]

    def GetObjectIcon(self):
        return self.GetClassIcon()

    def GetClassIcon(self):
        return Channel.GetClassIcon()

    def GetClassTitle(self):
        return (
            Channel._getClassDef().getDesignation()  # pylint: disable=protected-access
        )

    def add_posting(self, text):
        return operation(kOperationNew, UserPosting, cdbblog_posting_txt=text)


class ToAllChannelPostings(WithExtraParams):
    def _get_to_all_postings_condition(self):
        return "context_object_id = ''"

    def _get_query_cond(self):
        cond = [self._get_to_all_postings_condition()]
        cond += self._get_all_query_conditions()
        return u" and ".join(cond)


class PersonSearchModel(object):
    __default_query_results__ = 7

    def __init__(self, extra_parameters):
        self.extra_parameters = extra_parameters

    def _get_count(self):
        string_count = self.extra_parameters.get("result_count", "")
        try:
            cnt = int(string_count)
        except ValueError:
            cnt = self.__default_query_results__
        return cnt

    def query(self):
        search_string = self.extra_parameters.get("fulltextsearch", "").strip()
        cnt = self._get_count()
        if search_string:
            es_query = StandardQuery(query=search_string)
            es_query.set_owner_type(
                [User._getClassname()]  # pylint: disable=protected-access
            )
            query_helper = es_utils.PersonESQueryHelper(es_query)

            results = query_helper.get_results(cnt)
            return {
                "result": results[0],
                "curr_total": results[1],
                "settings": {"query": search_string},
            }
        return {"result": [], "curr_total": 0, "settings": {"query": search_string}}


class MentionSubjectSearchModel(object):
    __default_query_results__ = 7

    def __init__(self, extra_parameters):
        self.extra_parameters = extra_parameters

    def _get_count(self):
        string_count = self.extra_parameters.get("result_count", "")
        try:
            cnt = int(string_count)
        except ValueError:
            cnt = self.__default_query_results__
        return cnt

    @classmethod
    def _get_from_database(cls, search_string):
        search_sql = u"'{}%'".format(sqlapi.quote(search_string.lower()))
        where_cond = """(
                LOWER(personalnummer) LIKE {search_str}
             OR LOWER(name) LIKE {search_str}
             OR LOWER(firstname) LIKE {search_str}
             OR LOWER(lastname) LIKE {search_str}
             OR LOWER(firstname {0} ' ' {0} lastname) LIKE {search_str}
             OR LOWER(lastname {0} ' ' {0} firstname) LIKE {search_str}
            ) AND (
                 active_account='1'
             AND is_system_account=0
             AND visibility_flag=1
            )""".format(
            sqlapi.SQLstrcat(), search_str=search_sql
        )
        addtl = "ORDER BY name"
        return sqlapi.RecordSet2(
            table=User.GetTableName(), condition=where_cond, addtl=addtl, access="read"
        )

    def query(self):
        search_string = self.extra_parameters.get("fulltextsearch", "").strip()
        cnt = self._get_count()
        if search_string:
            records = self._get_from_database(search_string)
            results = User.FromRecords(records[:cnt])
            return {
                "result": results,
                "curr_total": len(records),
                "settings": {"query": search_string},
            }
        return {"result": [], "curr_total": 0, "settings": {"query": search_string}}
