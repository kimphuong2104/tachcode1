# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import datetime
import json
import logging

import morepath
import six
from cdb import auth, constants, sqlapi, typeconversion, util
from cdb.dberrors import ElementsError
from cdb.misc import getClientUTCOffset
from cdb.objects import ByID, Object, cdb_file
from cdb.platform import mom
from cdb.storage.index.errors import ESException
from cs.platform.web.rest import support
from cs.platform.web.rest.generic.model import FileCollection
from cs.platform.web.root import get_root, get_v1
from cs.platform.web.uisupport import get_ui_link
from webob.exc import HTTPInternalServerError, HTTPUnprocessableEntity

from cs.activitystream import hooks
from cs.activitystream.mention import InvalidRecipientsError, Mention
from cs.activitystream.objects import (
    Comment,
    Posting,
    Subscription,
    SystemPosting,
    Topic2Posting,
)
from cs.sharing import Sharing

from .main import ActivityStreamApp
from .model import (
    Attachments,
    ChannelCollection,
    CommentAttachments,
    CommentReactionModel,
    MentionSubjectSearchModel,
    Navigation,
    NavigationSubmenu,
    ObjectPostings,
    PersonSearchModel,
    PostingAttachments,
    PostingCollection,
    PostingComments,
    PostingReactionModel,
    PostingTopics,
    SharingChannel,
    SharingCollection,
    SubscriptionCategoryBase,
    SubscriptionCollection,
    ToAllChannel,
    ToAllChannelPostings,
)

# cache generated person views and links for current session
# to boost the performance
PERSON_VIEW_CACHE = {}
PERSON_LINK_CACHE = {}

log = logging.getLogger(__name__)


def _get_collection_app(request):
    return get_v1(request).child("collection")


def _get_person_view(request, person):
    if not person:
        return None
    if person.personalnummer not in PERSON_VIEW_CACHE:
        PERSON_VIEW_CACHE[person.personalnummer] = request.view(
            person, app=_get_collection_app(request)
        )

    result = PERSON_VIEW_CACHE[person.personalnummer]
    result["thumb_src"] = _get_thumbnail_from_user(person, request)
    return result


def _get_person_link(request, person):
    if not person:
        return None
    if person.personalnummer not in PERSON_LINK_CACHE:
        PERSON_LINK_CACHE[person.personalnummer] = get_ui_link(request, person)
    return PERSON_LINK_CACHE[person.personalnummer]


def _call_action_hook(obj, created):
    ctx = hooks.ASChannelActionContext(obj, created)
    hooks.call_channelaction_hook(ctx)


@ActivityStreamApp.json(model=PostingCollection)
def postings_get(posting_collection, request):
    queried = posting_collection.query()
    postings = [request.view(obj) for obj in queried[0]]
    return {
        "@id": request.link(posting_collection),
        "default_topic": ToAllChannel().GetDescription(),
        "postings": postings,
        "result_complete": queried[1],
    }


def _mention_user(posting, request, comment_id=None):
    if "mention_subjects" in list(request.json):
        try:
            Mention.mentionUsers(
                request.json["mention_subjects"], posting.cdb_object_id, comment_id
            )
        except InvalidRecipientsError as e:
            log.error("Error while mentioning users: %s", e)


@ActivityStreamApp.json(model=PostingCollection, request_method="POST")
def posting_new(self, request):
    if "text" not in list(request.json) or len(request.json["text"]) < 1:
        raise HTTPUnprocessableEntity()
    posting = self.add_posting(request.json["text"])
    _add_attachments(PostingAttachments(posting), request)
    if "topic_ids" in list(request.json):
        PostingTopics(posting).set_topics(request.json["topic_ids"])
    _mention_user(posting, request)
    _call_action_hook(posting, True)
    return request.view(posting)


