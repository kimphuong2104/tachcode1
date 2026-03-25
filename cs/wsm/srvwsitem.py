#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import logging

from collections import OrderedDict

import six


class ChildAlreadyExistingError(Exception):
    """
    This exception is thrown when trying to append a child with an identical (name, type).
    """

    pass


class InvalidItemPath(Exception):
    pass


class InvalidItem(Exception):
    pass


class SrvWsItem(object):
    """
    Baseclass for WsItem implementations.

    :ivar _itemName: unicode string
    :ivar _itemType: unicode string
    :ivar _parent: WsItem tree
    :ivar _children: dictionary of child WsItem objects children are accessed using (itemName, itemType) as key
    """

    def __init__(self, itemName, itemType):
        """
        Initialize WsItem.

        :Parameters:
            itemName : string
                name of the object. The pair (type, itemName) is unique for all
                direct children of one WsItem.
            itemType : string
                type of the object. The pair (type, itemName) is unique for all
                direct children of one WsItem.
            mesh : Mesh instance
                the Mesh containing this WsItem
        """
        self._itemName = itemName
        self._itemType = itemType
        self._itemId = None
        self._parent = None
        self._children = OrderedDict()
        self._attrDict = {}

    def __str__(self):
        """
        Return a printable representation of self for debug purposes.
        """
        retStr = "WsItem instance at %s\n" % hex(id(self)).upper()
        retStr = "%s_itemName:%s\n_itemType:%s" % (
            retStr,
            self._itemName,
            self._itemType,
        )
        return retStr

    def getParent(self):
        """
        Get the parent item of this item. None if not available

        :returns: WsItem or None
        """
        return self._parent

    def setParent(self, parent):
        """
        Set the parent item of self.
        """
        self._parent = parent

    def getAttributes(self):
        """
        Get all attributes of this item

        :returns: Dict of attributes
        """
        return self._attrDict

    def getChildren(self):
        """
        Get all children of this item

        :returns: List of children
        """
        return list(six.itervalues(self._children))

    def _getItemPathList(self):
        if self._parent is not None:
            p = self._parent._getItemPathList()
            p.append(self.getItemId())
        else:
            p = [self.getItemId()]

        return p

    def getItemPath(self):
        """
        Get the full wsitem path of this item up to the root item.

        :returns: the path (from type, itemName) up to the root item (item with no parent)
        """

        return tuple(self._getItemPathList())

    def appendChild(self, child, overwriteExisting=False):
        """
        Append a child to self.

        Appends a child to self. Modifies the _parent and ._mesh attributes in child
        if overwriteExtisting is False and child.getItemID exists in children an
        exception (ChildAlreadyExistingError) will bei thrown.
        :raises: ChildAlreadyExistingError , AccessViolationError
        """

        typeNamePair = (child._itemType, child._itemName)
        if not overwriteExisting:
            if typeNamePair in self._children:
                logging.error(
                    u"Unable to append child instance '%s' to WsItem instance '%s', because a child with identical name and value already exists",
                    child.getItemId(),
                    self.getItemId(),
                )
                e = ChildAlreadyExistingError(
                    "cannot append child node '%s' to node '%s'"
                    % (
                        six.text_type(child.getItemId()),
                        six.text_type(self.getItemId()),
                    )
                )
                e.args = (child,)
                raise e

        self._children[typeNamePair] = child
        child._parent = self

    def deleteChild(self, child):
        """
        delete the child from self
        """
        if child:
            self._children.pop(child.getItemId(), None)

    def delete(self):
        """
        remove itself from the tree
        """
        if self._parent:
            self._parent.deleteChild(self)

    def appendChildToList(self, item, subType, overwriteExisting=False):
        """
        Appends passed item to a itemlist with passed subType

        :Parameters:
            subType : String
                Subtype of passed wsitem
            item : WsItem
                the wsitem to add
        """
        listItem = self.findChildByType(subType)
        if not listItem:
            listItem = SrvWsItem(u"list", subType)
            self.appendChild(listItem)

        listItem.appendChild(item, overwriteExisting)

    def deleteChildFromList(self, item, subType):
        """
        Removes passed item from an itemlist of passed subType

        :Parameters:
            subType : String
                Subtype of passed wsitem
            item : WsItem
                the wsitem to remove
        """
        listItem = self.findChildByType(subType)
        if listItem:
            listItem.deleteChild(item)

    def getItemsAsList(self, itemType):
        """
        Returns all children of a WsItem of passed itemType

        :Parameters:
            itemType : String
                Type of a WsItem
        :returns: List of WsItems or empty List
        """
        ret = []
        rel = self.findChildByType(itemType)
        if rel is not None:
            ret = rel.getChildren()
        return ret

    def setAttribute(self, name, value):
        """
        Sets an attribute for self by name and value.

        :Parameters:
            name : String
                The attributes name
            value : object
                The attributes value

        :raises AccessViolationError: if mesh is readonly
        """

        self._attrDict[name] = value

    def getItemType(self):
        """
        Get the item type of self.

        :returns: itemType : string
        """
        return self._itemType

    def getItemName(self):
        """
        Get the item name of self.

        :returns: item name : string
        """
        return self._itemName

    def getItemId(self):
        """
        Get the unique id of self.

        :returns: item id : string
        """
        if self._itemId is None:
            self._itemId = self.getItemType(), six.text_type(self.getItemName())

        return self._itemId

    def findChildById(self, itemId):
        """
        Find child by id itemId.

        :Parameters:
            itemId : tuple (type,name)
                id identifying a child WsItem instance

        :returns: found WsItem instance or None
        """
        return self._children.get(itemId, None)

    def findChildrenByName(self, itemName):
        """
        Find child by name itemName.

        :Parameters:
            itemName : unicode
                WsItem instance name

        :returns: list of found WsItem instances
        """
        retChildren = []
        for (_, childName), child in six.iteritems(self._children):
            if itemName == childName:
                retChildren.append(child)
        return retChildren

    def findChildrenByType(self, itemType):
        """
        Find child by type itemType.

        :Parameters:
            itemType : unicode
                WsItem instance type

        :returns: list of found WsItem instances
        """
        retChildren = []
        for (childType, _), child in six.iteritems(self._children):
            if itemType == childType:
                retChildren.append(child)
        return retChildren

    def findChildByType(self, itemType):
        """
        Find child by type itemType.

        :Parameters:
            itemType : unicode
                WsItem instance type

        :returns: the first found WsItem of the given type
        """
        for (childType, _), child in six.iteritems(self._children):
            if itemType == childType:
                return child

    def findAttributeByName(self, name):
        """
        Find attribute by its name.

        :Parameters:
            name : string
                the attribute's name

        :returns: object: the found attribute value or None
        """
        return self._attrDict.get(name, None)

    def findUpByType(self, itemType):
        """
        Find WsItem instances matching itemType upwards in the tree hierarhy.

        Search the hierarchy upwardly for the first occurrence of a matching
        WsItem instance.

        :Parameters:
            itemType : string
                a string describing the searched type

        :returns: WsItem. The first matching WsItem instance or None
        """
        retWsItem = None
        if self._parent is not None:
            if self._parent._itemType == itemType:
                retWsItem = self._parent
            else:
                retWsItem = self._parent.findUpByType(itemType)

        return retWsItem

    def findItemByPath(self, itemPath):
        """
        :Parameters:
            itemPath : list of (type, name) pairs
                The path of the item to find

        :returns: WsItem. The item which corresponds to the passed absolute wsitem path or None
        """
        item = None

        if itemPath:
            if len(itemPath) == 1:
                nodeId = itemPath[0]
                if nodeId == self.getItemId():
                    item = self

            elif len(itemPath) > 1:
                currentNode = self
                itemPath = itemPath[1:]
                for node in itemPath:
                    child = currentNode.findChildById(node)
                    if child is None:
                        break
                    else:
                        currentNode = child
                else:
                    item = child

        return item
