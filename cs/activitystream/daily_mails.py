# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import argparse
import datetime
import logging
import sys

import six
from cdb import CADDOK, auth, i18n, sig, sqlapi, ue, util
from cdb.objects import ByID
from cdb.objects.common import WithEmailNotification
from cdb.objects.org import User
from cdb.platform.gui import Label, Message
from cdbwrapc import get_active_account_sqlcond

from cs.activitystream.attachment import Attachment
from cs.activitystream.objects import Posting, Subscription
from cs.activitystream.posting_text_content_type import PostingTextConverter
from cs.sharing import Sharing

DAILY_AS_SETTING = "user.email_daily_as"
DAILY_MAILS_SIGNAL = "daily_mails_signal"

log = logging.getLogger(__name__)


class DailyMailer(WithEmailNotification):
    # pylint: disable=R0902
    __notification_template__ = "activity_digest.html"
    __notification_title__ = "activity_digest"

    def __init__(self, recipient=None, days=None, sender=None):
        self.notification_title = None
        self._getPerson(recipient)
        self._getDate(days)
        self._getLabels()
        self.cached_postings = None
        self.sender = User.ByKeys(sender if sender else "caddok")
        self.__attachment_cache__ = {}

    def _getPerson(self, recipient):
        if recipient:
            self.user = recipient
        else:
            self.user = User.ByKeys(auth.persno)

        if not self.user.e_mail:
            raise ue.Exception(
                "just_a_replacement",
                "user has no e-mail address (%s)" % self.user.personalnummer,
            )
        if self.user.getSettingValue(DAILY_AS_SETTING) != "1":
            raise ue.Exception(
                "just_a_replacement",
                "user does not want daily mails (%s)" % self.user.personalnummer,
            )

    def _getDate(self, days=None):
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 1
        newer_than = datetime.datetime.today() - datetime.timedelta(days=days)
        self.newer_than = newer_than

    def _getLabels(self):
        self.isolang = self.user.GetPreferredLanguage()
        self.lang = i18n._to_cdb(self.isolang)  # pylint: disable=protected-access
        if not self.lang:
            self.lang = self.isolang

        def get_datetime_format():
            replacements = [
                ("YYYY", "%Y"),
                ("MM", "%m"),
                ("DD", "%d"),
                ("hh", "%H"),
                ("mm", "%M"),
                ("ss", "%S"),
            ]
            result = i18n.get_datetime_format(self.lang)
            for a, b in replacements:
                result = result.replace(a, b)
            return result

        def get_label_text(label):
            if label[self.lang]:
                return label[self.lang]
            elif label["uk"]:
                return label["uk"]
            else:
                return ""

        self.datetime_format = "%A, " + get_datetime_format()

        self.product = get_label_text(Message.ByKeys("branding_product_name"))
        self.open_activity_stream = get_label_text(
            Label.ByKeys("cdbblog_activity_stream")
        )
        self.shared = get_label_text(Label.ByKeys("web.share_objects.shared"))
        self.all = get_label_text(Label.ByKeys("web.activitystream.to-all"))
        self.disclaimer = "\n".join(
            get_label_text(label)
            for label in Label.Query(
                "ausgabe_label LIKE 'daily_activities_disclaimer%%'",
                addtl="ORDER BY ausgabe_label ASC",
            )
        )
        self.notification_title = get_label_text(
            Label.ByKeys(self.__notification_title__)
        )

    def _getComments(self, posting):
        comments = posting.AllComments.Query(
            "cdb_cdate>{} AND is_deleted=0".format(
                sqlapi.SQLdbms_date(self.newer_than)
            ),
        )
        return [c for c in comments if c.CheckAccess("read", self.user.personalnummer)]

    def _getTopicIDs(self):
        my_subscriptions = (
            "SELECT channel_cdb_object_id FROM %s "
            "WHERE personalnummer='%s'"
            % (Subscription.GetTableName(), self.user.personalnummer)
        )
        my_sharings = "SELECT cdb_object_id FROM %s WHERE cdb_cpersno='%s'" % (
            Sharing.GetTableName(),
            self.user.personalnummer,
        )
        return "%s UNION %s" % (my_subscriptions, my_sharings)

    def _getTopicCondition(self):
        subscriptions = Posting.getTopicCondition(
            persno=self.user.personalnummer
        ).format(self._getTopicIDs())
        return "(context_object_id='' " "OR (%s))" % subscriptions

    def _getPostings(self, newer_than):
        """
        emulates cs.activitystream.objects.Posting.getPostingsByCondition

        returns all cs.activitystream.objects.Posting objects visible to current user
        that are newer than given datetime.datetime newer_than
        """
        last_date = sqlapi.SQLdbms_date(newer_than)
        topics = self._getTopicCondition()
        postings = Posting.Query(
            "(is_deleted=0 OR is_deleted IS NULL) AND last_comment_date>%s AND %s"
            % (last_date, topics),
            order_by=[-Posting.last_comment_date, Posting.cdb_object_id],
        )
        return Posting._getAccessiblePostings(  # pylint: disable=protected-access
            [p for p in postings if p.CheckAccess("read", self.user.personalnummer)],
            persno=self.user.personalnummer,
        )

    @property
    def postings(self):
        result = []
        postings = self._getPostings(self.newer_than)
        # FIXME: skip new postings/comments by self.user
        # (only include postings by self.user as context
        # if new comments are by someone else)
        for posting in postings:
            result.append(posting)  # FIXME: skip uncommented SystemPostings
            result += self._getComments(posting)
        return result

    def getNotificationTitle(self, ctx=None):
        return self.notification_title

    def setNotificationContext(self, sc, ctx=None):
        sc.self = self

    def getNotificationReceiver(self, ctx=None):
        return [{"to": [(self.user.e_mail, self.user.name)]}]

    def getNotificationSender(self, ctx=None):
        return (self.sender.e_mail, self.sender.name)

    def getTitle(self, posting_or_comment):
        if posting_or_comment.GetClassname() == "cdbblog_system_posting":
            return posting_or_comment.getTitle(lang=self.isolang)
        author = posting_or_comment.Author
        if author:
            return author.name
        return ""

    def getAuthorName(self, posting_or_comment):
        if posting_or_comment.GetClassname() == "cdbblog_system_posting":
            author = posting_or_comment.Author
            if author:
                return author.name
            return ""
        return None

    def getChannelName(self, posting_or_comment):
        if posting_or_comment.GetClassname() == "cdbblog_user_posting":
            channel = posting_or_comment.ContextObject
            if not channel:
                return self.all

            if channel.GetClassname() == "cdb_sharing":
                return self.shared

            return channel.GetDescription(self.isolang)
        return None

    def getASLink(self, posting_or_comment=None):
        from cs.activitystream.web.main import get_posting_link

        if not posting_or_comment:
            return "%s/activitystream" % CADDOK.WWWSERVICE_URL

        if posting_or_comment.GetClassname() == "cdbblog_comment":
            posting_or_comment = posting_or_comment.Posting

        return get_posting_link(posting_or_comment)

    def getFormattedTime(self, posting_or_comment):
        return util.Labels()["cdbblog_formatted_date_utc"].format(
            cdb_cdate=posting_or_comment.cdb_cdate.strftime(self.datetime_format)
        )

    def getFormattedMessage(self, posting_or_comment):
        if posting_or_comment.GetClassname() == "cdbblog_comment":
            text = posting_or_comment.GetText("cdbblog_comment_txt")
        else:
            text = posting_or_comment.GetText("cdbblog_posting_txt")
        text = six.text_type(text)
        converter = PostingTextConverter()
        return converter.convert(text)

    def getAttachmentLink(self, attachment):
        if isinstance(attachment, Posting):
            return self.getASLink(attachment)
        else:
            return attachment.MakeURL(action="CDB_ShowObject", plain=0)

    def getAttachments(self, posting_or_comment):
        result = self.__attachment_cache__.get(posting_or_comment.cdb_object_id, [])
        if not result:
            for a in Attachment.KeywordQuery(
                posting_id=posting_or_comment.cdb_object_id
            ):
                attachment = ByID(a.attachment_id)
                if attachment and attachment.CheckAccess(
                    "read", self.user.personalnummer
                ):
                    result.append(attachment)

            self.__attachment_cache__[posting_or_comment.cdb_object_id] = result

        return result

    def _buildHTML(self, ctx):
        """
        for acceptance tests only
        emulates cdb.objects.common.WithEmailNotification.sendNotification
        """
        templ_file = self._getNotificationTemplateFile(ctx)
        if not templ_file:
            logging.getLogger(__name__).error(
                "%s.sendNotification: could not find the template file: %s.",
                self.__module__,
                self.getNotificationTemplateName(ctx),
            )
            return None
        return self._render_mail_template(ctx, templ_file)

    def sendNotification(self, ctx=None, test=False):
        if self.postings:
            if test:
                self.html = self._buildHTML(ctx)
            else:
                WithEmailNotification.sendNotification(self, ctx)

    @classmethod
    def set_template_folder(cls, folder_path):
        """Allow customizing mail template in customer modules"""
        cls.__notification_template_folder__ = folder_path

    def set_notification_title(self, notification_title):
        """Call this function to change the title of the daily mail notifications"""
        self.notification_title = notification_title

    def _render_mail_template(self, ctx, templ_file):
        """
        rewrite the function _render_mail_template to use chameleon
        """
        import chameleon
        from cdb import elink
        from cdb.wsgi.util import TemplateCacheDir

        if not TemplateCacheDir.TEMPLATE_CACHE_INIT:
            TemplateCacheDir.init_template_cache()
        sc = elink.SimpleContext()
        sc.obj = self
        self.setNotificationContext(sc, ctx)
        mail_templ = chameleon.PageTemplateFile(templ_file)
        return mail_templ(context=sc)


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)-8s] [%(name)s] %(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--sender",
        metavar="USERID",
        type=str,
        default="caddok",
        dest="sender",
        help="user ID of sender",
    )
    args = parser.parse_args()
    # no interface to filter by user settings, so iterate over all users
    users = User.Query(
        get_active_account_sqlcond(False) + u" AND e_mail>'' AND visibility_flag=1"
    )
    for user in users:
        if user.getSettingValue(DAILY_AS_SETTING) != "1":
            log.info("user '%s' does not want daily AS mails", user.personalnummer)
        else:
            try:
                # Import "DailyMailer" so that setting the class attribute
                # in "set_template_folder" works correctly in customer modules
                from cs.activitystream.daily_mails import (  # pylint: disable=import-self
                    DailyMailer,
                )

                dailyMailer = DailyMailer(
                    recipient=user,
                    sender=args.sender,
                )
                sig.emit(DAILY_MAILS_SIGNAL)(dailyMailer)
                dailyMailer.sendNotification()
            except Exception:  # pylint: disable=W0703
                log.exception(
                    "Failed to send daily activities to '%s'", user.personalnummer
                )
