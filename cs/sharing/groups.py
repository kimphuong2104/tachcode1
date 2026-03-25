#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import six
from cdb import CADDOK, auth, misc, sqlapi, transaction, ue, util
from cdb.objects import Forward, ObjectCollection, Reference_1, Reference_N
from cdb.objects.operations import operation
from cdb.objects.org import CommonRole, Person, User, WithSubject

__docformat__ = "restructuredtext en"

fSharingGroup = Forward(__name__ + ".SharingGroup")
fPersonalSharingGroup = Forward(__name__ + ".PersonalSharingGroup")
fObjectSharingGroup = Forward(__name__ + ".ObjectSharingGroup")
fSharingGroupMember = Forward(__name__ + ".SharingGroupMember")
fPyrule = Forward("cdb.objects.Rule")


def isUserVisible(user):
    return (
        user.visibility_flag and user.active_account == "1" and user.CheckAccess("read")
    )


def get_mssql_collation():
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault

        return " COLLATE %s " % CollationDefault.get_default_collation()
    else:
        return ""


def _get_sharing_recipients_languages():
    from cdb.platform.mom import fields

    f = fields.DDField.ByKeys("cdb_sharing_recipients", "name")
    if f and f.multilang_dlg_languages:
        langlist = fields.IsoLangList.ByKeys(f.multilang_dlg_languages)
        if langlist:
            return [
                lang.strip()
                for lang in langlist.iso_languages.split(",")
                if lang.strip()
            ]
    return []


def generate_cdb_sharing_recipients_v():
    """
    Joins users, common roles, and sharing groups
    """

    def _get_attr_or_empty(relation, attr):
        if util.column_exists(relation, attr):
            return attr
        return "''"

    collate = get_mssql_collation()
    std_languages = [
        "cs",
        "de",
        "en",
        "es",
        "fr",
        "it",
        "ja",
        "ko",
        "pl",
        "pt",
        "tr",
        "zh",
    ]
    # At least the languages that are defined in the corresponding
    # multilanguage attribute should be part of the view
    for lang in _get_sharing_recipients_languages():
        if lang not in std_languages:
            std_languages.append(lang)

    ang_attrs = ", ".join(["name AS name_%s" % lang for lang in std_languages])
    role_attrs = ", ".join(
        [
            _get_attr_or_empty("cdb_global_role", "name_%s" % lang)
            for lang in std_languages
        ]
    )
    sharing_attrs = ", ".join(
        [
            _get_attr_or_empty("cdb_sharing_group", "name_%s" % lang)
            for lang in std_languages
        ]
    )
    return (
        "SELECT 'angestellter' {collate} AS table_name, personalnummer AS subject_id, "
        "   'Person' {collate} AS subject_type, {ang_attrs} "
        "FROM angestellter WHERE cdb_classname='angestellter' "
        "UNION SELECT 'cdb_global_role' {collate} AS table_name, role_id AS subject_id, "
        "   'Common Role' {collate} AS subject_type, {role_attrs} "
        "FROM cdb_global_role "
        "UNION SELECT 'cdb_sharing_group' {collate} AS table_name, "
        "   cdb_object_id AS subject_id, 'Sharing Group' {collate} AS subject_type, "
        "   {sharing_attrs} "
        "FROM cdb_sharing_group".format(
            collate=collate,
            ang_attrs=ang_attrs,
            role_attrs=role_attrs,
            sharing_attrs=sharing_attrs,
        )
    )


def generate_cdb_sharing_subjects():
    collate = get_mssql_collation()

    return (
        "SELECT role_id AS subject_id, description AS description, "
        "    'Common Role' AS subject_type, "
        "    role_id AS subject_name, 0 AS order_by "
        "FROM cdb_global_role WHERE role_id='public' "
        "UNION SELECT role_id AS subject_id, description AS description, "
        "    'Common Role' {collate} AS subject_type, "
        "    role_id AS subject_name, 1 AS order_by "
        "FROM cdb_global_role WHERE role_id!='public' AND is_org_role='1' "
        "UNION SELECT personalnummer AS subject_id, name AS description, "
        "    'Person' {collate} AS subject_type, "
        "    name AS subject_name, 2 AS order_by "
        "FROM angestellter "
        "WHERE active_account='1' AND visibility_flag='1'".format(collate=collate)
    )