@ActivityStreamApp.json(model=Posting)
def posting_get(self, request):
    """Get a posting."""
    is_system_posting = isinstance(self, SystemPosting)
    files = None
    upload_url = ""
    is_deleted = bool(self.is_deleted)
    context_object_designation = None
    if not is_system_posting and not is_deleted:
        generic_as = _get_collection_app(request).child(
            "{rest_name}", rest_name="activitystream"
        )
        files = request.view(FileCollection(self), app=generic_as)
        if self.cdb_cpersno == auth.persno:
            upload_url = request.link(self, app=generic_as) + "/files"
    elif self.context_object_id:
        cdb_object_handle = mom.getObjectHandleFromObjectID(self.context_object_id)
        if cdb_object_handle:
            context_object_designation = cdb_object_handle.getDesignation()

    # This access check could be optimized if it becomes a performance
    # problem. Options:
    # 1. Cache access rights per posting cdb_object_id
    # 2. Hard-coding access conditions (own postings or
    #    administrator), not customizable
    # 3. Creating a separate view for deleted postings with "empty"
    #    relationships, makes customizing harder
    has_access = self.CheckAccess(constants.kAccessSave)
    editable = (
        has_access
        and self.ToObjectHandle().getOperationInfo(constants.kOperationModify)
        is not None
    )

    topics = request.view(PostingTopics(self)) if has_access or not is_deleted else None

    reactions = self.get_reaction_ids()

    result = {
        "@id": request.link(self),
        "cdb_object_id": self.cdb_object_id,
        "context_object_designation": context_object_designation,
        "system:navigation_id": support.rest_key(self),
        "text": self.GetText("cdbblog_posting_txt"),
        "icon": self.GetClassIcon(),
        "title": self.GetDescription(),
        "datetime": self.cdb_cdate.isoformat(),
        "cdb_mdate": self.cdb_mdate.isoformat(),
        "last_comment_date": self.last_comment_date.isoformat(),
        "author": _get_person_view(request, self.Author),
        "comments": request.view(PostingComments(self)),
        "topics": topics,
        "attachments": request.view(PostingAttachments(self)),
        "is_system_posting": is_system_posting,
        "system:ui_link": request.link(
            self, app=get_root(request).child("activitystream")
        ),
        "relship:files": files,
        "file_upload_url": upload_url,
        "is_deleted": is_deleted,
        "removed": self.is_deleted and self.cdb_mpersno != self.cdb_cpersno,
        "editable": editable,
        "allow_reactions": True if not is_system_posting else False,
        "my_reaction": "like" if auth.persno in reactions else None,
        "number_of_reactions": {"like": len(reactions)},
    }
    return result


@ActivityStreamApp.json(model=Posting, request_method="DELETE")
def posting_delete(self, request):
    """
    Delete posting contents
    """
    if isinstance(self, SystemPosting):
        raise HTTPUnprocessableEntity()

    self.deleteEntry()
    return request.view(self)


@ActivityStreamApp.json(model=Posting, request_method="PUT")
def posting_update(self, request):
    """
    Update and/or restore posting
    """
    if isinstance(self, SystemPosting):
        raise HTTPUnprocessableEntity()

    if self.is_deleted and request.json.get("is_deleted") == 0:
        self.restoreEntry()
    else:
        # Update text
        text = request.json.get("text", "")
        if not text:
            raise HTTPUnprocessableEntity()
        modify_args = {"cdbblog_posting_txt": text}
        # Update topics
        topic_ids = request.json.get("topic_ids", [])
        modified = PostingTopics(self).set_topics(topic_ids)
        if modified:
            modify_args["cdb_mdate"] = typeconversion.to_legacy_date_format(
                datetime.datetime.utcnow()
            )
            modify_args["cdb_mpersno"] = auth.persno
        self.modifyEntry(**modify_args)
        # Update attchment
        attachment_ids = request.json.get("attachment_ids", [])
        PostingAttachments(self).set_attachments(attachment_ids)
        # Update mention
        _mention_user(self, request)
        # clean up unused files(pictures, videos)
        saved_files = request.json.get("saved_files", [])
        prev_ones = cdb_file.CDB_File.Query(
            (cdb_file.CDB_File.cdbf_object_id == self.cdb_object_id)
            & (cdb_file.CDB_File.cdbf_name.not_one_of(*saved_files))
        )
        for f in prev_ones:
            f.delete_file()
        _call_action_hook(self, False)

    return request.view(self)


