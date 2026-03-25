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

from cdb import i18n

from cs.classification import search_parser
from cs.classification import search_semantics
from cs.classification.tests import utils
from cs.classification.util import get_epsilon

LOG = logging.getLogger(__name__)


class TestSearchSemantics(utils.ClassificationTestCase):

    def setUp(self):
        super(TestSearchSemantics, self).setUp()
        self.maxDiff = None
        # remove this if tatsu has been updated in plattform to 4.4.0
        tatsu_version = tatsu.__version__
        if tatsu_version.startswith("4.2") or tatsu_version.startswith("4.3"):
            self.bracket_open = "("
            self.bracket_close = ")"
        else:
            self.bracket_open = ""
            self.bracket_close = ""

    def test_search_semantics_for_inputs_with_id_needed(self):
        """ search semantics tests for inputs which need to have identifiers """
        semantic = search_semantics.ClassificationSolrSearchWithIdentifiersSemantics()
        for k, teststr in sorted({
            '01: simple left expression, complex right expression': ('((a=1) or ((b=2) and (c=1)))', 'a:1 or (b:2 and c:1)'),
            '02: complex query with "and", "or" and inclusive range': ('((a=30 and b=40) or (c>=10 and c<=20))', '(a:30 and b:40) or c:[10 TO 20]'),
            '04: complex query with single asterisks': ('((a=*n and a=B*) and b!=Br*n)', '(a:*n and a:B*) and {bracket_open}*:* AND -b:Br*n{bracket_close}'.format(bracket_open=self.bracket_open, bracket_close=self.bracket_close)),
            '05: simple phrase without whitespace and special chars': ('a="test"', 'a:test'),
            '06: simple phrase without whitespace and quote in the middle': ('a="te\\"st"', 'a:"te\\"st"'),
            '07: simple phrase with escaped quote sign in the middle and at the end': ('(a="te\\"st\\"")', 'a:"te\\"st\\""'),
            '08: simple phrase with whitespaces': ('a="dies ist ein test"', 'a:"dies ist ein test"'),
            '09: simple phrase with asterisk in the middle of a word (unescaped)': ('a="di*es ist ein test"', 'a:di*es\\ ist\\ ein\\ test'),
            '10: simple phrase with asterisk in the middle of a wort (escaped)': ('a="di\*es ist ein test"', 'a:"di\*es ist ein test"'),
            '11: simple phrase with asterisk at the end (unescaped)': ('a="dies ist ein test*"', 'a:dies\\ ist\\ ein\\ test*'),
            '12: simple phrase with asterisk at the end (escaped)': ('a="dies ist ein test\*"', 'a:"dies ist ein test\*"'),
            '13: simple phrase with asterisk at the beginning (unescaped)': ('a="*dies ist ein test"', 'a:*dies\\ ist\\ ein\\ test'),
            '14: simple phrase with asterisk at the beginning (escaped)': ('a="\*dies ist ein test"', 'a:"\*dies ist ein test"'),
            '15: simple phrase with percent sign at the middle of a word (unescaped)': ('a="di%es ist ein test"', 'a:di*es\\ ist\\ ein\\ test'),
            '16: simple phrase with percent sign at the middle of a word (escaped)': ('a="di\%es ist ein test"', 'a:"di%es ist ein test"'),
            '17: simple phrase with percent sign at the end (unescaped)': ('a="dies ist ein test%"', 'a:dies\\ ist\\ ein\\ test*'),
            '18: simple phrase with percent sign at the end (escaped)': ('a="dies ist ein test\%"', 'a:"dies ist ein test%"'),
            '19: simple phrase with percent sign at the beginning (unescaped)': ('a="%dies ist ein test"', 'a:*dies\\ ist\\ ein\\ test'),
            '20: simple phrase with percent sign at the beginning (escaped)': ('a="\%dies ist ein test"', 'a:"%dies ist ein test"'),
            '21: simple phrase with question mark in the middle of a word (unescaped)': ('a="di?es ist ein test"', 'a:di?es\\ ist\\ ein\\ test'),
            '22: simple phrase with question mark in the middle of a word (escaped)': ('a="di\?es ist ein test"', 'a:"di\?es ist ein test"'),
            '23: simple phrase with question mark at the end (unescaped)': ('a="dies ist ein test?"', 'a:dies\\ ist\\ ein\\ test?'),
            '24: simple phrase with question mark at the end (escaped)': ('a="dies ist ein test\?"', 'a:"dies ist ein test\?"'),
            '25: simple phrase with question mark at the beginning (unescaped)': ('a="?dies ist ein test"', 'a:?dies\\ ist\\ ein\\ test'),
            '26: simple phrase with question mark at the beginning (escaped)': ('a="\?dies ist ein test"', 'a:"\?dies ist ein test"'),
            '27: simple phrase with double question mark (unescaped)': ('a="??dies ist ein test"', 'a:??dies\\ ist\\ ein\\ test'),
            '28: simple phrase with triple question mark (unescaped)': ('a="???dies ist ein test"', 'a:???dies\\ ist\\ ein\\ test'),
            '29: simple phrase with question mark between to whitespaces (unescaped)': ('a="dies ? ist ein test"', 'a:dies\\ ?\\ ist\\ ein\\ test'),
            '30: simple phrase with escaped and': ('a="this \\and that"', 'a:"this and that"'),
            '31: simple phrase with escaped or': ('a="this \\or that"', 'a:"this or that"'),
            # term escaping / special chars
            # ranges/relops
            '32: simple term with asterisk in the middle of a word (unescaped)': ('a=di*es', 'a:di*es'),
            '33: simple term with asterisk at the end (unescaped)': ('a=dies*', 'a:dies*'),
            '34: simple term with asterisk at the beginning (unescaped)': ('a=*dies', 'a:*dies'),
            '35: simple exclusive range with brackets': ('(a>10 and a<20)', 'a:{10 TO 20}'),
            '36: simple int inclusive range with brackets': ('(a>=0 and a<=2)', 'a:[0 TO 2]'),
            '37: simple int not equal without brackets': ('a!=0', '*:* AND -a:0'),
            '38: simple int not equal without brackets': ('a<>0', '*:* AND -a:0'),
            '39: simple int equal without brackets': ('a=1', 'a:1'),
            '40: simple text equal without brackets': ('a=test', 'a:test'),
            '41: simple phrase with german umlauts': ('a=öäüß', 'a:öäüß'),
            '42: complex query': ('(((a=1) or (b="dies is\?t ein te\%stöäüß\*")) and ((c>=3) and (d!="di%es ?ist *ein test")))', '(a:1 or b:"dies is\\?t ein te%stöäüß\\*") and (c:[3 TO *] and *:* AND -d:di*es\\ ?ist\\ *ein\\ test)'),
            '43: single range query exclusive max': ('a<5', 'a:[* TO 5}'),
            '44: single range query exclusive min': ('a>5', 'a:{5 TO *]'),
            '45: single range query inclusive max': ('a<=5', 'a:[* TO 5]'),
            '46: single range query inclusive min': ('a>=5', 'a:[5 TO *]'),
            '47: double range query using "or"': ('a<=5 or a>=5', 'a:[* TO 5] or a:[5 TO *]'),
            '48: complex range combination': ('a<=5 and (b>5 or c<asd)', '(a:[* TO 5]) and (b:{5 TO *] or c:[* TO asd})'),
            '49: test': ('((a=1 or b=1) and c=1)', '(a:1 or b:1) and {}c:1{}'.format(self.bracket_open, self.bracket_close)),
            '50: test automatic lucene special chars escaping in single term': ('a=+-!{}[]^~:', 'a:\+\-\!\{\}\[\]\^\~\:'),
            '51: test automatic lucene special chars escaping in single phrase': ('a="+-!{}[]^~:"', 'a:"\+\-\!\{\}\[\]\^\~\:"'),
            '52: single date and time term in isoformat with UTC timezone': ('a=2016-12-02T14:14:00Z', 'a:"2016-12-02T14:14:00Z"'),
            '53: single date in legacy ce format': ('a=02.12.2016', 'a:"2016-12-02T00:00:00Z"'),
            '54: single date range query': ('a>01.01.2016 and a<01.01.2019', 'a:{"2016-01-01T00:00:00Z" TO "2019-01-01T00:00:00Z"}'),
            '55: simple phrase with escaped (': ('a="this \( that"', 'a:"this \( that"'),
            '56: simple phrase with escaped )': ('a="this \) that"', 'a:"this \) that"'),
            # Tests for floating point formats
            "57: floating point with comma as separator": ("a=0,8", "a:0.8"),
            "58: floating point with dot as separator": ("a=0.8", "a:0.8"),
            # Floats without leading zero are currently not supported
            # "59: floating point with comma and without leading zero": ("a=,8", "a:0.8"),
            # "60: floating point with dot and without leading zero": ("a=.8", "a:0.8"),
        }.items(), key=lambda t: t[0]):
            parsestr = teststr[0]
            expected = teststr[1]
            try:
                ast = search_parser.parse_with_identifiers_needed(parsestr, semantic)
                assert isinstance(ast, dict), json.dumps(ast, indent=4, ensure_ascii=False)
                assert 'solr_complete_term' in ast, json.dumps(ast, indent=4, ensure_ascii=False)
                parseresult = ast.get('solr_complete_term')
                assert parseresult == expected, '{}: expected: "{}" != "{}"'.format(k, expected, parseresult)
            except tatsu.exceptions.ParseError:
                ast = search_parser.parse_with_identifiers_needed(parsestr,
                                                                  semantic,
                                                                  trace=True)
                assert False, '{} failed'.format(k)

    def test_search_semantics_for_inputs_with_id_not_needed_and_no_float_normalization(self):
        """ search semantics tests for inputs which do not need to have identifiers but use default identifier instead and have no float normalization function given"""
        default_property_code = 'DEFAULT_PROPERTY_CODE'
        for k, testargs in sorted({
            '01: inclusive range without identifiers': ('>=10 and <=20', default_property_code + ':[10 TO 20]', {}),
            '02: exclusive range without identifiers': ('>10 and <20', default_property_code + ':{10 TO 20}', {}),
            '03: complex query with single asterisks': ('((=*n and =B*) and !=Br*n)', "({default_code}:*n and {default_code}:B*) and {bracket_open}*:* AND -{default_code}:Br*n{bracket_close}".format(default_code=default_property_code, bracket_open=self.bracket_open, bracket_close=self.bracket_close), {}),
            '04: simple phrase with spaces': ('="dies ist ein test"', default_property_code + ':"dies ist ein test"', {}),
            '05: simple phrase with int number': ('test="dies ist ein 1000000 test"', 'test:"dies ist ein 1000000 test"', {"is_text_property": True}),
            '06: simple phrase with int number and wildcard': ('test="dies ist * 1000000 test"', 'test:dies\\ ist\\ *\\ 1000000\\ test', {"is_text_property": True}),
            '07: simple phrase with float number and comma separator': ('test="dies ist ein 1000,000 test"', 'test:"dies ist ein 1000,000 test"', {"is_text_property": True}),
            '07.1: simple phrase with float number and dot separator': ('test="dies ist ein 1000.000 test"', 'test:"dies ist ein 1000.000 test"', {"is_text_property": True}),
            '08 simple phrase with dots, equality signs and spaces': ('="dies.text = das.nicht"', default_property_code + ':"dies\\.text = das\\.nicht"', {}),
            '09 simple query for an int value': ('=10', default_property_code + ':10', {}),
            '10 simple query for a float value': ('=10.123', default_property_code + ':10.123', {}),
            '11 simple query for a float value': ('=10,123', default_property_code + ':10.123', {}),
            '12 simple query for a text value without spaces': ('=test'.replace('.', i18n.get_decimal_separator()), default_property_code + ':test', {}),
            '13: single date and time term in isoformat with UTC timezone': ('=2016-12-02T14:14:00Z', default_property_code + ':"2016-12-02T14:14:00Z"', {}),
            '14: single date in legacy ce format': ('=02.12.2016', default_property_code + ':"2016-12-02T00:00:00Z"', {})
        }.items(), key=lambda t: t[0]):
            parsestr = testargs[0]
            expected = testargs[1]
            semanticArgs = testargs[2]
            try:
                semantic = search_semantics.ClassificationSolrSearchWithoutIdentifiersSemantics(default_property_code, **semanticArgs)
                ast = search_parser.parse_without_identifiers_needed(parsestr, semantic)
                assert isinstance(ast, dict), json.dumps(ast, indent=4, ensure_ascii=False)
                assert 'solr_complete_term' in ast, json.dumps(ast, indent=4, ensure_ascii=False)
                parseresult = ast.get('solr_complete_term')
                assert parseresult == expected, '{}: expected: "{}" != "{}"'.format(k, expected, parseresult)
            except tatsu.exceptions.ParseError:
                ast = search_parser.parse_without_identifiers_needed(parsestr, semantic, trace=True)
                assert False, '{} failed'.format(k)

    def test_search_semantics_for_inputs_with_id_not_needed_and_float_normalization(self):
        """ search semantics tests for inputs which do not need to have identifiers but use default identifier instead and have a float normalization function given"""
        default_property_code = 'DEFAULT_PROPERTY_CODE'

        def normalize_float_func(val, repair_dict):
            ret = "[{} TO {}]".format(val - get_epsilon(val), val + get_epsilon(val))
            repair_dict[ret] = val
            return ret

        semantic = search_semantics.ClassificationSolrSearchWithoutIdentifiersSemantics(default_property_code, normalize_float_func=normalize_float_func)
        for k, teststr in sorted({
            '01: single float': ('=5,0', '{}:[{} TO {}]'.format(
                default_property_code, 5.0 - get_epsilon(5.0), 5.0 + get_epsilon(5.0))
            ),
            '02: complex float condition': ('=5,0 OR =6,0', '{}:[{} TO {}] OR {}:[{} TO {}]'.format(
                default_property_code,
                5.0 - get_epsilon(5.0),
                5.0 + get_epsilon(5.0),
                default_property_code,
                6.0 - get_epsilon(6.0),
                6.0 + get_epsilon(6.0))
            ),
            '03: single float range query exclusive max': ('a<5,0', 'a:[* TO 5.0}'),
            '04: single float range query exclusive min': ('a>5,0', 'a:{5.0 TO *]'),
            '05: single float range query inclusive max': ('a<=5,0', 'a:[* TO 5.0]'),
            '06: single float range query inclusive min': ('a>=5,0', 'a:[5.0 TO *]'),
            '07: complex float query': ('a=5,0 OR a=6,0', 'a:[{} TO {}] OR a:[{} TO {}]'.format(
                5.0 - get_epsilon(5.0), 5.0 + get_epsilon(5.0), 6.0 - get_epsilon(6.0), 6.0 + get_epsilon(6.0))
            ),
        }.items(), key=lambda t: t[0]):
            parsestr = teststr[0]
            expected = teststr[1]
            try:
                ast = search_parser.parse_without_identifiers_needed(parsestr,
                                                                     semantic)
                assert isinstance(ast, dict), json.dumps(ast, indent=4, ensure_ascii=False)
                assert 'solr_complete_term' in ast, json.dumps(ast, indent=4, ensure_ascii=False)
                parseresult = ast.get('solr_complete_term')
                assert parseresult == expected, '{}: expected: "{}" != "{}"'.format(k, expected, parseresult)
                LOG.debug('{}: "{}"'.format(k, parseresult))
            except tatsu.exceptions.ParseError:
                ast = search_parser.parse_without_identifiers_needed(parsestr,
                                                                     semantic,
                                                                     trace=True)
                assert False, '{} failed'.format(k)

    def test_search_semantics_for_multiple_logical_expressions(self):
        default_property_code = 'A'
        parsestr = "(=10 or =20 or =30)"
        expected = "(A:10 or A:20) or A:30"
        semantic = search_semantics.ClassificationSolrSearchWithoutIdentifiersSemantics(default_property_code)
        try:
            ast = search_parser.parse_without_identifiers_needed(parsestr, semantic)
            assert isinstance(ast, dict), json.dumps(ast, indent=4, ensure_ascii=False)
            assert 'solr_complete_term' in ast, json.dumps(ast, indent=4, ensure_ascii=False)
            parseresult = ast.get('solr_complete_term')
            assert parseresult == expected, '{}: expected: "{}" != "{}"'.format(parsestr, expected, parseresult)
        except tatsu.exceptions.ParseError:
            ast = search_parser.parse_without_identifiers_needed(parsestr, semantic, trace=True)
            assert False, '{} failed'.format(parsestr)
