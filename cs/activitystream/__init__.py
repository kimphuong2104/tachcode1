#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import logging

import six
from cdb import misc
from cdb.classbody import classbody
from cdb.objects import Object, Rule

from cs.activitystream.activitylistener import ActivityListener
from cs.activitystream.objects import (
    Comment,
    Posting,
    Subscription,
    SystemPosting,
    Topic2Posting,
    UserPosting,
)

__all__ = [
    "PostingRuleChecker",
    "create_system_posting",
    "APP_MOUNT_PATH",
    "CHANNEL_OVERVIEW_PATH",
    "DEFAULT_POSTING_COUNT",
    # Deprecated - import these from cs.activitystream.objects:
    "Comment",
    "Posting",
    "Subscription",
    "SystemPosting",
    "Topic2Posting",
    "UserPosting",
]
__docformat__ = "restructuredtext en"

log = logging.getLogger(__name__)

# How many postings can be listed by default
DEFAULT_POSTING_COUNT = 20

APP_MOUNT_PATH = "activitystream"
CHANNEL_OVERVIEW_PATH = "channels"


@classbody
class Object(object):
    def GetActivityStreamTopics(self, posting):
        """
        If a posting is generated within the activity stream that
        belongs to `self` this method is called to ask for the topics
        the posting should be assigned to. `posting` is the
        `cs.activitystream.Posting` object the topics are assigned to.
        The method returns a list. The elements of the list are
        strings containing an UUID (cdb_object_id) or objects of
        the type `cdb.objects.Object`. Empty strings or ``None``
        elements will be ignored by the caller. All other entries represents
        the topics the posting will be assigned to.
        The default implementation
        returns [self]. You may overwrite the method
        to assign the posting to additional objects, e.g. like this: ::

           def GetActivityStreamTopics(self, posting):
              return [self, self.Project]

        """
        return [self.cdb_object_id]


@six.add_metaclass(misc.Singleton)
class PostingRuleChecker(object):
    RULES_CACHE = {}

    def _get_rule(self, pyrule):
        """
        Retrieve the `cdb.objects.Rule` object. To increase the performance
        the rules are cached.
        """
        rule = self.RULES_CACHE.get(pyrule, None)
        if not rule:
            rule = Rule.ByKeys(pyrule)
            if rule:
                self.RULES_CACHE[pyrule] = rule
        return rule

    def _checkRule(self, pyrule, oh):
        """
        Checks whether `oh` matches the rule identified by the rule's name
        given in `pyrule`.
        """
        rule = self._get_rule(pyrule)
        result = True
        if not rule:
            log.error(
                "Invalid rule '%s' when evaluating activity stream " "rules", pyrule
            )
            result = False
        else:
            result = rule.match(oh)
        return result

    def checkRules(self, oh):
        """
        Checks whether `oh` matches all rules that are specified for a system
        posting of the objects class within the data dictionary.
        """
        cldef = oh.getClassDef()
        result = True
        for pyrule in cldef.getSysPostingRules():
            if not self._checkRule(pyrule, oh):
                result = False
                break
        return result


def create_system_posting(cdb_object, msg_label, check_rules=True):
    """
    Creates a system posting. `cdb_object` can either be an instance of
    `cdb.objects.Object` or a `cdb.platform.mom.CDBObjectHandle`. `msg_label`
    defines the message label to use. `check_rules` is optional and set to
    ``True`` by default. If it is set to ``True`` all related rules will be
    checked before the posting job is created. Otherwise the job will be
    created directly without further checks.
    """
    handle = None

    try:
        handle = cdb_object.ToObjectHandle()
    except AttributeError:
        handle = cdb_object

    if not check_rules or PostingRuleChecker().checkRules(handle):
        ActivityListener().create_posting_job(None, handle, msg_label)
