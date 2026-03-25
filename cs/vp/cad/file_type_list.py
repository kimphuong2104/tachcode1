# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com

_FILE_TYPE_SEPARATOR = ","


def parse_file_types(string):
    """
    Parses a list of file type names from string. The individual file types are parsed assuming comma (",")
    separation.

    Examples:

    - "Acrobat" -> ["Acrobat"]
    - "Acrobat, PNG" -> ["Acrobat, "PNG"]

    :return: list containing the individual file types parsed from string
    :rtype: list
    """
    if string is None:
        return []

    file_type_names = [s.strip() for s in string.split(_FILE_TYPE_SEPARATOR)]
    return [file_type for file_type in file_type_names if file_type]


class FileTypeList(object):
    """
    Wrapper class around a list of file type names. The class allows for case-insensitive checking whether
    file types are contained in the list. This class can be used in scenarios where allow/deny lists of file
    types are required.
    """

    @classmethod
    def from_string(cls, file_types_string):
        """
        Creates a FileTypeList from a single string containing the names of file types, e.g. "Acrobat" or
        "Acrobat, PNG" and so on. The individual file types are parsed assuming comma (",") separation.

        :return: FileTypeList containing the individual file types parsed from file_types_string
        :rtype: FileTypeList
        """
        return cls(*parse_file_types(file_types_string))

    def __init__(self, *file_types):
        """
        Construct a FileTypeList from one or more file type names.

        :param file_types: One or more file type names, e.g. "Acrobat", "PNG" etc.
        """
        self.file_types = []
        if file_types is None:
            return

        for f_type in file_types:
            if f_type is None:
                continue

            cleaned_type = f_type.strip()
            if cleaned_type != "":
                self.file_types.append(cleaned_type)

    def contains(self, file_type):
        """
        Checks case-insensitively whether file_type is contained in this list.

        :return: True if file_type is contained in this list, False otherwise.
        :rtype: bool
        """

        # Make check case insensitive by comparing UPPER file types.
        return file_type.upper() in [f_type.upper() for f_type in self.file_types]