class SharingGroup(WithSubject):
    """
    A `SharingGroup` is a named list of Subjects that can be used to share
    objects with a predefined set of recipients. It is available for its own
    Subject's members.

    This class is abstract. Use its subclasses only.
    """

    __maps_to__ = "cdb_sharing_group"
    __classname__ = "cdb_sharing_group"

    @classmethod
    def ByName(cls, name):
        """
        Gets the first `SharingGroup` with given name that current user has read
        access to, e.g. user is part of the group's `Subject` relationship
        """
        for group in cls.KeywordQuery(name=name):
            if group.CheckAccess("read"):
                return group
        return None


class PersonalSharingGroup(SharingGroup):
    __classname__ = "cdb_personal_sharing_group"
    __match__ = SharingGroup.cdb_classname >= __classname__
    __subject_type__ = "Sharing Group"

    Members = Reference_N(
        fSharingGroupMember, fSharingGroupMember.group_id == fSharingGroup.cdb_object_id
    )

    @classmethod
    def fromSubjectList(cls, name, subject_list):
        """
        Creates a new `SharingGroup` named after name and set its members
        according to `subject_list`, which is type checked. For details, see
        `cs.sharing.groups.RecipientCollection`.
        """
        with transaction.Transaction():
            subjects = RecipientCollection(subjects=subject_list)
            name_attr = "name_%s" % CADDOK.get("ISOLANG", "en")
            predef = {
                name_attr: name,
                "subject_id": auth.persno,
                "subject_type": User.__subject_type__,
            }

            if cls.KeywordQuery(**predef):
                raise ue.Exception("cdb_sharing_group_name_taken", predef[name_attr])

            vals = cls.MakeChangeControlAttributes()
            vals.update(predef)
            group = cls.Create(**vals)

            for subject in subjects.subjects:
                group.addMember(*subject)

            return group

    def CDB_Delete(self):
        operation("CDB_Delete", self)

    def addMember(self, subject_id, subject_type):
        return SharingGroupMember.Create(
            group_id=self.cdb_object_id,
            subject_id=subject_id,
            subject_type=subject_type,
        )

    def getMemberSubjectList(self):
        return [(m.subject_id, m.subject_type) for m in self.Members]

    def getSubjectList(self):
        "returns a subject_list constructed from self"
        member_list = self.getMemberSubjectList()
        return RecipientCollection(subjects=member_list).subjects

    def iterPersons(self):
        member_list = self.getMemberSubjectList()
        for person in RecipientCollection(subjects=member_list).iterPersons():
            yield person

    def getPersons(self):
        member_list = self.getMemberSubjectList()
        return RecipientCollection(subjects=member_list).getPersons()


class ObjectSharingGroup(SharingGroup):
    __classname__ = "cdb_object_sharing_group"
    __match__ = SharingGroup.cdb_classname >= __classname__
    __subject_type__ = "Object Sharing Group"

    Rule = Reference_1(fPyrule, fObjectSharingGroup.pyrule)

    @classmethod
    def forObject(cls, theObject):
        return [
            g
            for g in cls.Query(addtl="ORDER BY name_%s" % CADDOK.ISOLANG)
            if g.Rule.match(theObject)
        ]

    @classmethod
    def nonEmptyForObject(cls, theObject):
        result = []
        for g in cls.forObject(theObject):
            try:
                if g._resolve_object(theObject):  # pylint: disable=protected-access
                    result.append(g)
            except AttributeError:
                misc.log_traceback(
                    "failed to access sharing group '%s'" % g.GetDescription()
                )
        return result

    def _is_valid_attr(self, attr):
        if self[attr]:
            classes = [
                c for c in self.Rule.getClasses() if not getattr(c, self[attr], None)
            ]
            return not classes
        return None

    def _resolve_object(self, obj):
        if self.fqpyname:
            # get subject list from obj method
            return_value = getattr(obj, self.fqpyname)(self)
            # sanitize return value
            result = RecipientCollection(subjects=return_value).subjects
        else:
            # get cdb_person_id from obj
            # FIXME: error handling?
            result = [(getattr(obj, self.field_name), User.__subject_type__)]

        return set(result)

    def iterPersons(self, objects):
        if not type(objects) in (list, ObjectCollection):
            raise ue.Exception("cdb_sharing_malformed_list", type(objects))

        persnos = []
        for obj in self.Rule.match(objects):
            # check if obj is derived from cdb.object.Object
            resolved = self._resolve_object(obj)
            for person in resolved:
                if person[0] not in persnos:
                    persnos.append(person[0])
                    persObj = User.ByKeys(person[0])
                    if persObj and isUserVisible(persObj):
                        yield persObj

    def getPersons(self, objects):
        return [p for p in self.iterPersons(objects)]

    event_map = {(("create", "modify", "copy"), "pre"): "validate"}

    def validate(self, ctx=None):
        if not (self._is_valid_attr("fqpyname") or self._is_valid_attr("field_name")):
            raise ue.Exception("cdb_sharing_invalid_resolution")


