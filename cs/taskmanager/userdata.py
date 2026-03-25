#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from collections import defaultdict

from cdb import auth, sqlapi, transaction
from cdb.objects import Object


class Tags(Object):
    """
    Tags are personal labels to help users organize their tasks.
    """

    __maps_to__ = "cs_tasks_tag"
    __classname__ = "cs_tasks_tag"

    @classmethod
    def GetTagObjects(cls, persno, task_object_id):
        """
        :param persno: ``personalnummer`` of user to get tags for. If
            ``None``, tags for all users are returned.
        :type persno: basestring

        :param task_object_id: Either single ``cdb_object_id`` identifying a
            task object or a list of these.
        :type task_object_id: basestring or list

        :returns: Tags matching given criteria, sorted by ascending
            ``task_object_id`` and ``tag``.
        :rtype: :py:class:`cdb.objects.ObjectCollection`


        :rubric: Usage Example

        .. code-block :: python

            >>> Tags.GetTagObjects(task_object_id="task_id").tag
            [u"otherUserTag",u"myTag1", u"myTag2"]
            >>> Tags.GetTagObjects(
            >>>     task_object_id="task_id",
            >>>     persno="caddok").tag
            [u"myTag1", u"myTag2"]

        """
        query = {
            "task_object_id": task_object_id,
            "order_by": "task_object_id, tag",
        }

        if persno:
            query["persno"] = persno

        return cls.KeywordQuery(**query)

    @classmethod
    def GetTaskTags(cls, persno, task_object_id):
        """
        :param persno: ``personalnummer`` of user to get tags for. If
            ``None``, tags for all users are returned.
        :type persno: basestring

        :param task_object_id: Either single ``cdb_object_id`` identifying a
            task object or a list of these.
        :type task_object_id: basestring or list

        :returns: List of tag texts matching given criteria.
        :rtype: list

        :rubric: Usage Example

        .. code-block :: python

            >>> Tags.getTaskTags(
            >>>     task_object_id="task_id",
            >>>     persno="caddok")
            [u"myTag1", u"myTag2"]

        """
        return cls.GetTagObjects(persno, task_object_id).tag

    @classmethod
    def GetUserTags(cls):
        tags = sqlapi.RecordSet2(
            sql=(
                "SELECT DISTINCT tag "
                "FROM {} "
                "WHERE persno = '{}' "
                "ORDER BY tag".format(
                    cls.__maps_to__,
                    auth.persno,
                )
            )
        )
        return [x.tag for x in tags]

    @classmethod
    def GetIndexedTags(cls, task_object_ids):
        """
        :param task_object_ids: List of ``cdb_object_id`` of task objects.
        :type task_object_ids: list

        :returns: Lists of sorted tag texts indexed by ``cdb_object_id``.
        :rtype: dict

        :rubric: Usage Example

        .. code-block :: python

            >>> Tags.getIndexedTags(["task_id_1", "task_id_2"])
            <defaultdict, len() = 2>
            >>> _.items()
            [(u'task_id_1', [[u'myTag1', u'myTag2']),
            (u'task_id_2', [u'myTag3'])]

        """
        tags = cls.GetTagObjects(auth.persno, task_object_ids)
        result = defaultdict(set)

        for tag in tags:
            result[tag.task_object_id].add(tag.tag)

        result = {object_id: sorted(tags) for object_id, tags in result.items()}
        return result

    @classmethod
    def SetTaskTags(cls, persno, task_object_id, tags):
        """
        Persists the given ``tags`` for given ``persno`` and
        ``task_object_id``. Tags not included in ``tags`` will be removed.

        :param persno: ``personalnummer`` of user to persist given tags for.
        :type persno: basestring

        :param task_object_id: Single ``cdb_object_id`` identifying a task
            object.
        :type task_object_id: basestring

        :param tags: List of tag texts to set for given ``task_object_id``.
        :type tags: list

        :rubric: Usage Example

        .. code-block :: python

            Tags.setTaskTags(
                persno="caddok",
                task_object_id="task_id,
                tags=["myTag1","myTag2"])

        """
        if not isinstance(tags, list):
            raise ValueError("'tags' must be a list")

        vals = {
            "persno": sqlapi.quote(persno),
            "task_object_id": sqlapi.quote(task_object_id),
        }

        unique_tags = {sqlapi.quote(t.strip()) for t in tags}.difference([""])

        with transaction.Transaction():
            for tag in unique_tags:
                vals["tag"] = tag

                if not cls.ByKeys(**vals):
                    cls.Create(**vals)

            cls.Query(
                "persno='{}' "
                "AND task_object_id='{}' "
                "AND tag NOT IN ('{}')".format(
                    vals["persno"], vals["task_object_id"], "', '".join(unique_tags)
                )
            ).Delete()


class ReadStatus(Object):
    """
    To keep track of new or already seen tasks, tasks read by a user have a
    corresponding entry in this class.

    While read_status can be modified to be 0, and thus not "count" as read,
    the system itself only creates entries with read_status 1 and does not
    modify it. To set a task back to "unread", the entry is deleted instead.
    """

    __maps_to__ = "cs_tasks_read_status"
    __classname__ = "cs_tasks_read_status"

    @classmethod
    def SetTasksRead(cls, *object_ids):
        status = cls.KeywordQuery(
            persno=auth.persno,
            task_object_id=object_ids,
        )
        if status:
            status.Update(read_status=1)

        missing_ids = set(object_ids).difference(status.task_object_id)

        for missing_id in missing_ids:
            cls.Create(
                persno=auth.persno,
                task_object_id=missing_id,
                read_status=1,
            )

    @classmethod
    def SetTasksUnread(cls, *object_ids):
        status = cls.KeywordQuery(
            persno=auth.persno,
            task_object_id=object_ids,
        )
        if status:
            status.Delete()

    @classmethod
    def GetReadStatus(cls, task_object_ids):
        statuses = cls.KeywordQuery(
            persno=auth.persno,
            read_status=1,
            task_object_id=task_object_ids,
        )
        return statuses.task_object_id
