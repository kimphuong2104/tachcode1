import json
import os
import base64
import zipfile
from xml.etree import ElementTree

from webtest import TestApp as Client

from cdb import constants, sig
from cdb.objects import operations
from cdb.objects.cdb_file import CDB_File
from cdb.objects.pdd import Sandbox
from cdb.testcase import RollbackTestCase

from cs.documents import Document
from cs.platform.web.root import Root

from cs.threed.hoops import bcf

from cs.vp.cad import Model
from cs.vp.items.tests import generateItem


class TestBCFSignals(RollbackTestCase):
    def setUp(self):
        super(TestBCFSignals, self).setUp()
        self.root_item = generateItem()
        self.root_doc = operations.operation(
            constants.kOperationNew,
            Model,
            titel="root_doc",
            z_categ1="144",
            z_categ2="296",
            teilenummer=self.root_item.teilenummer,
            t_index=self.root_item.t_index,
        )

        self.markup_filename = "markup.bcf"
        self.markup_xml = '<Markup><Header /><Topic Guid="f08043e4-19fa-4647-8b3f-0cbb1ff6148e" TopicStatus="Open" TopicType="Test"><Title>Test</Title><CreationDate>2020-10-15T20:31:32.151Z</CreationDate><CreationAuthor>Administrator</CreationAuthor><ModifiedDate>2020-10-15T20:32:27.781Z</ModifiedDate><ModifiedAuthor>Administrator</ModifiedAuthor><DueDate>2020-10-15T22:00:00.000Z</DueDate><AssignedTo>Nobody</AssignedTo><Description>This is just a test.</Description><Stage>1</Stage><Labels><Label>test</Label></Labels></Topic></Markup>'
        self.viewpoint_xml = '<VisualizationInfo><Components><ViewSetupHints /><Selection /><Visibility DefaultVisibility="true"><Exceptions /></Visibility><Coloring /></Components><OrthogonalCamera><CameraViewPoint><X>-4.89516578851365</X><Y>0.05919274779810394</Y><Z>3.5214495946865574</Z></CameraViewPoint><CameraViewPoint><X>0.9069226708110792</X><Y>0.3664205255252526</Y><Z>-0.20791168231414076</Z></CameraViewPoint><CameraViewPoint><X>0.19277235636755818</X><Y>0.07788508370153653</Y><Z>0.9781476025413055</Z></CameraViewPoint><ViewToWorldScale>4.741074604635564</ViewToWorldScale></OrthogonalCamera></VisualizationInfo>'
        self.b64_snapshot = 'iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAQAAAAnOwc2AAAAD0lEQVR42mNkwAIYh7IgAAVVAAuInjI5AAAAAElFTkSuQmCC'

        self.payload = {
            'meta': {
                'bcf_filename': 'test.bcf',
                'z_nummer': self.root_doc.z_nummer,
                'z_index': self.root_doc.z_index,
                'topic_id': 'topic_id_1'
            },
            'bcf': {
                'topic_id_1': {
                    'markup': self.markup_xml,
                    'snapshots': {
                        'snapshot.png': list(bytearray(base64.b64decode(self.b64_snapshot)))
                    },
                    'viewpoints': {
                        'viewpoint.bcfv': self.viewpoint_xml
                    }
                }
            }
        }

    def _test_signal_called(self, signal, view_name):
        _signal = {'called': False}

        @sig.connect(signal)
        def slot(obj, data):
            _signal['called'] = True
            self.assertEqual(obj.cdb_object_id, self.root_item.cdb_object_id)
            self.assertEqual(data, self.payload)

        c = Client(Root())
        url = "/internal/threed/{}/{}".format(
            self.root_item.cdb_object_id, view_name)
        response = c.post(url, json.dumps(self.payload))
        self.assertEqual(200, response.status_int)
        self.assertTrue(_signal['called'])

    def test_bcf_topic_saved(self):
        """the `BCF_TOPIC_SAVED` signal gets called"""
        self._test_signal_called(bcf.BCF_TOPIC_SAVED, "save_bcf_topic")

    def test_bcf_topic_viewpoint_added(self):
        """the `BCF_TOPIC_VIEWPOINT_ADDED` signal gets called"""
        self._test_signal_called(
            bcf.BCF_TOPIC_VIEWPOINT_ADDED, "add_bcf_viewpoint")

    def test_bcf_topic_comment_added(self):
        """the `BCF_TOPIC_COMMENT_ADDED` signal gets called"""
        self._test_signal_called(
            bcf.BCF_TOPIC_COMMENT_ADDED, "add_bcf_comment")

    def _create_initial_bcf(self, filename):
        init_data = {
            'meta': {
                'bcf_filename': filename,
                'z_nummer': self.root_doc.z_nummer,
                'z_index': self.root_doc.z_index,
                'topic_id': 'topic_id_1'
            },
            'bcf': {
                'topic_id_1': {
                    'markup': '',
                    'snapshots': {},
                    'viewpoints': {}
                }
            }
        }

        topics = init_data['bcf']

        with Sandbox() as sb:
            bcf_path = os.path.join(sb.location, filename)
            bcf_zip = zipfile.ZipFile(bcf_path, 'w')
            for t_idx, topic in topics.items():
                xml_markup = topic['markup']
                markup_path = os.path.join(sb.location, self.markup_filename)
                with open(markup_path, "w") as f:
                    f.write(xml_markup)
                    f.close()
                bcf_zip.write(markup_path, os.path.join(
                    t_idx, self.markup_filename))
            bcf_zip.close()
            d = Document.ByKeys(z_nummer=self.root_doc.z_nummer,
                                z_index=self.root_doc.z_index)
            f = CDB_File.NewFromFile(d.cdb_object_id, bcf_path, False)

    def test_make_bcf_file(self):
        """the BCF File gets created and is added to document"""

        bcf_filename = self.payload['meta']['bcf_filename']
        topic_id = self.payload['meta']['topic_id']
        snapshot_filename = list(self.payload['bcf'][topic_id]['snapshots'].keys())[
            0]
        viewpoint_filename = list(self.payload['bcf'][topic_id]['viewpoints'].keys())[
            0]

        self._create_initial_bcf(bcf_filename)

        bcf.make_bcf_file(self.payload)
        d = Document.ByKeys(z_nummer=self.root_doc.z_nummer,
                            z_index=self.root_doc.z_index)
        for f in d.Files.KeywordQuery(cdbf_name=bcf_filename):
            with Sandbox() as sb:
                result_path = os.path.join(sb.location, bcf_filename)

                f.checkout_file(result_path)
                self.assertTrue(os.path.exists(
                    result_path), "file should exist")

                self.assertTrue(zipfile.is_zipfile(
                    result_path), "not a valid zipfile")

                with zipfile.ZipFile(result_path, 'r') as zip_file:
                    zip_file.extractall(sb.location)

                    topic_folder = os.path.join(sb.location, topic_id)

                    markup_path = os.path.join(
                        topic_folder, self.markup_filename)
                    self.assertTrue(os.path.exists(markup_path),
                                    "markup file should exist")
                    markup_xml = ElementTree.tostring(ElementTree.parse(
                        markup_path).getroot(), encoding='unicode')
                    self.assertEqual(markup_xml, self.markup_xml,
                                     "markup content has changed")

                    snapshot_path = os.path.join(
                        topic_folder, snapshot_filename)
                    self.assertTrue(os.path.exists(snapshot_path),
                                    "snapshot file should exist")
                    with open(snapshot_path, "rb") as snapshot:
                        snapshot_bin = snapshot.read()
                        self.assertTrue(base64.b64encode(
                            snapshot_bin) == bytes(self.b64_snapshot, "utf-8"), "snapshot content has changed")

                    viewpoint_path = os.path.join(
                        topic_folder, viewpoint_filename)
                    self.assertTrue(os.path.exists(viewpoint_path),
                                    "viewpoint file should exist")
                    viewpoint_xml = ElementTree.tostring(ElementTree.parse(
                        viewpoint_path).getroot(), encoding='unicode')
                    self.assertEqual(
                        viewpoint_xml, self.viewpoint_xml, "viewpoint content has changed")
