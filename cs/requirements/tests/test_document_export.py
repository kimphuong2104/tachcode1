# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import datetime
import json
import logging
import os
from io import BytesIO
import subprocess
import sys
import tempfile
import zipfile

from lxml import etree

from cdb import CADDOK, ElementsError, rte, util
from cdb.objects import operations
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import form_input, operation
from cdb.wsgi.util import jail_filename
from cs.classification import api as classification_api
from cs.requirements import RQMSpecification, RQMSpecObject, rqm_utils
from cs.requirements.classes import DocumentExportProfile, RQMExportProcessRun
from cs.requirements.document_export import DocumentExportTools, XSLTransformer
from cs.requirements.richtext import RichTextVariables
from cs.requirements.tests.utils import ChangedFile
from cs.requirements_reqif import ReqIFProfile
from cs.requirements_reqif.reqif_import_ng import ReqIFImportNG

from .utils import RequirementsTestCase

LOG = logging.getLogger(__name__)


class TestXSLT(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        super(TestXSLT, self).__init__(*args, need_uberserver=False,
                                       **kwargs)

    def setUp(self):
        RequirementsTestCase.setUp(self)
        self.tmpdir = tempfile.mkdtemp()
        xml_filename = 'test.xhtml'
        self.xml_filepath = os.path.join(self.tmpdir, xml_filename)
        with open(self.xml_filepath, 'w+') as f:
            f.write("""
                <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
                <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
                    <head>
                        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
                        <title>xhtml-object-transformation-test</title>
                    </head>
                    <body>
                        <object data="test_svg.html" height="640" type="image/svg+xml" width="472">
                            <object data="id1_PreView.png" height="50" type="image/png" width="37">id1.html</object>
                        </object>
                    </body>
                </html>
            """)

    def tearDown(self):
        DocumentExportTools.cleanup_folder(self.tmpdir)
        RequirementsTestCase.tearDown(self)

    def test_positive_transformation(self):
        """ check that a basic XSLT2 stylesheet transformation works """
        xslt_template_name = 'good_template.xsl'
        xslt_template_path = os.path.join(self.tmpdir, xslt_template_name)
        with open(xslt_template_path, 'w+') as f:
            f.write("""
                <xsl:stylesheet version="2.0"
                    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                    xmlns:con_rqm="con_rqm" extension-element-prefixes="con_rqm"
                    xmlns:xhtml="http://www.w3.org/1999/xhtml"
                    xmlns="http://www.w3.org/1999/xhtml"
                >
                    <xsl:output method="xml" indent="yes" encoding="utf-8" omit-xml-declaration="yes"/>
                        <xsl:template match="@* | node()">
                            <xsl:copy>
                                <xsl:apply-templates select="@* | node()"/>
                            </xsl:copy>
                        </xsl:template>
                </xsl:stylesheet>
            """)

        XSLTransformer.transform(
            xslt_template_path,
            self.xml_filepath,
            working_directory=self.tmpdir,
            with_rqm_extension=False
        ).write_output(
            self.xml_filepath + '.transformed.xml.xhtml'
        )
        self.assertTrue(os.path.isfile(self.xml_filepath + '.transformed.xml.xhtml'))

    def test_attacker_transformation1(self):
        """ check that a XSLT1 stylesheet cannot write to other output files """
        xslt_template_name = 'bad_template.xsl'
        xslt_template_path = os.path.join(self.tmpdir, xslt_template_name)
        with open(xslt_template_path, 'w+') as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
                <xsl:stylesheet
                  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                  xmlns:exsl="http://exslt.org/common"
                  extension-element-prefixes="exsl"
                  exclude-result-prefixes="exsl"
                  version="1.0">
                  <xsl:output method="xml"
                                  indent="yes"
                                  encoding="utf-8"
                                  omit-xml-declaration="yes"/>
                    <xsl:template match="@* | node()">
                        <xsl:copy>
                            <xsl:apply-templates select="@* | node()"/>
                        </xsl:copy>
                        <exsl:document href="./testfile" method="text">test</exsl:document>
                        <exsl:document href="./testfile2" method="text">test2</exsl:document>
                    </xsl:template>
                </xsl:stylesheet>""")
        with self.assertRaises(etree.XSLTApplyError):
            XSLTransformer.transform(
                xslt_template_path,
                self.xml_filepath,
                working_directory=self.tmpdir,
                with_rqm_extension=False
            ).write_output(
                self.xml_filepath + '.transformed.xml.xhtml'
            )
        self.assertFalse(os.path.isfile(self.xml_filepath + '.transformed.xml.xhtml'))
        self.assertFalse(os.path.isfile(os.path.join(self.tmpdir, 'testfile')))
        self.assertFalse(os.path.isfile(os.path.join(self.tmpdir, 'testfile2')))

    def test_attacker_transformation2(self):
        """ check that a XSLT2 stylesheet cannot write to other output files """
        xslt_template_name = 'bad_template.xsl'
        xslt_template_path = os.path.join(self.tmpdir, xslt_template_name)
        with open(xslt_template_path, 'w+') as f:
            f.write("""<xsl:stylesheet version="2.0"
                  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                  xmlns:xhtml="http://www.w3.org/1999/xhtml"
                  xmlns="http://www.w3.org/1999/xhtml"
                  >
                <xsl:output method="xml"
                  indent="yes"
                  encoding="utf-8"
                  omit-xml-declaration="yes"/>
                <xsl:template match="@* | node()">
                <xsl:result-document href="./testfile" method="text">test</xsl:result-document>
                <xsl:result-document href="./testfile2" method="text">test2</xsl:result-document>
                </xsl:template>
                </xsl:stylesheet>""")
        XSLTransformer.transform(
            xslt_template_path,
            self.xml_filepath,
            working_directory=self.tmpdir,
            with_rqm_extension=False
        ).write_output(
            self.xml_filepath + '.transformed.xml.xhtml'
        )
        # XSLT2 result-document is not supported but does not lead to an error
        # therefore assume that the transformation was done but without the additional files
        self.assertTrue(os.path.isfile(self.xml_filepath + '.transformed.xml.xhtml'))
        self.assertFalse(os.path.isfile(os.path.join(self.tmpdir, 'testfile')))
        self.assertFalse(os.path.isfile(os.path.join(self.tmpdir, 'testfile2')))


class TestDocumentExports(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        super(TestDocumentExports, self).__init__(*args, need_uberserver=False,
                                                  **kwargs)

    def _get_content(self, content):
        content = BytesIO(content.encode('utf-8'))
        return content

    def setUp(self):
        RequirementsTestCase.setUp(self)
        new_spec_args = {
            u"name": u'Test Specification %s' % datetime.datetime.now(),
            u"is_template": 0,
            u"category": u'System Specification'
        }
        self.spec = spec = operations.operation(
            "CDB_Create",
            RQMSpecification,
            **new_spec_args
        )
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'document_export_testspec.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        self.requirements_selected = self._get_selected_leaf_requirements()
        self.requirement_not_included = self._get_not_included_requirement()

    def _get_selected_leaf_requirements(self):
        return self.spec.Requirements.KeywordQuery(reqif_id=[
            # this leaf should also lead to export of its parents
            'cdb-000ea466-37b8-4f58-bf09-20179f1a0689',  # test5 with picture
            # this one is toplevel so it does not have parent
            'cdb-edbbeab2-15eb-45a1-9373-6c2c8a8a91a3',  # chapter 3
        ])

    def _get_not_included_requirement(self):
        req = RQMSpecObject.ByKeys(
            reqif_id='cdb-13489874-0bf3-43c4-b62c-1945efb03f53', ce_baseline_id=''
        )
        self.assertNotEqual(req.mapped_category_en, 'Chapter')
        return req

    def _extract_zip_container(self, the_file):
        namelist = []
        try:
            tmp_dir_path = tempfile.mkdtemp()
            archive_path = str(os.path.join(tmp_dir_path, 'result.zip'))
            the_file.checkout_file(archive_path)
            with zipfile.ZipFile(archive_path, allowZip64=True) as zfile:
                namelist = zfile.namelist()
                for name in namelist:
                    zfile.extract(name, tmp_dir_path)
        except BaseException as e:
            LOG.exception('Failed to extract zip container: %s', the_file)
            print(e)
            return None, None
        return tmp_dir_path, namelist

    def _convert_pdf_to_text(self, the_file):
        try:
            tmp_dir_path = tempfile.mkdtemp()
            archive_path = str(os.path.join(tmp_dir_path, 'result.pdf'))
            the_file.checkout_file(archive_path)
            cmd = 'pdftotext {} -layout -l 1 -'.format(archive_path)
            title_page_content = subprocess.check_output(
                DocumentExportTools.ensure_allowed_binaries(cmd),
                cwd=tmp_dir_path
            ).decode('utf-8')
            cmd = 'pdftotext {} -layout -f 2 -'.format(archive_path)
            other_pages_content = subprocess.check_output(
                DocumentExportTools.ensure_allowed_binaries(cmd),
                cwd=tmp_dir_path
            ).decode('utf-8')
            return title_page_content, other_pages_content
        except BaseException as e:
            LOG.exception('Failed to convert pdf to text: %s', the_file)
            print(e)
            return None, None

    def _get_word_document_content(self, the_file):
        tmp_dir_path, _ = self._extract_zip_container(the_file)
        if tmp_dir_path is not None:
            document_xml_path = os.path.join(tmp_dir_path, 'word', 'document.xml')
            if os.path.isfile(document_xml_path):
                with open(document_xml_path) as f:
                    return f.read()

    def _get_xhtml_content(self, the_file):
        tmp_dir_path, _ = self._extract_zip_container(the_file)
        if tmp_dir_path is not None:
            xhtml_path = os.path.join(tmp_dir_path, '{}.xhtml'.format(self.spec.spec_id))
            if os.path.isfile(xhtml_path):
                with open(xhtml_path) as f:
                    return f.read()

    def _create_export_profile(self, name, steps, fqpyname=None, obsolete=0, **kwargs):
        if fqpyname is None:
            fqpyname = "cs.requirements.document_export.generic_export"
        settings = kwargs.copy()
        settings['steps'] = steps
        profile = operation(
            "CDB_Create", DocumentExportProfile,
            name_en=name,
            name_de=name,
            fqpyname=fqpyname,
            obsolete=obsolete,
            cdbrqm_doc_export_profile_cfg=u"%s" % json.dumps(settings)
        )
        return profile

    def test_not_allowed_or_not_existing_step_call_preserves_folder_content(self):
        # at least two cases
        # 1st - binary is not there/configured to be executed
        profile = self._create_export_profile(
            'non_existing_binary',
            ["this_one_does_not_exist"]
        )
        with self.assertRaises(ElementsError):
            operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=profile.cdb_object_id,
                    languages='de'
                )
            )
        self.persist_export_run('not_allowed_or_not_existing_step_call_preserves_folder_content')
        self.spec.Reload()
        process_run = self.spec.ExportRuns.KeywordQuery(
            export_type="Document Export ({})".format(profile.GetDescription()),
            export_status=RQMExportProcessRun.FAILED
        ).Execute()
        self.assertEqual(len(process_run), 1)
        self.assertEqual(len(process_run[0].Files), 1)

    def test_failing_step_call_preserves_folder_content(self):
        # 2nd - binary can be called, fails but have written a log file
        config_file = os.path.join(
            CADDOK.BASE, 'etc', 'requirements_doc_export_allowed_binaries.json'
        )
        platform_python_path = os.path.join(
            rte.environ.get('CADDOK_RUNTIME'),
            'python.exe' if sys.platform == 'win32' else 'python'
        )
        changed_content = json.dumps(dict(
            python=platform_python_path.replace('\\', '\\\\'), ensure_ascii=False
        ))
        with ChangedFile(config_file, changed_content):
            content_to_check = "some dummy text to write to a file"
            profile2 = self._create_export_profile(
                'existing_binaries_but_failing',
                [  # the good thing - steps can have commands with explicit arguments
                    ['python', '-c', 'f=open("test.log", "w+");f.write("%s");f.close()' % content_to_check],
                    ['python', '-c', 'does_not_exist']
                ]
            )
            with self.assertRaises(ElementsError):
                operations.operation(
                    "cdbrqm_document_export",
                    self.spec,
                    form_input(
                        self.spec,
                        profile=profile2.cdb_object_id,
                        languages='de'
                    )
                )
            self.persist_export_run("failing_step_call_preserves_folder_content")
            self.spec.Reload()
            process_run = self.spec.ExportRuns.KeywordQuery(
                export_type="Document Export ({})".format(profile2.GetDescription()),
                export_status=RQMExportProcessRun.FAILED
            ).Execute()
            self.assertEqual(len(process_run), 1)
            self.assertEqual(len(process_run[0].Files), 1)
            tmp_dir_path, contents = self._extract_zip_container(process_run[0].Files[0])
            self.assertIn('test.log', contents)
            file_path = os.path.join(tmp_dir_path, 'test.log')
            self.assertTrue(os.path.isfile(file_path))
            with open(file_path) as f:
                content = f.read()
                self.assertEqual(content, content_to_check)

    def test_pdf_example_export_profile(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        pdf_profile = DocumentExportProfile.KeywordQuery(name_en='PDF')[0]
        result = None
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=pdf_profile.cdb_object_id,
                    languages='de'
                )
            )
        except ElementsError:
            LOG.exception('test_pdf_example_export_profile failed')
        finally:
            self.persist_export_run("pdf_example_export_profile")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        title_page_content, other_pages_content = self._convert_pdf_to_text(result)
        self.assertNotEqual(title_page_content, None)
        self.assertNotEqual(other_pages_content, None)
        # TODO: we should test also for some title page fields (status, initial version etc.)
        self.assertIn(self.spec.GetDescription(), title_page_content)
        self.assertIn(self.requirement_not_included.name_de, title_page_content + other_pages_content)
        self.assertNotIn(util.get_label('cdbrqm_partial_hint'), title_page_content + other_pages_content)

    def test_pdf_example_export_profile_with_variables_and_values(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        pdf_profile = DocumentExportProfile.KeywordQuery(name_en='PDF')[0]
        result = None
        variable_id = 'RQM_RATING_RQM_COMMENT_EXTERN'
        req = self.spec.Requirements[1]
        req.SetText("cdbrqm_spec_object_desc_de", """<xhtml:div>{}</xhtml:div>""".format(
            RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        ))
        classification_data = classification_api.get_new_classification(
            ["RQM_RATING"], narrowed=False
        )
        variable_value = '### test comment ###'
        classification_data['properties']['RQM_RATING_RQM_COMMENT_EXTERN'][0]['value'] = variable_value
        classification_api.update_classification(req, classification_data)
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=pdf_profile.cdb_object_id,
                    languages='de'
                )
            )
        except ElementsError:
            LOG.exception('test_pdf_example_export_profile failed')
        finally:
            self.persist_export_run("pdf_example_export_profile_with_variables_and_values")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        title_page_content, other_pages_content = self._convert_pdf_to_text(result)
        self.assertNotEqual(title_page_content, None)
        self.assertNotEqual(other_pages_content, None)
        # TODO: we should test also for some title page fields (status, initial version etc.)
        fullcontent = title_page_content + other_pages_content
        self.assertIn(self.spec.GetDescription(), title_page_content)
        self.assertIn(self.requirement_not_included.name_de, fullcontent)
        self.assertNotIn(util.get_label('cdbrqm_partial_hint'), fullcontent)
        self.assertNotIn(variable_id, fullcontent)
        if variable_value not in other_pages_content:
            self.persist_export_run("pdf_example_export_profile_with_variables_and_values")
        self.assertIn(variable_value, other_pages_content)

    def test_pdf_example_export_profile_with_variables_without_values(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        variable_id = 'RQM_TEST_VARIABLE_001'
        req = self.spec.Requirements[0]
        req.SetText("cdbrqm_spec_object_desc_de", """<xhtml:div>{}</xhtml:div>""".format(
            RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        ))
        pdf_profile = DocumentExportProfile.KeywordQuery(name_en='PDF')[0]
        with self.assertRaises(ElementsError):
            operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=pdf_profile.cdb_object_id,
                    languages='de'
                )
            )

    def test_pdf_example_export_profile_only_selected_reqs(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        self._skip_before_specific_platform_version(sl=18)
        pdf_profile = DocumentExportProfile.KeywordQuery(name_en='PDF')[0]
        result = None
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.requirements_selected,
                form_input(
                    self.spec,
                    profile=pdf_profile.cdb_object_id,
                    languages='de'
                )
            )
        except ElementsError:
            LOG.exception('test_pdf_example_export_profile failed')
        finally:
            self.persist_export_run("pdf_example_export_profile_only_selected_reqs")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        title_page_content, other_pages_content = self._convert_pdf_to_text(result)
        self.assertNotEqual(title_page_content, None)
        self.assertNotEqual(other_pages_content, None)
        # TODO: we should test also for some title page fields (status, initial version etc.)
        self.assertIn(self.spec.GetDescription(), title_page_content)
        self.assertNotIn(self.requirement_not_included.name_de, title_page_content)
        self.assertNotIn(self.requirement_not_included.name_de, other_pages_content)
        self.assertIn(util.get_label('cdbrqm_partial_hint'), title_page_content + other_pages_content)

    def test_word_example_export_profile(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        word_profile = DocumentExportProfile.KeywordQuery(name_en='Word')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=word_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("word_example_export_profile")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertNotEqual(tmp_dir_path, None, 'failed to extract result archive - invalid result?')
        self.assertTrue(len([x for x in contents if x.endswith('.png')]) > 0)

    def test_word_example_export_profile_with_variables_and_values(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        word_profile = DocumentExportProfile.KeywordQuery(name_en='Word')[0]
        variable_id = 'RQM_RATING_RQM_COMMENT_EXTERN'
        req = self.spec.Requirements[1]
        req.SetText("cdbrqm_spec_object_desc_de", """<xhtml:div>{}</xhtml:div>""".format(
            RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        ))
        classification_data = classification_api.get_new_classification(
            ["RQM_RATING"], narrowed=False
        )
        variable_value = '### test comment ###'
        classification_data['properties']['RQM_RATING_RQM_COMMENT_EXTERN'][0]['value'] = variable_value
        classification_api.update_classification(req, classification_data)
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=word_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("word_example_export_profile")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        text_content = self._get_word_document_content(result)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertNotEqual(tmp_dir_path, None, 'failed to extract result archive - invalid result?')
        self.assertTrue(len([x for x in contents if x.endswith('.png')]) > 0)
        self.assertNotIn(variable_id, text_content)
        self.assertIn(variable_value, text_content)

    def test_word_example_export_profile_with_variables_without_values(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        variable_id = 'RQM_TEST_VARIABLE_001'
        req = self.spec.Requirements[0]
        req.SetText("cdbrqm_spec_object_desc_de", """<xhtml:div>{}</xhtml:div>""".format(
            RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        ))
        word_profile = DocumentExportProfile.KeywordQuery(name_en='Word')[0]
        with self.assertRaises(ElementsError):
            operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=word_profile.cdb_object_id,
                    languages='de'
                )
            )

    def test_word_export_using_list_step_profile(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        word_profile = DocumentExportProfile.KeywordQuery(name_en='Word')[0]
        word_profile_with_list_step = operation("CDB_Copy", word_profile)
        word_profile_with_list_step.SetText('cdbrqm_doc_export_profile_cfg', json.dumps(
            obj=dict(
                steps=[
                    "templateRendering",
                    "xslTransformation",
                    [
                        "pandoc",
                        "-r",
                        "html",
                        "-w",
                        "docx",
                        "--toc",
                        "--standalone",
                        "--reference-doc={templates_folder}/template.docx",
                        "{prev_result_filepath}",
                        "-o",
                        "{prev_result_filepath}.docx"
                    ]
                ],
                export_filename="{spec_id}.xhtml.docx",
                xslt_template_filename="convert_objects_to_images_word.xsl"
            )
        ))
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=word_profile_with_list_step.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("word_export_using_list_step_profile")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertNotEqual(tmp_dir_path, None, 'failed to extract result archive - invalid result?')
        self.assertTrue(len([x for x in contents if x.endswith('.png')]) > 0)

    def test_word_example_export_profile_only_selected_reqs(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        self._skip_before_specific_platform_version(sl=18)
        word_profile = DocumentExportProfile.KeywordQuery(name_en='Word')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.requirements_selected,
                form_input(
                    self.requirements_selected,
                    profile=word_profile.cdb_object_id,
                    languages='de'
                ),
            )
        finally:
            self.persist_export_run("word_example_export_profile_only_selected_reqs")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        content = self._get_word_document_content(result)
        self.assertNotEqual(content, None)
        # TODO: we should test also for some title page fields (status, initial version etc.)
        plain_content = rqm_utils.strip_tags(content)
        self.assertIn(self.spec.GetDescription(), plain_content)
        self.assertNotIn(self.requirement_not_included.name_de, plain_content)

    def test_xhtml_example_export_profile(self):
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("xhtml_example_export_profile")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertNotEqual(tmp_dir_path, None, 'failed to extract result archive - invalid result?')
        self.assertTrue(len([x for x in contents if x.endswith('.png')]) > 0)

    def test_xhtml_example_export_profile_with_file_attached_to_spec(self):
        CDB_File.NewFromFile(
            for_object_id=self.spec.cdb_object_id,
            from_path='',
            primary=False,
            additional_args={
                "cdb_file.cdbf_name": "hello.txt"
            },
            stream=self._get_content("""Hello World!""")
        )
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("xhtml_example_export_profile")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertNotEqual(tmp_dir_path, None, 'failed to extract result archive - invalid result?')
        self.assertTrue(len([x for x in contents if x.endswith('.png')]) > 0)
        self.assertTrue(len([x for x in contents if x.endswith('.txt')]) > 0)

    def test_xhtml_example_export_profile_with_variables_and_values(self):
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        variable_id = 'RQM_RATING_RQM_COMMENT_EXTERN'
        req = self.spec.Requirements[1]
        req.SetText("cdbrqm_spec_object_desc_de", """<xhtml:div>{}</xhtml:div>""".format(
            RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        ))
        classification_data = classification_api.get_new_classification(
            ["RQM_RATING"], narrowed=False
        )
        variable_value = '### test comment ###'
        classification_data['properties']['RQM_RATING_RQM_COMMENT_EXTERN'][0]['value'] = variable_value
        classification_api.update_classification(req, classification_data)
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("xhtml_example_export_profile")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertNotEqual(tmp_dir_path, None, 'failed to extract result archive - invalid result?')
        self.assertTrue(len([x for x in contents if x.endswith('.png')]) > 0)
        content = self._get_xhtml_content(result)
        self.assertIn(variable_id, content)
        self.assertIn(variable_value, content)

    def test_xhtml_example_export_profile_with_variables_without_values(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        variable_id = 'RQM_TEST_VARIABLE_001'
        req = self.spec.Requirements[0]
        req.SetText("cdbrqm_spec_object_desc_de", """<xhtml:div>{}</xhtml:div>""".format(
            RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        ))
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        with self.assertRaises(ElementsError):
            operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                )
            )

    def test_xhtml_example_export_profile_only_selected_reqs(self):
        self._skip_before_specific_platform_version(sl=18)
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.requirements_selected,
                form_input(
                    self.requirements_selected,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                ),
            )
        finally:
            self.persist_export_run("xhtml_example_export_profile_only_selected_reqs")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        content = self._get_xhtml_content(result)
        self.assertNotEqual(content, None)
        # TODO: we should test also for some title page fields (status, initial version etc.)
        plain_content = rqm_utils.strip_tags(content)
        self.assertIn(self.spec.GetDescription(), plain_content)
        self.assertNotIn(self.requirement_not_included.name_de, plain_content)

    def test_obsolete_profiles_cannot_be_used(self):
        obsolete_profile = self._create_export_profile(
            'obsolete_profile',
            ["inkscape --version"],
            obsolete=1
        )
        with self.assertRaises(ElementsError):
            operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=obsolete_profile.cdb_object_id,
                    languages='de'
                )
            )

    def test_customizability_of_generic_export(self):
        template_name = 'template.json'
        profile = self._create_export_profile(
            name='customized_generic_export',
            steps=[
                "templateRendering",
                "sum_weights"
            ],
            export_filename='calculation_result.txt',
            fqpyname='cs.requirements.tests.test_document_export.customized_generic_export',
            template_filename=template_name
        )
        CDB_File.NewFromFile(
            for_object_id=profile.cdb_object_id,
            from_path='',
            primary=False,
            additional_args={
                "cdb_file.cdbf_name": template_name
            },
            stream=self._get_content("""
                {
                    "weights": [
                        {% for node in tree %}
                            {{node[1].weight}}
                            {% if not loop.last %}
                            ,
                            {% endif %}
                        {% endfor %}
                    ],
                    "multiplier": {{multiplier}}
                }
            """)
        )
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run('customizability_of_generic_export')
        self.assertIsInstance(result, CDB_File)
        self.spec.Reload()
        process_run = self.spec.ExportRuns.KeywordQuery(
            export_type="Document Export ({})".format(profile.GetDescription()),
            export_status=RQMExportProcessRun.FINISHED
        ).Execute()
        self.assertEqual(len(process_run), 1)
        process_run = process_run[0]
        self.assertEqual(len(process_run.Files), 2)
        # result file content check
        content = result.get_content()
        multiplier = 42
        expected_weight_sum = '%d' % (
            multiplier * sum(self.spec.Requirements.weight + self.spec.TargetValues.weight)
        )
        self.assertEqual(content.decode(), expected_weight_sum)

        # no metadata should be written
        zip_archive = [x for x in process_run.Files if x.cdbf_name.endswith('.zip')][0]
        _, name_list = self._extract_zip_container(zip_archive)
        self.assertEqual(len([x for x in name_list if 'metadata.json' in x]), 0)

    def test_customizability_with_additional_preprocessor_of_generic_export(self):
        template_name = 'template.md'
        profile = self._create_export_profile(
            name='rudimentary_markdown',
            steps=[
                "templateRendering",
            ],
            export_filename='export.txt',
            template_output_filename='export.txt',
            fqpyname='cs.requirements.tests.test_document_export.plaintext_generic_export',
            template_filename=template_name
        )
        CDB_File.NewFromFile(
            for_object_id=profile.cdb_object_id,
            from_path='',
            primary=False,
            additional_args={
                "cdb_file.cdbf_name": template_name
            },
            stream=self._get_content("""
{% for node in tree %}
{% if node[1].is_chapter %}
{{ '#' * node[0] }} {{node[1].name_de}}
{% else %}
{{node[1].de}}
{% endif %}
{% endfor %}
            """)
        )
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                self.spec,
                form_input(
                    self.spec,
                    profile=profile.cdb_object_id,
                    languages='de'
                )
            )
        except ElementsError:
            LOG.exception('customizability_with_additional_preprocessor_of_generic_export failed')
        finally:
            self.persist_export_run('customizability_with_additional_preprocessor_of_generic_export')
        self.assertIsInstance(result, CDB_File)
        self.spec.Reload()
        process_run = self.spec.ExportRuns.KeywordQuery(
            export_type="Document Export ({})".format(profile.GetDescription()),
            export_status=RQMExportProcessRun.FINISHED
        ).Execute()
        self.assertEqual(len(process_run), 1)
        process_run = process_run[0]
        self.assertEqual(len(process_run.Files), 2)
        # result file content check
        content = result.get_content()
        self.assertNotEqual(content, '')
        self.assertIn('# test1', content.decode())
        # no metadata should be written
        zip_archive = [x for x in process_run.Files if x.cdbf_name.endswith('.zip')][0]
        _, name_list = self._extract_zip_container(zip_archive)
        self.assertEqual(len([x for x in name_list if 'metadata.json' in x]), 0)

    def test_duplicate_filenames_between_requirements(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        new_spec_args = {
            u"name": u'Test duplicate filenames spec',
            u"is_template": 0,
            u"category": u'System Specification'
        }
        spec = operations.operation(
            "CDB_Create",
            RQMSpecification,
            **new_spec_args
        )

        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'identical_filenames.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        expected_path_pic1 = '/'.join((spec.Requirements[0].reqif_id, 'test.png'))
        expected_path_pic2 = '/'.join((spec.Requirements[1].reqif_id, 'test.png'))
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                spec,
                form_input(
                    spec,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("duplicate_filenames_between_requirements")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertIn(expected_path_pic1, contents)
        self.assertIn(expected_path_pic2, contents)
        if tmp_dir_path is not None:
            xhtml_path = os.path.join(tmp_dir_path, '{}.xhtml'.format(spec.spec_id))
            if os.path.isfile(xhtml_path):
                with open(xhtml_path) as f:
                    content = f.read()
        self.assertIn('<object data="' + expected_path_pic1, content)
        self.assertIn('<object data="' + expected_path_pic2, content)

        word_profile = DocumentExportProfile.KeywordQuery(name_en='Word')[0]
        result = operations.operation(
            "cdbrqm_document_export",
            spec,
            form_input(
                spec,
                profile=word_profile.cdb_object_id,
                languages='de'
            )
        )
        content = self._get_word_document_content(result)
        self.assertIn('<pic:cNvPr descr="' + '/'.join((spec.Requirements[0].reqif_id, 'test.png')), content)
        self.assertIn('<pic:cNvPr descr="' + '/'.join((spec.Requirements[1].reqif_id, 'test.png')), content)

    def test_invalid_xml_characters_in_specification_title(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        new_spec_args = {
            u"name": u'malformed & <title>',
            u"is_template": 0,
            u"category": u'System Specification'
        }
        spec = operations.operation(
            "CDB_Create",
            RQMSpecification,
            **new_spec_args
        )
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                spec,
                form_input(
                    spec,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("duplicate_filenames_between_requirements")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        if tmp_dir_path is not None:
            xhtml_path = os.path.join(tmp_dir_path, '{}.xhtml'.format(spec.spec_id))
            if os.path.isfile(xhtml_path):
                with open(xhtml_path) as f:
                    content = f.read()
        self.assertNotIn('malformed & <title>', content)
        self.assertIn("malformed &amp; &lt;title&gt;", content)

    def test_special_chars_in_filenames(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        new_spec_args = {
            u"name": u'Test special chars in filenames spec',
            u"is_template": 0,
            u"category": u'System Specification'
        }
        spec = operations.operation(
            "CDB_Create",
            RQMSpecification,
            **new_spec_args
        )
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'special_chars_filenames.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        expected_path_pic1 = '/'.join((spec.Requirements[0].reqif_id, u'äöü.png'))
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                spec,
                form_input(
                    spec,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("test_special_chars_in_filenames")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertIn(expected_path_pic1, contents)


    def test_xml_chars_in_filenames(self):
        if sys.platform == 'win32' and 'RQM_FORCE_doc_export_tests' not in rte.environ:
            self.skipTest('we do not have inkscape, pandoc and xelatex under windows currently')
        new_spec_args = {
            u"name": u'Test xml chars in filenames spec',
            u"is_template": 0,
            u"category": u'System Specification'
        }
        spec = operations.operation(
            "CDB_Create",
            RQMSpecification,
            **new_spec_args
        )

        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'test_xml_chars_in_filenames.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        expected_xhtml_ref = '/'.join((spec.Requirements[0].reqif_id, u"&amp;.png"))
        self.assertIn('<xhtml:object data="' + expected_xhtml_ref, spec.Requirements[0].GetText('cdbrqm_spec_object_desc_de'))
        expected_path_pic1 = '/'.join((spec.Requirements[0].reqif_id, u"&.png"))
        xhtml_profile = DocumentExportProfile.KeywordQuery(name_en='XHTML')[0]
        try:
            result = operations.operation(
                "cdbrqm_document_export",
                spec,
                form_input(
                    spec,
                    profile=xhtml_profile.cdb_object_id,
                    languages='de'
                )
            )
        finally:
            self.persist_export_run("test_special_chars_in_filenames")
        self.assertIsInstance(result, CDB_File)
        self.assertGreater(result.cdbf_fsize, 0)
        tmp_dir_path, contents = self._extract_zip_container(result)
        self.assertIn(expected_path_pic1, contents)


def plaintext_generic_export(
        **kwargs
):
    from webob.exc import strip_tags
    from cs.requirements.document_export import generic_export, template_rendering_step

    def plaintext_preprocessor(obj, prev_preprocessor_result):
        # preprocessor which strips xhtml tags from requirement description
        if prev_preprocessor_result:
            result_update = {
                k: strip_tags(v) for (k, v) in prev_preprocessor_result.items() if k in ['de', 'en']
            }
            return result_update
        else:
            return {}

    def customized_template_rendering_step(**kwargs):
        return template_rendering_step(
            preprocessor=plaintext_preprocessor,
            override_preprocessor=False,  # only add another preprocessor after the default one
            update_metadata=False,  # we do not need external metadata file
            **kwargs
        )

    steps_mapping = {
        'templateRendering': customized_template_rendering_step  # overwrite a standard special step
    }
    return generic_export(
        steps_mapping=steps_mapping,
        **kwargs
    )


def customized_generic_export(
        **kwargs
):
    from cs.requirements.document_export import generic_export, template_rendering_step

    def preprocessor(obj, prev_preprocessor_result=None):
        return {'weight': obj.weight}

    def customized_template_rendering_step(**kwargs):
        # Use custom render data which should be globally available for the use within templates
        # Use a different preprocessor to get different data per object within tree node generator within templates
        return template_rendering_step(
            custom_render_data={
                'multiplier': 42
            },
            preprocessor=preprocessor,
            override_preprocessor=True,  # replace default preprocessor as we do not need it's values
            update_metadata=False,  # we do not external metadata file
            **kwargs
        )

    def sum_weights(tmp_dir_path, prev_result_filename, **kwargs):
        prev_result_filepath = jail_filename(tmp_dir_path, prev_result_filename)
        with open(prev_result_filepath) as f:
            obj = json.load(f)
            weights = obj.get('weights')
            multiplier = obj.get('multiplier')
            result = sum(weights) * multiplier
        result_filename = jail_filename(tmp_dir_path, 'calculation_result.txt')
        with open(result_filename, 'w+') as f:
            f.write("{}".format(result))
        return result_filename

    steps_mapping = {
        'sum_weights': sum_weights,  # add a custom special step
        'templateRendering': customized_template_rendering_step  # overwrite a standard special step
    }
    return generic_export(
        steps_mapping=steps_mapping,
        **kwargs
    )


