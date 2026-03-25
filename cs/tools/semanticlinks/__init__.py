#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
u"""
Semantic Links

"""

from __future__ import absolute_import

import six

from cdb import ue
from cdb import util
from cdb import sqlapi
from cdb import ElementsError
from cdb.objects import ByID
from cdb.objects import Forward
from cdb.objects import NULL
from cdb.objects import Object
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import Rule
from cdb.objects.core import ClassRegistry
from cdb.platform import gui
from cdb.platform import mom

from cdb import typeconversion

__docformat__ = u"restructuredtext en"
__revision__ = u"$Id$"


fSemanticLinkType = Forward(__name__ + u".SemanticLinkType")
fSemanticLink = Forward(__name__ + u".SemanticLink")
fLinkGraphConfig = Forward(__name__ + u".LinkGraphConfig")
fLinkMatrixRelship = Forward(__name__ + u".LinkMatrixRelship")
fLinkMatrixConfig = Forward(__name__ + u".LinkMatrixConfig")


class LinkMatrixConfig(Object):

    __maps_to__ = u"cdb_link_matrix_cfg"
    __classname__ = u"cdb_link_matrix_cfg"

    RelationshipsConfigs = Reference_N(fLinkMatrixRelship,
                                       fLinkMatrixRelship.dsm_object_id == fLinkMatrixConfig.cdb_object_id)


class LinkMatrixRelship(Object):

    __maps_to__ = u"cdb_link_matrix_rs"
    __classname__ = u"cdb_link_matrix_rs"


class LinkGraphConfig(Object):

    __maps_to__ = u"cdb_link_graph_cfg"
    __classname__ = u"cdb_link_graph_cfg"


