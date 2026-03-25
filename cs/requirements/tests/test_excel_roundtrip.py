from cdb import ElementsError
from cdb.objects import operations
from cdb.platform import gui
import os

from cs.classification import api
from cs.requirements import RQMSpecObject
from cs.requirements import RQMSpecification
from cs.requirements.tests.utils import RequirementsTestCase


class TestExcelRoundtripInterface(RequirementsTestCase):
    def setUp(self):
        RequirementsTestCase.setUp(self)
        # Test empty specification and requirement
        self.evaluator_h = "ed981532-62b7-11ea-b0a1-34e12d2f8425"
        self.req = RQMSpecObject.ByKeys(specobject_id="RT000000060")
        # ensure classification is empty
        api.update_classification(self.req, data={'assigned_classes': [], 'properties': {}})
        self.spec = RQMSpecification.ByKeys(spec_id='ST000000013', revision='0')
        self.spec_old = RQMSpecification.ByKeys(spec_id='ST000000015', revision='0')
        self.spec_latest = RQMSpecification.ByKeys(spec_id='ST000000015', revision='1')

    def test_wrong_file_format(self):
        """ Check if moving a non Excel format input file is detected"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '01_notExcelDoc.png')
        # Expected message value
        m = gui.Message.GetMessage('cdbrqm_not_excel', test_file)
        # Execute import operation and catch expected message
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec,
                                 operations.form_input(self.spec, bewerter=self.evaluator_h, import_excel=test_file))
        self.assertIn(m, str(e.exception))

    def test_no_xml_data(self):
        """ Check for an Excel file that does not have the expected internall structure"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '02_no_xml_data.xlsx')
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_no_matching_table')
        # Execute import operation and catch expected message
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec,
                                 operations.form_input(self.spec, bewerter=self.evaluator_h, import_excel=test_file))
        self.assertIn(m.d, str(e.exception))

    def test_wrong_spec_num(self):
        """ Check if the specification number in the file is in the DB"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '03_wrong_spec_num.xlsx')
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_wrong_specification')
        # Execute import operation and catch expected message
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec,
                                 operations.form_input(self.spec, bewerter=self.evaluator_h, import_excel=test_file))
        self.assertIn(m.d, str(e.exception))

    def test_empty_spec_number(self):
        """ Check for invalid input fiels"""
        # Get test files
        test_files = [os.path.join(os.path.dirname(__file__), '04_empty_spec_num.xlsx'),
                      os.path.join(os.path.dirname(__file__), '05_none_spec_num.xlsx'),
                      os.path.join(os.path.dirname(__file__), '06_empty_index.xlsx'),
                      os.path.join(os.path.dirname(__file__), '07_none_index.xlsx'),
                      os.path.join(os.path.dirname(__file__), '08_empty_language.xlsx'),
                      os.path.join(os.path.dirname(__file__), '09_none_language.xlsx'),
                      os.path.join(os.path.dirname(__file__), '10_not_a_language.xlsx')]

        m = gui.Message.ByKeys('cdbrqm_invalid_field')
        for test_file in test_files:
            # Execute import operation and catch expected message
            with self.assertRaises(ElementsError) as e:
                operations.operation("cdbrqm_rating_import", self.spec,
                                     operations.form_input(self.spec, bewerter=self.evaluator_h,
                                                           import_excel=test_file))
            self.assertIn(m.d, str(e.exception))

    def test_invalid_specification_index(self):
        """ Check if moving the combination of spec id and revision in the file exists"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '11_spec_id_index_not_valid.xlsx')
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_specification_not_exist')
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec,
                                 operations.form_input(self.spec, bewerter=self.evaluator_h, import_excel=test_file))
        self.assertIn(m.d, str(e.exception))

    def test_missing_xml_columns(self):
        """ Check if all of the expected input fields are in the Excel file"""
        # Get test files
        test_files = [os.path.join(os.path.dirname(__file__), '12_missing_comment_col.xlsx'),
                      os.path.join(os.path.dirname(__file__), '13_missing_rating_col.xlsx'),
                      os.path.join(os.path.dirname(__file__), '14_missing_req_id_col.xlsx')]
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_no_matching_table')
        for test_file in test_files:
            # Execute import operation and catch expected message
            with self.assertRaises(ElementsError) as e:
                operations.operation("cdbrqm_rating_import", self.spec,
                                     operations.form_input(self.spec, bewerter=self.evaluator_h,
                                                           import_excel=test_file))
            self.assertIn(m.d, str(e.exception))

    def test_success_single_req_empty_rating(self):
        """ Test of successful rating import which does not change anything due invalid data to import"""
        # Get test files
        test_files = [os.path.join(os.path.dirname(__file__), '15_empty_req_id_values.xlsx'),  # FIXME: case should log errors/warnings
                      os.path.join(os.path.dirname(__file__), '16_empty_rating_values.xlsx'),
                      os.path.join(os.path.dirname(__file__), '17_invalid_rating_values.xlsx')]  # FIXME: case should log errors/warnings
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_excel_import_success')
        req_class = api.get_classification(self.req)
        class_condition = 'RQM_RATING' in req_class["assigned_classes"]
        self.assertEqual(class_condition, False)
        for test_file in test_files:
            # Execute import operation and catch expected message
            with self.assertRaises(ElementsError) as e:
                operations.operation("cdbrqm_rating_import", self.spec,
                                     operations.form_input(self.spec, bewerter=self.evaluator_h,
                                                           import_excel=test_file))
            self.assertIn(m.d, str(e.exception))

            req_class = api.get_classification(self.req)
            class_condition = 'RQM_RATING' in req_class["assigned_classes"]
            self.assertEqual(class_condition, False)

    def test_aggregated_rating_change(self):  # How to change users
        """ Change the aggregated rating"""
        # Test data
        evaluator_person = "fde6cf6a-6793-11ea-b0a7-34e12d2f8425"
        test_comment = "Comment for testing purposes"

        # Give permissions to Admin
        self.req.subject_type = "Person"
        self.req.subject_id = "caddok"

        # Values for the new Rating
        rating_de = 'akzeptiert'
        rating_en = 'accepted'

        # Obtain classification from the test requirement
        req_class = api.get_classification(self.req)

        # Add the rating class
        if 'RQM_RATING' not in req_class["assigned_classes"]:
            req_class = api.rebuild_classification(req_class, ['RQM_RATING'])
            api.update_classification(self.req, req_class)
            req_class = api.get_classification(self.req)
        # Test if class is in classification
        self.assertIn('RQM_RATING', req_class["assigned_classes"])

        # Check if overall classification is initially empty
        previous_bewertung = req_class['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value']['de']['text_value']
        self.assertEqual(previous_bewertung, None)

        # Change the rating
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_COMMENT_EXTERN'][0][
            "value"] = test_comment
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]["value"][
            'de']['text_value'] = rating_de
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]["value"][
            'en']['text_value'] = rating_en
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_EVALUATOR'][0][
            'value'] = evaluator_person
        req_class['properties']['RQM_RATING_RQM_RATING_CALCULATED'][0]['value'] = True
        api.update_classification(self.req, req_class)

        # Check if the expected overall rating is the highest
        expected_rating = 'akzeptiert'
        req_class = api.get_classification(self.req)
        new_bewertung = req_class['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value']['de']['text_value']
        self.assertEqual(new_bewertung, expected_rating)

        # Change the rating to a higher rated rating
        rating_de = 'nicht akzeptiert'
        rating_en = 'not accepted'
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_COMMENT_EXTERN'][0][
            "value"] = test_comment
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]["value"][
            'de']['text_value'] = rating_de
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]["value"][
            'en']['text_value'] = rating_en
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_EVALUATOR'][0][
            'value'] = evaluator_person
        api.update_classification(self.req, req_class)

        # Check if the expected overall rating is the new highest rating
        expected_rating = 'nicht akzeptiert'
        req_class = api.get_classification(self.req)
        new_bewertung = req_class['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value']['de']['text_value']
        self.assertEqual(new_bewertung, expected_rating)

    def test_aggregated_rating_override(self):
        """ Override a calculated aggregated rating"""
        # Test data
        evaluator_person = "fde6cf6a-6793-11ea-b0a7-34e12d2f8425"
        test_comment = "Comment for testing purposes"

        # Give permissions to admin
        self.req.subject_type = "Person"
        self.req.subject_id = "caddok"

        # Override the automatic overall rating calculation
        forced_rating_de = 'akzeptiert'
        forced_rating_en = 'accepted'

        rating_de = 'nicht akzeptiert'
        rating_en = 'not accepted'

        # Get rating
        req_class = api.get_classification(self.req)

        # Add the rating class
        if 'RQM_RATING' not in req_class["assigned_classes"]:
            req_class = api.rebuild_classification(req_class, ['RQM_RATING'])
            api.update_classification(self.req, req_class)
            req_class = api.get_classification(self.req)

        # Test if class is in classification
        self.assertIn('RQM_RATING', req_class["assigned_classes"])

        # Check if overall classification is initially empty
        previous_bewertung = req_class['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value']['de']['text_value']
        self.assertEqual(previous_bewertung, None)

        # Set checkbox to false
        req_class['properties']['RQM_RATING_RQM_RATING_CALCULATED'][0]['value'] = False
        # api.update_classification(self.req, req_class)

        # Set overall rating
        req_class['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value']['de']['text_value'] = forced_rating_de
        req_class['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value']['en']['text_value'] = forced_rating_en

        # Values given by a Person
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_COMMENT_EXTERN'][0][
            "value"] = test_comment
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]["value"][
            'de']['text_value'] = rating_de
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]["value"][
            'en']['text_value'] = rating_en
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_EVALUATOR'][0][
            'value'] = evaluator_person
        api.update_classification(self.req, req_class)

        # Check if the expected overall rating is overriden
        req_class = api.get_classification(self.req)
        new_bewertung = req_class['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value']['de']['text_value']
        self.assertEqual(new_bewertung, forced_rating_de)

    def test_success_no_previous_rating(self):
        """ Successfully import a rating to an existing Requirement"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '18_success.xlsx')

        # Give permissions to admin
        self.req.subject_type = "Person"
        self.req.subject_id = "caddok"

        # Expected success message
        m = gui.Message.ByKeys('cdbrqm_excel_import_success')

        # Rating input
        input_rating = "Info fehlt"
        input_comment = "Comment for test purposes"

        # Execute import operation and catch success message
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec,
                                 operations.form_input(self.spec, bewerter=self.evaluator_h, import_excel=test_file))
        self.assertIn(m.d, str(e.exception))

        # Execute import operation and catch expected message
        req_class = api.get_classification(self.req)
        evaluator_from_req = \
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_EVALUATOR'][0]['value']
        self.assertEqual(evaluator_from_req, self.evaluator_h)

        rating_from_req = \
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]["value"][
            'de']['text_value']
        self.assertEqual(rating_from_req, input_rating)

        comment_from_req = \
        req_class['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_COMMENT_EXTERN'][0]["value"]
        self.assertEqual(comment_from_req, input_comment)

    def test_index_mismatch(self):
        """ Check if the index in the file matches the selected index"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '19_index_mismatch.xlsx')
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_specification_not_exist')
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec,
                                 operations.form_input(self.spec, bewerter=self.evaluator_h, import_excel=test_file))
        self.assertIn(m.d, str(e.exception))

    def test_old_index_old_spec(self):
        """ Check detection of an old index in a write protected specification"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '20_old_index_old_spec.xlsx')
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_wrong_index')
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec_old,
                                 operations.form_input(self.spec_old, bewerter=self.evaluator_h,
                                                       import_excel=test_file))
        self.assertIn(m.d, str(e.exception))

    def test_current_index_old_spec(self):
        """ Check detection of a current index in a write protected specification"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '21_current_index_old_spec.xlsx')
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_wrong_specification')
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec_old,
                                 operations.form_input(self.spec_old, bewerter=self.evaluator_h,
                                                       import_excel=test_file))
        self.assertIn(m.d, str(e.exception))

    def test_old_index_latest_spec(self):
        """ Check detection of an old index in the current specification"""
        # Get test file
        test_file = os.path.join(os.path.dirname(__file__), '22_old_index_current_spec.xlsx')
        # Expected message value
        m = gui.Message.ByKeys('cdbrqm_wrong_index')
        with self.assertRaises(ElementsError) as e:
            operations.operation("cdbrqm_rating_import", self.spec_latest,
                                 operations.form_input(self.spec_latest, bewerter=self.evaluator_h,
                                                       import_excel=test_file))
        self.assertIn(m.d, str(e.exception))

