# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


import logging
import re

from cs.classification.units import UnitCache
from cs.classification.util import convert_datestr_to_datetime

LOG = logging.getLogger(__name__)


class AbstractSemantic(object):

    def __init__(self, default_identifier=None, *args, **kwargs):
        # at least the following variables needs to be adjusted when the grammar is changed
        self.range_lower_relop = '<'
        self.range_higher_relop = '>'
        self.lower_range_relops = [self.range_lower_relop, '<=']
        self.higher_range_relops = [self.range_higher_relop, '>=']
        self.range_relops = self.lower_range_relops + self.higher_range_relops
        self.bool_relops = ['=', '!=', '<>']
        self.positive_bool_relops = ['=']
        self.negative_bool_relops = ['!=', '<>']
        self.and_ops = ['and', 'And', 'AND']
        self.default_identifier = default_identifier
        self._grammar_op = 'op'
        self._grammar_word = 'word'
        self._grammar_wordsequence = 'wordsequence'
        self._grammar_identifier = 'identifier'
        self._grammar_quantifier = 'quantifier'
        self._grammar_space = 'space'
        self._grammar_content = 'content'
        self._grammar_lhs_g = 'lhs_g'
        self._grammar_lhs_t = 'lhs_t'
        self._grammar_rhs_g = 'rhs_g'
        self._grammar_rhs_t = 'rhs_t'
        # '\\' must be the first special char, otherwise we will get double escapings!
        self._grammar_specialchars = ['\\', '+', '-', '!', '{', '}', '[', ']', '^', '~', ':', '#']
        self._grammar_specialchar = 'specialchar'

    def _get_closure_content(self, val):
        import tatsu
        if isinstance(val, tatsu.contexts.closure):
            if len(val) == 1:
                return self._get_closure_content(val[0])
            else:
                return [self._get_closure_content(x) for x in val]
        else:
            return val