class SemanticLinkType(Object):
    u""" Class for semantic link types. """
    __maps_to__ = u"cdb_semantic_link_type"
    __classname__ = u"cdb_semantic_link_type"

    __invalid__ = u"invalid"

    MirrorLinkType = Reference_1(fSemanticLinkType,
                                 fSemanticLinkType.cdb_object_id == fSemanticLinkType.mirror_lt_object_id)

    @classmethod
    def _validLinkTypesArguments(cls, obj=None, subject_object_classname=u"",
                          object_object_classname=u"", **kwargs):
        args = {SemanticLinkType.__invalid__: 0}
        if obj is not None and hasattr(obj, u'Subject') and hasattr(obj, u'Object') and \
            hasattr(obj.Subject, u'GetClassname') and hasattr(obj.Object, u'GetClassname'):
                subject_object_classname = obj.Subject.GetClassname()
                object_object_classname = obj.Object.GetClassname()
        if subject_object_classname and object_object_classname:
            args.update({u"subject_object_classname": subject_object_classname,
                         u"object_object_classname": object_object_classname})

        args.update(kwargs)
        return args

    @classmethod
    def _validLinkTypesFallbackResults(cls, subject_object_classname,
                                       object_object_classname, **kwargs):
        # Fallback as described in getValidLinkTypes description
        from cdbwrapc import CDBClassDef
        subj_clsdf = CDBClassDef(subject_object_classname)
        subj_clsbase = subj_clsdf.getBaseClassNames()
        if subj_clsbase:
            kwargs[u"subject_object_classname"] = subj_clsbase[-1]
        obj_clsdf = CDBClassDef(object_object_classname)
        obj_clsbase = obj_clsdf.getBaseClassNames()
        if obj_clsbase:
            kwargs[u"object_object_classname"] = obj_clsbase[-1]
        if subj_clsbase or obj_clsbase:
            link_types = cls.KeywordQuery(**kwargs)
            return link_types

    @classmethod
    def getValidLinkTypes(cls, obj=None, subject_object_classname=u"",
                          object_object_classname=u"", **kwargs):
        u"""
        Returns the valid link types for the classnames of the
        Subject-/Object-references of the given obj. Both references must
        have a method GetClassname to resolve their classnames.

        subject_object_classname and object_object_classname are used directly
        when given.

        Additional attributes can be filtered by kwargs, kwargs can also override
        all arguments previously set.

        Fallback:
                when no specialized link types for subject_object_classname and
                object_object_classname exists,
                the link types of their root classes are returned if configured.
        """
        args = cls._validLinkTypesArguments(obj,
                                            subject_object_classname,
                                            object_object_classname,
                                            **kwargs)
        link_types = cls.KeywordQuery(**args)
        if len(link_types) == 0 and \
        u'subject_object_classname' in args and \
        args[u'subject_object_classname'] and \
        u'object_object_classname' in args and \
        args[u'object_object_classname']:
            base_link_types = cls._validLinkTypesFallbackResults(**args)
            link_types = base_link_types if base_link_types else link_types
        return link_types

    @classmethod
    def isValidLinkType(cls, link_type_object_id, obj=None,
                        subject_object_classname=u"", object_object_classname=""):
        link_types = cls.getValidLinkTypes(obj,
                                           subject_object_classname,
                                           object_object_classname,
                                           cdb_object_id=link_type_object_id)
        return len(link_types) == 1

    def isUsed(self):
        u""" Indicates whether a semantic link type is used by semantic links. """
        return len(SemanticLink.KeywordQuery(link_type_object_id=self.cdb_object_id)) > 0

    def setEditMode(self, ctx):
        u"""
        Set dialog fields read only if the semantic link type is used and
        the field for the selected mirror link type mandatory if a mirror link
        should be created. Only exception is the field invalid to disable or
        re-enable future use of the semantic link type.
        """
        if self.isUsed():
            for attribute in ctx.dialog.get_attribute_names():
                if attribute != SemanticLinkType.__invalid__:
                    ctx.set_readonly(attribute)
        if u'gen_mirror_link' in ctx.dialog.get_attribute_names() and \
            ctx.dialog[u'gen_mirror_link'] == u"1":
                ctx.set_mandatory(u'mirror_lt_object_id')
        else:
            ctx.set_optional(u'mirror_lt_object_id')

    def enforceMirrorLinkType(self, ctx=None):
        u"""
        Updates mirror link type if exists or deletes references from former
        mirror link types.
        """
        if self.MirrorLinkType:
            self.MirrorLinkType.mirror_lt_object_id = self.cdb_object_id
            self.MirrorLinkType.invalid = self.invalid
            self.MirrorLinkType.gen_mirror_link = self.gen_mirror_link
        else:
            mirror_links = SemanticLinkType.KeywordQuery(mirror_lt_object_id=self.cdb_object_id)
            for mirror_link in mirror_links:
                mirror_link.mirror_lt_object_id = u""
                mirror_link.gen_mirror_link = 0

    def resetIsCopyLinkType(self, ctx=None):
        u""" Resets whether a mirror link should be created. """
        if not self.is_copy_link_type:
            self.is_copy_link_type = NULL

    def checkUsedConstraint(self, ctx=None):
        u""" Checks whether link type is used already. """
        if self.isUsed():
            raise util.ErrorMessage(u"cdb_semantic_lt_used_constraint")

    def deleteMirrorLinkType(self, ctx=None):
        u""" Deletes mirror link type if it is not used. """
        if self.MirrorLinkType and not self.MirrorLinkType.isUsed():
            self.MirrorLinkType.Delete()
        elif self.MirrorLinkType:
            self.MirrorLinkType.mirror_lt_object_id = u""
            self.MirrorLinkType.gen_mirror_link = 0

    def checkEditConstraint(self, ctx=None):
        u""" Prohibits changes to used link types.
        Only exception is the invalid switch to indicate that
        a semantic link type can not be used any longer."""
        if self.isUsed():
            pobj = self.getPersistentObject()
            attrs = [x.getName() for x in pobj.GetClassDef().getAttributeDefs()]
            check = True
            for attr in attrs:
                previous_val = getattr(pobj, attr)
                actual_val = getattr(self, attr)
                if (actual_val != previous_val) and \
                attr != SemanticLinkType.__invalid__ and \
                not (actual_val == u"" and previous_val == None):
                    check = False
                    break
            if not check:
                raise util.ErrorMessage(u"cdb_semantic_lt_used_constraint")

    event_map = {
                ((u'create', u'modify', u'copy'), (u'pre_mask', u'dialogitem_change')): u'setEditMode',
                ((u'create', u'modify', u'copy'), u'pre'): (u'resetIsCopyLinkType',
                                                            u'checkEditConstraint'),
                ((u'create', u'modify', u'copy'), u'post'): u'enforceMirrorLinkType',
                (u'delete', u'pre'): u'checkUsedConstraint',
                (u'delete', u'post'): u'deleteMirrorLinkType'
                }


