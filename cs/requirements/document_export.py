# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import codecs
import collections
import datetime
import json
import logging
import os
import sys
import tempfile
import zipfile

from jinja2.exceptions import TemplateError
from jinja2.loaders import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment
from jinja2.utils import select_autoescape
from lxml import etree

from _cdbwrapc import getFileTypeByFilename
from cdb import CADDOK, constants, i18n, objects, plattools, sig, ue, util
from cdb.lru_cache import lru_cache
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation
from cdb.wsgi.util import jail_filename
from cs.documents import Document, DocumentCategory
from cs.platform.web.uisupport import get_webui_link
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.classes import (DocumentExportProfile,
                                     RQMExportProcessRun, RQMProtocol,
                                     RQMProtocolLogging,
                                     RQMSpecObjectDocumentReference)
from cs.requirements.exceptions import (DocumentExportError,
                                        DocumentExportTemplateError,
                                        FileNameCollision,
                                        MissingVariableValueError)
from cs.requirements.rqm_utils import RQMHierarchicals, statement_count
from cs.requirements.richtext import RichTextModifications

try:
    from exceptions import WindowsError
    subprocess_error = WindowsError
except ImportError:
    subprocess_error = OSError

LOG = logging.getLogger(__name__)


class ConvertSVGExtension(object):
    """ converts the content of an svg embedded into an html5 object tag into a png/pdf
        and returns the path to this pdf using inkscape which must be in path
        can be used like this in XSL Stylesheets:

        <img>
            <xsl:attribute name="src">
                <xsl:value-of select="con_rqm:convert_svg_to_pdf(@data)" />
            </xsl:attribute>
        </img>
        <img>
            <xsl:attribute name="src">
                <xsl:value-of select="con_rqm:convert_svg_to_png(@data)" />
            </xsl:attribute>
        </img>
    """

    def __init__(self, working_directory):
        self.ensure_inkscape()
        self.working_directory = working_directory

    def ensure_inkscape(self):
        try:
            plattools.killableprocess.check_output(
                DocumentExportTools.ensure_allowed_binaries('inkscape --version')
            )
        except subprocess_error:
            raise ValueError(
                'inkscape is not allowed in requirements_doc_export_allowed_binaries.json or has an invalid path'
            )

    def convert_svg_to_pdf(self, context, args, extension=None):
        return self.convert_svg_to_x(context, args, extension='pdf')

    def convert_svg_to_png(self, context, args, extension=None):
        return self.convert_svg_to_x(context, args, extension='png')

    def convert_svg_to_x(self, context, args, extension=None):
        src = jail_filename(self.working_directory, args[0])
        dst = "{src}.{extension}".format(extension=extension, src=src)
        plattools.killableprocess.call(
            DocumentExportTools.ensure_allowed_binaries(
                'inkscape --export-filename={dst} {src}'.format(
                    src=src,
                    dst=dst
                )
            ),
            cwd=self.working_directory,
            timeout=30
        )
        if not os.path.isfile(dst):
            raise Exception('Failed to convert %s to %s' % (src, dst))
        return os.path.basename(dst)


class XSLTransformer(object):

    @classmethod
    def transform(cls, xsl_path, xml_path, working_directory=None, with_rqm_extension=True):
        if working_directory is None:
            working_directory = '.'
        if with_rqm_extension:
            convert_svg_to_x = ConvertSVGExtension(working_directory=working_directory)
            extensions = {
                ('con_rqm', 'convert_svg_to_pdf'): convert_svg_to_x.convert_svg_to_pdf,
                ('con_rqm', 'convert_svg_to_png'): convert_svg_to_x.convert_svg_to_png
            }
        else:
            extensions = {}
        xsl_root = etree.parse(xsl_path)
        transform_func = etree.XSLT(
            xsl_root,
            extensions=extensions,
            # never remove the access_control, this is for security reasons
            # as otherwise a stylesheet can access the network or filesystem
            # see tests for more details
            access_control=etree.XSLTAccessControl.DENY_ALL
        )
        xml_root = etree.parse(xml_path)
        return transform_func(xml_root)


@lru_cache(clear_after_ue=True)
def get_allowed_binaries():
    config_file = os.path.join(CADDOK.BASE, 'etc', 'requirements_doc_export_allowed_binaries.json')
    if not os.path.isfile(config_file) and sys.platform != 'win32':
        config_file = '/etc/contact/requirements_doc_export_allowed_binaries.json'
    allowed_binaries = {}
    try:
        with open(config_file) as f:
            allowed_binaries = json.load(f)
    except (ValueError, TypeError, IOError):
        LOG.error('No allowed binaries can be read from %s', config_file)
    return allowed_binaries