@ActivityStreamApp.json(model=PostingComments)
def comments_get(obj_collection, request):
    """Get a listing of comments for a posting."""
    objs = [request.view(obj) for obj in obj_collection.query()]
    return {
        "@id": request.link(obj_collection),
        "comments": objs,
        "result_complete": True,
    }


def _add_comment(col, request, reply_to=None):
    if "text" in list(request.json) and request.json["text"]:
        if not reply_to:
            comment = col.add_comment(request.json["text"])
        else:
            comment = col.add_reply_to(request.json["text"], reply_to)
        _add_attachments(CommentAttachments(comment), request)
        # Handle user mention
        _mention_user(col.posting, request, comment.cdb_object_id)
        _call_action_hook(comment, True)
        # Return newly created entry instead of collection
        return request.view(comment)
    else:
        raise HTTPUnprocessableEntity()


@ActivityStreamApp.json(model=PostingComments, request_method="POST")
def comment_new(self, request):
    return _add_comment(self, request)


@ActivityStreamApp.json(model=Comment)
def comment_get(self, request):
    """Get a comment."""
    is_deleted = bool(self.is_deleted)
    reply_to_comment = self.ReplyTo
    if reply_to_comment is not None:
        reply_to_author = _get_person_link(request, reply_to_comment.Author)
    else:
        reply_to_author = None
    generic_as = _get_collection_app(request).child(
        "{rest_name}", rest_name="activitystream_comment"
    )
    files = None
    upload_url = ""
    if generic_as and not is_deleted:
        files = request.view(FileCollection(self), app=generic_as)
        if self.cdb_cpersno == auth.persno:
            upload_url = request.link(self, app=generic_as) + "/files"

    # See comment to equivalent access check for postings (posting_get) regarding performance
    has_access = self.CheckAccess(constants.kAccessSave)
    editable = (
        has_access
        and self.ToObjectHandle().getOperationInfo(constants.kOperationModify)
        is not None
    )

    reactions = self.get_reaction_ids()

    return {
        "@id": request.link(self),
        "cdb_object_id": self.cdb_object_id,
        "text": self.GetText("cdbblog_comment_txt"),
        "reply_to": request.link(reply_to_comment),
        "reply_to_author": reply_to_author,
        "posting_id": request.link(self.Posting),
        "datetime": self.cdb_cdate.isoformat(),
        "cdb_mdate": self.cdb_mdate.isoformat(),
        "author": _get_person_view(request, self.Author),
        "attachments": request.view(CommentAttachments(self)),
        "relship:files": files,
        "file_upload_url": upload_url,
        "is_deleted": is_deleted,
        "removed": self.is_deleted and self.cdb_mpersno != self.cdb_cpersno,
        "editable": editable,
        "allow_reactions": True,
        "my_reaction": "like" if auth.persno in reactions else None,
        "number_of_reactions": {"like": len(reactions)},
    }


@ActivityStreamApp.json(model=Comment, request_method="POST")
def reply_new(self, request):
    return _add_comment(PostingComments(self.Posting), request, self)


@ActivityStreamApp.json(model=Comment, request_method="DELETE")
def comment_delete(self, request):
    """
    Delete comment contents
    """
    self.deleteEntry()
    return request.view(self)


@ActivityStreamApp.json(model=Comment, request_method="PUT")
def comment_update(self, request):
    """
    Update and/or restore comment
    """

    if self.is_deleted and request.json.get("is_deleted") == 0:
        self.restoreEntry()
    else:
        # Update text
        text = request.json.get("text", "")
        if not text:
            raise HTTPUnprocessableEntity()
        self.modifyEntry(cdbblog_comment_txt=text)
        # Update attachments
        attachment_ids = request.json.get("attachment_ids", [])
        CommentAttachments(self).set_attachments(attachment_ids)
        # Update mention
        _mention_user(self.Posting, request, self.cdb_object_id)
        # clean up unused files(pictures, videos)
        saved_files = request.json.get("saved_files", [])
        prev_ones = cdb_file.CDB_File.Query(
            (cdb_file.CDB_File.cdbf_object_id == self.cdb_object_id)
            & (cdb_file.CDB_File.cdbf_name.not_one_of(*saved_files))
        )
        for f in prev_ones:
            f.delete_file()
        _call_action_hook(self, False)
    return request.view(self)


