# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

import six
from itertools import islice
from six.moves import reduce


def asPairs(seq):
    """
    >>> list(asPairs([1,2,3,4]))
    [(1, 2), (2, 3), (3, 4)]
    """
    it = iter(seq)
    pair = tuple(islice(it, 2))
    if len(pair) == 2:
        yield pair
    for elem in it:
        pair = (pair[1], elem)
        yield pair


def removeDuplicatesOrdered(values):
    """
    >>> removeDuplicatesOrdered([2, 4, 2, 3])
    [2, 4, 3]
    """
    resultList = []
    resultSet = set()

    for v in values:
        if v not in resultSet:
            resultSet.add(v)
            resultList.append(v)

    return resultList


def toposort(data):
    """
    :param data dictionary whose values are sets
    :return: (list of sets, set)  the second element contains the remaining elements
                                  in case of cycles

    Adapted from:
    http://code.activestate.com/recipes/578272-topological-sort/

    >>> toposort({1:{2, 3}, 2:{3}, 3:set()})
    ([set([3]), set([2]), set([1])], set([]))
    """
    # remove self-references
    for k, v in list(data.items()):
        v.discard(k)
    groups = []
    # Find all items that don't depend on anything and add empty set
    extra_items_in_deps = reduce(set.union, six.iteritems(data), set()) - set(data)
    for item in extra_items_in_deps:
        data[item] = set()

    while True:
        ordered = set(item for item, dep in six.iteritems(data) if not dep)
        if not ordered:
            break
        groups.append(ordered)
        data = {item: (dep - ordered)
                for item, dep in six.iteritems(data) if item not in ordered}

    return groups, set(data.keys())