class DocumentExportTools(object):

    @classmethod
    def ensure_allowed_binaries(cls, cmd):
        args = []
        allowed_binaries = get_allowed_binaries()
        if isinstance(cmd, str) and ' ' in cmd:
            args = cmd.split(' ')
            executable = args[0]
            args = args[1:]
        elif isinstance(cmd, list) and len(cmd) == 0:
            raise ValueError('invalid command %s' % cmd)
        elif isinstance(cmd, list) and len(cmd) > 0:
            executable = cmd[0]
            args = cmd[1:]
        else:
            executable = cmd
        if executable in allowed_binaries:
            executable = allowed_binaries[executable]
            if not os.path.isabs(executable) or not os.path.isfile(executable):
                LOG.error('%s is missing in requirements_doc_export_allowed_binaries.json', executable)
                raise ValueError('%s is not a valid path to an executable.' % executable)
        else:
            LOG.error('%s is missing in requirements_doc_export_allowed_binaries.json', executable)
            raise ValueError('%s is not allowed to be executed.' % executable)
        return [executable] + [arg for arg in args]

    @classmethod
    def cleanup_folder(cls, folder_path):
        from shutil import rmtree
        try:
            rmtree(folder_path)
        except IOError as e:
            LOG.exception(e)

    @classmethod
    def save_result_file(cls, export_run, tmp_dir_path, result_file_name):
        """
        Helper method which attaches the result file through the export run

        :param RQMExportProcessRun export_run: The export process run where the result file should be attached to
        :param str tmp_dir_path: The filepath of the temporary directory where the result file is in
        :param str result_file_name: The filename of the result file within the temporary directory
        """
        # force file_name to be only a file name not a path
        result_file_name = os.path.basename(result_file_name)
        result_file_path = jail_filename(tmp_dir_path, result_file_name)
        if not os.path.isfile(result_file_path):
            raise ValueError('Result file %s does not exist.' % result_file_name)
        ftype = getFileTypeByFilename(result_file_name)
        result_file = CDB_File.NewFromFile(
            export_run.cdb_object_id,
            result_file_path,
            primary=True,
            additional_args=dict(
                cdbf_name=result_file_name,
                cdbf_type=ftype.getName()
            )
        )
        return result_file

    @classmethod
    def save_folder_content_as_zip(cls, export_run, tmp_dir_path, archive_name):
        """
        Helper method which attaches the contents of the folder as an ZIP archive
        to the export run

        :param RQMExportProcessRun export_run: The export process run where the ZIP archive should be attached to
        :param str tmp_dir_path: The filepath of the temporary directory which contents should be attached as ZIP
        :param str archive_name: The filename of the ZIP archive when attaching it to the export run
        """
        # force archive name to be only a archive name not a path
        archive_name = os.path.basename(archive_name)
        archive_file_path = jail_filename(tmp_dir_path, archive_name)
        with zipfile.ZipFile(archive_file_path, mode='w', allowZip64=True) as zf:
            for root, _, files in os.walk(tmp_dir_path):
                for f in files:
                    full_path = jail_filename(root, f)
                    if full_path != archive_file_path:
                        zf.write(full_path, os.path.relpath(full_path, tmp_dir_path))
        ftype = getFileTypeByFilename(archive_name)
        result_file = CDB_File.NewFromFile(
            export_run.cdb_object_id,
            archive_file_path,
            primary=True,
            additional_args=dict(
                cdbf_name=archive_name,
                cdbf_type=ftype.getName()
            )
        )
        return result_file

    @classmethod
    def update_metadata(cls, profile, templates_folder, specification, global_data):
        date = datetime.datetime.now()
        fmt = i18n.get_date_format()
        fmt = fmt.replace("DD", "%d").replace("MM", "%m").replace("YYYY", "%Y")
        date = date.strftime(fmt)
        # update meta information in metadata.json
        metadata_file_path = jail_filename(templates_folder, 'metadata.json')
        metadata = {
            "__attribute_mapping__": {},
        }
        metadata.update(global_data)
        if os.path.isfile(metadata_file_path):
            with open(metadata_file_path) as f:
                metadata = json.load(f)
        for k in ['headerlogo', 'titlelogo']:
            if k in metadata:
                metadata[k] = "/".join(['.', os.path.basename(templates_folder), metadata[k]])

        for k, v in metadata.get('__attribute_mapping__', {}).items():
            if v == '$date':
                metadata[k] = date
            elif v == '$objDescription':
                metadata[k] = specification.GetDescription()
            else:
                value = getattr(specification, v) if hasattr(specification, v) else None
                if isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
                    value = value.strftime(fmt)
                metadata[k] = value
        with open(metadata_file_path, 'w+') as f:
            json.dump(obj=metadata, fp=f, ensure_ascii=False)

    @classmethod
    def get_preprocessor(cls, tree_down_context, languages, custom_preprocessor=None):
        spec_object_ids = list(tree_down_context.get('spec_object_cache'))
        spec_obj_ids_with_tvs = set(tree_down_context.get('target_value_cache').keys())
        referencedDocumentCache = collections.defaultdict(list)
        documentIds = set()
        for doc_ref in RQMSpecObjectDocumentReference.KeywordQuery(
            specobject_object_id=spec_object_ids
        ):
            referencedDocumentCache[doc_ref.specobject_object_id].append(doc_ref.document_object_id)
            documentIds.add(doc_ref.document_object_id)

        DocumentDescCache = {
            x.cdb_object_id: x.GetDescription() for x in
            Document.KeywordQuery(cdb_object_id=list(documentIds)).Execute()
        }
        referencedDocumentDescriptionCache = {
            k: [DocumentDescCache.get(d) for d in v] for (k, v) in referencedDocumentCache.items()
        }

        variable_values_by_id = RichTextModifications.get_variable_values_by_id(
            spec_object_ids, tree_down_context.get('root').cdb_object_id
        )
        
        type_map = {
            RQMSpecObject.__maps_to__: 'spec_object',
            TargetValue.__maps_to__: 'target_value'
        }

        def preprocessor(obj, prev_preprocessor_result=None):
            longtexts = tree_down_context.get('long_text_cache').get(obj.__maps_to__)
            referenced_documents = referencedDocumentDescriptionCache.get(obj.cdb_object_id, [])
            result = {
                'type': type_map.get(obj.__maps_to__, ''),
                'is_chapter': obj.mapped_category_en == 'Chapter' if hasattr(obj, 'mapped_category_en') else False,
                'has_target_values': obj.cdb_object_id in spec_obj_ids_with_tvs,
                'chapter_number': obj.chapter if hasattr(obj, 'chapter') else '',
                'documents': referenced_documents,
                'has_documents': len(referenced_documents) > 0,
                'target_value': obj.target_value if isinstance(obj, TargetValue) else None,
                'target_value_unit': obj.mapped_unit if isinstance(obj, TargetValue) else None
            }
            attr_values = {}
            for language in languages:
                description_attr_name = obj.__description_attrname_format__.format(
                    iso=language
                )
                description = (
                    longtexts
                    .get(description_attr_name, {})
                    .get(obj.cdb_object_id, '')
                )
                result[language] = (
                    description
                    .replace('<xhtml:', '<').replace('</xhtml:', '</')
                )
                attr_values[description_attr_name] = description
                try:
                    short_title_attr_name = obj.__short_description_attrname_format__.format(
                        iso=language
                    )
                    short_title = getattr(obj, short_title_attr_name)
                    if short_title is None:
                        short_title = ''
                    result['name_{}'.format(language)] = short_title
                except AttributeError:
                    LOG.error("%s does not have %s", obj, short_title_attr_name)

            try:
                modifications = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
                    objs=obj,
                    attribute_values=attr_values,
                    from_db=True,
                    raise_for_empty_value=True,
                    variable_values_by_id=variable_values_by_id,
                    file_link_rest_replacement=False
                )

                for key in modifications:
                    lang_key = key.replace(obj.__description_attrname_format__.format(iso=''), '')
                    result[lang_key] = modifications[key]
                    result[lang_key] = result[lang_key].replace('<xhtml:', '<').replace('</xhtml:', '</')
            except MissingVariableValueError as e:
                raise ue.Exception(
                    "just_a_replacement", 
                    "Missing variable value for %s on object %s" % (
                        e.variable_id, obj.GetDescription()
                    )
                )

            if custom_preprocessor is not None:
                result.update(custom_preprocessor(obj, prev_preprocessor_result=result))
            return result

        return preprocessor

    @classmethod
    def transform_variables(cls, richtext):
        if not richtext:
            return richtext
        return RichTextModifications.replace_filled_variables_with_text_nodes(
            xhtml_text=richtext, ns_prefix=''
        )

    @classmethod
    def inject_chapter_number(cls, chapter_number, richtext, pretty_print=False):
        # TODO: chapter_number regex check (only numbers and characters a-z but no other contents?
        # find out whether lxml elem.text or elem.attribut = allow/prohibits adding some tags there
        if not richtext:
            return richtext
        # TODO: think about whether we need/can sanitize richtext as this must be threatened as user input
        root = etree.fromstring(richtext)
        chapter_number_elem = etree.Element('span')
        chapter_number_elem.attrib['data-ce-chapter-number'] = chapter_number
        chapter_number_elem.text = "{} ".format(chapter_number)
        text_elems = root.xpath('//*[string-length(normalize-space(text())) > 0]')  # first text
        add_as_first_child = False
        if len(text_elems) == 0:
            add_as_first_child = True
        else:
            text_elems = [x for x in text_elems if x.text]  # only nodes which have text at the start
            if len(text_elems) == 0:
                add_as_first_child = True
            else:
                # if we have text use the first text elem and insert chapter number
                # text into it in front of the other text
                first_text_elem = text_elems[0]
                chapter_number_elem.tail = first_text_elem.text
                first_text_elem.text = None
                first_text_elem.insert(0, chapter_number_elem)
        if add_as_first_child:
            # if we have no text add chapter number tag as first child
            chapter_number_elem.tail = root.text
            root.text = None
            root.insert(0, chapter_number_elem)
        # result is used in templating as result and should be str not bytes
        return etree.tostring(root, pretty_print=bool(pretty_print)).decode()

    @classmethod
    def get_label(cls, label_identifier, *args):
        if args:
            lang = args[0]
        else:
            lang = 'en'
        return util.get_label_with_fallback(label_identifier, lang)

    @classmethod
    def _get_attached_object(cls, specification, tree_down_context, target_value_by_id_cache, cdb_object_id):
        # cdb_object_id can be spec, requirement or target value
        if cdb_object_id == specification.cdb_object_id:
            return specification
        elif cdb_object_id in tree_down_context["spec_object_cache"]:
            return tree_down_context["spec_object_cache"][cdb_object_id]
        else:
            # tree_down_context["target_value_cache"] is indexed by requirement_object_id and not cdb_object_id of tvs
            return target_value_by_id_cache.get(cdb_object_id)

    @classmethod
    def render_specification_with_template(
            cls,
            specification,
            profile,
            tmp_dir_path,
            languages=None,
            requirements=None,
            preprocessor=None,
            override_preprocessor=False,
            custom_render_data=None,
            update_metadata=True,
            **kwargs
    ):
        """
        Render the given specification into a file using a template.

        :param RQMSpecification specification: The specification to be exported
        :param DocumentExportProfile profile: The document export profile which should be used
        :param str tmp_dir_path: absolute path to an empty or explicitely prefilled temporary directory which should be used as working directory
        :param list languages: List of iso language codes for all languages to be exported, first language will be used as primary one.
        :param list requirements: Optional list of requirements to limit export only to them + their parents
        :param func preprocessor: Visitor like function which is called for each requirement in tree with that object and returns a dictionary of things which is available then in the template, if set the default preprocessor output will be updated be the given preprocessor.
        :param bool override_preprocessor: Defines whether the given preprocessor should replace or complement the default preprocessor, default is that the it complements it
        :param bool update_metadata: Defines whether this function should update the file "metadata.json" within the template sub directory with some default metadata or not

        :return: absolute path to result file
        :rtype: str
        :raises FileNameCollision: in case of duplicate file attachments
        :raises DocumentExportTemplateError: in case of template errors
        """
        settings = profile.get_settings()
        template_filename = settings.get('template_filename', 'template.html')
        templates_folder = os.path.join(tmp_dir_path, settings.get('templates_folder_name', 'templates'))

        if languages is None:
            languages = ['en']
        spec_object_ids = None
        if requirements:
            requirement_ids = {r.cdb_object_id: 1 for r in requirements}
            for r in requirements:
                # also collect their parents to have a valid filter criteria for the whole tree
                # TODO: for huge sets this should be done using a hierarchical as well later
                r._get_parent_ids(requirement_ids)
            spec_object_ids = list(requirement_ids)
        try:
            jinja2env = SandboxedEnvironment(
                loader=FileSystemLoader(templates_folder),
                autoescape=select_autoescape([])
            )
            jinja2env.filters['inject_chapter_number'] = cls.inject_chapter_number
            jinja2env.filters['labels'] = cls.get_label
            jinja2env.filters['transform_variables'] = cls.transform_variables

            for attachment in profile.Files:
                fp = jail_filename(templates_folder, attachment.cdbf_name)
                attachment.checkout_file(fp)

            partial_hint = util.get_label('cdbrqm_partial_hint') if requirements else ''

            if update_metadata:
                DocumentExportTools.update_metadata(
                    profile, templates_folder, specification, global_data=dict(
                        partial_hint=partial_hint
                    )
                )

            template = jinja2env.get_template(template_filename)
            tree_down_context = RQMHierarchicals.get_tree_down_context(
                specification, spec_object_ids=spec_object_ids
            )
            if not override_preprocessor:
                preprocessor = (
                    cls.get_preprocessor(tree_down_context, languages, preprocessor)
                )
            render_args = {
                'title': specification.GetDescription(),
                'tree': RQMHierarchicals.walk(tree_down_context, None, preprocessor=preprocessor),
                'language': languages[0],
                'languages': languages,
                'partial_hint': partial_hint
            }
            if custom_render_data:
                render_args.update(custom_render_data)
            all_ids = list(tree_down_context['classification_cache'])  # spec, reqs, tvs
            target_value_by_id_cache = {}
            for tvs in tree_down_context['target_value_cache'].values():
                # tree_down_context['target_value_cache'] is indexed by requirement_object_id and contain lists of tvs for that
                for tv in tvs:
                    target_value_by_id_cache[tv.cdb_object_id] = tv
            for attachment in CDB_File.KeywordQuery(cdbf_object_id=all_ids):
                object_attached_to = cls._get_attached_object(
                    specification=specification,
                    tree_down_context=tree_down_context,
                    target_value_by_id_cache=target_value_by_id_cache,
                    cdb_object_id=attachment.cdbf_object_id
                )
                if hasattr(object_attached_to, 'reqif_id') and object_attached_to.reqif_id != '':
                    sub_dir = os.path.join(tmp_dir_path, object_attached_to.reqif_id)
                else:
                    sub_dir = os.path.join(tmp_dir_path, object_attached_to.cdb_object_id)
                if not os.path.isdir(sub_dir):
                    os.mkdir(sub_dir)
                fp = jail_filename(sub_dir, attachment.cdbf_name)
                if os.path.isfile(fp):
                    raise FileNameCollision(
                        'Attachment name clash: %s (assigned to %s) exists more than once' % (attachment.cdbf_name, object_attached_to.GetDescription())
                    )

                attachment.checkout_file(fp)
            spec_xhtml = template.render(**render_args)
            xhtml_file_name = settings.get('template_output_filename', "{}.xhtml".format(specification.spec_id))
            spec_xhtml_rendered_file = jail_filename(tmp_dir_path, xhtml_file_name)
            with codecs.open(spec_xhtml_rendered_file, 'w+', 'utf-8') as f:
                f.write(spec_xhtml)
        except TemplateError as e:
            raise DocumentExportTemplateError(e)
        return spec_xhtml_rendered_file