@ActivityStreamApp.json(model=PostingReactionModel, request_method="GET")
def _get_posting_reactions(self, request):
    posting = self.reaction_to
    return {"users": _get_users_view(request, posting)}


@ActivityStreamApp.json(model=PostingReactionModel, request_method="PUT")
def _add_posting_reaction(self, request):
    posting = self.reaction_to
    self.add_reaction()
    return {
        "posting": request.view(posting),
        "users": _get_users_view(request, posting),
    }


@ActivityStreamApp.json(model=PostingReactionModel, request_method="DELETE")
def _remove_posting_reaction(self, request):
    posting = self.reaction_to
    self.remove_reaction()
    return {
        "posting": request.view(posting),
        "users": _get_users_view(request, posting),
    }


@ActivityStreamApp.json(model=CommentReactionModel, request_method="GET")
def _get_comment_reactions(self, request):
    comment = self.reaction_to
    return {"users": _get_users_view(request, comment)}


@ActivityStreamApp.json(model=CommentReactionModel, request_method="PUT")
def _add_comment_reaction(self, request):
    comment = self.reaction_to
    self.add_reaction()
    return {
        "posting": request.view(comment.Posting),
        "users": _get_users_view(request, comment),
    }


@ActivityStreamApp.json(model=CommentReactionModel, request_method="DELETE")
def _remove_comment_reaction(self, request):
    comment = self.reaction_to
    self.remove_reaction()
    return {
        "posting": request.view(comment.Posting),
        "users": _get_users_view(request, comment),
    }


def _get_users_view(request, activity_entry):
    users = activity_entry.get_reactions()
    return [_get_person_view(request, user) for user in users]


def _object_view(obj, request):
    """mini object view"""
    return {
        "@id": request.link(obj),
        "cdb_object_id": obj.cdb_object_id,
        "description": obj.GetDescription(),
        "object_icon": obj.GetObjectIcon(),
        "class_icon": obj.GetClassIcon(),
    }


def _subscribable_object_view(self, request):
    """object view with thumbnail"""
    result = _object_view(self, request)
    coll_app = _get_collection_app(request)
    thumbnail = self.GetThumbnailFile()
    link = ""
    if thumbnail:
        link = request.link(thumbnail, app=coll_app)
    result.update(thumbnail=link)
    clsdef = self.GetClassDef()
    rest_key = support.rest_key(self)
    result["class_title"] = clsdef.getDesignation()
    result["system:classname"] = clsdef.getClassname()
    result["system:navigation_id"] = rest_key
    result["subscribe_operation"] = "CDB_SubscribeToChannel"
    ctx_obj = support.get_object_from_rest_name(clsdef.getRESTName(), rest_key)
    result["rest_link"] = support.get_restlink(ctx_obj, request)
    cond = "channel_cdb_object_id='%s' and personalnummer='%s'" % (
        sqlapi.quote(self.cdb_object_id),
        sqlapi.quote(auth.persno),
    )
    if Subscription.Query(condition=cond, access="read"):
        # subscribed, can be unsubscribe
        result["subscribe_operation"] = "CDB_UnsubscribeFromChannel"
    return result


@ActivityStreamApp.json(model=Object, name="with_ui_links")
def object_view_with_links(obj, request):
    """object view with UI links"""
    _view = _object_view(obj, request)
    obj_link = obj_ui_link = ""
    # UI link to the real business object referenced as topic
    if isinstance(obj, Posting):
        obj_ui_link = request.link(obj, app=get_root(request).child("activitystream"))
    else:
        try:
            obj_link = request.link(obj, app=_get_collection_app(request))
        except morepath.error.LinkError as exc:
            log.debug("object_view_with_links: %s", exc)
        obj_ui_link = get_ui_link(request, obj) or ""
    _view.update({"object_id": obj_link, "object_ui_link": obj_ui_link})
    return _view


@ActivityStreamApp.json(model=Object, name="compact")
def object_get_compact(self, request):
    """mini object view"""
    return _object_view(self, request)


