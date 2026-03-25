# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


__all__ = [
    'parse_with_identifiers_needed',
    'parse_without_identifiers_needed']


grammar_ebnf = """
searchWithIdentifiers = groupedWithIdentifiers$;
groupedWithIdentifiers = [space]'('[space] @:( groupcontent:{ expressionWithIdentifiers | termExpressionWithIdentifiers }+ ) [space]')'[space]
                        | termExpressionWithIdentifiers;
expressionWithIdentifiers = {lhs_g:groupedWithIdentifiers [space] op:combineop [space] rhs_g:groupedWithIdentifiers}+
                            | groupedWithIdentifiers;
termExpressionWithIdentifiers = {lhs_t:termWithIdentifiers [space] op:combineop [space] rhs_t:termWithIdentifiers}+
                                | {lhs_t:termWithIdentifiers [space] op:combineop [space] rhs_g:groupedWithIdentifiers}+
                                | {lhs_g:groupedWithIdentifiers [space] op:combineop [space] rhs_t:termWithIdentifiers}+
                                | termWithIdentifiers;
termWithIdentifiers = identifier:key[space] op:relop [space] {wordsequence:wordsequence|word:complexword}+;

searchWithoutIdentifiers = groupedWithoutIdentifiers$;
groupedWithoutIdentifiers = [space]'('[space] @:( groupcontent:{ expressionWithoutIdentifiers | termExpressionWithoutIdentifiers }+ ) [space]')'[space]
                            | termExpressionWithoutIdentifiers;
expressionWithoutIdentifiers = {lhs_g:groupedWithoutIdentifiers [space] op:combineop [space] rhs_g:groupedWithoutIdentifiers}+ | groupedWithoutIdentifiers;
termExpressionWithoutIdentifiers = {lhs_t:termWithoutIdentifiers [space] op:combineop [space] rhs_t:termWithoutIdentifiers}+
                                    | {lhs_t:termWithoutIdentifiers [space] op:combineop [space] rhs_g:groupedWithoutIdentifiers}+
                                    | {lhs_g:groupedWithoutIdentifiers [space] op:combineop [space] rhs_t:termWithoutIdentifiers}+
                                    | termWithoutIdentifiers;
termWithoutIdentifiers = [identifier:key][space] op:relop [space] {wordsequence:wordsequence|word:complexword}+;

key = !combineop !relop identifiers;
relop = '='
        | !'\>=' !'>=' '>'
        | !'\<=' !'<=' !'<>' '<'
        | !'\>=' '>='
        | !'\<=' '<='
        | !'\<>' '<>'
        | !'\!=' '!=';

wordsequence = !combineop wordsequencebegin {content:sentence}* wordsequenceend;
wordsequencebegin = wordsequencebegin:'"';
wordsequenceend = wordsequenceend:'"';
escapedwordsequencechar = !'"' escapedwordsequencechar:'\\\\"';
sentence = lhs:([space|quantifier|specialchars|escapedwordsequencechar|escapedquantifier|escapedspecialchar|escapedcombineop|escapedbackslash]) content:[word] rhs:([space|quantifier|specialchars|escapedwordsequencechar|escapedquantifier|escapedspecialchar|escapedcombineop|escapedbackslash]);
complexword = !combineop lhs:([quantifier|specialchars|escapedwordsequencechar|escapedquantifier|escapedspecialchar|escapedcombineop|escapedbackslash]) content:[word] rhs:([quantifier|specialchars|escapedwordsequencechar|escapedquantifier|escapedspecialchar|escapedcombineop|escapedbackslash]);
word =!quantifier !combineop !space !specialchars (plainword|numbers|date);
plainword = !digits !date !numbers !relop /([^\\\\()\"*%?\s\.]+)/;
date = date:?"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\.\d{1,2}\.\d{4}|\d{1,2}/\d{1,2}/\d{4})+([T\s])?(\d{1,2}:\d{1,2}:\d{1,2}\.?\d*)*(\+\d{0,2}:?\d{0,2}|\-\d{0,2}:?\d{0,2}|Z)*";
numbers = !date numbers:?"((\d)+([\.,])?(\d)*)";
space = space:/([\s]+)/;
underscore = '_';
identifiers = lhs:{letters | underscore}+ rhs:{letters|digits|underscore}*;
letters = !digits !underscore /[\w]+/;
digits = digits:/[\d]+/;
escapedbackslash = '\\\\\\\\';
escapedquantifier = !'*' '\*'
                    |!'%' '\%'
                    |!'?' '\?';
quantifier = !'\*' quantifier:'*'
            |!'\%' quantifier:'%'
            |!'\?' quantifier:'?';
combineop = 'and ' | 'or ' | 'AND ' | 'OR ' | 'And ' | 'Or ' | '&& ' | '|| ';
escapedcombineop = '\\\\and' | '\or' | '\AND' | '\OR' | '\\\\And' | '\Or' | '\&&' | '\||';
specialchars = !date specialchar:'+'
                 | specialchar:'-'
                 | specialchar:'!'
                 | specialchar:'§'
                 | specialchar:'$'
                 | specialchar:'&'
                 | specialchar:'{'
                 | specialchar:'}'
                 | specialchar:'['
                 | specialchar:']'
                 | specialchar:'^'
                 | specialchar:'°'
                 | specialchar:'~'
                 | specialchar:':'
                 | specialchar:','
                 | specialchar:'.'
                 | specialchar:"'"
                 | specialchar:"´"
                 | specialchar:"`"
                 | specialchar:"/"
                 | specialchar:"|"
                 | specialchar:"#"
                 | relop;
escapedspecialchar = !'(' '\('
                    |!')' '\)'
                    |!'=' '\=';
""" # pylint: disable=W1401


PARSER = None


def get_parser():
    import tatsu
    global PARSER
    if PARSER is None:
        PARSER = tatsu.tool.genmodel(
            "ClassificationSearch",
            grammar_ebnf,
            comments_re=None,
            eol_comments_re=None,
        )
        ast_parser_config = getattr(PARSER, "config", None)
        if ast_parser_config:
            # workaround as tatsu > 5.7 changed the defaults and does not replace the given
            # comments_re and eol_comments_re if they are None or ""
            ast_parser_config.comments_re = None
            ast_parser_config.eol_comments_re = None
    return PARSER


def parse(text, start, semantic=None, **kwargs):
    parser = get_parser()
    if semantic:
        semantic.reset()
    return parser.parse(
        text,
        semantics=semantic,
        start=start,
        whitespace='',
        **kwargs
    )


def parse_with_identifiers_needed(text, semantic=None, **kwargs):
    return parse(text, 'searchWithIdentifiers', semantic=semantic, **kwargs)


def parse_without_identifiers_needed(text, semantic=None, **kwargs):
    return parse(text, 'searchWithoutIdentifiers', semantic=semantic, **kwargs)
