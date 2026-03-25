#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
from __future__ import absolute_import
from contextlib import contextmanager
from lxml import etree as ElementTree

import cgi
import six

if six.PY2:
    _escape = cgi.escape  # @UndefinedVariable pylint: disable=no-member
else:
    import html

    _escape = html.escape


@contextmanager
def xmlfile(stream, encoding="utf-8"):
    """
    Implements incremental XML serialization.
    This is similar to the xmlfile context manager of lxml, but our
    implementation is a bit faster.
    """
    yield XmlFile(stream, encoding)


class XmlFile(object):
    def __init__(self, stream, encoding):
        self.stream = stream
        self.encoding = encoding

    @contextmanager
    def element(self, tag, attrib):
        self._writeHeader(tag, attrib)
        yield
        self._writeClosing(tag)

    def write(self, inputElem):
        """
        @param inputElem must be an etree.Element.
        This class does not support writing plain strings!
        """
        bytestr = ElementTree.tostring(inputElem, encoding=self.encoding)
        self.stream.write(bytestr)

    def _writeHeader(self, tag, attrib):
        e = ElementTree.Element(tag, attrib)
        fullElement = ElementTree.tostring(e, encoding=self.encoding)
        # fullElement contains something like:
        # <tag attr="val" />
        # so omit the "/" because we want to write an opening tag
        if six.PY2:
            self.stream.write(fullElement[0:-2] + ">")
        else:
            self.stream.write(fullElement[0:-2] + ">".encode("utf-8"))

    def _writeClosing(self, tag):
        s = u"</%s>" % _escape(tag)
        s = s.encode(self.encoding)
        self.stream.write(s)
