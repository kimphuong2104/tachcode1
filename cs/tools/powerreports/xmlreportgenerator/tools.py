import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime

SPLIT_LETTER_NUMBER = r"\d+|\D+"


def sheet_images(sheet):
    return sheet._images  # pylint: disable=W0212


def refresh_pivot(sheet):
    for pivot_table in sheet._pivots:  # pylint: disable=W0212
        pivot_table.cache.refreshOnLoad = True


def anchor_from(image):
    return image.anchor._from  # pylint: disable=W0212


def temporary_unzip_file(zip_file):
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_file) as f:
        f.extractall(temp_dir)
    return temp_dir


def get_date_time(date_time):
    try:
        return datetime.strptime(date_time, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.strptime(date_time, "%Y-%m-%d")


def letter_num_seperated(cell_address):
    letter, number = re.findall(SPLIT_LETTER_NUMBER, cell_address)
    return letter, int(number)


def get_base_offset_color(colorize_string):
    """
    Return base_color and offset_color from group attributes as rgb tuple

    :param string colorize_string: contains color information of grouping

    :return tuple base_color
    :return tuple color_offset
    """
    colorize_string = colorize_string.replace("colorize", "")
    base_color = re.search(r"\((.*?)\)", colorize_string)
    color_offset = None

    if base_color is not None:
        base_color = base_color.group(1)
        colorize_string = colorize_string.replace("(" + base_color + ")", "")
        color_offset = re.search(r"\((.*?)\)", colorize_string)
        base_color = tuple(map(int, base_color.split(",")))

        if color_offset is not None:
            color_offset = color_offset.group(1)
            color_offset = tuple(map(int, color_offset.split(",")))

    return base_color, color_offset


def calculate_color(base_color, color_offset):
    """
    Calculate new color

    From base_color subtract the offset
    Special cases for color >255 or <0 (based on OfficeLink)

    :return new color
    """
    new_color = []
    for color, offset in zip(base_color, color_offset):
        changed_color = color - offset

        if changed_color < 0:
            changed_color = 255 + changed_color
        changed_color = min(changed_color, 255)
        new_color.append(changed_color)

    return tuple(new_color)


def get_dict_reversed(to_reverse_dict):
    """
    Return reversed dict
    """
    reverse_dict = {}
    for key, value in to_reverse_dict.items():
        dict_element = {key: value}
        dict_element.update(reverse_dict)
        reverse_dict = dict_element

    return reverse_dict


def get_fieldname_and_provider_from_path(path):
    """
    Return field name and provider from given xml data (xpath)
    """
    path = path.split("/")
    fieldname = path[-1].replace("@", "")
    provider = path[2]

    return fieldname, provider


def get_hex_of_color_rgb(color_rgb):
    """
    Convert rgb to hex

    :param color_rgb: tuple with (r, g, b)
    :return string color_hex
    """
    r = color_rgb[0]
    g = color_rgb[1]
    b = color_rgb[2]
    color_hex = "{0:02x}{1:02x}{2:02x}".format(r, g, b)

    return color_hex


def get_new_table_size(table_start, table_end, table_length):
    """
    Create new size of table

    :return string new_table_size
    """
    if table_start[1] == table_end[1]:
        new_table_end = table_end[0] + str(int(table_start[1]) + table_length - 1)
    else:
        new_table_end = table_end[0] + str(int(table_start[1]) + table_length)
    new_table_start = table_start[0] + table_start[1]
    new_table_size = new_table_start + ":" + new_table_end

    return new_table_size


def get_start_end_of_table(table_size_start_and_end):
    """
    Returns start and end of table

    :return list table_start:  [column, row]
    :return list table_end:  [column, row]
    """
    table_start = re.findall(SPLIT_LETTER_NUMBER, table_size_start_and_end[0])
    table_end = re.findall(SPLIT_LETTER_NUMBER, table_size_start_and_end[1])

    return table_start, table_end


def save_excel(excel_file, excel_dir):
    """
    Zip all files in dir (with arcname there is no extra dir in zip) - otherwise excel cant be open
    save excel by closing the zipfile
    """
    zip_name = shutil.make_archive(excel_file, "zip", excel_dir)
    if os.path.exists(excel_file):
        os.remove(excel_file)
    os.rename(zip_name, excel_file)
