# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

from cdb import constants
from cdb.objects import ByID, Object

from cs.activitystream.objects import Comment, Posting

from .main import ActivityStreamApp
from .model import (
    ChannelCollection,
    CommentAttachments,
    CommentReactionModel,
    MentionSubjectSearchModel,
    Navigation,
    NavigationChannel,
    NavigationSubscription,
    ObjectPostings,
    PersonSearchModel,
    PostingAttachments,
    PostingCollection,
    PostingComments,
    PostingReactionModel,
    PostingTopics,
    SharingChannel,
    SubscriptionCollection,
    ToAllChannel,
)


@ActivityStreamApp.path(path="posting", model=PostingCollection)
def get_postings(extra_parameters):
    return PostingCollection(extra_parameters)


@ActivityStreamApp.path(
    path="posting/{posting_id}",
    model=Posting,
    variables=lambda p: {"posting_id": p.cdb_object_id},
)
def get_posting(posting_id):
    posting = Posting.ByKeys(posting_id)
    if posting and posting.CheckAccess(constants.kAccessRead):
        return posting
    return None


@ActivityStreamApp.path(
    path="posting/{posting_id}/comment",
    model=PostingComments,
    variables=lambda c: {"posting_id": c.posting.cdb_object_id},
)
def get_comments(posting_id):
    posting = get_posting(posting_id)
    if posting is None:
        return None
    return PostingComments(posting)


@ActivityStreamApp.path(
    path="posting/{posting_id}/comment/{comment_id}",
    model=Comment,
    variables=lambda c: {"comment_id": c.cdb_object_id, "posting_id": c.posting_id},
)
def get_comment(posting_id, comment_id):
    comment = Comment.ByKeys(comment_id)
    if comment and comment.CheckAccess(constants.kAccessRead):
        return comment
    return None


@ActivityStreamApp.path(
    path="/posting/{posting_id}/reactions", model=PostingReactionModel
)
def _posting_reaction(posting_id):
    posting = get_posting(posting_id)
    if posting is None:
        return None
    return PostingReactionModel(posting)


@ActivityStreamApp.path(
    path="/posting/{posting_id}/comment/{comment_id}/reactions",
    model=CommentReactionModel,
)
def _comment_reaction(posting_id, comment_id):
    comment = get_comment(posting_id, comment_id)
    if comment is None:
        return None
    return CommentReactionModel(comment)


@ActivityStreamApp.path(
    path="posting/{posting_id}/topic",
    model=PostingTopics,
    variables=lambda c: {"posting_id": c.posting.cdb_object_id},
)
def get_topics(posting_id):
    posting = get_posting(posting_id)
    if posting is None:
        return []
    return PostingTopics(posting)


@ActivityStreamApp.path(
    path="posting/{posting_id}/attachment",
    model=PostingAttachments,
    variables=lambda c: {"posting_id": c.entry.cdb_object_id},
)
def get_posting_attachments(posting_id):
    posting = get_posting(posting_id)
    if posting is None:
        return []
    return PostingAttachments(posting)


@ActivityStreamApp.path(
    path="posting/{posting_id}/comment/{comment_id}/attachment",
    model=CommentAttachments,
    variables=lambda c: {
        "posting_id": c.entry.posting_id,
        "comment_id": c.entry.cdb_object_id,
    },
)
def get_comment_attachments(posting_id, comment_id):
    comment = get_comment(posting_id, comment_id)
    if comment is None:
        return []
    return CommentAttachments(comment)


@ActivityStreamApp.path(path="topic", model=ObjectPostings)
def get_topic_base():
    """
    Only to generate the base part of link for object stream, which can be used
    in UI e.g for client side routing. No default views.
    """
    return ObjectPostings(None, {})


@ActivityStreamApp.path(path="topic/to_all", model=ToAllChannel)
def get_to_all():
    return ToAllChannel()


@ActivityStreamApp.path(path="topic/sharing", model=SharingChannel)
def get_sharing_channel():
    return SharingChannel()


@ActivityStreamApp.path(
    path="topic/{topic_id}",
    model=Object,
    variables=lambda t: {"topic_id": t.cdb_object_id},
)
def get_topic(topic_id):
    return ByID(topic_id)


@ActivityStreamApp.path(path="channel", model=ChannelCollection)
def get_channels():
    return ChannelCollection()


@ActivityStreamApp.path(path="subscription", model=SubscriptionCollection)
def get_subscriptions():
    return SubscriptionCollection()


@ActivityStreamApp.path(path="search/person", model=PersonSearchModel)
def get_person_search(extra_parameters):
    return PersonSearchModel(extra_parameters)


@ActivityStreamApp.path(path="search/mention_subject", model=MentionSubjectSearchModel)
def get_mention_subject_search(extra_parameters):
    return MentionSubjectSearchModel(extra_parameters)


@ActivityStreamApp.path(path="navigation", model=Navigation)
def get_navigation():
    return Navigation()


@ActivityStreamApp.path(path="navigation/channel", model=NavigationChannel)
def get_navigation():
    return NavigationChannel()


@ActivityStreamApp.path(path="navigation/subscription", model=NavigationSubscription)
def get_navigation(name=""):
    return NavigationSubscription(name)
