#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import ElementsError, testcase
from cdb.objects import Object
from cdb.validationkit.op import operation

from cs.pcs.checklists import Checklist, ChecklistItem
from cs.pcs.checklists.tests.integration import util as test_util


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


def get_rating_ctx(rating_id, objects):
    # create mocked context object
    ctx = mock.Mock(spec=["dialog", "objects", "refresh_tables"])
    d = mock.MagicMock()
    real_dict = {"rating_id": rating_id, "cdbpcs_clir_txt": "bar"}
    d.get_attribute_names.return_value = real_dict.keys()
    d.__getitem__.side_effect = real_dict.__getitem__
    ctx.dialog = d
    ctx.objects = list(objects)
    return ctx


def create_project():
    project = test_util.create_project("checklist_item_test", "")
    project.status = project.EXECUTION.status
    checklist = test_util.create_checklist(project)
    return project, checklist


@pytest.mark.dependency(name="integration", depends=["cs.pcs.checklists"])
class ChecklistItemEvaluation(testcase.RollbackTestCase):
    def test_check_consistency_of_rating_id_and_status(self):
        "ChecklistItem: check consistency of rating_id and status."
        user = test_util.get_user("caddok")
        project, checklist = create_project()
        cl_item_1 = test_util.create_checklist_item(
            user, project, checklist, cl_item_id="111"
        )
        cl_item_2 = test_util.create_checklist_item(
            user, project, checklist, cl_item_id="222"
        )
        cl_item_3 = test_util.create_checklist_item(
            user, project, checklist, cl_item_id="333"
        )
        self.assertEqual((checklist.rating_id, checklist.status), ("clear", 0))
        self.assertEqual((cl_item_1.rating_id, cl_item_1.status), ("clear", 0))
        self.assertEqual((cl_item_2.rating_id, cl_item_2.status), ("clear", 0))
        self.assertEqual((cl_item_3.rating_id, cl_item_3.status), ("clear", 0))

        # execute rating operation with mocked context object
        ChecklistItem.on_cdbpcs_clitem_rating_now(get_rating_ctx("rot", [cl_item_1]))
        # check values
        checklist.Reload()
        cl_item_1.Reload()
        cl_item_2.Reload()
        cl_item_3.Reload()
        self.assertEqual((checklist.rating_id, checklist.status), ("rot", 20))
        self.assertEqual((cl_item_1.rating_id, cl_item_1.status), ("rot", 200))
        self.assertEqual((cl_item_2.rating_id, cl_item_2.status), ("clear", 20))
        self.assertEqual((cl_item_3.rating_id, cl_item_3.status), ("clear", 20))

        # execute rating operation with mocked context object
        ChecklistItem.on_cdbpcs_clitem_rating_now(
            get_rating_ctx("gruen", [cl_item_1, cl_item_2])
        )
        # check values
        checklist.Reload()
        cl_item_1.Reload()
        cl_item_2.Reload()
        cl_item_3.Reload()
        self.assertEqual((checklist.rating_id, checklist.status), ("gruen", 20))
        self.assertEqual((cl_item_1.rating_id, cl_item_1.status), ("gruen", 200))
        self.assertEqual((cl_item_2.rating_id, cl_item_2.status), ("gruen", 200))
        self.assertEqual((cl_item_3.rating_id, cl_item_3.status), ("clear", 20))

        # execute rating operation with mocked context object
        ChecklistItem.on_cdbpcs_clitem_rating_now(
            get_rating_ctx("gelb", [cl_item_2, cl_item_3])
        )
        # check values
        checklist.Reload()
        cl_item_1.Reload()
        cl_item_2.Reload()
        cl_item_3.Reload()
        self.assertEqual((checklist.rating_id, checklist.status), ("gelb", 200))
        self.assertEqual((cl_item_1.rating_id, cl_item_1.status), ("gruen", 200))
        self.assertEqual((cl_item_2.rating_id, cl_item_2.status), ("gelb", 200))
        self.assertEqual((cl_item_3.rating_id, cl_item_3.status), ("gelb", 200))


