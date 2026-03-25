#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import os

import six
from cdb import CADDOK, rte, sig, util
from cdb.objects.org import User
from cs.platform.web import static
from cs.platform.web.rest import CollectionApp, get_collection_app
from cs.platform.web.root import Root, get_root, get_v1
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK, BaseApp, BaseModel
from six.moves import urllib

from cs.activitystream import APP_MOUNT_PATH, CHANNEL_OVERVIEW_PATH
from cs.activitystream.objects import Channel, Comment, Posting, Subscription
from cs.activitystream.rest_app.main import get_activitystream
from cs.activitystream.rest_app.model import (
    ChannelCollection,
    MentionSubjectSearchModel,
    ObjectPostings,
    PersonSearchModel,
    PostingCollection,
    SubscriptionCollection,
)

__docformat__ = "restructuredtext en"

COMPONENTNAME = "cs-activitystream-web"


def _get_collection_app(request):
    return get_v1(request).child("collection")


class ASApp(BaseApp):
    client_favicon = "cdb_elink_activity"

    def update_app_setup(self, app_setup, model, request):
        super(ASApp, self).update_app_setup(app_setup, model, request)
        app_setup.merge_in(
            [COMPONENTNAME],
            {
                "channelOverviewURL": request.link(
                    ChannelCollection(),
                    app=get_activitystream(request),
                    name="overview",
                ),
                "channelContextType": Channel._getClassname(),  # pylint: disable=protected-access
                "allowCreatingChannel": Channel.allowCreatingChannel(),
                "instanceName": "standalone",
                "channelOverviewPath": CHANNEL_OVERVIEW_PATH,
            },
        )


class ASModel(BaseModel):
    def __init__(self, absorb=""):
        super(ASModel, self).__init__()
        self.absorb = absorb


@Root.mount(app=ASApp, path=APP_MOUNT_PATH)
def _mount_app():
    return ASApp()


@ASApp.path(model=ASModel, path="/", absorb=True)
def get_app_model(absorb):
    return ASModel(absorb)


@ASApp.view(model=ASModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label("cdbblog_elink_title_activities")


@ASApp.view(model=ASModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include(COMPONENTNAME, "15.1.0")
    return "%s-App" % COMPONENTNAME


@ASApp.view(model=ASModel, name="base_path", internal=True)
def get_base_path(self, request):
    return "/activitystream"


@ASApp.path(model=Posting, path="posting/{cdb_object_id}")
def _get_posting(cdb_object_id):
    """
    Only to generate the link to posting thread. Should be handled by
    client side routes.
    """
    return Posting.ByKeys(cdb_object_id)


@sig.connect(GLOBAL_APPSETUP_HOOK)
def update_app_setup(app_setup, request):
    postings = PostingCollection({})
    channels = ChannelCollection()
    subscriptions = SubscriptionCollection()
    topic_base = ObjectPostings(None, {})
    excl_topic_classes = (
        [Posting._getClassname()]  # pylint: disable=protected-access
        + list(
            Posting._getClassDef().getSubClassNames(  # pylint: disable=protected-access
                True
            )
        )
        + [Comment._getClassname()]  # pylint: disable=protected-access
        + list(
            Comment._getClassDef().getSubClassNames(  # pylint: disable=protected-access
                True
            )
        )
    )
    app_setup.merge_in(
        [COMPONENTNAME],
        {
            "dataURL": request.link(postings, app=get_activitystream(request)),
            "channelURL": request.link(channels, app=get_activitystream(request)),
            "subscriptionURL": request.link(
                subscriptions, app=get_activitystream(request)
            ),
            "topicURL": request.link(topic_base, app=get_activitystream(request)),
            "personSearchURL": request.link(
                PersonSearchModel(None), app=get_activitystream(request)
            ),
            "mentionSubjectSearchURL": request.link(
                MentionSubjectSearchModel(None), app=get_activitystream(request)
            ),
            "personDataURL": urllib.parse.unquote(
                request.class_link(
                    User, {"keys": "${persno}"}, app=get_collection_app(request)
                )
            ),
            "excludeTopicClasses": excl_topic_classes,
            "subscribersURL": request.class_link(
                Subscription,
                {"keys": "", "extra_parameters": {"_as_table": "cdbblog_subscribers"}},
                app=_get_collection_app(request),
            )
            + "&$filter=channel_cdb_object_id eq '${topic_id}'",
        },
    )


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENTNAME, "15.1.0", os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("%s.js" % COMPONENTNAME)
    lib.add_file("%s.js.map" % COMPONENTNAME)
    static.Registry().add(lib)

    stories = COMPONENTNAME + "-stories"
    lib = static.Library(
        stories, "15.1.0", os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("%s.js" % stories)
    lib.add_file("%s.js.map" % stories)
    static.Registry().add(lib)

    from cs.web.components.storybook.main import add_stories

    add_stories((COMPONENTNAME, "15.1.0"), (stories, "15.1.0"))


# register UI link for posting objects by REST API
@CollectionApp.view(model=Posting, name="ui_link", internal=True)
def _get_posting_ui_link(posting, request):
    return six.moves.urllib.parse.unquote(
        request.link(posting, app=get_root(request).child("activitystream"))
    )


def get_posting_link(posting):

    from cs.platform.web.uisupport import get_webui_link
    from morepath import Request

    return get_webui_link(Request.blank(CADDOK.WWWSERVICE_URL, app=Root()), posting)
