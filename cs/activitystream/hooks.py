# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
The module provides support for calling the AS hooks, e. g.
the ``ASChannelAction`` hook.
"""

__docformat__ = "restructuredtext en"
# Exported objects
__all__ = ["ASChannelActionContext"]

import logging

from cdb.platform.mom.hooks import PowerscriptHook


def call_channelaction_hook(ctx):
    """
    Calls the ``ASChannelAction`` powerscript hook.

    :param ctx: A `ASChannelActionContext` object.
    """
    callables = PowerscriptHook.get_active_callables("ASChannelAction")
    for c in callables:
        logging.debug("Calling ASChannelAction Hook")
        try:
            c(ctx)
        except Exception as e:  # pylint: disable=W0703
            logging.error("Call of ASChannelAction failed with: %s", e)


class ASChannelActionContext(object):
    def __init__(self, obj, created):
        """
        Initializes a context.

        :param obj:
            The created or modified object. This is a `cdb.objects.Object`
            object that represents a comment, posting or system posting

        :param created:
            A bool that is ``True`` if the user has created a new posting entry
            and ``False`` if a posting or comment has been updated.
        """
        self.object = obj
        self.created = created

    def get_object(self):
        """
        Retrieve the object the action belongs to. This is a posting or comment
        object.
        """
        return self.object

    def is_create(self):
        """
        Returns ``True`` if the posting or comment has been created with this
        action and ``False`` if it has been modified.
        """
        return self.created

    def is_user_posting(self):
        """
        Returns ``True`` for user posting actions.
        """
        return self.object and self.object.GetClassname() == "cdbblog_user_posting"

    def is_system_posting(self):
        """
        Returns ``True`` for system posting actions.
        """
        return self.object and self.object.GetClassname() == "cdbblog_user_posting"

    def is_comment(self):
        """
        Returns ``True`` for system posting actions.
        """
        return self.object and self.object.GetClassname() == "cdbblog_comment"


# Guard importing as main module
if __name__ == "__main__":
    pass