class SolrBaseSemantic(AbstractSemantic):

    def __init__(self, *args, **kwargs):
        self._solr_content = 'solr_content'
        self._solr_op = 'solr_op'
        self._solr_value = 'solr_value'
        self._solr_identifier = 'solr_identifier'
        self._solr_complete_term = 'solr_complete_term'
        self._solr_type = 'solr_type'
        self._solr_single_range = 'solr_single_range'
        self._solr_type_term = 'term'
        self._solr_type_expression = 'expression'
        self._solr_group_open_char = '('
        self._solr_group_close_char = ')'
        self._solr_exclusive_range_open_char = '{'
        self._solr_exclusive_range_close_char = '}'
        self._solr_inclusive_range_open_char = '['
        self._solr_inclusive_range_close_char = ']'
        self._solr_negation_char = '*:* AND -'  # needed as solr does not transform every - version to *:* AND which lucene needs - https://stackoverflow.com/questions/634765/using-or-and-not-in-solr-query
        self._solr_equal_char = ':'
        self._solr_multi_wildcard_char = '*'
        self._solr_empty_multi_wildcard_char = kwargs.get("empty_wildcard_char")
        if not self._solr_empty_multi_wildcard_char:
            self._solr_empty_multi_wildcard_char = self._solr_multi_wildcard_char
        self._solr_escape_char = '\\'
        self._solr_whitespace_char = ' '
        self._solr_escaped_whitespace_char = '\ '
        self._solr_contains_whitespaces = 'solr_contains_whitespaces'
        self._solr_contains_quantifier = 'solr_contains_quantifier'
        self._solr_float_epsilon_range_repair = {}
        self._solr_float_normalization_function = kwargs.get("normalize_float_func")
        self.handle_numbers_as_float = self._solr_float_normalization_function is not None
        self._solr_is_text_property = kwargs.get("is_text_property", False)
        self._solr_is_within_block = kwargs.get("is_within_block", False)
        self._solr_is_catalog_property = kwargs.get("is_catalog_property", False)
        self._enum_values = kwargs.get("enum_values", None)
        self._float_factor = 1
        self._unit_object_id = kwargs.get("unit_object_id", "")
        super(SolrBaseSemantic, self).__init__(*args, **kwargs)

    def reset(self):
        self._float_factor = 1

    def get_result(self, ast):
        return ast.get(self._solr_complete_term)

    def _handle_word(self, word):
        if isinstance(word, dict):
            return word.get(self._solr_content)
        else:
            return "".join([str(part.get(self._solr_content)) for part in word])

    def _handle_value(self, ast):
        val = self._handle_word(ast[self._grammar_word] if ast[self._grammar_word] is not None else ast[self._grammar_wordsequence])
        ast[self._solr_value] = val
        return ast

    def _get_identifier(self, ast):
        if self._grammar_identifier in ast and ast.get(self._grammar_identifier) is not None:
            return ast.get(self._grammar_identifier)
        else:
            return self.default_identifier

    def _handle_identifier(self, ast):
        from cs.classification.solr import SOLR_EMPTY_VALUES_KEY
        if ast.get(self._grammar_op) in self.positive_bool_relops:
            ast[self._solr_op] = self._solr_equal_char
        if ast.get(self._grammar_op) in self.negative_bool_relops:
            identifier = self._get_identifier(ast)
            if self._solr_is_catalog_property:
                ast[self._solr_identifier] = """
                    ({identifier}:* OR {empty_values}:{identifier}) AND -{identifier}
                    """.format(
                    empty_values=SOLR_EMPTY_VALUES_KEY,
                    identifier=identifier
                )
            else:
                ast[self._solr_identifier] = self._solr_negation_char + identifier
            ast[self._solr_op] = self._solr_equal_char
        else:
            ast[self._solr_identifier] = self._get_identifier(ast)
        return ast

    def _add_currency_condition(self, ast, value_term):
        from cs.classification.solr import SOLR_CURRENCY_KEY
        identifier = self._get_identifier(ast)
        if UnitCache.is_currency(self._unit_object_id):
            return '({value_term} AND {curreny_prefix}{solr_identifier}:{unit_object_id})'.format(
                value_term=value_term,
                curreny_prefix=SOLR_CURRENCY_KEY,
                solr_identifier=identifier,
                unit_object_id=self._unit_object_id
            )
        else:
            return value_term

    def _escape_specialchars(self, text_value):
        for special_char in self._grammar_specialchars:
            text_value = text_value.replace(special_char, self._solr_escape_char + special_char)
        return text_value

    def _unescape_specialchars(self, text_value):
        for special_char in self._grammar_specialchars:
            text_value = text_value.replace(self._solr_escape_char + special_char, special_char)
        return text_value

    def _handle_term(self, ast):
        from cs.classification import tools
        from cs.classification.solr import SOLR_EMPTY_VALUES_KEY

        ast = self._handle_value(ast)
        ast = self._handle_identifier(ast)
        ast = self._handle_single_range(ast)
        if self._solr_op in ast and self._solr_value in ast:
            if isinstance(ast[self._solr_value], str) and 0 == len(ast[self._solr_value]):
                # search for set/unset property value
                if ast.get(self._grammar_op) in self.positive_bool_relops:
                    # search for not set property (="")
                    if self._solr_is_catalog_property:
                        ast[self._solr_complete_term] = SOLR_EMPTY_VALUES_KEY + \
                            '{solr_op}{solr_identifier}'.format(**ast)
                    else:
                        ast[self._solr_complete_term] = \
                            '(*:* -{solr_identifier}{solr_op}[* TO *])'.format(
                                **ast
                            )
                elif ast.get(self._grammar_op) in self.negative_bool_relops:
                    # search for any property value (!="")
                    value_term = '{default_identifier}{solr_op}{wildcard}'.format(
                        default_identifier=self.default_identifier,
                        solr_op=self._solr_equal_char,
                        wildcard=self._solr_empty_multi_wildcard_char
                    )
                    ast[self._solr_complete_term] = self._add_currency_condition(
                        ast, value_term
                    )
            elif "*" == ast[self._solr_value]:
                if self._solr_is_catalog_property:
                    ast[self._solr_complete_term] = """
                        {default_identifier}{solr_op}{wildcard}
                        OR {empty_values}{solr_op}{default_identifier}
                    """.format(
                        empty_values=SOLR_EMPTY_VALUES_KEY,
                        default_identifier=self.default_identifier,
                        solr_op=self._solr_equal_char,
                        wildcard=self._solr_multi_wildcard_char
                    )
                else:
                    # a single * means also all unset values. solr would only find all object with
                    # a value for this property and not those with no value set.
                    ast[self._solr_complete_term] = ''
            else:
                if self._enum_values and len(self._enum_values):
                    # add search conditions for description search ...
                    pattern = ast[self._solr_value]
                    pattern = re.sub(r'(?<!\\)[\*%]', r'.*', pattern)
                    pattern = re.sub(r'(?<!\\)[\?]', r'.', pattern)
                    # only use search value for the case that it is surrounded by ""
                    matcher = re.compile("^{}$".format(self._unescape_specialchars(pattern.strip('"'))))

                    prop_code = ast[self._solr_identifier].replace(self._solr_negation_char, '', 1)
                    identifier = ast[self._solr_identifier] if '=' == ast.get('op', '') else '-' + prop_code

                    terms = ['{solr_identifier}{solr_op}{solr_value}'.format(**ast)]
                    for enum_value in self._enum_values.get(prop_code, []):
                        if matcher.match(tools.get_label("label", enum_value)):
                            # label matches add value to search condition because labels are not in solr index
                            description_search_value = '"{}"'.format(self._escape_specialchars(enum_value.text_value))
                            if ast[self._solr_value] == description_search_value:
                                # ignore descriptions that are equal to the search value
                                continue
                            term = '{solr_identifier}{solr_op}{solr_value}'.format(
                                solr_identifier=identifier,
                                solr_op=ast[self._solr_op],
                                solr_value=description_search_value
                            )
                            terms.append(term)
                    if ast.get('op', '') in self.positive_bool_relops:
                        ast[self._solr_complete_term] = '(' + " OR ".join(terms) + ')'
                    elif ast.get('op', '') in self.negative_bool_relops:
                        ast[self._solr_complete_term] = '(' + " AND ".join(terms) + ')'
                else:
                    # normal value search ...
                    ast[self._solr_complete_term] = self._add_currency_condition(
                        ast,
                        '{solr_identifier}{solr_op}{solr_value}'.format(**ast)
                    )
        return ast

    def _repair_float_ranges(self, min_val, max_val):
        if self.handle_numbers_as_float:
            min_val = self._solr_float_epsilon_range_repair.get(min_val, min_val)
            max_val = self._solr_float_epsilon_range_repair.get(max_val, max_val)
        return min_val, max_val

    def _handle_single_range(self, ast):
        left_range_char = self._solr_inclusive_range_open_char
        right_range_char = self._solr_inclusive_range_close_char
        min_val = self._solr_multi_wildcard_char
        max_val = self._solr_multi_wildcard_char
        if ast.get(self._grammar_op) in self.range_relops and self._solr_value in ast:
            if self._solr_is_text_property:
                format_str = "{solr_identifier}:{op}{val}"
                ast[self._solr_single_range] = format_str.format(
                    op=ast.get(self._grammar_op),
                    val=ast.get(self._solr_value),
                    solr_identifier=ast.get(self._solr_identifier)
                )
            else:
                format_str = "{solr_identifier}:{left_range_char}{min_val} TO {max_val}{right_range_char}"
                if ast.get(self._grammar_op) in self.higher_range_relops:
                    if ast.get(self._grammar_op) == self.range_higher_relop:
                        left_range_char = self._solr_exclusive_range_open_char
                    min_val = ast.get(self._solr_value)
                else:
                    if ast.get(self._grammar_op) == self.range_lower_relop:
                        right_range_char = self._solr_exclusive_range_close_char
                    max_val = ast.get(self._solr_value)

                min_val, max_val = self._repair_float_ranges(min_val, max_val)
                ast[self._solr_single_range] = format_str.format(solr_identifier=ast.get(self._solr_identifier),
                                                                 min_val=min_val,
                                                                 max_val=max_val,
                                                                 left_range_char=left_range_char,
                                                                 right_range_char=right_range_char)
        return ast

    def _handle_range(self, lhs, rhs):
        min_val = self._solr_multi_wildcard_char
        max_val = self._solr_multi_wildcard_char
        format_str = "{solr_identifier}:{left_range_char}{min_val} TO {max_val}{right_range_char}"
        if lhs is not None and rhs is not None:
            left_range_char = self._solr_inclusive_range_open_char
            right_range_char = self._solr_inclusive_range_close_char
            if lhs.get(self._grammar_op) in self.lower_range_relops:
                if lhs.get(self._grammar_op) == self.range_lower_relop:
                    right_range_char = self._solr_exclusive_range_close_char
                if rhs.get(self._grammar_op) == self.range_higher_relop:
                    left_range_char = self._solr_exclusive_range_open_char
                max_val = lhs.get(self._solr_value)
                min_val = rhs.get(self._solr_value)
            else:
                if rhs.get(self._grammar_op) == self.range_lower_relop:
                    right_range_char = self._solr_exclusive_range_close_char
                if lhs.get(self._grammar_op) == self.range_higher_relop:
                    left_range_char = self._solr_exclusive_range_open_char
                max_val = rhs.get(self._solr_value)
                min_val = lhs.get(self._solr_value)
        min_val, max_val = self._repair_float_ranges(min_val, max_val)
        return format_str.format(solr_identifier=lhs.get(self._solr_identifier),
                                 min_val=min_val,
                                 max_val=max_val,
                                 left_range_char=left_range_char,
                                 right_range_char=right_range_char)

    def _handle_term_expression(self, ast):
        lhs_g = self._get_closure_content(ast.get(self._grammar_lhs_g))
        rhs_g = self._get_closure_content(ast.get(self._grammar_rhs_g))
        lhs_t = self._get_closure_content(ast.get(self._grammar_lhs_t))
        rhs_t = self._get_closure_content(ast.get(self._grammar_rhs_t))
        op = ast.get(self._grammar_op).strip()
        if lhs_t is not None and rhs_t is not None and op is not None:
            if self._solr_complete_term not in ast and self._solr_complete_term in lhs_t and self._solr_complete_term in rhs_t:
                ast[self._solr_complete_term] = '{lhs_content} {op} {rhs_content}'.format(lhs_content=lhs_t.get(self._solr_complete_term, lhs_t.get(self._solr_single_range)),
                                                                                          op=op,
                                                                                          rhs_content=rhs_t.get(self._solr_complete_term, rhs_t.get(self._solr_single_range)))
                if self._solr_type not in ast:
                    ast[self._solr_type] = self._solr_type_expression
            elif op in self.and_ops and lhs_t.get(self._solr_identifier) is not None and lhs_t.get(self._solr_identifier) != '' and lhs_t.get(self._solr_identifier) == rhs_t.get(self._solr_identifier) and ((lhs_t.get(self._grammar_op) in self.lower_range_relops and rhs_t.get(self._grammar_op) in self.higher_range_relops) or (lhs_t.get(self._grammar_op) in self.higher_range_relops and rhs_t.get(self._grammar_op) in self.lower_range_relops)):
                ast[self._solr_complete_term] = self._handle_range(lhs_t, rhs_t)
                if self._solr_type not in ast:
                    ast[self._solr_type] = self._solr_type_term
            else:
                lhs_content = lhs_t.get(self._solr_single_range) if self._solr_single_range in lhs_t else lhs_t.get(self._solr_complete_term)
                rhs_content = rhs_t.get(self._solr_single_range) if self._solr_single_range in rhs_t else rhs_t.get(self._solr_complete_term)
                ast[self._solr_complete_term] = '{lhs_content} {op} {rhs_content}'.format(lhs_content=lhs_content,
                                                                                          op=op,
                                                                                          rhs_content=rhs_content)
                if self._solr_type not in ast:
                    ast[self._solr_type] = self._solr_type_expression

        elif lhs_t is not None and rhs_g is not None and op is not None and self._solr_complete_term not in ast:
            ast[self._solr_complete_term] = '({lhs_content}) {op} ({rhs_content})'.format(lhs_content=lhs_t.get(self._solr_complete_term, lhs_t.get(self._solr_single_range)),
                                                                                          op=op,
                                                                                          rhs_content=rhs_g.get(self._solr_complete_term, rhs_g.get(self._solr_single_range)))
            ast[self._solr_type] = self._solr_type_expression
        elif lhs_g is not None and rhs_t is not None and op is not None and self._solr_complete_term not in ast:
            ast[self._solr_complete_term] = '({lhs_content}) {op} ({rhs_content})'.format(lhs_content=lhs_g.get(self._solr_complete_term, lhs_g.get(self._solr_single_range)),
                                                                                          op=op,
                                                                                          rhs_content=rhs_t.get(self._solr_complete_term, rhs_t.get(self._solr_single_range)))
            ast[self._solr_type] = self._solr_type_expression
        elif self._solr_single_range in ast:
            ast[self._solr_complete_term] = ast[self._solr_single_range]
            del ast[self._solr_single_range]
        return ast

    def _handle_expression(self, ast):
        if isinstance(ast, dict):
            lhs_g = self._get_closure_content(ast.get(self._grammar_lhs_g))
            rhs_g = self._get_closure_content(ast.get(self._grammar_rhs_g))
            lhs_t = self._get_closure_content(ast.get(self._grammar_lhs_t))
            rhs_t = self._get_closure_content(ast.get(self._grammar_rhs_t))
            op = ast.get(self._grammar_op).strip()
            if lhs_g is not None and rhs_g is not None and op is not None and self._solr_complete_term not in ast:
                lhs_need_brackets = self._solr_type in lhs_g and lhs_g.get(self._solr_type) != self._solr_type_term
                rhs_need_brackets = self._solr_type in rhs_g and rhs_g.get(self._solr_type) != self._solr_type_term
                ast[self._solr_complete_term] = '{lbl}{lhs_content}{lbr} {op} {rbl}{rhs_content}{rbr}'.format(lhs_content=lhs_g.get(self._solr_complete_term, lhs_g.get(self._solr_single_range)),
                                                                                                              lbl=self._solr_group_open_char if lhs_need_brackets else '',
                                                                                                              lbr=self._solr_group_close_char if lhs_need_brackets else '',
                                                                                                              op=op,
                                                                                                              rbl=self._solr_group_open_char if rhs_need_brackets else '',
                                                                                                              rbr=self._solr_group_close_char if rhs_need_brackets else '',
                                                                                                              rhs_content=rhs_g.get(self._solr_complete_term, rhs_g.get(self._solr_single_range)))
                ast[self._solr_type] = self._solr_type_expression
            elif lhs_t is not None and rhs_g is not None and op is not None and self._solr_complete_term not in ast:
                ast[self._solr_complete_term] = '({lhs_content}) {op} ({rhs_content})'.format(lhs_content=lhs_t.get(self._solr_complete_term, lhs_t.get(self._solr_single_range)),
                                                                                              op=op,
                                                                                              rhs_content=rhs_g.get(self._solr_complete_term, rhs_g.get(self._solr_single_range)))
                ast[self._solr_type] = self._solr_type_expression
            elif lhs_g is not None and rhs_t is not None and op is not None and self._solr_complete_term not in ast:
                ast[self._solr_complete_term] = '({lhs_content}) {op} ({rhs_content})'.format(lhs_content=lhs_g.get(self._solr_complete_term, lhs_g.get(self._solr_single_range)),
                                                                                              op=op,
                                                                                              rhs_content=rhs_t.get(self._solr_complete_term, rhs_t.get(self._solr_single_range)))
                ast[self._solr_type] = self._solr_type_expression

        return ast

    def _clean_escaped_chars_within_word_sequence(self, val):
        return val.replace('\\and', 'and').replace('\\or', 'or')

    def wordsequence(self, ast):
        content = ast.get(self._grammar_content)
        if isinstance(content, list):
            processed_content = []
            for content_part in content:
                processed_content_part = self._handle_complex_word(content_part, True)
                processed_content.append(processed_content_part.get(self._solr_content))
                for k in [self._solr_contains_whitespaces, self._solr_contains_quantifier]:
                    if k not in ast and k in processed_content_part:
                        ast[k] = processed_content_part[k]
            if (self._solr_contains_whitespaces in ast and self._solr_contains_quantifier not in ast) or \
                    (self._solr_contains_whitespaces not in ast and self._solr_contains_quantifier not in ast):
                        word_sequence_char_or_escaped_word_sequence_char = r'\"' if self._solr_is_within_block else r'"'
                        ast[self._solr_content] = self._clean_escaped_chars_within_word_sequence(
                            '{c}{content}{c}'.format(
                                content="".join(processed_content),
                                c=word_sequence_char_or_escaped_word_sequence_char
                            )
                        )
            elif self._solr_contains_whitespaces not in ast and self._solr_contains_quantifier in ast:
                ast[self._solr_content] = "".join(processed_content)
            elif self._solr_contains_whitespaces in ast and self._solr_contains_quantifier in ast:
                # phrases with whitespaces can only be searched when whitespaces are escaped
                # and the whole phrase is not marked as phrase but instead as term -> no quotation
                ast[self._solr_content] = "".join(processed_content).replace(self._solr_whitespace_char, self._solr_escaped_whitespace_char)
        else:
            processed_content = self._handle_complex_word(content, True)
            ast[self._solr_content] = processed_content.get(self._solr_content)
            for k in [self._solr_contains_whitespaces, self._solr_contains_quantifier]:
                if k not in ast and k in processed_content:
                    ast[k] = processed_content[k]
        return ast

    def _handle_quantifier(self, ast):
        if self._grammar_quantifier in ast and ast.get(self._grammar_quantifier):
            return {self._solr_contains_quantifier: True}, ast.get(self._grammar_quantifier).replace('%',
                                                                                                     self._solr_multi_wildcard_char)
        return {}, None

    def _handle_whitespace(self, ast):
        if self._grammar_space in ast and ast.get(self._grammar_space):
            return {self._solr_contains_whitespaces: True}, ast.get(self._grammar_space)
        return {}, None

    def _handle_special_chars(self, ast):
        if self._grammar_specialchar in ast and ast.get(self._grammar_specialchar):
            return {}, "{}{}".format(self._solr_escape_char, ast.get(self._grammar_specialchar))
        return {}, None

    def _handle_escaped_chars(self, ast):
        if isinstance(ast, dict):
            return {}, "".join(ast.values())
        elif isinstance(ast, str):
            return {}, ast.replace('{}%'.format(self._solr_escape_char), '%')
        else:
            return {}, None

    def _handle_special_word_parts(self, ast, with_spaces=False):
        val = None
        if self.handle_numbers_as_float:
            if self._grammar_specialchar in ast and ast.get(self._grammar_specialchar) in ('-', '+'):
                return {}, ''
        if with_spaces:
            handler_list = [self._handle_quantifier,
                            self._handle_whitespace,
                            self._handle_special_chars,
                            self._handle_escaped_chars]
        else:
            handler_list = [self._handle_quantifier,
                            self._handle_special_chars,
                            self._handle_escaped_chars]
        for special_case_handler in handler_list:
            meta, val = special_case_handler(ast)
            if val is not None:
                return meta, val
        return {}, None

    def _handle_complex_word(self, ast, with_spaces=False):
        if isinstance(ast, dict):
            lhs = ast.get('lhs')
            rhs = ast.get('rhs')
            content = ast.get(self._grammar_content)
            if content is None:
                content = ''
            if lhs is None and rhs is None:
                content_str = content[0] if isinstance(content, tuple) else content
                ast[self._solr_content] = content_str
            elif lhs is not None and rhs is None:
                lmeta, lhsval = self._handle_special_word_parts(lhs, with_spaces)
                ast.update(lmeta)
                content_str = content[0] if isinstance(content, tuple) else content
                ast[self._solr_content] = '{lhs}{content}'.format(content=content_str, lhs=lhsval)
            elif lhs is None and rhs is not None:
                rmeta, rhsval = self._handle_special_word_parts(rhs, with_spaces)
                ast.update(rmeta)
                content_str = content[0] if isinstance(content, tuple) else content
                ast[self._solr_content] = '{content}{rhs}'.format(content=content_str, rhs=rhsval)
            elif lhs is not None and rhs is not None:
                lmeta, lhsval = self._handle_special_word_parts(lhs, with_spaces)
                ast.update(lmeta)
                rmeta, rhsval = self._handle_special_word_parts(rhs, with_spaces)
                ast.update(rmeta)
                content_str = content[0] if isinstance(content, tuple) else content
                ast[self._solr_content] = '{lhs}{content}{rhs}'.format(content=content_str, lhs=lhsval, rhs=rhsval)
        return ast

    def identifiers(self, ast):
        if isinstance(ast, dict):
            lhs = ast.get('lhs')
            rhs = ast.get('rhs')
            return "{lhs}{rhs}".format(lhs="".join(lhs), rhs="".join(rhs))

    def complexword(self, ast):
        return self._handle_complex_word(ast)

    def numbers(self, ast):
        content = ast.get('numbers', [''])[0]
        if self._solr_is_text_property:
            return content
        else:
            content = content.replace(",", ".")
            if "." in content:
                ret_val = self._float_factor * float(content)
                self._float_factor = 1
                return ret_val
            else:
                return int(content)

    def date(self, ast):
        if 'date' in ast:
            # convert to solr datetime
            parseddate = "".join(ast.get('date', ''))
            if not self._solr_is_text_property:
                converted_date = convert_datestr_to_datetime(parseddate)
                normal_date = converted_date.replace(tzinfo=None).isoformat() + 'Z'
                block_date_format = "\\\"{date}\\\"".format(date=normal_date)
                non_block_date_format = "\"{date}\"".format(date=normal_date)
                return block_date_format if self._solr_is_within_block else non_block_date_format
            else:
                return ast.get('date')
        else:
            return ast

    def specialchars(self, ast):
        if self.handle_numbers_as_float and self._grammar_specialchar in ast and ast.get(self._grammar_specialchar) == '-':
            self._float_factor = -1
        return ast


