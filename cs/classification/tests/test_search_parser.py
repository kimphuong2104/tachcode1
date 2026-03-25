# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# pylint: disable-all
# pylint: skip-file



import json
import logging
import tatsu

from cs.classification.tests import utils
from cs.classification import search_parser

LOG = logging.getLogger(__name__)


class TestSearchParser(utils.ClassificationTestCase):

    specialchars_to_be_masked = ['%', '?', '=', '(', ')', '\\', '*']

    specialchars = [
        '+', '-', '!', '§', '$', '&', '{', '}', '[', ']', '^',
        '°', '~', ':', ',', '.', "'", "´", "`", "/", "|", '_', "#"
    ]

    unicode_special_chars = [
        '\u003C',  # u'<'
        '\u003E',  # u'>'
        '\u2013',  # u'–'
        '\u2018',  # u'‘'
        '\u2019',  # u'’'
        '\u201A',  # u'‚'
        '\u201B',  # u'‛'
        '\u201C',  # u'“'
        '\u201D',  # u'”'
        '\u201E',  # u'„'
        '\u201F',  # u'‟'
        '\u2212',  # u'−'
        '\u2215',  # u'∕'
        '\u2216',  # u'∖'
        '\u2217',  # u'∗'
        '\u2223',  # u'∣'
        '\u2264',  # u'≤'
        '\u2265',  # u'≥'
        '\u2266',  # u'≦'
        '\u2267',  # u'≧',
        '\u00A0'   # nbsp
    ]

    def setUp(self):
        super(TestSearchParser, self).setUp()
        self.maxDiff = None

    def _parse_search_term(self, search_term, with_identifier=True, with_dump=False, with_trace=False):
        try:
            if with_identifier:
                ast = search_parser.parse_with_identifiers_needed(search_term, trace=with_trace)
            else:
                ast = search_parser.parse_without_identifiers_needed(search_term, trace=with_trace)
            if with_dump:
                print(json.dumps(ast, indent=4, ensure_ascii=False))
            return True
        except tatsu.exceptions.ParseError as ex:
            LOG.exception(ex)
            if not with_trace:
                self._parse_search_term(
                    search_term, with_identifier=True, with_dump=with_dump, with_trace=True
                )
            return False

    def test_single_values(self):
        for indentifier in ['', 'a']:
            for k, teststr in sorted({
                '1: test float =': '{indentifier}=123,456',
                '2: test float <': '{indentifier}<123,456',
                '3: test float >': '{indentifier}>123,456',
                '4: test float >=': '{indentifier}>=123,456',
                '5: test float <=': '{indentifier}<=123,456',
                '6: test float <>': '{indentifier}<>123,456',
                '7: test float !=': '{indentifier}!=123,456',
                '8: test float with seperator': '{indentifier}=1.234,456',
                '9: test float without leading zero': '{indentifier}=,456',
                '10: test negative float': '{indentifier}=-123,456',
                '11: test float with one digit': '{indentifier}=3,3',
                '12: test float in string': '{indentifier}="float 3,3 im text"',
                '100: test int =': '{indentifier}=10',
                '101: test int <': '{indentifier}<10',
                '102: test int >': '{indentifier}>10',
                '103: test int >=': '{indentifier}>=10',
                '104: test int <=': '{indentifier}<=10',
                '105: test int <>': '{indentifier}<>10',
                '106: test int !=': '{indentifier}!=10',
                '106: test int with seperator': '{indentifier}=1.234',
                '107: test int with leading zero': '{indentifier}=0123',
                '109: test negative int': '{indentifier}=-2',
                '110: test int in string': '{indentifier}="int 2 im text"',
                '110: test int with one digit': '{indentifier}=0',
                '200: test string = ': '{indentifier}="teststring"',
                '201: test string != ': '{indentifier}!="teststring"',
                '202: test string <> ': '{indentifier}<>"teststring"',
                '203: test empty string': '{indentifier}=""',
                '200: test unquoted string = ': '{indentifier}=teststring',
                '300: test with date only in legacy format': '{indentifier}=22.11.2016',
                '301: test with date and time in legacy format': '{indentifier}=22.11.2016 23:59:59',
                '302: test with date and time in isoformat with ms': '{indentifier}=2016-12-02T14:14:00.011000',
                '303: test with date and time in isoformat without ms': '{indentifier}=2016-12-02T14:14:00',
                '304: test with date and time in isoformat with timezone UTC': '{indentifier}=2016-12-02T14:14:00Z',
                '305: test with date and time in isoformat with timezone as positive delta from UTC': '{indentifier}=2016-12-02T14:14:00+01:00',
                '306: test with date and time in isoformat with timezone as negative delta from UTC': '{indentifier}=2016-12-02T14:14:00-01:00',
                '307: test with date and time in isoformat with timezone UTC within a string': '{indentifier}="dies ist ein test mit datum 2016-12-02T14:14:00Z im text"',
            }.items(), key=lambda t: t[0]):
                with_identifier = True if indentifier else False
                if not self._parse_search_term(
                    teststr.format(indentifier=indentifier),
                    with_identifier=with_identifier
                ):
                    assert False, '{} failed'.format(teststr)

    def test_special_chars(self):
        for specialchar in TestSearchParser.specialchars:
            search_term = 'a="{}"'.format(specialchar)
            self._parse_search_term(search_term)

    def test_masked_special_chars(self):
        for specialchar in TestSearchParser.specialchars_to_be_masked:
            search_term = 'a="\\{}"'.format(specialchar)
            self._parse_search_term(search_term)

    def test_unicode_special_chars(self):
        for specialchar in TestSearchParser.unicode_special_chars:
            search_term = 'a="{}"'.format(specialchar)
            self._parse_search_term(search_term)

    def test_inputs_with_id_needed(self):
        """ search parser tests for inputs which need to have identifiers """
        for k, teststr in sorted({
            '01: simple left expression, complex right expression': '((a=1) or ((b=2) and (c=1)))',  # grouping
            '02: complex left expression, simple right expression': '(((a=1) or (b=2)) and (c=1))',
            # phrase escaping / special chars
            '03: simple phrase without whitespace and special chars': 'a="test"',
            '04: simple phrase without whitespace and quote in the middle': '(a="te\\"st")',
            '05: simple phrase with escaped quote sign in the middle and at the end': '(a="te\\"st\\"")',
            '06: simple phrase with whitespaces': 'a="dies ist ein test"',
            '07: simple phrase with asterisk in the middle of a word (unescaped)': 'a="di*es ist ein test"',
            '08: simple phrase with asterisk in the middle of a wort (escaped)': 'a="di\*es ist ein test"',
            '09: simple phrase with asterisk at the end (unescaped)': 'a="dies ist ein test*"',
            '10: simple phrase with asterisk at the end (escaped)': 'a="dies ist ein test\*"',
            '11: simple phrase with asterisk at the beginning (unescaped)': 'a="*dies ist ein test"',
            '12: simple phrase with asterisk at the beginning (escaped)': 'a="\*dies ist ein test"',
            '13: simple phrase with percent sign at the middle of a word (unescaped)': 'a="di%es ist ein test"',
            '14: simple phrase with percent sign at the middle of a word (escaped)': 'a="di\%es ist ein test"',
            '15: simple phrase with percent sign at the end (unescaped)': 'a="dies ist ein test%"',
            '16: simple phrase with percent sign at the end (escaped)': 'a="dies ist ein test\%"',
            '17: simple phrase with percent sign at the beginning (unescaped)': 'a="%dies ist ein test"',
            '18: simple phrase with percent sign at the beginning (escaped)': 'a="\%dies ist ein test"',
            '19: simple phrase with question mark in the middle of a word (unescaped)': 'a="di?es ist ein test"',
            '20: simple phrase with question mark in the middle of a word (escaped)': 'a="di\?es ist ein test"',
            '21: simple phrase with question mark at the end (unescaped)': 'a="dies ist ein test?"',
            '22: simple phrase with question mark at the end (escaped)': 'a="dies ist ein test\?"',
            '23: simple phrase with question mark at the beginning (unescaped)': 'a="?dies ist ein test"',
            '24: simple phrase with question mark at the beginning (escaped)': 'a="\?dies ist ein test"',
            '25: simple phrase with double question mark (unescaped)': 'a="??dies ist ein test"',
            '26: simple phrase with triple question mark (unescaped)': 'a="???dies ist ein test"',
            '27: simple phrase with question mark between to whitespaces (unescaped)': 'a="dies ? ist ein test"',
            '28: simple phrase with escaped and': 'a="this \\and that"',
            '29: simple phrase with escaped or': 'a="this \\or that"',
            # term escaping / special chars
            # ranges/relops
            '30: simple term with asterisk in the middle of a word (unescaped)': 'a=di*es',
            '31: simple term with asterisk at the end (unescaped)': 'a=dies*',
            '32: simple term with asterisk at the beginning (unescaped)': 'a=*dies',
            '33: simple int exclusive range with brackets': '(a>0 and a<2)',
            '34: simple int inclusive range with brackets': '(a>=0 and a<=2)',
            '35: simple int not equal without brackets': 'a!=0',
            '36: simple int not equal without brackets': 'a<>0',
            '37: simple int equal without brackets': 'a=1',
            '38: simple text equal without brackets': 'a=test',
            '39: simple phrase with german umlauts': 'a=öäüß',
            '40: complex query': '(((a=1) or (b="dies is\?t ein te\%stöäüß\*")) and ((c>=3) and (d!="di%es ?ist *ein test")))',
            '43: test': '((a=1 or b=1) and c=1)',
            '44: test with number in identifier at the end': 'test1=1',
            '45: test with number in identifier in the middle': 'te1st=1',
            '46: test with underscore in identifier at the end': 'test_=1',
            '47: test with underscore in identifier in the middle': 'te_st=1',
            '48: test with underscore in identifier at the beginning': '_test=1',
            '49: test with float number': 'test=5,0',
            '50: test with int number': 'test=5',
            '51: test with int number with group separators': 'test=1.000.000',
            '52: test with float number with group separators': 'test=1.000.000,123',
            '53: test with date only in legacy format': 'test=22.11.2016',
            '54: test with date and time in legacy format': 'test=22.11.2016 23:59:59',
            '55: test with date and time in isoformat with ms': 'test=2016-12-02T14:14:00.011000',
            '56: test with date and time in isoformat without ms': 'test=2016-12-02T14:14:00',
            '57: test with date and time in isoformat with timezone UTC': 'test=2016-12-02T14:14:00Z',
            '58: test with date and time in isoformat with timezone as positive delta from UTC': 'test=2016-12-02T14:14:00+01:00',
            '59: test with date and time in isoformat with timezone as negative delta from UTC': 'test=2016-12-02T14:14:00-01:00',
            '60: test with date and time in isoformat with timezone UTC within a string': 'test="dies ist ein test mit datum 2016-12-02T14:14:00Z im text"',
            '61: test complex string with special chars': 'test="Hallo, ich bin\'s"',
            '62: test complex string with special chars': 'test="Hello, it\'s me"',
            '63: simple phrase with escaped (': 'a="this \\( that"',
            '64: simple phrase with escaped )': 'a="this \\) that"',
            '70: simple phrase with or as prefix': 'a="Orange"',
            '71: 40 halogen–free organic phosphorus compounds': 'a="40 halogen–free organic phosphorus compounds"',
            '70: simple phrase with slash': 'a="123/456"',
            '71: simple phrase with special chars': 'a="wert^°!§$%&?´`|\=123"'
        }.items(), key=lambda t: t[0]):
            if not self._parse_search_term(teststr, with_identifier=True):
                assert False, '{} failed'.format(teststr)

    def test_inputs_with_id_not_needed(self):
        """ search parser tests for inputs which do not need to have identifiers """
        for k, teststr in sorted(list({
            '1: range query without identifiers': '>=10 and <=20',
            '2: complex query partly without brackets': '(>=10 and (<=20 or =30) and (=3 or !=4))',
            '3: complex query without identifiers': '(((=1) or (="dies is\?t ein te\%stöäüß\*")) and ((>=3) and (!="di%es ?ist *ein test")))'
        }.items()), key=lambda t: t[0]):
            if not self._parse_search_term(teststr, with_identifier=False):
                print ('{} failed'.format(teststr))
                assert False, '{} failed'.format(teststr)