class EvaluationBase(testcase.RollbackTestCase):
    "Abstract base class for item rating acceptance tests"

    MSG_CHECKLIST_FINAL = str(
        "Die Checkliste wurde bereits abgeschlossen/verworfen. "
        "Es können daher keine Prüfpunkte mehr "
        "angelegt oder geändert werden.\n"
        "Die Operation wurde vom Benutzer abgebrochen."
    )

    def _create_cl(self, project, status, cl_id):
        return test_util.create_checklist(
            project,
            status=status,
            checklist_id=cl_id,
        )

    def _create_item(self, checklist, item_id):
        user = test_util.get_user("caddok")
        return test_util.create_checklist_item(
            user,
            checklist.Project,
            checklist,
            cl_item_id=item_id,
        )

    def _setup(self, no_of_cls, no_of_items, cl_status):
        project = test_util.create_project("cl_item_rating_test", "")
        project.status = project.EXECUTION.status
        cls = [self._create_cl(project, cl_status, cl_no) for cl_no in range(no_of_cls)]
        items = [
            self._create_item(cl, item_no)
            for item_no in range(no_of_items)
            for cl in cls
        ]
        return cls, items

    def _rate(self, cl, item):
        operation(
            "cdbpcs_clitem_rating",
            item,
            preset={"rating_id": "gruen"},
        )
        cl.Reload()
        if isinstance(item, Object):
            self.assertEqual(item.rating_id, "gruen")
        else:
            ratings = []
            for x in item:
                x.Reload()
                ratings.append(x.rating_id)

            self.assertEqual(ratings, ["gruen"] * len(item))

    def _fail(self, cl, item, err_msg):
        with self.assertRaises(ElementsError) as error:
            self._rate(cl, item)
        self.assertEqual(str(error.exception), err_msg)


@pytest.mark.dependency(name="acceptance", depends=["cs.pcs.checklists"])
@pytest.mark.dependency(name="acceptance", depends=["cs.pcs.checklists"])
class EvaluateOnlyItem(EvaluationBase):
    "Evaluating the only item of a checklist will also complete it"

    def _rate_only_item(self, cl_status):
        cls, items = self._setup(1, 1, cl_status)
        self._rate(cls[0], items[0])
        return cls[0]

    def _fail_only_item(self, cl_status):
        cls, items = self._setup(1, 1, cl_status)
        self._fail(cls[0], items[0], self.MSG_CHECKLIST_FINAL)

    def test_cl_new(self):
        "rate only item of new checklist"
        cl = self._rate_only_item(Checklist.NEW)
        self.assertEqual(
            (cl.status, cl.rating_id),
            (Checklist.COMPLETED.status, "gruen"),
        )

    def test_cl_evaluation(self):
        "rate only item of checklist in evaluation"
        cl = self._rate_only_item(Checklist.EVALUATION)
        self.assertEqual(
            (cl.status, cl.rating_id),
            (Checklist.COMPLETED.status, "gruen"),
        )

    def test_cl_completed(self):
        "cannot rate only item of completed checklist"
        self._fail_only_item(Checklist.COMPLETED)

    def test_cl_discarded(self):
        "cannot rate only item of discarded checklist"
        self._fail_only_item(Checklist.DISCARDED)


@pytest.mark.dependency(name="acceptance", depends=["cs.pcs.checklists"])
class EvaluateOneItem(EvaluationBase):
    "Evaluating any (but not the only) item of a checklist won't complete it"

    def _rate_one_item(self, cl_status):
        cls, items = self._setup(1, 2, cl_status)
        self._rate(cls[0], items[0])
        return cls[0]

    def _fail_one_item(self, cl_status):
        cls, items = self._setup(1, 2, cl_status)
        self._fail(cls[0], items[0], self.MSG_CHECKLIST_FINAL)

    def test_cl_new(self):
        "rate any item of new checklist"
        cl = self._rate_one_item(Checklist.NEW)
        self.assertEqual(
            (cl.status, cl.rating_id),
            (Checklist.EVALUATION.status, "gruen"),
        )

    def test_cl_evaluation(self):
        "rate any item of checklist in evaluation"
        cl = self._rate_one_item(Checklist.EVALUATION)
        self.assertEqual(
            (cl.status, cl.rating_id),
            (Checklist.EVALUATION.status, "gruen"),
        )

    def test_cl_completed(self):
        "cannot rate any item of completed checklist"
        self._fail_one_item(Checklist.COMPLETED)

    def test_cl_discarded(self):
        "cannot rate any item of discarded checklist"
        self._fail_one_item(Checklist.DISCARDED)


@pytest.mark.dependency(name="acceptance", depends=["cs.pcs.checklists"])
class EvaluateTwoItems(EvaluationBase):
    "Evaluating the only two items of a checklist will complete it"

    def _rate_two_items(self, cl_status):
        cls, items = self._setup(1, 2, cl_status)
        self._rate(cls[0], items)
        return cls[0]

    def _fail_two_items(self, cl_status):
        cls, items = self._setup(1, 2, cl_status)
        self._fail(cls[0], items, self.MSG_CHECKLIST_FINAL)

    def test_cl_new(self):
        "rate only two items of new checklist"
        cl = self._rate_two_items(Checklist.NEW)
        self.assertEqual(
            (cl.status, cl.rating_id),
            (Checklist.COMPLETED.status, "gruen"),
        )

    def test_cl_evaluation(self):
        "rate only two items of checklist in evaluation"
        cl = self._rate_two_items(Checklist.EVALUATION)
        self.assertEqual(
            (cl.status, cl.rating_id),
            (Checklist.COMPLETED.status, "gruen"),
        )

    def test_cl_completed(self):
        "cannot rate only two items of completed checklist"
        self._fail_two_items(Checklist.COMPLETED)

    def test_cl_discarded(self):
        "cannot rate only two items of discarded checklist"
        self._fail_two_items(Checklist.DISCARDED)


