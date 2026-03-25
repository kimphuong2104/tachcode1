#!/usr/bin/env python
# -*- Python -*-
# $Id$
#
# Copyright (C) 1990 - 2007 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     wssingleton.py
# Author:   ws
# Creation: 06.09.07
# Purpose:  Base Class for Singletons


"""
Implementation based on
http://blog.toidinamai.de/python/singletons
"""


from abc import ABCMeta
from six import add_metaclass


class SingletonClass(type):
    singletons = {}

    def __call__(self, *args, **kwds):
        try:
            return self.singletons[self]
        except KeyError:
            self.singletons[self] =\
                super(SingletonClass, self).__call__(*args, **kwds)
            return self.singletons[self]


class AbstractSingletonClass (SingletonClass, ABCMeta):

    """
    This metaclass is used for singletons which want to be abstract
    """
    pass


@add_metaclass(SingletonClass)
class Singleton(object):

    """
    Base class for singleton classes.
    """

    # for testing/debugging purposes...
    def _resetSingleton(self, inSingletonClass=None):
        """
            Reset a singleton that will be found in singletons
            :Parameters:
                inSingleton : Singleton-Instance that should be deleted
            :returns: nothing
        """
        if inSingletonClass is None:
            self.__metaclass__.singletons = {}
        else:
            if type(inSingletonClass) in self.__metaclass__.singletons:
                del self.__metaclass__.singletons[type(inSingletonClass)]


def testModule():
    n1 = Singleton()
    n2 = Singleton()
    n1.a = 10
    assert n2.a == 10
    assert n1 == n2


if "__main__" == __name__:
    testModule()