def _document_export(specification, ctx, requirements=None):
    start_sql_cnt = statement_count()
    start = datetime.datetime.now()
    profile = DocumentExportProfile.ByKeys(cdb_object_id=ctx.dialog.profile)
    if not profile or profile.obsolete:
        raise ValueError("Invalid or obsolete Profile")
    languages = ctx.dialog.languages.split(',')
    process_run = operation(
        constants.kOperationNew, RQMExportProcessRun,
        specification_object_id=specification.cdb_object_id,
        export_type="Document Export ({})".format(profile.GetDescription()),
        export_status=RQMExportProcessRun.CREATED,
        profile_object_id=profile.cdb_object_id
    )
    protocol = operation(
        constants.kOperationNew, RQMProtocol,
        cdbf_object_id=process_run.cdb_object_id,
        protocol_id=1,
        action="Execution"
    )
    logger_extra_args = dict(
        tags=['rqm_protocol'],
        specification_object_id=specification.cdb_object_id
    )
    result_file = None
    result_document = None
    with RQMProtocolLogging(protocol) as logger:
        try:
            tmp_dir_path = tempfile.mkdtemp()
            logger.info('Created temporary working directory: %s', tmp_dir_path, extra=logger_extra_args)
            result_file = profile.export(
                export_run=process_run,
                tmp_dir_path=tmp_dir_path,
                specification=specification,
                requirements=requirements,
                languages=languages,
                logger=logger,
                extra=logger_extra_args
            )
            if (
                'create_document' in ctx.dialog.get_attribute_names() and
                int(ctx.dialog.create_document) == 1
            ):
                logger.info('Create document', extra=logger_extra_args)
                document_category = DocumentCategory.ByKeys(util.get_prop('rmdc'))
                result_document = operation(
                    constants.kOperationNew,
                    Document,
                    titel=specification.name,
                    z_categ1=document_category.parent_id,
                    z_categ2=document_category.categ_id
                )
                result_file.Copy(cdbf_object_id=result_document.cdb_object_id)
                logger.info('Document created: %s', result_document.z_nummer, extra=logger_extra_args)
            process_run.export_status = RQMExportProcessRun.FINISHED
        except BaseException as e:
            logger.exception(e, extra=logger_extra_args)
            process_run.export_status = RQMExportProcessRun.FAILED
    end = datetime.datetime.now()
    stop_sql_cnt = statement_count()
    LOG.debug('took %s seconds and %d statements', (
        (end - start).total_seconds()), stop_sql_cnt - start_sql_cnt
    )

    if result_document is not None:
        if ctx.uses_webui:
            ctx.url(get_webui_link(None, result_document))
        elif ctx.interactive:
            ctx.url(result_document.MakeURL(constants.kOperationShowObject))
        else:
            ctx.set_object_result(result_document)
    else:
        if result_file is None:
            msg = 'Failed to export %s with profile %s, look into export run for details.' % (specification.GetDescription(), profile.GetDescription())
            if ctx.interactive or ctx.uses_webui:
                raise ue.Exception('just_a_replacement', msg)
            else:
                raise DocumentExportError(msg)
        if ctx.uses_webui:
            ctx.url(
                "/api/v1/collection/rqm_export_run/%s/files/%s" % (
                    process_run.cdb_object_id,
                    result_file.cdb_object_id
                )
            )
        else:
            if result_file is not None:
                if ctx.interactive:
                    ctx.url(result_file.MakeURL())
                else:
                    ctx.set_object_result(result_file)