@ActivityStreamApp.json(model=Object)
def object_get(self, request):
    """object view with referenced postings"""
    _view = _subscribable_object_view(self, request)
    queried = ObjectPostings(self.cdb_object_id, request.params.mixed()).query()
    postings = [request.view(obj) for obj in queried[0]]

    _view.update({"postings": postings, "result_complete": queried[1]})
    return _view


@ActivityStreamApp.json(model=Object, name="no_postings")
def object_get_no_postings(self, request):
    """object view without referenced postings"""
    return _subscribable_object_view(self, request)


@ActivityStreamApp.json(model=Topic2Posting, internal=True)
def topic2posting_get(self, request):
    """Get a topic for a posting.
    Deprecated: It would be called nowhere.
    """
    topic = ByID(self.topic_id)
    if not topic.CheckAccess("read"):
        return None
    return request.view(topic, name="with_ui_links")


@ActivityStreamApp.json(model=Sharing, name="with_ui_links")
def sharing_get(self, request):
    view = object_view_with_links(self, request)
    users = self.getSubscriptionUsers()
    subscribers = []
    for user in users:
        _view = request.view(user, name="with_ui_links")
        _view.update({"firstname": user["firstname"], "lastname": user["lastname"]})
        subscribers.append(_view)

    cdb_cdate = (
        typeconversion.to_user_repr_date_format(
            self.cdb_cdate + datetime.timedelta(minutes=getClientUTCOffset())
        )
        if self.cdb_cdate is not None
        else "(Undefined date)"
    )
    description = util.Labels()["cdbblog_sharing_description"].format(
        mapped_cpersno=self.mapped_cpersno, cdb_cdate=cdb_cdate
    )
    view.update({"subscribers": subscribers, "description": description})
    return view


@ActivityStreamApp.json(model=PostingTopics)
def topics_get(obj_collection, request):
    topics = [
        request.view(topic, name="with_ui_links") for topic in obj_collection.query()
    ]
    return {
        "topics": topics,
        "@id": request.link(obj_collection),
        "result_complete": True,
    }


@ActivityStreamApp.json(model=Object, request_method="POST")
def topic_posting_new(self, request):
    """Add a posting to an object."""
    col = ObjectPostings(self.cdb_object_id, {})
    return posting_new(col, request)


@ActivityStreamApp.json(model=ChannelCollection, request_method="GET")
def channels_get(obj_collection, request):
    predef, normal = obj_collection.query()
    predef_channels = [request.view(obj, name="compact") for obj in predef]
    channels = sorted(
        [request.view(obj, name="compact") for obj in normal],
        key=lambda c: c["description"],
    )
    return {
        "@id": request.link(obj_collection),
        "predefined": predef_channels,
        "channels": channels,
        "result_complete": True,
    }


@ActivityStreamApp.json(model=ChannelCollection, request_method="GET", name="overview")
def channel_overview_get(obj_collection, request):
    _, normal = obj_collection.query(True)
    channels = sorted(
        [_subscribable_object_view(obj, request) for obj in normal],
        key=lambda c: c["description"],
    )
    return {
        "@id": request.link(obj_collection),
        "channels": channels,
        "result_complete": True,
    }


@ActivityStreamApp.json(model=SubscriptionCollection, request_method="GET")
def subscriptions_get(subscr_collection, request):
    groups = subscr_collection.query()
    subscriptions = []
    for grp in groups:
        subscriptions.append(request.view(grp))
    return {
        "@id": request.link(subscr_collection),
        "subscriptions": subscriptions,
        "result_complete": True,
    }


@ActivityStreamApp.json(model=SharingChannel, name="compact")
def sharing_get_compact(self, request):
    """Get a topic."""
    return _object_view(self, request)


@ActivityStreamApp.json(model=SharingChannel, name="with_ui_links")
def sharing_get_with_links(self, request):
    """Get a topic."""
    _view = _object_view(self, request)
    _view.update({"object_id": "", "object_ui_link": ""})
    return _view


@ActivityStreamApp.json(model=SharingChannel, name="no_postings")
def sharing_get_no_postings(self, request):
    _view = _object_view(self, request)
    _view.update(
        {
            "class_title": self.GetClassTitle(),
        }
    )
    return _view


