#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import base64
import mimetypes

import six
from cdb import CADDOK, ElementsError, i18n, util
from cdb.objects.common import RecipientDirectory, WithMultilanguageNotification
from cdb.objects.org import User
from cdb.platform.gui import Message
from cdb.wsgi.util import TemplateCacheDir
from cdbwrapc import retrieve_icon, verstring

from cs.activitystream.objects import Comment, Posting, Subscription
from cs.activitystream.posting_text_content_type import PostingTextConverter


class InvalidRecipientsError(ElementsError):
    pass


def get_product_icon_b64enc():
    product_icon_id = "branding_web_app_icon"
    icon = retrieve_icon(product_icon_id, 0, "")
    # Icon has changed in CE16 valid-> is_valid(), filename -> get_filename()
    if not icon.valid if hasattr(icon, "valid") else not icon.is_valid():
        return False, ""
    filename = icon.filename if hasattr(icon, "filename") else icon.get_filename()
    mtype, _ = mimetypes.guess_type(filename)
    icon_data = base64.b64encode(icon.get_image_data())
    return True, "data:{};base64,{}".format(mtype, icon_data)


class Mention(WithMultilanguageNotification):
    __notification_template__ = "tagged_notification.html"
    __notification_title__ = "cdb_new_tagged_mail"

    _shortened_msg_length = 250

    def __init__(self, target_users, posting_id, comment_id=None):
        posting = Posting.ByKeys(cdb_object_id=posting_id)
        comment = Comment.ByKeys(cdb_object_id=comment_id) if comment_id else None
        if not posting:
            raise ElementsError("Posting with ID {} does not exist".format(posting_id))

        recipients = User.KeywordQuery(personalnummer=target_users)
        if len(recipients) < len(target_users):
            raise InvalidRecipientsError(
                "At least one mentioned user has a malformed personalnummer"
            )

        super(Mention, self).__init__()
        self._notification_recipients = recipients
        self._posting = posting
        self._comment = comment

    @classmethod
    def mentionUsers(cls, target_users, posting_id, comment_id=None):
        if target_users:
            mention = Mention(target_users, posting_id, comment_id)
            mention.addSubscriptions()
            mention.sendNotification()

    def addSubscriptions(self):
        for user in self._notification_recipients:
            Subscription.subscribeToChannel(
                self._posting.cdb_object_id, user.personalnummer
            )

    def getNotificationTitle(self, ctx=None):
        languages = i18n.getActiveGUILanguages()
        title_map = {}
        sender_name = ""
        author = self._comment.Author if self._comment else self._posting.Author
        if author:
            sender_name = author.name

        for language in languages:
            label = util.get_label_with_fallback(self.__notification_title__, language)
            title_map[language] = label.format(sender=sender_name)

        return title_map

    def getNotificationReceiver(self, ctx=None):
        directory = RecipientDirectory()
        for user in self._notification_recipients:
            directory.add_recipient(user.e_mail, user.name, user.GetPreferredLanguage())
        return directory

    def getNotificationSender(self, ctx=None):
        author = self._comment.Author if self._comment else self._posting.Author
        if author:
            return author.e_mail, author.name
        return "", ""

    def getShortenedMessage(self):
        converter = PostingTextConverter()
        text = (
            six.text_type(self._comment.GetText("cdbblog_comment_txt"))
            if self._comment
            else six.text_type(self._posting.GetText("cdbblog_posting_txt"))
        )
        text = converter.convert(text)

        # return full message if it is short enough
        if len(text) <= Mention._shortened_msg_length:
            return text

        # else, cut off the text after the specified length (currently 250 chars),
        # then walk through the string backwards and trim it to the last space
        # or linefeed in order to remove any half-complete words left behind by the trim
        text = text[: Mention._shortened_msg_length]
        word_separators = [" ", "\n"]
        while text and text[-1] not in word_separators:
            text = text[:-1]
        if text[-1] in word_separators or text[-1] == ".":
            text = text[:-1]

        text += "..."
        return text

    def get_template_arguments(self):
        posting_context = self._posting.getContextObject()
        if posting_context:
            topic_map = Mention._get_topics(posting_context)
        else:
            languages = list(i18n.getActiveGUILanguages())
            if "en" not in languages:
                # At this time the standard only offers a template for "en" and
                # the code will raise a key error if en is missing
                languages.append("en")

            topic_map = {
                lang: util.get_label_with_fallback("web.activitystream.to-all", lang)
                for lang in languages
            }

        product_name = Message.GetMessage("branding_product_name")
        is_icon_valid, icon_data = get_product_icon_b64enc()
        author = self._comment.Author if self._comment else self._posting.Author
        if verstring(True).startswith("16.0"):
            # FIXME: this should be removed but it is still used for the template
            cdbpc = ""
        else:
            cdbpc = self._posting.MakeURL(
                self._posting.getActionForSharingNotification(), plain=2
            )
        data = {
            "author": author.name if author else "",
            "topic": dict(topic_map),
            "text": self.getShortenedMessage(),
            "links": {
                "web": "{}/activitystream/posting/{}".format(
                    CADDOK.WWWSERVICE_URL, self._posting.cdb_object_id
                ),
                "cdbpc": cdbpc,
            },
            "is_product_icon_valid": is_icon_valid,
            "product_icon_b64": icon_data,
            "product_name": product_name,
        }

        # some values taken from cs.web defaults (in variables.scss) for consistent styling.
        # note that the font size and padding are not applied on the reply buttons. they need hardcoded values because
        # of hacky vertical centering via line-height.
        style_data = {
            "font_family_sans_serif": 'SourceSansPro, "Helvetica Neue", Helvetica, Arial, sans-serif',
            "font_size_base": "14px",
            "margin_sm": "8px",
            "margin_md": "24px",
            "padding_sm": "8px",
            "padding_md": "24px",
        }

        return {"data": data, "styles": style_data}

    @classmethod
    def _get_topics(cls, topic_object):
        languages = list(i18n.getActiveGUILanguages())
        if "en" not in languages:
            # At this time the standard only offers a template for "en" and
            # the code will raise a key error if en is missing
            languages.append("en")
        topic_map = {}

        for language in languages:
            topic_map[language] = topic_object.GetDescription(language)

        return topic_map

    def _render_mail_template(self, ctx, templ_file):
        import chameleon

        if not TemplateCacheDir.TEMPLATE_CACHE_INIT:
            TemplateCacheDir.init_template_cache()

        tpl_args = self.get_template_arguments()
        mail_templ = chameleon.PageTemplateFile(templ_file)
        return mail_templ(**tpl_args)