@sig.connect(RQMSpecObject, list, "cdbrqm_document_export", "pre_mask")
def preselect_default_export_settings(requirements, ctx):
    profile_object_id = util.PersonalSettings().getValueOrDefault(
        "cs.requirements",
        "document_export_profile",
        None
    )
    ctx.set('profile', profile_object_id)
    languages = util.PersonalSettings().getValueOrDefault(
        "cs.requirements",
        "document_export_languages",
        None
    )
    ctx.set('languages', languages)


@sig.connect(RQMSpecObject, list, "cdbrqm_document_export", "now")
def document_export_selected_reqs(requirements, ctx):
    if requirements:
        if ctx.dialog.profile != '':
            util.PersonalSettings().setValue(
                "cs.requirements",
                "document_export_profile",
                ctx.dialog.profile
            )
        if ctx.dialog.languages:
            util.PersonalSettings().setValue(
                "cs.requirements",
                "document_export_languages",
                ctx.dialog.languages
            )
        specification = None
        for r in requirements:
            if specification is None:
                specification = r.Specification
            if r.specification_object_id != specification.cdb_object_id:
                raise ValueError("Only multiple requirements from one specification can be exported")
        try:
            _document_export(specification, ctx, requirements)
        except (ValueError, DocumentExportError) as e:
            LOG.exception(e)
            if ctx.interactive or ctx.uses_webui:
                raise ue.Exception('just_a_replacement', e)
            else:
                raise


