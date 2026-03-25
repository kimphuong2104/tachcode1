#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module activitylistener

The activity listener collects database events that
might lead to the creation of an activity stream entry.
"""
from __future__ import absolute_import

import datetime
import logging

import six
from cdb import ddl, misc, rte, sig, typeconversion, util
from cdb.objects.cdb_file import CDB_File

import cs.activitystream
from cs.activitystream.attachment import Attachment

__all__ = ["activate"]
__docformat__ = "restructuredtext en"

log = logging.getLogger(__name__)


@six.add_metaclass(misc.Singleton)
class ActivityListener(util.DBEventListener):
    def __init__(self):
        util.DBEventListener.__init__(self)
        self.__observed_relations = set()
        self.__relevant_upd_attrs = {}  # A dictionary relation:[DDField]
        self.__relation_classes = {}  # A dictionary of relation:[Class]
        self.__channels = set()  # A set of relations that are used as Channels
        self.__process_inital_relations_to_observe()
        self.__enabled = True

    @classmethod
    def _getObjectHandle(cls, relation, eventinfo):
        """
        Retrieve a `CDBObjectHandle` from the informations
        given by a notification event.
        """
        # TODO: Check whether this leads to additional selects -
        #       use keys otherwise
        from cdb.platform import mom

        return mom.getObjectHandleFromObjectID(eventinfo.m_cdb_object_id)

    def __process_inital_relations_to_observe(self):
        try:
            from cdb.platform.mom.entities import Class

            if not Class.HasField("activity_enable_sys_posting"):
                log.warning(
                    "Could not enable ActivityListener - no attribute "
                    "named switch_tabelle.activity_enable_sys_posting"
                )
                return

            for clazz in Class.Query(
                "activity_enable_sys_posting=1 or " "activity_is_channel=1"
            ):
                relation = clazz.getTableName()
                if self.do_register(relation):
                    if clazz.activity_enable_sys_posting == 1:
                        if relation in self.__relation_classes:
                            self.__relation_classes[relation].append(clazz)
                        else:
                            self.__relation_classes[relation] = [clazz]
                    if clazz.activity_is_channel == 1:
                        self.__channels.add(relation)
        except Exception:  # pylint: disable=W0703
            log.exception(
                "Error during initial relation registration for"
                " activity listener. This is ok during the"
                " update process"
            )

    def __get_ddfield(self, relation, attrname):
        """
        Checks whether the change of `attrname` should generate a posting.
        Returns the `cdb.platform.mom.fields.DDField` definition if a posting
        should be generated on change, ``NULL`` otherwise.
        """
        if relation not in self.__relevant_upd_attrs:
            classes = self.__relation_classes.get(relation, [])
            posting_fields = []
            for clss in classes:
                for field in clss.DDAllFields:
                    if field.activity_enable_sys_posting == 1:
                        if field not in posting_fields:
                            posting_fields.append(field)
            self.__relevant_upd_attrs[relation] = posting_fields

        for field in self.__relevant_upd_attrs[relation]:
            if attrname == field.field_name:
                return field
        return None

    def __check_relation(self, relation):
        """
        Checks whether `relation` is suitable for
        activity stream postings. At this time we
        check, whether there is a ``cdb_object_id``.
        """
        result = False
        table = ddl.Table(relation)
        if table.exists():
            if table.getColumn("cdb_object_id"):
                result = True
            else:
                log.error(
                    "Could not register relation '%s' for activity "
                    "streams. The relation does not have a "
                    "cdb_object_id attribute.",
                    relation,
                )
        else:
            log.error(
                "Could not register relation '%s' for activity "
                "streams. The relation does not exist.",
                relation,
            )
        return result

    def do_unregister(self, relation):
        if relation in self.__observed_relations:
            util.DBEventListener.doUnregister(self, relation)
            self.__observed_relations.remove(relation)

    def do_register(self, relation):
        """
        Registers a listener and returns ``True`` if a listener
        is active for the relation afterwards - regardless
        whether the listener had been active before or
        has been activated by the call.
        """
        # The listener should never be told to listen to all relations, so
        # explicitly forbid the empty string. "".
        if not relation or relation.strip(" ") == "":
            return False
        if relation not in self.__observed_relations:
            try:
                if not self.__check_relation(relation):
                    return False
                log.debug("Activity listener: Registering relation: %s", relation)
                util.DBEventListener.doRegister(self, relation)
                self.__observed_relations.add(relation)
            except Exception:  # pylint: disable=W0703
                log.exception("Error while registering relation: %s", relation)
                return False
        return True

    def enable(self):
        """Set "enabled" flag. The flag is set by default."""
        self.__enabled = True

    def isEnabled(self):
        """Returns the value of the "enabled" flag."""
        return self.__enabled

    def disable(self):
        """Clear "enabled" flag. The listener will ignore all
        DB-Events until enabled() is called.

        Returns True if the flag was previously set.
        """
        result = self.__enabled
        self.__enabled = False
        return result

    def notify(self, relation, eventinfo):
        try:
            if not self.__enabled:
                return
            log.debug(
                "ActivityListener: received the DB event for relation " "'%s': %s",
                relation,
                eventinfo,
            )
            result = None
            if eventinfo.m_event == util.kRecordInserted:
                result = self._handle_create(relation, eventinfo)
            elif eventinfo.m_event == util.kRecordUpdated:
                result = self._handle_update(relation, eventinfo)
            elif eventinfo.m_event == util.kRecordDeleted:
                result = self._handle_delete(relation, eventinfo)
            else:
                log.debug("Ignoring the Event %s (no insert/update)", eventinfo.m_event)
            if not result:
                log.debug("No posting has been generated")
            else:
                log.debug("Posting(s) has been generated")
        except Exception:  # pylint: disable=W0703
            log.exception(
                "Error during the activity notification for cdb_object_id: %s",
                eventinfo.m_cdb_object_id,
            )

    def _handle_create(self, relation, event):
        """
        Checks whether a posting should be generated and generates
        the posting if the checks are ok.
        """
        if not self.__enabled:
            return None
        pattern = ""
        oh = self._getObjectHandle(relation, event)
        if oh:
            cldef = oh.getClassDef()
            if cldef.generatesSysPostingsOnCreate():
                if cs.activitystream.PostingRuleChecker().checkRules(oh):
                    pattern = cldef.getCreatePostingMessageLabel()
                    return self.create_posting_job(event, oh, pattern)
        else:
            log.info(
                "ActivityListener: Failed to retrieve objecthandle for" " '%s': %s",
                relation,
                event,
            )
        return None

    def _handle_delete(self, relation, event):
        """
        If an object is removed all postings has to be removed, too.
        """
        # Think about: its better to remove the postings here or to generate a
        # removal entry in the queue?
        from cs.activitystream.objects import (
            Comment,
            Posting,
            Reaction,
            Subscription,
            Topic2Posting,
        )

        if event.m_cdb_object_id:
            postings = Posting.KeywordQuery(context_object_id=event.m_cdb_object_id)
            posting_ids = [posting.cdb_object_id for posting in postings]
            comments = Comment.KeywordQuery(posting_id=posting_ids)
            comment_ids = [comment.cdb_object_id for comment in comments]
            attachments = Attachment.KeywordQuery(posting_id=posting_ids + comment_ids)
            files = CDB_File.KeywordQuery(cdbf_object_id=posting_ids + comment_ids)
            reactions = Reaction.KeywordQuery(reaction_to=posting_ids + comment_ids)

            for posting in postings:
                posting.DeleteText("cdbblog_posting_txt")

            for comment in comments:
                comment.DeleteText("cdbblog_comment_txt")

            for f in files:
                f.delete_file()

            attachments.Delete()
            comments.Delete()
            postings.Delete()
            reactions.Delete()

            # If the relation is a channel remove the subscriptions
            if relation in self.__channels:
                Subscription.KeywordQuery(
                    channel_cdb_object_id=event.m_cdb_object_id
                ).Delete()
                Topic2Posting.KeywordQuery(topic_id=event.m_cdb_object_id).Delete()

    def _handle_update(self, relation, event):
        """
        Checks whether postings should be generated and generates
        the posting if the checks are ok. Returns a list of generated
        postings
        """
        if not self.__enabled:
            return None
        result = []
        fields = []
        for attr in event.m_attrs:
            f = self.__get_ddfield(relation, attr)
            if f:
                fields.append(f)
        if fields:  # pylint: disable=too-many-nested-blocks
            oh = self._getObjectHandle(relation, event)
            if oh:
                if cs.activitystream.PostingRuleChecker().checkRules(oh):
                    std_msg_fields = []
                    for field in fields:
                        if field.activity_posting_label:
                            posting = self.create_posting_job(
                                event, oh, field.activity_posting_label
                            )
                            if posting:
                                result.append(posting)
                        else:
                            std_msg_fields.append(field)
                    if std_msg_fields:
                        posting = self.create_posting_job(event, oh, "", std_msg_fields)
                        if posting:
                            result.append(posting)
            else:
                log.info(
                    "ActivityListener: Failed to retrieve objecthandle" " for '%s': %s",
                    relation,
                    event,
                )
        return result

    def _adapt_value(self, attrname, value):
        """
        Checks whether the length of `value` is
        suitable for the posting attribute `attrname`.
        Strips characters from value if value is longer
        than the attributes length.
        Also replaces \\n with \n.
        """
        try:
            value = value[: util.tables["cdbblog_posting"].column(attrname).length()]
        except Exception as exc:  # pylint: disable=W0703
            log.error("Exception %s in _adapt_value()", exc)
        return value.replace("\\n", "\n")

    def create_posting_job(self, event, oh, pattern, fields=None):
        """
        Creates the job. If `event` is an upate event for attributes
        using the standard pattern, `fields` should contain a
        list of DDField objects of the changed attributes.
        """
        from cdb import auth, i18n

        from cs.activitystream import posting_queue

        if not self.__enabled:
            return

        if fields is None:
            fields = []
        values = {"context_object_id": oh.cdb_object_id}
        if not event or event.m_event == util.kRecordUpdated:  # wflow
            values["type"] = "update"
        elif event.m_event == util.kRecordInserted:
            values["type"] = "insert"
        # Generate a text for all active languages
        for lang in i18n.getActiveGUILanguages():
            attrname = "title_" + lang
            value = ""
            if pattern:
                value = oh.getDesignation(pattern, lang)
            elif not event:
                msg = util.CDBMsg(util.CDBMsg.kNone, "activity_obj_wfstep")
                msg.addReplacement(oh.getDesignation("", lang))
                msg.addReplacement(oh.getStateLabel(lang))
                value = msg.getText(lang, True)
            elif event.m_event == util.kRecordInserted:
                msg = util.CDBMsg(util.CDBMsg.kNone, "activity_obj_created")
                msg.addReplacement(oh.getDesignation("", lang))
                value = msg.getText(lang, True)
            elif event.m_event == util.kRecordUpdated:
                msg = util.CDBMsg(util.CDBMsg.kNone, "activity_obj_modified")
                msg.addReplacement(oh.getDesignation("", lang))
                the_change = ", ".join(
                    "%s:%s" % (field.getLabel(lang), event.m_attrs[field.field_name])
                    for field in fields
                )
                msg.addReplacement(the_change)
                value = msg.getText(lang, True)
            values[attrname] = self._adapt_value(attrname, value)

        if oh.getClassDef().has_workflow():
            values["context_object_status"] = oh.getState()

        values["cdb_cpersno"] = auth.persno
        values["cdb_cdate"] = typeconversion.to_legacy_date_format(
            datetime.datetime.utcnow()
        )
        posting_queue.getQueue().insert_job(**values)


def _state_change_event(classname, keys, msg_label):
    """
    Called by the |elements| kernel to generate a posting. The caller is
    responsible to check, whether such a posting is configured
    in the object life cycle configuration. `msg_label` is the
    configured label. This function checks whether objects of this
    class should generate events and if the object matches the rules
    for generating a posting.
    """
    from cdb.platform import mom

    if not ActivityListener().isEnabled():
        return
    c = mom.entities.CDBClassDef(classname)
    keylist = mom.SimpleArguments(**keys)

    oh = mom.CDBObjectHandle(c, keylist, True, True)
    if oh:
        # state change action can occure within a transaction
        # so we have to ensure we get the actual data
        # exists will reload the object
        if oh.exists(True):
            if cs.activitystream.PostingRuleChecker().checkRules(oh):
                ActivityListener().create_posting_job(None, oh, msg_label)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def activate():
    """
    The ActivityListener needs to be activated on server startup, so it can
    register itself to receive notifications from activity objects.
    """
    ActivityListener()
