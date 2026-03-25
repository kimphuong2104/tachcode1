# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Module reports

This is the documentation for the reports module.
"""

from __future__ import unicode_literals
from cdb import ue


class ExcelImportError(ue.Exception):
    pass


class ExcelImportNoMatchingTableFound(ExcelImportError):
    """Raised when no table was found matching the target columns"""
    pass


class ExcelImportTooManyTablesFound(ExcelImportError):
    """Raised when more than one table was found matching the target columns"""
    pass


class ExcelImportDataNotFound(ExcelImportError):
    """Raised when a the information is not present in the Excel file"""
    pass


class ExcelImportSpecificationNotFound(ExcelImportError):
    """Raised when a Specification ID is not found in the DB"""
    pass


class DocumentExportError(Exception):
    pass


class DocumentExportTemplateError(DocumentExportError):
    pass


class FileNameCollision(DocumentExportError, ValueError):
    pass

class RichTextModificationError(Exception):
    pass

class MissingVariableValueError(RichTextModificationError):
    def __init__(self, *args, **kwargs):
        self.variable_id = kwargs.pop('variable_id')
        super(MissingVariableValueError, self).__init__(*args, **kwargs)

class InvalidVariableValueTypeError(RichTextModificationError):
    def __init__(self, *args, **kwargs):
        self.variable_id = kwargs.pop('variable_id')
        self.variable_value = kwargs.pop('variable_value')
        super(InvalidVariableValueTypeError, self).__init__(
            "Variable Value for %s is of type %s which is unsupported" % (
                self.variable_id, type(self.variable_value)
            )
        )

class InvalidRichTextAttributeValueType(RichTextModificationError):
    def __init__(self, *args, **kwargs):
        self.attribute_name = kwargs.pop('attribute_name')
        self.attribute_value = kwargs.pop('attribute_value')
        super(InvalidRichTextAttributeValueType, self).__init__(
            "Attribute Value for %s is of type %s which is unsupported" % (
                self.attribute_name, type(self.attribute_value)
            )
        )