#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
r"""
Module TargetProcessor

Parse an expression for the target value and returns a
boolean value (True if the expression is satisfied).

Usage:

from cs.metrics.targetprocessor import TargetProcessor
tp = TargetProcessor(<target value>)
tp(<actual value>)
    True if <actual value> satisfies <target value>, False otherwise
    raises InvalidTargetValue if <target value> is not a legal expression
tp.values
    Set of values which satisfy the target value


>>> from cs.metrics.targetprocessor import TargetProcessor
>>> tp = TargetProcessor('< 10 and > 2')
>>> tp(7)
True
>>> tp(20)
False
>>> tp.values
(2.0, 10.0)
>>> TargetProcessor('invalid expression')
Traceback (most recent call last):
  File "<console>", line 1, in <module>
  File "C:\Users\gda\AppData\Local\Contact\Server\cdbqc\site-packages\contact\solutions\qc\TargetProcessor.py", line 54, in __init__
    raise InvalidTargetValue
InvalidTargetValue
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import enum
import six


class TargetStatus(enum.IntEnum):
    not_given = 0
    invalid = 1
    red = 2
    yellow = 3
    green = 4


def _initialite_grammar(parser):
    """
    Construct a grammar for target value expressions and configure a parser for it.

    :param parser: a parser for the grammar
    :type parser: a class which implements the same interface as ``TargetProcessor``
    """
    # Late import for better performance while bootstrapping
    import pyparsing
    number = pyparsing.Combine(pyparsing.Optional(pyparsing.Literal("-")) +
                               pyparsing.Word(pyparsing.nums) +
                               pyparsing.Optional("." + pyparsing.Word(pyparsing.nums))
                               ).setParseAction(lambda x, y, z: parser.number(z[0]))
    numberlist = pyparsing.delimitedList(number, ";").setParseAction(lambda x, y, z: parser.numberlist(list(z)))
    le = pyparsing.Literal('<=')
    lt = pyparsing.Literal('<')
    ge = pyparsing.Literal('>=')
    gt = pyparsing.Literal('>')
    eq = pyparsing.Literal('=')
    comparison = ((le | lt | ge | gt | eq) + number).setParseAction(lambda x, y, z: parser.comparison(z[0], z[1]))
    expr = (numberlist | comparison).setParseAction(lambda x, y, z: parser.expr(z[0]))
    target = pyparsing.infixNotation (expr, [
        ("not", 1, pyparsing.opAssoc.RIGHT, lambda x, y, z: parser.lnot(z[0][1])),
        ("or", 2, pyparsing.opAssoc.LEFT, lambda x, y, z: parser.lor(z[0][0::2])),
        ("and", 2, pyparsing.opAssoc.LEFT, lambda x, y, z: parser.land(z[0][0::2])),
    ])
    return target


class TargetProcessor:
    """
    Parser for target value expression

    To be used as follows:

    tp = TargetProcessor(<target value>)
    tp(<actual value>)
        True if <actual value> satisfies <target value>, False otherwise
        raises InvalidTargetValue if <target value> is not a legal expression
    tp.values
        Set of values which satisfy the target value
    """

    def __init__(self, tvalue):
        # Late import for better performance while bootstrapping
        import pyparsing
        self.tvalue = tvalue

        try:
            grammar = _initialite_grammar(self)
            self.values = grammar.parseString(tvalue, parseAll=True)[0]
        except pyparsing.ParseException:
            raise InvalidTargetValue

    def __call__(self, value):
        return float(value) in self.values

    def land(self, ssets):
        return six.moves.reduce(lambda x, y: x.intersect(y), ssets)

    def lor(self, ssets):
        return six.moves.reduce(lambda x, y: x.union(y), ssets)

    def lnot(self, sset):
        return sset.complement

    def expr(self, sset):
        return sset

    def comparison(self, op, value):
        # Late import for better performance while bootstrapping
        import sympy
        if op == '<=':
            return sympy.Interval(-sympy.oo, value)
        elif op == '<':
            return sympy.Interval(-sympy.oo, value, right_open=True)
        elif op == '>=':
            return sympy.Interval(value, sympy.oo)
        elif op == '>':
            return sympy.Interval(value, sympy.oo, left_open=True)
        elif op == '=':
            return sympy.FiniteSet(value)

    def numberlist(self, nums):
        # Late import for better performance while bootstrapping
        import sympy
        return sympy.FiniteSet(nums)

    def number(self, num):
        number = float(num)
        return number


class InvalidTargetValue(Exception):
    """
    Exception raised when the considered expression
    is not a valid target value expression
    """
    pass