@sig.connect(RQMSpecification, "cdbrqm_document_export", "pre_mask")
def preselect_default_export(specification, ctx):
    profile_object_id = util.PersonalSettings().getValueOrDefault(
        "cs.requirements",
        "document_export_profile",
        None
    )
    ctx.set('profile', profile_object_id)
    languages = util.PersonalSettings().getValueOrDefault(
        "cs.requirements",
        "document_export_languages",
        None
    )
    ctx.set('languages', languages)


@sig.connect(RQMSpecification, "cdbrqm_document_export", "now")
def document_export(specification, ctx):
    if ctx.dialog.profile != '':
        util.PersonalSettings().setValue(
            "cs.requirements",
            "document_export_profile",
            ctx.dialog.profile
        )
    if ctx.dialog.languages:
        util.PersonalSettings().setValue(
            "cs.requirements",
            "document_export_languages",
            ctx.dialog.languages
        )
    try:
        _document_export(specification, ctx)
    except (ValueError, DocumentExportError) as e:
        LOG.exception(e)
        if ctx.interactive or ctx.uses_webui:
            raise ue.Exception('just_a_replacement', e)
        else:
            raise


def template_rendering_step(**kwargs):
    logger = kwargs.get('logger', LOG)
    extra = kwargs.get('extra')
    start = datetime.datetime.now()
    result_filename = DocumentExportTools.render_specification_with_template(**kwargs)
    end = datetime.datetime.now()
    logger.info(
        'Rendered content into template (%s seconds).',
        (end - start).total_seconds(), extra=extra
    )
    return result_filename


