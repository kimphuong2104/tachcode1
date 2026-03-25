from cdb.objects.core import Object
from cdb import ue
import logging

LOG = logging.getLogger(__name__)


class Symbol(Object):

    __classname__ = "cs_classification_symbol"
    __maps_to__ = "cs_classification_symbol"

    ALPHABETIC_CHARACTER = 'Alphabetic character'
    CHARACTER = 'Character'
    NUMERIC_CHARACTER = 'Numeric character'
    SEPARATOR = 'Separator'
    SIGN = 'Sign'


class Pattern(Object):

    __classname__ = "cs_classification_pattern"
    __maps_to__ = "cs_classification_pattern"

    @staticmethod
    def build_error_string(symbol_dict):
        possible_chars = ""
        inv_dict = {}
        for k, v in symbol_dict.items():
            inv_dict[v] = inv_dict.get(v, [])
            inv_dict[v].append(str(k))
        for item in inv_dict:
            possible_chars = possible_chars + str(item) + ": " + str(inv_dict[item]) + "\n"
        return possible_chars

    @classmethod
    def create_reg_ex(cls, pattern):
        # Query all symbols
        symbol_set = Symbol.Query()
        symbol_dict = {obj.pattern_char: obj.pattern_usage for obj in symbol_set}
        regex = "^"

        if pattern:
            for sym_char in pattern:
                if sym_char in symbol_dict:

                    if symbol_dict[sym_char] == Symbol.ALPHABETIC_CHARACTER:
                        regex = regex + r"[^\W0-9_]"

                    elif symbol_dict[sym_char] == Symbol.CHARACTER:
                        regex = regex + "."

                    elif symbol_dict[sym_char] == Symbol.NUMERIC_CHARACTER:
                        regex = regex + r"\d"

                    elif symbol_dict[sym_char] == Symbol.SIGN:
                        regex = regex + "[+-]"

                    elif symbol_dict[sym_char] == Symbol.SEPARATOR:
                        regex = regex + sym_char
                else:
                    possible_chars = Pattern.build_error_string(symbol_dict)
                    raise ue.Exception("cs_classification_invalid_character", sym_char, possible_chars)

            regex = regex + "$"
            return regex
        else:
            return ""

    def validate_pattern(self, ctx):
        text_prop_pattern = self.pattern
        is_new = False
        was_modified = False
        if "pattern" not in ctx.object.get_attribute_names():
            # Its new
            is_new = True
        elif ctx.dialog.pattern != ctx.object.pattern:
            # Its now new and the pattern has changed
            was_modified = True

        if is_new or was_modified:
            # Query all symbols
            symbol_set = Symbol.Query()
            symbol_dict = {obj.pattern_char: obj.pattern_usage for obj in symbol_set}
            symbol_list = symbol_dict.keys()
            for sym_char in text_prop_pattern:
                if sym_char not in symbol_list:
                    possible_chars = Pattern.build_error_string(symbol_dict)
                    raise ue.Exception("cs_classification_invalid_character", sym_char, possible_chars)

    event_map = {
        (('create', 'copy', 'modify'), 'pre'): ('validate_pattern')
    }