class SemanticLink(Object):
    u""" Class for semantic links. """
    __maps_to__ = u"cdb_semantic_link"
    __classname__ = u"cdb_semantic_link"

    LinkType = Reference_1(fSemanticLinkType,
                           fSemanticLinkType.cdb_object_id == fSemanticLink.link_type_object_id)
    MirrorLink = Reference_1(fSemanticLink,
                             fSemanticLink.cdb_object_id == fSemanticLink.mirror_link_object_id)
    Subject = ReferenceMethods_1(Object, lambda self: self._subjectObject())
    Object = ReferenceMethods_1(Object, lambda self: self._objectObject())

    def _subjectObject(self):
        return ByID(self.subject_object_id)

    def _objectObject(self):
        return ByID(self.object_object_id)

    def isEditable(self):
        u""" Indicates whether link is editable.
        A link is editable means that both objects (subject/object) do NOT match the
        'cdb_semantic_link: readonly object' object rule"""

        rule = Rule.ByKeys(u"cdb_semantic_link: readonly object")
        if rule is not None:
            return not rule.match(self.Subject) and not rule.match(self.Object)
        return False

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the mirrorlink and the object itself.
        """
        return [self, self.MirrorLink]

    @classmethod
    def createCopyLink(cls, source_obj, dest_obj):
        u""" Creates a copy link between source object and destination object. """
        dest_classname = dest_obj.GetClassname()
        source_classname = source_obj.GetClassname()
        copy_link_type = SemanticLinkType.getValidLinkTypes(subject_object_classname=dest_classname,
                                                            object_object_classname=source_classname,
                                                            is_copy_link_type=1)
        copy_link_type = copy_link_type[0] if copy_link_type else None
        if copy_link_type:
            sem_link = cls.KeywordQuery(link_type_object_id=copy_link_type.cdb_object_id,
                                        subject_object_id=dest_obj.cdb_object_id,
                                        object_object_id=source_obj.cdb_object_id)
            if not sem_link:
                change_control_values = SemanticLink.MakeChangeControlAttributes()
                sem_link = cls.Create(link_type_object_id=copy_link_type.cdb_object_id,
                                      subject_object_id=dest_obj.cdb_object_id,
                                      object_object_id=source_obj.cdb_object_id,
                                      subject_object_classname=dest_classname,
                                      object_object_classname=source_classname,
                                      **change_control_values)
            sem_link.generateMirrorLink()

    def generateMirrorLink(self, subject_object_classname=None,
                           object_object_classname=None):
        u"""
        Generates a mirror link if not present and should be created
        by the link type.
        """
        if not self.MirrorLink and self.linktype_gen_mirror_link == 1:
            if not subject_object_classname:
                subject_object_classname = self.subject_object_classname
            if not object_object_classname:
                object_object_classname = self.object_object_classname
            change_control_values = SemanticLink.MakeChangeControlAttributes()
            args = {u"link_weight": self.link_weight,
                    u"link_type_object_id": self.linktype_mirror_lt_object_id,
                    u"subject_object_id": self.object_object_id,
                    u"object_object_id": self.subject_object_id,
                    u"mirror_link_object_id": self.cdb_object_id,
                    u"subject_object_classname": object_object_classname,
                    u"object_object_classname": subject_object_classname
                  }
            args.update(change_control_values)
            mirror_link = SemanticLink.Create(**args)
            pobj = self.getPersistentObject()
            pobj_args = {u"subject_object_classname": subject_object_classname,
                         u"object_object_classname": object_object_classname,
                         u"mirror_link_object_id": mirror_link.cdb_object_id
                     }
            pobj_args.update(change_control_values)
            pobj.Update(**pobj_args)

    def processMirrorLink(self, ctx):
        u"""
        Generates mirror link if not present and deletes former mirror link if
        actual link type has no mirror link.

        Updates mirror link if present.
        """
        context = self._loadContext(ctx)
        if ctx.action == u"modify":
            if self.MirrorLink and self.LinkType.mirror_lt_object_id == '':
                self.MirrorLink.Delete()
                self.Reload()
            elif self.MirrorLink:
                change_control_values = SemanticLink.MakeChangeControlAttributes()
                args = dict(link_weight=self.link_weight,
                            link_type_object_id=self.linktype_mirror_lt_object_id)
                args.update(change_control_values)
                self.MirrorLink.Update(**args)
        self.generateMirrorLink(context.get(u'subject_obj_classname'),
                                context.get(u'object_obj_classname'))

    def deleteMirrorLink(self, ctx=None):
        u""" Deletes mirror link. """
        if self.MirrorLink:
            self.MirrorLink.Delete()

    def checkMirrorConstraint(self, ctx=None):
        u"""
        Checks whether a semantic link pair with the same
        link type / mirror link type already exists.
        """
        context = self._loadContext(ctx)
        if self.LinkType and self.LinkType.MirrorLinkType:
            has_mirror_links = SemanticLink.KeywordQuery(subject_object_id=self.subject_object_id,
                                                         object_object_id=context.get(u'object_obj_cdb_object_id'),
                                                         link_type_object_id=self.LinkType.MirrorLinkType.cdb_object_id)
            if has_mirror_links and not has_mirror_links[0].cdb_object_id == self.cdb_object_id and \
                not self.LinkType.cdb_object_id == self.LinkType.MirrorLinkType.cdb_object_id:
                    raise util.ErrorMessage(u"cdb_semantic_link_mirror_constraint",
                                            self.LinkType.MirrorLinkType.GetDescription())

    def checkInvalidConstraint(self, ctx=None):
        u""" Checks if link type is invalid. """
        if self.LinkType.invalid == 1:
            raise util.ErrorMessage(u"cdb_semantic_lt_invalid_constraint")

    def _saveContext(self, ctx):
        u""" Stores context information. """
        subject_obj = self.Subject
        if ctx.dragged_obj:
            object_obj = ByID(ctx.dragged_obj.cdb_object_id)
        else:
            object_obj = self.Object
        ctx.keep(u"subject_obj_classname", subject_obj.GetClassname())
        ctx.keep(u"object_obj_cdb_object_id", object_obj.cdb_object_id)
        ctx.keep(u"object_obj_classname", object_obj.GetClassname())

    def _loadContext(self, ctx):
        if u"subject_obj_classname" in ctx.ue_args.get_attribute_names():
            subject_obj_classname = ctx.ue_args[u"subject_obj_classname"]
        else:
            subject_obj_classname = self.Subject.GetClassname()

        if u"object_obj_classname" in ctx.ue_args.get_attribute_names():
            object_obj_classname = ctx.ue_args[u"object_obj_classname"]
        else:
            object_obj_classname = self.Object.GetClassname()
        object_obj_cdb_object_id = ctx.ue_args[u"object_obj_cdb_object_id"]
        return dict(subject_obj_classname=subject_obj_classname,
                    object_obj_classname=object_obj_classname,
                    object_obj_cdb_object_id=object_obj_cdb_object_id)

    def check_editable_constraint(self, ctx):
        u""" Editable Context Constraint: a link must be editable indicated by
        isEditable to be changed"""
        if not self.isEditable():
            raise ue.Exception(u"cdb_semantic_link_editable_constraint")

    def check_creatable_constraint(self, ctx):
        u""" Creatable Constraint: a link can only be created using
        drag and drop or within the Link-Matrix"""
        if not ctx.dragged_obj and not self.object_object_id:
            raise ue.Exception(u"cdb_semantic_link_creatable_constraint")

    def check_valid_link_type_constraint(self, ctx):
        u""" Ensures that only links with configured link types can be created """

        subj_cls = self.subject_object_classname
        if not subj_cls and self.Subject:
            subj_cls = self.Subject.GetClassname()
        obj_cls = self.object_object_classname
        if not obj_cls and self.Subject:
            obj_cls = self.Object.GetClassname()

        if not SemanticLinkType.isValidLinkType(self.link_type_object_id,
                                                subject_object_classname=subj_cls,
                                                object_object_classname=obj_cls):
            raise ue.Exception(u"cdb_semantic_link_invalid_link_type_constraint")

    def check_equality_constraint(self, ctx):
        u""" Ensure that source and target are not equal """
        if self.subject_object_id == self.object_object_id:
            raise ue.Exception(u"cdb_semantic_link_equality_constraint")

    @classmethod
    def createLink(cls, ctx):
        u""" Preset eLinkUrl"""
        sub = None
        if ctx.parent:
            if "cdb_object_id" in ctx.parent.get_attribute_names():
                sub = ByID(ctx.parent.cdb_object_id)
            else:
                relship = mom.relships.Relship.ByKeys(ctx.relationship_name)
                keys = {}
                for keyname in ctx.parent.get_attribute_names():
                    keys[keyname] = ctx.parent[keyname]
                cl = ClassRegistry().findByClassname(relship.referer)
                sub = cl.ByKeys(**keys)
        if sub:
            link = '/cs-tools-semanticlinks-createLinksApp?restname=%s&cdb_object_id=%s' % (sub.GetClassDef().getRESTName(), sub.cdb_object_id)
            ctx.url(link)
        else:
            raise ue.Exception("subject_not_found")

    def setObsolete(self, ctx):
        if "cdb_obsolete" in self.Subject:
            self.subject_cdb_obsolete = self.Subject.cdb_obsolete
        else:
            self.subject_cdb_obsolete = 0
        if "cdb_obsolete" in self.Object:
            self.object_cdb_obsolete = self.Object.cdb_obsolete
        else:
            self.object_cdb_obsolete = 0

    def checksingularlink(self, ctx):
        if ctx.dragged_obj:
            subj = ByID(self.subject_object_id)
            obj = ByID(self.object_object_id)
            poslink = SemanticLinkType.getValidLinkTypes(subject_object_classname=subj.__classname__,
                                                         object_object_classname=obj.__classname__)
            if len(poslink) == 1:
                ctx.set("link_type_object_id", poslink[0].cdb_object_id)
                ctx.set("linktype_name", poslink[0].name)

    def refresh_table(self, ctx):
        ctx.refresh_tables(['cdb_semantic_link'])

    event_map = {
                (u'create', (u'pre', u'pre_mask')): u'check_creatable_constraint',
                ((u'create', u'modify', u'copy'), u'pre_mask'): u'check_editable_constraint',
                ((u'create', u'modify', u'copy', u'delete'), u'pre'): u'check_editable_constraint',
                ((u'create', u'modify', u'copy'), u'pre'): (u'_saveContext',
                                                            u'check_valid_link_type_constraint',
                                                            u'checkMirrorConstraint',
                                                            u'checkInvalidConstraint',
                                                            u'check_equality_constraint'),
                ((u'create', u'copy'), u'post'): "refresh_table",
                ((u'create', u'copy'), u'now'): "refresh_table",
                ((u'create'), u'pre'): (u'setObsolete'),
                ((u'create', u'modify', u'copy'), u'post'): u'processMirrorLink',
                (u'delete', u'post'): u'deleteMirrorLink',
                (u'create', u'pre_mask'): u'checksingularlink',
                (u'createlink', u'now'): u'createLink',
                }


class SemanticLinkTypeCatalog(gui.CDBCatalog):
    u""" Browser for link types for given subject and object. """
    def init(self):
        try:
            subject_object_id = self.getInvokingDlgValue(u"subject_object_id")
            object_object_id = self.getInvokingDlgValue(u"object_object_id")
            subject_obj = ByID(subject_object_id)
            object_obj = ByID(object_object_id)
            if subject_object_id and object_object_id:
                self.setResultData(SemanticLinkTypeCatalogContent(subject_obj,
                                                                  object_obj, self))
        except KeyError:
            pass


class SemanticLinkTypeCatalogContent(gui.CDBCatalogContent):
    def __init__(self, subject_obj, object_obj, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)

        gui.CDBCatalogContent.__init__(self, tabdef)

        self.data = None
        self.Subject = subject_obj
        self.Object = object_obj
        self._initData()  # initializes self.data

    def _initData(self):
        if self.data is None:
            self.data = SemanticLinkType.getValidLinkTypes(self)

    def getNumberOfRows(self):
        return len(self.data)

    def getRowObject(self, row):
        self._initData()
        return self.data[row].ToObjectHandle()


class SemanticLinkTypeSelectionCatalog(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):
        cdb_object_id = ""
        try:
            cdb_object_id = self.getInvokingDlgValue("cdb_object_id")
        except Exception:
            pass
        if cdb_object_id:
            self.setResultData(SemanticLinkTypeSelectionContent(cdb_object_id, self))


class SemanticLinkTypeSelectionContent(gui.CDBCatalogContent):
    def __init__(self, cdb_object_id, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        gui.CDBCatalogContent.__init__(self, tabdef)
        self.cdb_object_id = cdb_object_id
        self.data = None

    def _initData(self, refresh=False):
        if not self.data or refresh:
            sqlSelect = u"SELECT subject_object_classname, name, object_object_classname "
            sqlFrom = u" FROM cdb_semantic_link_type "
            addCondition = u" where cdb_object_id != '%s' " \
                           u"and subject_object_classname = (select object_object_classname " \
                           u"from cdb_semantic_link_type where cdb_object_id = '%s') " \
                           u"and object_object_classname = (select subject_object_classname " \
                           u"from cdb_semantic_link_type where cdb_object_id = '%s') " \
                           % (self.cdb_object_id, self.cdb_object_id, self.cdb_object_id)
            self.data = sqlapi.RecordSet2(sql=sqlSelect + sqlFrom + addCondition)

    def onSearchChanged(self):
        self._initData()

    def refresh(self):
        self._initData()

    def getNumberOfRows(self):
        self._initData()
        return len(self.data)

    def getRowObject(self, row):
        if not self.cdef:
            return gui.CDBCatalogContent.getRowObject(self, row)
        else:
            self._initData()
            keys = mom.SimpleArgumentList()
            for keyname in self.cdef.getKeyNames():
                keys.append(mom.SimpleArgument(keyname, self.data[row][keyname]))
            return mom.CDBObjectHandle(self.cdef, keys, False, True)

    def _get_value(self, rec, attr):
        """
        Retrieves the value of `attr` from the record `rec`-
        """
        result = u""
        if self.cdef:
            adef = self.cdef.getAttributeDefinition(attr)
            for db_name in adef.getSQLSelectNames():
                result = rec[db_name]
                if result:
                    break
        else:
            result = rec[attr]
        return typeconversion.to_untyped_c_api(result)

    def getRowData(self, row):
        self._initData()
        result = []
        tdef = self.getTabDefinition()
        for col in tdef.getColumns():
            attr = col.getAttribute()
            value = u""
            try:
                obj = self.data[row]
                value = self._get_value(obj, attr)
            except Exception:
                pass
            result.append(value)
        return result


class WithSemanticLinks(object):
    u""" Mixin base-class for classes which possess a semantic link """
    def _SemanticLinks(self):
        return fSemanticLink.KeywordQuery(subject_object_id=self.cdb_object_id)
    SemanticLinks = ReferenceMethods_N(fSemanticLink, _SemanticLinks)


class SemanticLinkGenerator(object):
    __maps_to__ = u"cdb_semantic_link_generator"
    __classname__ = u"cdb_semantic_link_generator"

    event_map = {(('create', 'copy', 'modify'), 'dialogitem_change'): 'change_dialog_field'}

    def change_dialog_field(self, ctx):
        if not self.link_type_object_id:
            ctx.set("mirror_link_object_id", "")
        else:
            slt = SemanticLinkType.ByKeys(self.link_type_object_id)
            ctx.set("mirror_link_object_id", slt.mirror_lt_object_id)


class WithSematicLinkGenerator(object):
    event_map = {
        ('semantic_link_generator_selectiv', 'pre_mask'): 'preset_sl_classname',
        ('semantic_link_generator_selectiv', 'now'): 'generate_sl_selective',
        ('semantic_link_generator_all', 'now'): 'generate_sl_all'
    }

    def preset_sl_classname(self, ctx):
        ctx.set("classname", self.GetClassname())

    def generate_sl_selective(self, ctx):
        if ctx.dialog and ctx.dialog.pyrule_name:
            clsname = ctx.dialog.classname
            rule_name = ctx.dialog.pyrule_name
            slg = SemanticLinkGenerator.ByKeys(classname=clsname,
                                               name=rule_name)
            if slg:
                rule = Rule.ByKeys(rule_name)
                self._generate_from_rule(slg, rule, clsname)
            else:
                raise ue.Exception("semantic_links_generator_rule_not_found")

    def generate_sl_all(self, ctx):
        clsname = self.GetClassname()
        slgs = SemanticLinkGenerator.KeywordQuery(classname=clsname)
        for slg in slgs:
            rule = Rule.ByKeys(slg.name)
            self._generate_from_rule(slg, rule, clsname)

    def _generate_from_rule(self, slg, rule, clsname):
        objects = rule.getObjects()
        for obj in objects:
            obj_clsname = obj.GetClassname()
            args = {u"link_type_object_id": slg.link_type_object_id,
                    u"subject_object_id": self.cdb_object_id,
                    u"object_object_id": obj.cdb_object_id,
                    u"mirror_link_object_id": slg.mirror_link_object_id,
                    u"subject_object_classname": clsname,
                    u"object_object_classname": obj_clsname
                    }
            try:
                SemanticLink.CreateNoResult(**args)
            except ElementsError:
                pass
            if slg.mirror_link_object_id:
                mirror_args  = {u"link_type_object_id": slg.mirror_link_object_id,
                                u"subject_object_id": obj.cdb_object_id,
                                u"object_object_id": self.cdb_object_id,
                                u"mirror_link_object_id": slg.link_type_object_id,
                                u"subject_object_classname": obj_clsname,
                                u"object_object_classname": clsname
                                }
                try:
                    SemanticLink.CreateNoResult(**mirror_args)
                except ElementsError:
                    pass
