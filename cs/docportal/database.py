# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import json

from cs.docportal.util import get_logger

_logger = get_logger(__name__)


class DocDB:
    import apsw

    def __init__(self, path):
        self.db_path = str(path)
        self.db = None

    def __enter__(self):
        self.db = self.apsw.Connection(self.db_path, self.apsw.SQLITE_OPEN_READONLY)
        self.db.setrowtrace(self._apsw_row_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
        return exc_type is None and exc_val is None and exc_tb is None

    @staticmethod
    def _apsw_row_factory(cursor, row):
        columns = (t[0] for t in cursor.getdescription())
        return dict(zip(columns, row))

    def books(self):
        _query = (
            'SELECT b.id, b.title, b.teaser, b.name, cat.lang AS lang, '
            'cat.title AS cat_title, relpath, extra_formats '
            'FROM `books` b '
            'JOIN `categories` AS cat ON b.category_id = cat.id;'
        )
        for row in self.db.cursor().execute(_query):
            if (
                not row.get('lang')
                or not row.get('name')
                or not row.get('title')
                or not row.get('cat_title')
            ):
                _logger.warning('incomplete book row encountered: %s', row)
                continue

            kwargs = {
                'identifier': row['name'],
                'name': row['title'],
                'lang_id': row['lang'],
                'db_id': row['id'],
                'teaser': row['teaser'],
                'cat_title': row['cat_title'],
                'relpath': row['relpath'],
                'extra_formats': {},
            }
            if row['extra_formats']:
                kwargs['extra_formats'] = json.loads(row['extra_formats'])
            yield kwargs

    def toc(self, db_id):
        _query = (
            'SELECT id, uri, anchor, title, parent_id '
            'FROM `navigation` WHERE book_id=? ORDER BY id;'
        )
        for row in self.db.cursor().execute(_query, [db_id]).fetchall():
            tid = row.get('id')
            uri = row.get('uri')
            anchor = row.get('anchor')
            title = row.get('title')
            parent_id = row.get('parent_id')

            if not uri or not title:
                continue

            yield tid, parent_id, title, uri, anchor

    def pages(self, db_id):
        _query = 'SELECT * FROM `pages` WHERE book_id=?;'
        for row in self.db.cursor().execute(_query, [db_id]).fetchall() or {}:
            title = row.get('title')
            body = row.get('body')

            if not row or not title or not body:
                continue

            # most strings are encoded correctly, but some still contain html tags
            title = title.replace('<em>', '').replace('</em>', '')
            title = title.replace('&#8217;', "'")

            yield {
                'identifier': row.get('name'),
                'name': title,
                'next_link': (row.get('next_link'), row.get('next_title')),
                'prev_link': (row.get('prev_link'), row.get('prev_title')),
                'body': body,
            }

    def categories(self):
        _query = 'SELECT id, lang, title, teaser, orderval, name FROM `categories`;'
        for row in self.db.cursor().execute(_query):
            yield row

    def count_book_words(self, db_id):
        from re import compile as re_compile

        from bs4 import BeautifulSoup

        for book in self.books():
            if book['db_id'] == db_id:
                book_name = book['name']
                break
        else:
            raise ValueError(
                f'Database {self.db_path} does not contain a book with ID {db_id}'
            )

        word_count = 0

        for page in self.pages(db_id):
            raw = BeautifulSoup(page['body'], 'html.parser').get_text()
            text = raw.split()

            # remove punctuation, count raw words
            no_punctuation_re = re_compile('.*[A-Za-z].*')
            raw_words = [w for w in text if no_punctuation_re.match(w)]
            word_count += len(raw_words)

        if not word_count:
            raise ValueError(f'Book {book_name} of {self.db_path} appears to be empty')

        return word_count