def xsl_transformation_step(profile, tmp_dir_path, prev_result_filename=None, **kwargs):
    logger = kwargs.get('logger', LOG)
    extra = kwargs.get('extra')
    settings = profile.get_settings()
    templates_folder = os.path.join(tmp_dir_path, settings.get('templates_folder_name', 'templates'))
    start = datetime.datetime.now()
    if not prev_result_filename:
        prev_result_filename = settings.get('xslt_input_filename')
    if not prev_result_filename:
        raise ValueError('XSLTransformation needs input filename, nothing given')
    xslt_template_name = settings.get('xslt_template_filename', 'convert_objects_to_images.xsl')
    xslt_output_filename = settings.get('xslt_output_filename')
    if xslt_output_filename is not None:
        xslt_output_filename = jail_filename(tmp_dir_path, xslt_output_filename)
    else:
        xslt_output_filename = prev_result_filename
    XSLTransformer.transform(
        jail_filename(templates_folder, xslt_template_name),
        prev_result_filename,
        working_directory=tmp_dir_path
    ).write_output(
        xslt_output_filename
    )
    end = datetime.datetime.now()
    logger.info(
        'Transformation using %s finished (%s seconds).',
        xslt_template_name, (end - start).total_seconds(), extra=extra
    )
    return xslt_output_filename