class SharingGroupMember(WithSubject):
    """
    Member of a `SharingGroup`. Can either be a `cdb.objects.org.User` or a
    `cdb.objects.org.Common Role`.
    """

    __maps_to__ = "cdb_sharing_group_member"
    __classname__ = "cdb_sharing_group_member"

    Group = Reference_1(fSharingGroup, fSharingGroupMember.group_id)

    def CDB_Delete(self):
        if not isinstance(self.Group, PersonalSharingGroup):
            raise ue.Exception("cdb_sharing_del_only_personal")
        operation("CDB_Delete", self)


class RecipientsBrowser(object):
    __ranking__ = [
        User.__classname__,
        "cdb_global_role",
        PersonalSharingGroup.__classname__,
    ]
    __classes__ = {
        User.__classname__: {
            "cls": User,
            "where": [
                "(LOWER(name) LIKE '%%{1}%%' OR "
                "LOWER(firstname {0} ' ' {0} lastname) LIKE '%%{1}%%' OR "
                "LOWER(lastname {0} ' ' {0} firstname) LIKE '%%{1}%%' OR "
                "LOWER(beruf) LIKE '%%{1}%%' OR "
                "LOWER(abt_nummer) LIKE '%%{1}%%' OR "
                "LOWER(personalnummer) LIKE '%%{1}%%')",
                "(active_account='1' AND visibility_flag=1 AND is_system_account=0)",
            ],
        },
        "cdb_global_role": {
            "cls": CommonRole,
            "where": ["LOWER(role_id) LIKE '%%{1}%%'"],
        },
        PersonalSharingGroup.__classname__: {
            "cls": PersonalSharingGroup,
            "where": ["LOWER(name_%s) LIKE '%%{1}%%'" % CADDOK.get("ISOLANG", "en")],
        },
    }

    @classmethod
    def _getClassname(cls, objects_cls):
        if objects_cls == CommonRole:
            return "cdb_global_role"
        return objects_cls._getClassname()  # pylint: disable=protected-access

    @classmethod
    def getRecipientsOfClass(cls, cdb_class, query=None, limit=None):
        where = None

        if query:
            # prevent SQL injection
            query = sqlapi.quote(query.lower())
            clsmap = cls.__classes__.get(
                cls._getClassname(cdb_class), {}
            )  # pylint: disable=protected-access
            where = " AND ".join(clsmap.get("where")).format(sqlapi.SQLstrcat(), query)

        return cdb_class.Query(where, access="read", max_rows=limit)

    @classmethod
    def getDistribution(cls, dict_by_class, ranking, limit):
        if not ranking or not limit:
            return []

        fair = limit // len(ranking)
        rest = limit % len(ranking)
        distribution = [fair + (1 if i < rest else 0) for i, _ in enumerate(ranking)]

        # classes having less results: add difference to classes having more
        differences = [
            len(dict_by_class[c]) - distribution[i] for i, c in enumerate(ranking)
        ]

        for i in six.moves.range(len(ranking)):
            distribution[i] += min(0, differences[i])

        differences = [max(d, 0) for d in differences]

        # start at index rest, looping over ranking: distribute positive
        # differences until differences reach 0
        index = rest
        while sum(differences) and sum(distribution) < limit:
            if differences[index % len(distribution)] > 0:
                differences[index % len(distribution)] -= 1
                distribution[index % len(distribution)] += 1
            index += 1

        return distribution

    @classmethod
    def distribute(cls, dict_by_class, limit):
        ranking = [c for c in cls.__ranking__ if len(dict_by_class[c])]
        distribution = cls.getDistribution(dict_by_class, ranking, limit)
        result = []

        for index, clsname in enumerate(ranking):
            if distribution:
                result += dict_by_class[clsname][: distribution[index]]
            else:
                # no, no
                # no, no, no, no
                # no, no, no, no
                # no, no, there's no limit...
                result += dict_by_class[clsname]

        return result

    @classmethod
    def getAllPossibleRecipients(cls, flat=False, query=None, limit=None):
        dict_by_class = {
            clsname: cls.getRecipientsOfClass(clsdict["cls"], query, limit)
            for clsname, clsdict in six.iteritems(cls.__classes__)
        }

        if flat:
            return cls.distribute(dict_by_class, limit)
        else:
            return dict_by_class


