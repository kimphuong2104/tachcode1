import unittest
from cdb import testcase
from cs.platform.web.root import Root
from webtest import TestApp as Client

class TestClassdefs(testcase.RollbackTestCase):
    maxDiff = None

    def setUp(self):
        super(TestClassdefs, self).setUp()
        app = Root()
        self.c = Client(app)

    def test_classdefs(self):
        classes = [
            'csweb_outlet_position',
            'csweb_outlet_child',
            'foobah_is_unavailable'
        ]
        with testcase.error_logging_disabled():
            response = self.c.post_json('/internal/uisupport/classes', {
                'classes': classes
            })
        self.assertEqual(len(response.json['classes']), 2)
        self.assertEqual(set(cls['name'] for cls in response.json['classes']), set(classes[:2]))
        self.assertEqual(list(response.json['errors'].keys()), classes[2:])