def generic_export(
    specification,
    profile,
    languages,
    export_run,
    tmp_dir_path,
    requirements=None,
    steps_mapping=None,
    logger=None,
    extra=None,
):
    r"""
    Generic export function which allows simple and partially also advanced
    document export profiles to be simply configured.
    Therefore the :samp:`fqpyname` of such profiles must be set to this function.
    The profile then can contain its steps and settings like this::

        {
          "export_filename": "{spec_id}.xhtml",
          "steps": [
            "templateRendering"
          ]
        }

    The attachments of the profile will be automatically checked out to a subfolder of the temporary folder
    so that they can be used e.g. as template files etc.

    For simple commands steps can be either an available callable binary or a special step identifier
    which represents a function to be called from the :samp:`steps_mapping`.
    More complex commands in steps can also be defined as a list whereas the first element is a callable binary
    and the rest are parameters to this binary like this::

        {
          "steps": [
            ["an_allowed_binary", "-a", "1", "-b", "2"]
          ]
        }

    For security reasons the callable binaries **must** be explicitely configured
    within :file:`${CADDOK_BASE}/etc/requirements_doc_export_allowed_binaries.json`.
    This file needs to contain a JSON dictionary with the binary name which should be callable
    (and configured in document export profiles) as keys
    and the absolute file path to the binary as values.

    Windows Example ::

        {
            "inkscape": "C:\\Program Files\\Inkscape\\bin\\inkscape.exe"
        }

    Linux Example ::

        {
            "inkscape": "/usr/bin/inkscape"
        }

    .. important::

        The security depends on the called binaries and its parameters so be sure to know what is possible
        with the tools which will be called/allowed to call.

    Within the default steps_mapping currently the following two special steps with corresponding settings exist::

        - "templateRendering"
          - "template_filename"
          - "template_output_filename"

        - "xslTransformation"
          - "xslt_input_filename"
          - "xslt_template_filename"
          - "xslt_output_filename"

    In addition the following global settings exist::

        - "export_filename" # can use spec_id as format variable, if not given only the ZIP archive will be stored
        - "export_collection_filename" # ZIP archive name, defaults to "{spec_id}.zip"
        - "no_cleanup" # boolean flag, only for debugging: prevent temporary folder to be cleaned/removed
        - "templates_folder_name" # can be used to change the name of the sub folder where the templates will be checked out, defaults to "templates"

    This function can be enhanced/customized when it is wrapped.

    :param RQMSpecification specification: The specification to be exported
    :param DocumentExportProfile profile: The document export profile which should be used
    :param list languages: List of iso language codes for all languages to be exported, first language will be used as primary one.
    :param RQMExportProcessRun export_run: The export process run object for the current run, used to store the resulting file objects (ZIP archive + result object) and log informations
    :param str tmp_dir_path: absolute path to an empty or explicitely prefilled temporary directory which should be used as working directory
    :param list requirements: Optional list of requirements to limit export only to them + their parents
    :param dict steps_mapping: Dictionary to map ({"identifier": callable_func}) some functions to some static identifiers for the configurable steps, these functions get the previous step filename of the result (prev_result_filename) as parameter
    :param Logger logger: Logger which should be used for logging messages
    :param dict extra: Extra arguments for logging

    :return: The exported specification as file object.
    :rtype: CDB_File
    :raises DocumentExportError: in case of an error, the folder content of the temporary folder will be stored as ZIP archive to the export run anyway if possible

    """
    initial_start = datetime.datetime.now()
    settings = profile.get_settings()
    # use a separate folder for templates/files from doc export profile
    # to prevent name clash/file collisions with attachments of spec/requirements
    # results are written directly to tmp_dir_path as otherwise image
    # pathes etc. are wrong for the content
    templates_folder = os.path.join(tmp_dir_path, settings.get('templates_folder_name', 'templates'))
    os.makedirs(templates_folder)

    special_steps_mapping = {
        'templateRendering': template_rendering_step,
        'xslTransformation': xsl_transformation_step
    }
    if steps_mapping is not None:
        special_steps_mapping.update(steps_mapping)
    steps = settings.get('steps', [])
    step_process_timeout = int(settings.get("step_process_timeout", 60))
    logger.info('Using step process timeout of %d seconds', step_process_timeout, extra=extra)
    error = None
    result_filename = ''
    try:
        for step in steps:
            cmd = None
            start = datetime.datetime.now()
            if isinstance(step, str) and step in special_steps_mapping:
                result_filename = special_steps_mapping[step](
                    specification=specification,
                    profile=profile,
                    export_run=export_run,
                    tmp_dir_path=tmp_dir_path,
                    languages=languages,
                    logger=logger,
                    extra=extra,
                    requirements=requirements,
                    prev_result_filename=result_filename
                )
                end = datetime.datetime.now()
                logger.info(
                    'Executed %s (%s seconds)',
                    step, (end - start).total_seconds(), extra=extra
                )
            else:
                dynamic_cmd_args = dict(
                    prev_result_filepath=result_filename,
                    prev_result_filename=os.path.basename(result_filename),
                    language=languages[0],
                    languages=",".join(languages),
                    templates_folder=templates_folder
                )
                if isinstance(step, str):
                    cmd = step.format(**dynamic_cmd_args)
                else:
                    cmd = [x.format(**dynamic_cmd_args) for x in step]
                DEVNULL = open(os.devnull, 'w')
                filtered_cmd = DocumentExportTools.ensure_allowed_binaries(cmd)
                plattools.killableprocess.check_call(
                    filtered_cmd,
                    cwd=tmp_dir_path,
                    stdout=DEVNULL,
                    stderr=plattools.killableprocess.STDOUT,
                    timeout=step_process_timeout
                )
                end = datetime.datetime.now()
                logger.info(
                    'Executed %s (%s seconds)',
                    cmd, (end - start).total_seconds(), extra=extra
                )
    except plattools.killableprocess.CalledProcessError as cpe:
        end = datetime.datetime.now()
        logger.exception(
            'Execution of %s failed (%s) (%s seconds)',
            cmd, cpe.returncode, (end - start).total_seconds(), extra=extra
        )
        error = DocumentExportError()
    except (ValueError, DocumentExportError) as e:
        end = datetime.datetime.now()
        logger.exception(
            'Execution of %s failed (%s) (%s seconds)',
            cmd if cmd is not None else step, e, (end - start).total_seconds(), extra=extra
        )
        error = DocumentExportError(e)
    finally:
        # finally store temp folder content even if some steps crashed for better analysis
        logger.info('Save folder content as zip', extra=extra)
        export_file = settings.get("export_collection_filename", "%s.zip" % specification.spec_id)
        result_file = DocumentExportTools.save_folder_content_as_zip(
            export_run, tmp_dir_path, export_file
        )
    if error:
        raise error
    result_file_name = settings.get('export_filename')
    if result_file_name is not None:
        if '{' in result_file_name:
            result_file_name = result_file_name.format(spec_id=specification.spec_id)
        result_file = DocumentExportTools.save_result_file(
            export_run, tmp_dir_path, result_file_name
        )
    end = datetime.datetime.now()
    no_cleanup = settings.get('no_cleanup', False)
    if not no_cleanup:
        DocumentExportTools.cleanup_folder(tmp_dir_path)
    logger.info(
        'Export to %s finished (total: %s seconds)',
        result_file.GetDescription(), (end - initial_start).total_seconds(), extra=extra
    )
    return result_file