@pytest.mark.dependency(name="acceptance", depends=["cs.pcs.checklists"])
class EvaluateItemsDifferentChecklists(EvaluationBase):
    "Rating items of different checklists is not allowed"

    MSG_MULTIPLE_CHECKLISTS = str(
        "Diese Operation kann nur auf Prüfpunkten "
        "einer einzigen Checkliste ausgeführt werden.\n"
        "Die Operation wurde vom Benutzer abgebrochen."
    )

    def test_multiple_cls(self):
        "cannot rate items of different checklists"
        cls, items = self._setup(2, 2, Checklist.NEW)
        multi_items = [items[0], items[-1]]
        self.assertNotEqual(items[0].checklist_id, items[-1].checklist_id)
        self._fail(cls[0], multi_items, self.MSG_MULTIPLE_CHECKLISTS)


@pytest.mark.dependency(name="integration", depends=["cs.pcs.checklists"])
class ChecklistItemAccessTestCase(testcase.RollbackTestCase):
    def test_completed_checklist_item_access_by_non_admin_user(self):
        "Create a checklist item in project by public user."
        project = test_util.create_project("bass", "")
        self.assertIsNotNone(project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(user, project, role_id="Projektmitglied")
        test_util.assign_user_project_role(user, project, role_id="Projektleiter")

        checklist = test_util.create_checklist(project)
        self.assertIsNotNone(checklist, "Checklist has not been created.")
        checklist.status = Checklist.COMPLETED

        cl_item = test_util.create_checklist_item(user, project, checklist)
        self.assertIsNotNone(cl_item, "Checklist Item has not been created.")
        cl_item.status = ChecklistItem.COMPLETED
        cl_item.checklist_state = ChecklistItem.COMPLETED

        self.assertIsNotNone(
            checklist.ChecklistItems, "Checklist has no Checklist Items."
        )

        c, r, s, d, e, ch = self.check_access_rights(cl_item, user)
        self.assertTrue(c, "Checklist Item should be creatable by non-admin user.")
        self.assertTrue(r, "Checklist Item should be readable by non-admin user.")
        self.assertTrue(d, "Checklist Item should be deletable by non-admin user.")

        self.assertFalse(
            s, "Completed Checklist Item should not be modifiable by non-admin user."
        )
        self.assertFalse(
            e, "Completed Checklist Item should not be evaluateable by non-admin user."
        )
        self.assertFalse(
            ch, "Completed Checklist Item should not be changeable by non-admin user."
        )

    def test_completed_checklist_item_access_by_admin_user(self):
        "Create a checklist item in project by admin user."
        project = test_util.create_project("bass", "")
        self.assertIsNotNone(project, "Project has not been created.")

        user = test_util.create_user("admin")
        test_util.assign_user_role_administrator(user)
        test_util.assign_user_project_role(user, project, role_id="Projektmitglied")
        test_util.assign_user_project_role(user, project, role_id="Projektleiter")

        checklist = test_util.create_checklist(project)
        self.assertIsNotNone(checklist, "Checklist has not been created.")
        checklist.status = Checklist.COMPLETED

        cl_item = test_util.create_checklist_item(user, project, checklist)
        self.assertIsNotNone(cl_item, "Checklist Item has not been created.")
        cl_item.status = ChecklistItem.COMPLETED
        cl_item.checklist_state = ChecklistItem.COMPLETED

        self.assertIsNotNone(
            checklist.ChecklistItems, "Checklist has no Checklist Items."
        )

        c, r, s, d, e, ch = self.check_access_rights(cl_item, user)
        self.assertTrue(c, "Checklist Item should be creatable by Admin user.")
        self.assertTrue(r, "Checklist Item should be readable by Admin user.")
        self.assertTrue(d, "Checklist Item should be deletable by Admin user.")

        self.assertTrue(
            s, "Completed Checklist Item should be modifiable by Admin user."
        )
        self.assertTrue(
            e, "Completed Checklist Item should be evaluateable by Admin user."
        )
        self.assertTrue(
            ch, "Completed Checklist Item should be changeable by Admin user."
        )

    def check_access_rights(self, obj, user):
        create = obj.CheckAccess("create", user.personalnummer)
        read = obj.CheckAccess("read", user.personalnummer)
        delete = obj.CheckAccess("delete", user.personalnummer)
        save = obj.CheckAccess("save", user.personalnummer)
        valuate_checklist = obj.CheckAccess("valuate_checklist", user.personalnummer)
        change = obj.CheckAccess("CHANGE", user.personalnummer)
        return create, read, save, delete, valuate_checklist, change


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
