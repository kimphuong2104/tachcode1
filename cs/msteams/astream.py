#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import util
from cdb.objects import ByID
from cdb.platform.mom import getObjectHandlesFromObjectIDs
from cs.activitystream.attachment import Attachment
from cs.activitystream.objects import Comment
from cs.activitystream.posting_text_content_type import PostingTextConverter
from cs.msteams import MessageCard, MessageCardSection
from cs.msteams.objects import MSTeamsASAssignment, MSTeamsFailedJob


def get_text(posting_or_comment):
    if posting_or_comment.GetClassname() == "cdbblog_comment":
        text = posting_or_comment.GetText("cdbblog_comment_txt")
    elif posting_or_comment.GetClassname() == "cdbblog_system_posting":
        # The whole text is part of the title but an empty text is
        # not allowed
        text = " "
    else:
        text = posting_or_comment.GetText("cdbblog_posting_txt")
    converter = PostingTextConverter()
    return converter.convert(text)


def _get_channel_label(posting, language):
    if posting and posting.ContextObject:
        return posting.ContextObject.GetDescription(language)
    else:
        return util.get_label_with_fallback("cdbblog_posting_to_all", language)


def _get_author(posting_or_comment):
    user = posting_or_comment.getAuthor()
    if user:
        return user.name
    else:
        return ""


def get_system_posting_title(posting, language):
    author = _get_author(posting)
    title = posting.GetLocalizedValue("title", language)
    if not title:
        title = posting.title
    return util.get_label_with_fallback(
        "ce_msteams_system_posting_title", language
    ).format(author=author, posting=title)


def get_posting_title(posting, language):
    channel_label = _get_channel_label(posting, language)
    author = _get_author(posting)
    return util.get_label_with_fallback("ce_msteams_posting_title", language).format(
        author=author, channel=channel_label
    )


def get_comment_title(comment, language):
    channel_label = _get_channel_label(comment.Posting, language)
    author = _get_author(comment)
    posting = ""
    if comment.Posting:
        posting = comment.Posting.GetDescription(language)

    return util.get_label_with_fallback("ce_msteams_comment_title", language).format(
        author=author, channel=channel_label, posting=posting
    )


def get_title(posting_or_comment, language):
    if posting_or_comment.GetClassname() == "cdbblog_comment":
        return get_comment_title(posting_or_comment, language)
    elif posting_or_comment.GetClassname() == "cdbblog_system_posting":
        return get_system_posting_title(posting_or_comment, language)
    else:
        return get_posting_title(posting_or_comment, language)


def get_attachments(posting_or_comment):
    result = []
    for a in Attachment.KeywordQuery(posting_id=posting_or_comment.cdb_object_id):
        attachment = ByID(a.attachment_id)
        result.append(attachment)
    return result


def _get_posting(posting_or_comment):
    if isinstance(posting_or_comment, Comment):
        return posting_or_comment.Posting
    return posting_or_comment


def get_channel_ids(posting_or_comment):
    thread = _get_posting(posting_or_comment)
    channel_ids = []
    if thread.context_object_id:
        channel_ids.append(thread.context_object_id)
    for ta in thread.TopicAssignments:
        if thread.context_object_id and ta.topic_id != thread.context_object_id:
            channel_ids.append(ta.topic_id)
    return channel_ids


def find_channels(posting_or_comment):
    """
    Returns a list of channels that should receive this posting.
    """
    channel_ids = get_channel_ids(posting_or_comment)
    channel_cfgs = MSTeamsASAssignment.get_channel_cfg(channel_ids)
    result = set()
    is_comment = isinstance(posting_or_comment, Comment)
    for channel_cfg in channel_cfgs:
        if (
            (channel_cfg.transfer_comments and is_comment)
            or (
                channel_cfg.transfer_user_postings
                and posting_or_comment.cdb_classname == "cdbblog_user_posting"
            )
            or (
                channel_cfg.transfer_system_postings
                and posting_or_comment.cdb_classname == "cdbblog_system_posting"
            )
        ):
            result.add(channel_cfg.TeamsChannel)
    return result


def _cut_text(txt):
    """
    Applies the settings for max lines and max chars to the posting
    """
    pset = util.PersSettings()
    max_lines = int(
        pset.getValueOrDefaultForUser("msteams.posting_max_lines", "", "2", "")
    )
    if max_lines > 0:
        lines = txt.split("\n")
        count = 0
        not_empty_lines = 0
        for line in lines:
            count += 1
            if line:
                not_empty_lines += 1
            if not_empty_lines == int(max_lines):
                break
        if len(lines) > count:
            lines[count - 1] += " ..."
        txt = "\n".join(lines[:count])

    max_chars = int(
        pset.getValueOrDefaultForUser("msteams.posting_max_chars", "", "300", "")
    )
    if 0 < max_chars < len(txt):
        txt = txt[:max_chars] + "..."
    return txt


def create_message_card(posting_or_comment, language):
    title = get_title(posting_or_comment, language)
    txt = _cut_text(get_text(posting_or_comment))
    card = MessageCard(title, txt, language)
    title = util.get_label_with_fallback("ce_msteams_button_view_posting", language)
    posting = _get_posting(posting_or_comment)
    if posting:
        action_section = MessageCardSection()
        action_section.add_object_link(posting, title)
        card.add_section(action_section)
        # Add all channels this posting is assigned to

    channel_ids = get_channel_ids(posting_or_comment)
    if channel_ids:
        sect_title = util.get_label_with_fallback(
            "ce_msteams_section_title_assigned_channels", language
        )
        channel_section = MessageCardSection(sect_title)
        channels = getObjectHandlesFromObjectIDs(channel_ids)
        for channel in channel_ids:
            if channel in channels:
                obj = channels[channel]
            if obj:
                channel_section.add_object_link(obj)
        card.add_section(channel_section)
    # Actually we have decided not to add the attachments
    # attachments = get_attachments(posting_or_comment)
    # if attachments:
    #    section = MessageCardSection("Attachments", language=language)
    #    for attachment in attachments:
    #        section.add_object_link(attachment)
    #    card.add_section(section)
    return card


def handle_as_obj(obj, channel=None):
    """
    Transfers the given `obj` to the given `channel`.
    If `channel` is ``None`` the configuration is used to find the channels.
    """
    if channel is None:
        channels = find_channels(obj)
        if not channels:
            return
    else:
        channels = [channel]
    lang2card = {}
    for c in channels:
        card = lang2card.get(c.lang)
        if card is None:
            card = create_message_card(obj, c.lang)
            lang2card[c.lang] = card
        try:
            card.post(c)
        except RuntimeError as e:
            MSTeamsFailedJob.create_log_entry(c, obj, str(e))