@ActivityStreamApp.json(model=SharingChannel)
def sharing_get(self, request):
    """Get postings of 'To All' channel."""
    _view = _object_view(self, request)
    queried = SharingCollection(request.params.mixed()).query()
    objs = [request.view(obj) for obj in queried[0]]
    _view.update(
        {
            "class_title": self.GetClassTitle(),
            "postings": objs,
            "result_complete": queried[1],
        }
    )
    return _view


@ActivityStreamApp.json(model=Attachments)
def attachments_get(obj_collection, request):
    views = [request.view(obj, name="with_ui_links") for obj in obj_collection.query()]
    return {
        "attachments": [aview for aview in views if aview is not None],
        "@id": request.link(obj_collection),
        "addable": obj_collection.modifiable(),
        "result_complete": True,
    }


def _add_attachments(col, request):
    if "attachment_ids" in list(request.json) and request.json["attachment_ids"]:
        col.add_attachments(request.json["attachment_ids"])
        return True
    else:
        return False


def _get_thumbnail_from_user(user, request):
    """
    Helper for retrieving the thumbnail for an instance of User. Will return
    an empty string if no thumbnail file is set.
    """
    thumb_file = user.GetThumbnailFile()
    if thumb_file is None:
        return ""

    return request.link(thumb_file, app=_get_collection_app(request))


@ActivityStreamApp.json(model=Attachments, request_method="POST")
def attachment_new(self, request):
    if _add_attachments(self, request):
        return request.view(self)
    else:
        raise HTTPUnprocessableEntity()


@ActivityStreamApp.json(model=ToAllChannel, name="compact")
def toall_get_compact(self, request):
    """Get a topic."""
    return _object_view(self, request)


@ActivityStreamApp.json(model=ToAllChannel, name="with_ui_links")
def toall_get_with_links(self, request):
    """Get a topic."""
    _view = _object_view(self, request)
    _view.update({"object_id": "", "object_ui_link": ""})
    return _view


@ActivityStreamApp.json(model=ToAllChannel, name="no_postings")
def toall_get_no_postings(self, request):
    _view = _object_view(self, request)
    _view.update(
        {
            "class_title": self.GetClassTitle(),
        }
    )
    return _view


@ActivityStreamApp.json(model=ToAllChannel)
def toall_get(self, request):
    """Get postings of 'To All' channel."""
    _view = _object_view(self, request)
    queried = ToAllChannelPostings(request.params.mixed()).query()
    objs = [request.view(obj) for obj in queried[0]]
    _view.update(
        {
            "class_title": self.GetClassTitle(),
            "postings": objs,
            "result_complete": queried[1],
        }
    )
    return _view


@ActivityStreamApp.json(model=ToAllChannel, request_method="POST")
def toall_post(self, request):
    return posting_new(self, request)


@ActivityStreamApp.json(model=PersonSearchModel)
@ActivityStreamApp.json(model=MentionSubjectSearchModel)
def search_person_get(self, request):
    """Get search result for topic or attachment object."""

    def error_reply(err):
        return request.ResponseClass(
            json.dumps(six.text_type(err)),
            status=HTTPInternalServerError.code,
            content_type="application/json",
        )

    try:
        query_result = self.query()
        query_result["result"] = [
            {"cs_activitystream_data": _get_person_view(request, entry)}
            for entry in query_result["result"]
        ]
        return {"result": query_result}
    except ESException as e:
        log.exception("Enterprise Search: %s", e)
        return error_reply(e)
    except ElementsError as ee:
        log.exception("Elements Error: %s", ee)
        return error_reply(ee)


# filter categories
@ActivityStreamApp.json(model=SubscriptionCategoryBase)
def subscription_category(self, request):
    return {
        "description": self.title,
        "icon": self.icon,
        "subscriptions": [
            request.view(obj, name="compact") for obj in self.get_objects()
        ],
    }


@ActivityStreamApp.json(model=Navigation)
def navigation(self, request):
    return self.get_navigation(request).frontEndModuleList()


@ActivityStreamApp.json(model=NavigationSubmenu)
def navigation_submenu(self, request):
    return self.render(request)
