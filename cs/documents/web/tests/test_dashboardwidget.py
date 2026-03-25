# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


__docformat__ = "restructuredtext en"


import unittest
from datetime import datetime, timedelta

from webtest import TestApp as Client

from cdb import auth
from cdb.testcase import RollbackOnceTestCase, error_logging_disabled
from cs.platform.web.root import Root


class TestDashboardWidgetRecentlyModified(RollbackOnceTestCase):
    @classmethod
    def setUpClass(cls):
        """
        Set up the test case
        """
        super(TestDashboardWidgetRecentlyModified, cls).setUpClass()
        try:
            from cs.documents import Document
        except ImportError:
            raise unittest.SkipTest("this test needs cs.documents")

        now = datetime.now()
        me = auth.persno
        other = "user.public"
        docs = [
            ("DBoardTestSeventh", 0, me, 0, me),
            ("DBoardTestSixth", None, None, 10, me),
            ("DBoardTestFifth", 20, me, None, me),
            ("DBoardTestFourth", -10, other, 30, me),
            ("DBoardTestThird", 40, me, 10, other),
            ("DBoardTestSecond", -10, me, 50, other),
            ("DBoardTestFirst", 60, other, -5, me),
        ]

        # We create the last one first to avoid that the
        # sort is randomly correct because it is the creation order
        for z_nummer, mdate, mpno, m2date, m2pno in docs:
            if mdate is not None:
                mdate = now + timedelta(seconds=mdate)
            if m2date is not None:
                m2date = now + timedelta(seconds=m2date)

            Document.Create(
                z_nummer=z_nummer,
                z_index="",
                titel=z_nummer,
                z_categ1=142,
                z_categ2=153,
                autoren="Administrator",
                z_bereich="IT",
                erzeug_system="PAPIER",
                z_status_txt="In Progress",
                z_art="doc_standard",
                z_status=0,
                cdb_obsolete=0,
                cdb_mpersno=mpno,
                cdb_mdate=mdate,
                cdb_m2persno=m2pno,
                cdb_m2date=m2date,
                cdb_cpersno="caddok",
                cdb_cdate=now,
            )

        cls.docs = docs
        cls.docs.reverse()
        app = Root()
        cls.c = Client(app)

    def test_recentlymodifieddocs(self):
        resp = self.c.get(
            "/internal/cs-documents/recentlymodifieddocs", params={"maxrows": 7}
        )
        self.assertEqual(len(resp.json["objects"]), 7)
        for obj in resp.json["objects"]:
            self.assertTrue(obj["stateName"])
            self.assertTrue(obj["stateColor"])
            self.assertTrue(obj["object"])
        znr_resp = [obj["object"]["z_nummer"] for obj in resp.json["objects"]]
        znr_docs = [doc[0] for doc in self.docs]
        self.assertEqual(znr_resp, znr_docs, "Wrong order %s" % (znr_resp))

    def test_max_rows_work(self):
        for rows in iter(range(1, 3)):
            resp = self.c.get(
                "/internal/cs-documents/recentlymodifieddocs", params={"maxrows": rows}
            )
            self.assertEqual(len(resp.json["objects"]), rows)

    def test_max_rows_invalid(self):
        with error_logging_disabled():
            self.c.get(
                "/internal/cs-documents/recentlymodifieddocs",
                params={"maxrows": 0},
                status=400,
            )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
