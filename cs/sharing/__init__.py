#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import base64
import json
import logging
import os

import cdbwrapc
import six
from cdb import CADDOK, constants, i18n, sig, sqlapi, util
from cdb.classbody import classbody
from cdb.cmsg import Cdbcmsg
from cdb.objects import (
    ByID,
    Forward,
    Object,
    Reference_1,
    Reference_N,
    ReferenceMethods_1,
    ReferenceMethods_N,
)
from cdb.objects.common import RecipientDirectory, WithMultilanguageNotification
from cdb.objects.operations import operation
from cdb.objects.org import User
from cdb.platform.gui import Label, Message

from cs.activitystream.attachment import Attachment
from cs.activitystream.objects import Posting, SystemPosting, UserPosting
from cs.activitystream.posting_text_content_type import PostingTextConverter
from cs.sharing.groups import RecipientCollection, isUserVisible

__docformat__ = "restructuredtext en"

log = logging.getLogger(__name__)

fSharing = Forward(__name__ + ".Sharing")
fSharingGroup = Forward("cs.sharing.groups.SharingGroup")
fSharingGroupMember = Forward("cs.sharing.groups.SharingGroupMember")
fPosting = Forward("cs.activitystream.objects.Posting")
fSubscription = Forward("cs.activitystream.objects.Subscription")
fAttachment = Forward("cs.activitystream.attachment.Attachment")
fUser = Forward("cdb.objects.org.User")
fObject = Forward("cdb.objects.Object")


SHARING_CREATED = sig.signal()


def get_base64_encoded_icon(icon_name):
    with open(
        os.path.join(os.path.dirname(__file__), "resources", icon_name), "rb"
    ) as f:
        return "data:image/png;base64,{}".format(base64.b64encode(f.read()))


MAIL_ICONS = {
    "cis_display_primary": get_base64_encoded_icon("cis_display_primary.png"),
    "cis_globe_primary": get_base64_encoded_icon("cis_globe_primary.png"),
    "cis_arrow_right": get_base64_encoded_icon("cis_arrow-right.png"),
}


@classbody
class User(object):
    def email_with_sharing(self):
        return self.getSettingValue("user.email_with_sharing") == "1"


def generate_cdb_sharing_posting_v():
    """
    Joins cdb_object_ids of attachments, postings, and sharings (newest first)
    """
    addtl = ""
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        addtl = "TOP 100 PERCENT"
    return (
        "SELECT %s a.attachment_id, s.cdb_object_id AS sharing_id, "
        "       p.cdb_object_id AS posting_id "
        "FROM cdb_sharing s "
        "   JOIN cdbblog_posting p ON s.cdb_object_id=p.context_object_id "
        "   JOIN cdbblog_attachment a ON p.cdb_object_id=a.posting_id "
        "ORDER BY p.cdb_cdate DESC"
    ) % addtl