class ClassificationSolrSearchWithoutIdentifiersSemantics(SolrBaseSemantic):
    """ a default identifier is needed to heal the resulting solr query """

    def __init__(self, default_identifier, *args, **kwargs):
        super(ClassificationSolrSearchWithoutIdentifiersSemantics, self).__init__(default_identifier, *args, **kwargs)

    def searchWithoutIdentifiers(self, ast):
        return self._get_closure_content(ast)

    def termWithoutIdentifiers(self, ast):
        return self._handle_term(ast)

    def expressionWithoutIdentifiers(self, ast):
        return self._handle_expression(ast)

    def termExpressionWithoutIdentifiers(self, ast):
        return self._handle_term_expression(ast)

    def numbers(self, ast):
        ret = super(ClassificationSolrSearchWithoutIdentifiersSemantics, self).numbers(ast)
        if self.handle_numbers_as_float:
            return self._solr_float_normalization_function(float(ret), self._solr_float_epsilon_range_repair)
        else:
            return ret


class ClassificationSolrSearchWithIdentifiersSemantics(SolrBaseSemantic):

    def searchWithIdentifiers(self, ast):
        return self._get_closure_content(ast)

    def expressionWithIdentifiers(self, ast):
        return self._handle_expression(ast)

    def termExpressionWithIdentifiers(self, ast):
        return self._handle_term_expression(ast)

    def termWithIdentifiers(self, ast):
        return self._handle_term(ast)


if __name__ == '__main__':
    import sys
    import os
    import json
    import codecs
    from cs.classification import search_parser
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        if os.path.isfile(filename):
            with codecs.open(filename, 'r', 'utf-8') as f:
                ast = search_parser.parse_without_identifiers_needed(f.read(), ClassificationSolrSearchWithoutIdentifiersSemantics('DEFAULT_PROPERTY_CODE'))
                LOG.debug(json.dumps(ast, indent=4, ensure_ascii=False))
