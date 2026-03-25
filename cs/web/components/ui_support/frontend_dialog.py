#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
API to define dialogs that are shown from a hook function in the frontend.
"""

__revision__ = "$Id$"


class FrontendDialog(object):
    """Used with
    :py:meth:`cs.web.components.ui_support.dialog_hooks.DialogHook.set_dialog`
    to display a dialog to the user.

    To specify an action for a button use the following class attributes.
    """

    #: Submit the operation to the backend
    ActionSubmit = 'SUBMIT'
    #: Cancel the operation
    ActionCancel = 'CANCEL'
    #: Cancel the operation without asking ...
    ActionForceCancel = 'FORCE_CANCEL'
    #: Call the backend hooks again
    ActionCallServer = 'CALL_SERVER'
    #: Show the operation dialog again
    ActionBackToDialog = 'BACK_TO_DIALOG'

    def __init__(self, title, text, argument_name=None):
        """The Buttons of a frontend dialog will modify an argument in the
        operation's state, the argument is specified via attribute
        `argument_name`.

        :param str title: The title of the dialog
        :param str text: The content of the dialog
        :param str argument_name: Determines the attribute that will store the value of
        """
        self.title = title
        self.text = text
        self.argument_name = argument_name
        self.buttons = []
        self.responsible_hook_name = None

    def add_button(self, label, value, action, is_default=False, is_cancel=False):
        """Add a button to the dialog `value` will be the value that is sent
        back to the server in the argument specified by `self.argument_name`.

        :param str label: The label of the button
        :param str value: The value sent to the server
        :param str action: One of the action constants above
        """
        self.buttons.append({"label": label,
                             "value": value,
                             "action": action,
                             "isDefault": is_default,
                             "isCancel": is_cancel})

    def set_hook_name(self, hook_name):
        self.responsible_hook_name = hook_name

    def to_json(self):
        return {"title": self.title,
                "text": self.text,
                "argumentName": self.argument_name,
                "buttons": self.buttons,
                "responsibleHookName": self.responsible_hook_name}
