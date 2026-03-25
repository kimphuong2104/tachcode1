# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module crossref

Merge all rst objects.inv catalogues into one large catalogue.

"""
import sys
from pathlib import Path

import apsw
from sphinx.ext import intersphinx

from cs.docportal.cdb.helptools.utils import find_inventories, get_package_doc_dir


class CrossRefCatalogue:
    srcdir = '.'  # needed as is for sphinx.ext.intersphinx App support
    SCHEMA = {
        'files': """CREATE TABLE files
                    (
                        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT NOT NULL,
                        package TEXT NOT NULL,
                        UNIQUE (filename)
                    )""",
        'types': """CREATE TABLE types
                    (
                        type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        typename TEXT NOT NULL,
                        UNIQUE (typename)
                    )""",
        'links': """CREATE TABLE links
                    (
                        name TEXT,
                        type_id INTEGER REFERENCES types (type_id) ON DELETE CASCADE,
                        file_id INTEGER REFERENCES files (file_id) ON DELETE CASCADE,
                        label TEXT,
                        project TEXT,
                        target_url TEXT NOT NULL,
                        PRIMARY KEY (name, type_id, file_id)
                    )""",
    }

    def __init__(self, filename):
        if filename == ':memory:' or not Path(filename).is_file():
            self.con = apsw.Connection(filename)
            self.create_schema()
        else:
            self.con = apsw.Connection(filename)

        self.sphinx_errors = []

    def create_schema(self):
        order = ('files', 'types', 'links')
        with self.con:
            cur = self.con.cursor()
            for table in order:
                cur.execute(self.SCHEMA[table])

    def warn(self, msg):
        """Sphinx error writer"""
        self.sphinx_errors.append(msg)

    def remove_inventory(self, package, label):
        """Remove an inventory file from the catalogue"""
        self.con.cursor().execute(
            """DELETE FROM files WHERE filename=? AND package =?""",
            (label, package),
        )

    def add_inventory(self, package, label: str, filename):
        """Add a given Sphinx ``objects.inv`` file with the set label"""
        # skip pickle inventories
        if 'pickle' in label:
            return

        inventory = intersphinx.fetch_inventory(app=self, uri='', inv=filename)
        if inventory is None:
            raise RuntimeError('Failed to import inventory', *self.sphinx_errors)

        with self.con:
            cur = self.con.cursor()
            self._add_inventory_data(cur, package, label, inventory)

    def get_help_links(self) -> list:
        cur = self.con.cursor()
        cur.execute(
            """SELECT
                 name, package, filename, typename,
                 label, target_url
               FROM
                 links
               JOIN
                 files ON links.file_id = files.file_id
               JOIN
                 types ON links.type_id = types.type_id
               WHERE
                 name LIKE 'helpid%'
               ORDER BY name, filename"""
        )

        return list(cur)

    def __contains__(self, link_name: str):
        """Check if link name exists"""
        cur = self.con.cursor()
        cur.execute(
            """SELECT target_url FROM links WHERE name = ?""", (f'{link_name}',)
        )

        # we're good if the apsw.Cursor can fetch at least one row
        for _ in cur:
            return True

        return False

    @staticmethod
    def _add_inventory_data(cur, package, filename, inv):
        cur.execute(
            """INSERT OR IGNORE
               INTO files (filename, package)
               VALUES (?, ?)""",
            (
                filename,
                package,
            ),
        )

        for typename in inv:
            cur.execute(
                """INSERT OR IGNORE
                   INTO types (typename)
                   VALUES (?)""",
                (typename,),
            )

            link_data = (
                (typename, filename, package, name, value[3], value[0], value[2])
                for name, value in inv[typename].items()
            )

            cur.executemany(
                """
                INSERT
                INTO links (type_id,
                            file_id,
                            name,
                            label,
                            project,
                            target_url)
                VALUES (
                    (SELECT type_id FROM types WHERE typename=?),
                    (SELECT file_id FROM files
                     WHERE filename=? AND package=?),
                    ?, ?, ?, ?)""",
                link_data,
            )


def main():
    catalogue = sys.argv[1]
    package = sys.argv[2]
    doc_root = get_package_doc_dir(package_name=package)
    cross_ref_cat = CrossRefCatalogue(filename=catalogue)
    inventories = find_inventories(path=doc_root)

    base = len(str(doc_root.resolve())) + 1
    for inv in inventories:
        label = inv[base:]
        label = label.replace('\\', '/')
        if label.endswith('/objects.inv'):
            label = label[: -len('/objects.inv')]
        cross_ref_cat.add_inventory(package=package, label=label, filename=inv)

    return 0


if __name__ == '__main__':
    sys.exit(main())