CLSDEF = "clsdef"
SUBJECT_ID = "subject_id"
SUBJECT_TYPE = "subject_type"


class RecipientCollection(object):
    """
    provides conversions for lists of recipients

    initialize by either giving a list of cdb.objects.org.User,
    cdb.objects.org.CommonRole, and cs.sharing.groups.SharingGroup's subclasses
    objects, or a list of tuples (subject_id, subject_type) where only
    subject_types of the aforementioned classes are allowed:

    .. code-block:: python

        from cdb.objects.org import CommonRole
        from cdb.objects.org import User
        from cs.sharing.groups import ObjectSharingGroup
        from cs.sharing.groups import PersonalSharingGroup
        from cs.sharing.groups import RecipientCollection

        # initialize with list of objects
        all = RecipientCollection(
            User.Query()
            + CommonRole.Query()
            + PersonalSharingGroup.Query()
            + ObjectSharingGroup.Query()
        )

        # initialize with list of subject tuples
        some = RecipientCollection(subjects=[("caddok", "Person")])

    Recipient objects immediately convert the input list (objects -> subjects
    and vice versa). You can access both lists, or a list of distinct Users
    calculated from the objects list like this:

    .. code-block:: python

        all.subjects
        all.getPersons()

    """

    __classmap__ = {
        User.__classname__: {
            CLSDEF: User,
            SUBJECT_ID: "personalnummer",
            SUBJECT_TYPE: User.__subject_type__,
        },
        "cdb_global_role": {
            CLSDEF: CommonRole,
            SUBJECT_ID: "role_id",
            SUBJECT_TYPE: CommonRole.__subject_type__,
        },
        ObjectSharingGroup.__classname__: {
            CLSDEF: ObjectSharingGroup,
            SUBJECT_ID: "cdb_object_id",
            SUBJECT_TYPE: ObjectSharingGroup.__subject_type__,
        },
        PersonalSharingGroup.__classname__: {
            CLSDEF: PersonalSharingGroup,
            SUBJECT_ID: "cdb_object_id",
            SUBJECT_TYPE: PersonalSharingGroup.__subject_type__,
        },
    }
    __typemap__ = {}  # calculated from __classmap__ on __init__

    def __init__(self, objects=None, subjects=None):
        self.__typemap__ = {
            self.__classmap__[k][SUBJECT_TYPE]: v
            for k, v in six.iteritems(self.__classmap__)
        }
        self.objects = []
        self.subjects = []

        if objects:
            self.objects = objects
            self.subjects = self.objectsToSubjects(objects)
        elif subjects:
            self.subjects = subjects
            self.objects = self.subjectsToObjects(subjects)

    def objectsToSubjects(self, objects):
        result = []
        for obj in objects:
            if obj.CheckAccess("read"):
                clsname = obj.GetClassname()
                clsmap = self.__classmap__.get(clsname, None)
                if not clsmap:
                    # handle special case: non-user person
                    if (
                        clsname
                        == Person._getClassname()  # pylint: disable=protected-access
                    ):
                        continue
                    else:
                        raise TypeError("illegal object {}".format(obj))
                result.append((obj[clsmap[SUBJECT_ID]], clsmap[SUBJECT_TYPE]))
        return result

    def subjectsToObjects(self, subjects):
        result = []
        for subject_id, subject_type in subjects:
            if not isinstance(subject_id, six.string_types):
                raise ue.Exception("cdb_sharing_unknown_subject", subject_id)

            typemap = self.__typemap__[subject_type]
            obj = typemap[CLSDEF].ByKeys(subject_id)
            if obj and obj.CheckAccess("read"):
                result.append(obj)
        return result

    def iterPersons(self, objects=None):
        persnos = []

        def yield_unique(person):
            if person.personalnummer not in persnos:
                persnos.append(person.personalnummer)
                if isUserVisible(person):
                    return person
            return None

        for obj in self.objects:
            if isinstance(obj, User):
                if yield_unique(obj):
                    yield obj
            elif isinstance(obj, ObjectSharingGroup):
                for person in obj.iterPersons(objects):
                    if yield_unique(person):
                        yield person
            else:
                obj_method = getattr(obj, "iterPersons", obj.getPersons)
                for person in iter(obj_method()):
                    if yield_unique(person):
                        yield person

    def getPersons(self, objects=None):
        return [p for p in self.iterPersons(objects)]
