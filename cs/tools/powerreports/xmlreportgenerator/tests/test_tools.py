from cdb import testcase
from cs.tools.powerreports.xmlreportgenerator import tools


class ToolsTestCases(testcase.RollbackTestCase):
    def test_color_offset_calc(self):
        base_color = (120, 30, 20)
        offset_color = (10, 15, 5)

        expected_color = (110, 15, 15)

        new_color = tools.calculate_color(base_color, offset_color)

        self.assertEqual(new_color, expected_color)

    def test_color_offset_calc_offset_bigger(self):
        base_color = (120, 15, 30)
        offset_color = (10, 20, 30)

        expected_color = (110, 250, 0)

        new_color = tools.calculate_color(base_color, offset_color)

        self.assertEqual(new_color, expected_color)

        expected_color = (100, 230, 225)

        new_color = tools.calculate_color(new_color, offset_color)

        self.assertEqual(new_color, expected_color)

    def test_rgb_to_hex(self):
        color_rgb = (230, 230, 255)
        expected_hex = "e6e6ff"

        color_hex = tools.get_hex_of_color_rgb(color_rgb)
        self.assertEqual(expected_hex, color_hex)

    def test_return_base_offset_color_typo(self):
        color_string = "colorize(120, 30, 20)"
        expected_base_color = (120, 30, 20)
        expected_offset_color = None

        base_color, offset_color = tools.get_base_offset_color(color_string)

        self.assertEqual(base_color, expected_base_color)

        self.assertEqual(offset_color, expected_offset_color)

    def test_return_base_offset_color_astuple(self):
        color_string = "colorize(120, 30, 20),(10, 15, 5)"
        expected_base_color = (120, 30, 20)
        expected_offset_color = (10, 15, 5)

        base_color, offset_color = tools.get_base_offset_color(color_string)

        self.assertEqual(type(base_color), tuple)
        self.assertEqual(base_color, expected_base_color)

        self.assertEqual(type(offset_color), tuple)
        self.assertEqual(offset_color, expected_offset_color)

    def test_reverse_dict(self):
        dictionary = {1: "one", 2: "two", 3: "three"}
        expected_reversed_dict = {3: "three", 2: "two", 1: "one"}

        reversed_dict = tools.get_dict_reversed(dictionary)

        self.assertEqual(type(dictionary), dict)
        self.assertEqual(reversed_dict, expected_reversed_dict)

    def test_reverse_dict_no_change_in_values(self):
        dictionary = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8], 4: 9}
        expected_2_values = [4, 5, 6]

        reversed_dict = tools.get_dict_reversed(dictionary)
        reversed_dict_key_2 = reversed_dict[2]

        self.assertEqual(type(dictionary), dict)
        self.assertEqual(reversed_dict_key_2, expected_2_values)

    def test_letter_num_separated(self):
        cell_address = "AB12"
        one, two = tools.letter_num_seperated(cell_address)
        both = tools.letter_num_seperated(cell_address)
        self.assertEqual(one, "AB")
        self.assertEqual(two, 12)
        self.assertEqual(both[1], 12)

    def test_get_fieldname_provider_from_path(self):
        path = "/Root/Arguments/@cdbxml_report_date"
        expected_fieldname = "cdbxml_report_date"
        expected_provider = "Arguments"

        fieldname, provider = tools.get_fieldname_and_provider_from_path(path)

        self.assertEqual(expected_fieldname, fieldname)
        self.assertEqual(expected_provider, provider)

    def test_new_table_size_no_header(self):
        table_start = ["A", "2"]
        table_end = ["C", "2"]
        table_length = 5

        expected_table_size = "A2:C6"

        table_size = tools.get_new_table_size(table_start, table_end, table_length)
        self.assertEqual(expected_table_size, table_size)

    def test_new_table_size_1_length(self):
        table_start = ["A", "1"]
        table_end = ["C", "2"]
        table_length = 1

        expected_table_size = "A1:C2"

        table_size = tools.get_new_table_size(table_start, table_end, table_length)
        self.assertEqual(expected_table_size, table_size)

    def test_new_table_size(self):
        table_start = ["A", "1"]
        table_end = ["C", "2"]
        table_length = 5

        expected_table_size = "A1:C6"

        table_size = tools.get_new_table_size(table_start, table_end, table_length)
        self.assertEqual(expected_table_size, table_size)

    def test_get_start_end_table(self):
        table_size = ["B27", "L28"]
        expected_start = ["B", "27"]
        expected_end = ["L", "28"]

        start, end = tools.get_start_end_of_table(table_size)

        self.assertEqual(expected_start, start)
        self.assertEqual(expected_end, end)