class Sharing(Object, WithMultilanguageNotification):
    """
    `Sharing` is the top-level object used for displaying user-shared objects in
    `cs.activitystream`. Users can add subscribers after creating a Sharing, but
    not remove anybody who already subscribed to it.

    There is no legacy UI (e.g. cdbpc.exe) for creating Sharings. Sharings are
    created exclusively using `cs.sharing.web.share_objects`.
    """

    __maps_to__ = "cdb_sharing"
    __classname__ = "cdb_sharing"
    __sys_posting__ = "cdb_sharing_created"

    Creator = Reference_1(fUser, fSharing.cdb_cpersno)
    AllPostings = Reference_N(
        fPosting, fPosting.context_object_id == fSharing.cdb_object_id
    )
    Subscriptions = Reference_N(
        fSubscription, fSubscription.channel_cdb_object_id == fSharing.cdb_object_id
    )

    def _get_first_posting(self):
        "Gets the first posting, which holds the attachments."
        for p in self.AllPostings:
            return p

    Posting = ReferenceMethods_1(fPosting, _get_first_posting)

    def _get_attachments(self):
        "Gets the first posting's attachments."
        return Attachment.KeywordQuery(posting_id=self.Posting.cdb_object_id)

    Attachments = ReferenceMethods_N(fAttachment, _get_attachments)

    def _get_attachment_objects(self):
        "Gets the first posting's attached objects."
        objects = [ByID(a.attachment_id) for a in self.Attachments]
        return [o for o in objects if o is not None and o.CheckAccess("read")]

    AttachedObjects = ReferenceMethods_N(fObject, _get_attachment_objects)

    @classmethod
    def getSharingsForAttachmentID(cls, cdb_object_id):
        sharing_ids = [
            rec.sharing_id
            for rec in sqlapi.RecordSet2(
                "cdb_sharing_posting_v",
                "attachment_id='%s'" % sqlapi.quote(cdb_object_id),
            )
        ]
        sharings = cls.KeywordQuery(cdb_object_id=sharing_ids)
        sharings = [s for s in sharings if s and s.CheckAccess("read")]
        sharings.sort(key=lambda x: x.cdb_cdate, reverse=True)
        return sharings

    def _get_sys_posting_vals(self, context_object):
        def _adapt_value(attrname, value):
            try:
                value = value[
                    : util.tables["cdbblog_posting"].column(attrname).length()
                ]
            except Exception as exc:  # pylint: disable=W0703
                log.debug("Failed to _adaptValue: %s", exc)
            return value.replace("\\n", "\n")

        oh = context_object.ToObjectHandle()
        values = {"context_object_id": context_object.cdb_object_id, "type": "update"}

        # Generate a text for all active languages
        for lang in i18n.getActiveGUILanguages():
            msg = util.CDBMsg(util.CDBMsg.kNone, self.__sys_posting__)
            msg.addReplacement(oh.getDesignation("", lang))
            value = msg.getText(lang, True)
            attrname = "title_" + lang
            values[attrname] = _adapt_value(attrname, value)

        if oh.getClassDef().has_workflow():
            values["context_object_status"] = oh.getState()

        return values

    def create_system_posting(self, context_object):
        """
        Synchronously creates a "cdb_sharing_created" system posting for the
        context_object, then adds the Sharing object self as the posting's
        Attachment (not supported by the system posting MQ).
        """
        if not context_object.GetClassDef().isActivityChannel():
            return

        posting = SystemPosting.do_create(**self._get_sys_posting_vals(context_object))
        Attachment.addAttachment(posting.cdb_object_id, self.cdb_object_id)

    @classmethod
    def createFromObjects(cls, objects, subjects, text=None):
        """
        Creates and returns a new `Sharing` with attachments `objects`. If
        `subjects` is a valid subject list, add its subjects as subscribers.
        """
        if not text:
            text = u""

        sharing = operation("CDB_Create", cls)
        for obj in objects:
            sharing.create_system_posting(obj)
        sharing.createPosting([o.cdb_object_id for o in objects], text)
        sharing.sendNotificationAsynchronously(subjects)
        sig.emit(SHARING_CREATED)(sharing)
        return sharing

    def addAttachment(self, object_or_object_id):
        Attachment.addAttachment(
            self.Posting.cdb_object_id,
            getattr(object_or_object_id, "cdb_object_id", object_or_object_id),
        )

    def createPosting(self, attachment_ids, text):
        posting = operation(
            constants.kOperationNew,
            UserPosting,
            cdbblog_posting_txt=text,
            context_object_id=self.cdb_object_id,
        )

        if posting:
            for object_id in attachment_ids:
                self.addAttachment(object_id)

    def addSubscriptions(self, subject_list):
        if self.GetClassDef().isActivityChannel():
            subscribers = RecipientCollection(subjects=subject_list)
            for person in subscribers.iterPersons():
                if isUserVisible(person):
                    fSubscription.subscribeToChannel(
                        self.cdb_object_id, person.personalnummer
                    )

    # Mail Notification
    __notification_template__ = "new_sharing.html"
    __notification_title__ = "cdb_new_sharing_email"
    __mail_relationships__ = {
        # name of Relship*1
        "Project": "cdb_sharing_project_label",
        "Process": "cdb_sharing_workflow_label",
    }

    def getNotificationTitle(self, ctx=None):
        ret = {}
        languages = i18n.getActiveGUILanguages()
        system_names = Message.ByKeys("branding_product_name_acronym")
        title_label = Label.ByKeys(self.__notification_title__)
        share_more_label = Label.ByKeys("cdb_sharing_more")
        for language in languages:
            localized_label = title_label.Text[language]
            if localized_label:
                localized_attachment_str = ""
                if self.AttachedObjects:
                    localized_attachment_str = self.AttachedObjects[0].GetDescription(
                        iso_lang=language
                    )
                    if len(self.AttachedObjects) > 1:
                        try:
                            localized_attachment_str += share_more_label.Text[
                                language
                            ] % (len(self.AttachedObjects) - 1)
                        except TypeError:
                            pass
                localized_system_name = system_names.Text[language]
                ret[language] = localized_label % (
                    localized_system_name,
                    localized_attachment_str,
                )
        return ret

    def getRelationships(self, obj, language="en"):
        result = {}
        if obj and isinstance(obj, Object):
            for relname, label in six.iteritems(self.__mail_relationships__):
                robj = getattr(obj, relname, None)
                if isinstance(robj, Object) and hasattr(robj, "cdb_object_id"):
                    result[robj.cdb_object_id] = {
                        "label": util.get_label_with_fallback(label, language),
                        "obj": robj,
                    }
        return list(six.itervalues(result))

    def setNotificationContext(self, sc, ctx=None):
        sc.self = self

    def getSubscriptionUsers(self):
        ids = self.Subscriptions.personalnummer
        return User.KeywordQuery(personalnummer=ids)

    def getNotificationReceiver(self, ctx=None):
        directory = RecipientDirectory()
        users = self.getSubscriptionUsers()
        for user in users:
            if user.email_with_sharing():
                directory.add_recipient(
                    user.e_mail, user.name, user.GetPreferredLanguage()
                )
        return directory

    def sendNotificationSyncronously(self, ctx=None):
        super(Sharing, self).sendNotification(ctx)

    def sendNotificationAsynchronously(self, subjects):
        from cs.sharing.share_objects_queue import share_objects_queue

        job = share_objects_queue.new(
            sharing_object_id=self.cdb_object_id, sharing_subjects=json.dumps(subjects)
        )
        job.start()

    def sendNotification(self, ctx=None):
        # overwrite cdb.objects.common.WithMultilanguageNotification.sendNotification
        self.sendNotificationAsynchronously(None)

    def getFormattedMessage(self):
        converter = PostingTextConverter()
        text = self.Posting.GetText("cdbblog_posting_txt")
        return converter.convert(text)

    def getActivityStreamURL(self):
        return "%s/activitystream/posting/%s" % (
            CADDOK.WWWSERVICE_URL,
            self.Posting.cdb_object_id,
        )

    def getActivityStreamURLcdbpc(self):
        cmsg = Cdbcmsg(
            classname="cdb_sharing", aktion="CDB_ShowObject", interactive=True
        )
        cmsg.add_item(
            attrib="cdb_object_id",
            relation=self.__table_name__,
            value=self.cdb_object_id,
        )
        return cmsg.cdbwin_url()

    def getSharedObjectURL(self, obj):
        """
        return cdbwin URL of the object
        """
        action = "CDB_ShowObject"
        if hasattr(obj, "getActionForSharingNotification"):
            action = obj.getActionForSharingNotification()
        return obj.MakeURL(action=action, plain=2)

    def getSharedObjectLink(self, obj):
        """
        return Web URL of the object
        """
        from cs.activitystream.web.main import get_posting_link

        if isinstance(obj, Posting):
            return get_posting_link(obj)
        else:
            action = "CDB_ShowObject"
            if hasattr(obj, "getActionForSharingNotification"):
                action = obj.getActionForSharingNotification()
            return obj.MakeURL(action=action, plain=0)

    # /Mail Notification

    event_map = {("cdb_sharing_add_person", "now"): "add_person"}

    def add_person(self, ctx):
        self.addSubscriptions([(ctx.dialog.person_id, User.__subject_type__)])

    def _send_to_group(self, directory, lang, msg):
        """
        Copied from objects.common.WithMultilanguageNotification._send_to_group but
        without the try/except, so jobs will actually fail if emails cannot be sent
        properly.

        Technically only group.to can be populated here, but to keep code consistent and
        not introduce unexpected behavior group.cc and group.bcc are also processed.
        """
        for group in directory.groups[lang]:
            for toaddr in group.to:
                msg.To(toaddr[0], toaddr[1])
            for toaddr in group.cc:
                msg.Cc(toaddr[0], toaddr[1])
            for toaddr in group.bcc:
                msg.Bcc(toaddr[0])
        if msg.to_addrs:
            msg.send()

    def _render_mail_template(self, ctx, templ_file):
        import chameleon
        from cdb import elink
        from cdb.wsgi.util import TemplateCacheDir

        if not TemplateCacheDir.TEMPLATE_CACHE_INIT:
            TemplateCacheDir.init_template_cache()
        sc = elink.SimpleContext()
        sc.obj = self
        self.setNotificationContext(sc, ctx)
        mail_templ = chameleon.PageTemplateFile(templ_file)
        return mail_templ(
            context=sc, product_name=cdbwrapc.getApplicationName(), **MAIL_ICONS
        )
