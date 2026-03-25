# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# See http://sphinx.pocoo.org/config.html for details to all options.
import os
import re
from importlib import resources
from pathlib import Path

import pkg_resources
from cdb import dotlib

from cs.userassistance import util

SPHINXPACKAGE = 'SPHINXPACKAGE'
_GRAPHVIZ_PATH = dotlib.graphviz_path()

BABEL = {
    'de': 'ngerman',
    'en': 'english',
}

PREAMBLE = {
    'de': """
\\addto\\extrasngerman{%
\\def\\pageautorefname{Seite}%
}
\\addto\\extrasngerman{%
\\def\\pagename{Seite}%
}
""",
    'en': '',
}

DOCPORTAL = {
    'en': 'Documentation Portal',
    'de': 'Dokumentationsportal',
}

# A Book with this category will be added to portal,
# but not listed in the category index. It still can be found with searching.
kDocCategoryUnlisted = -2
# A book with this category will be ignored.
kDocCategoryInternal = -1
kDocCategoryUser = 1
kDocCategoryAdmin = 2
kDocCategoryProgramming = 3
kDocCategoryReleaseNotes = 4
kDocCategoryDesign = 5


def get_package_name() -> str:
    """
    :returns: Name of the "local" package
    :raises: ValueError if environment variable SPHINXPACKAGE is not set
    """
    if SPHINXPACKAGE in os.environ:
        return os.environ[SPHINXPACKAGE]

    raise ValueError(
        f'environment variable "{SPHINXPACKAGE}" is required '
        'when referring to local package as args.prefix'
    )


def get_category_name(category, iso_lang):
    """
    Retrieves the name of the documentation category.
    If `category` is one of the ``kDocCategory...``
    constants the name for the specified `iso_lang`
    will be returned. If category is a string the
    function will return this string.
    """
    user_manuals = {'de': 'Anwendung', 'en': 'User Manuals'}
    admin_manuals = {'de': 'Administration', 'en': 'Administration Manuals'}
    prog_manuals = {'de': 'Entwicklung', 'en': 'Programming Manuals'}
    relnotes = {'de': 'Release Notes', 'en': 'Release Notes'}
    design = {'de': 'Design', 'en': 'Design'}

    categories = {
        kDocCategoryUser: user_manuals,
        kDocCategoryAdmin: admin_manuals,
        kDocCategoryProgramming: prog_manuals,
        kDocCategoryReleaseNotes: relnotes,
        kDocCategoryDesign: design,
    }

    result = ''
    if category == kDocCategoryInternal:
        result = 'Internal'
    elif category == kDocCategoryUnlisted:
        result = 'Unlisted'
    elif isinstance(category, int):
        namedict = categories.get(category, [])
        if namedict:
            # Get the specific one and fallback to "en" which
            # should be available for every category
            result = namedict.get(iso_lang, namedict['en'])
    elif isinstance(category, str):
        result = category

    if not result:
        return 'Manuals'

    return result


def prepare_substitutions(language: str) -> dict[str, str]:
    """
    Prepare substitutions for a given language.

    :param language: A string representing the language to prepare substitutions for.
    :return: A dictionary of substitutions.
    """
    _subs_dir = Path(__file__).parent / 'shortcuts'
    nolang = _subs_dir / 'nolang.rst'
    langsub = _subs_dir / f'{language}.rst'

    # Merge
    global_subs = parse_subst(nolang)
    language_subs = parse_subst(langsub)
    global_subs.update(language_subs)

    # Resolve internal references
    while 1:
        changed = resolve_subst(global_subs)
        if not changed:
            break

    return global_subs


def resolve_subst(subs: dict[str]) -> bool:
    """
    Resolve the substitutions in a dictionary by replacing values containing
    '|text|' patterns with corresponding values from the same dictionary.

    :param subs: A dictionary containing the substitutions to resolve.
                 The keys represent the original text and the values represent
                 the replacement text.
                 The values may contain '|' characters before and after
                 the text to replace.

    :return: True if any substitution was resolved, False otherwise.
    """
    to_resolve: list[tuple[str, str]] = []
    pattern = re.compile(r'\|([^|]+)\|')

    # filter for any substitutions that need to be resolved
    for key, value in subs.items():
        if '|' in value:
            to_resolve.append((key, value))

    if not to_resolve:
        return False

    # try to replace substitutions in the subs dictionary
    changed = False
    for k, v in to_resolve:
        new_val = v
        for match in pattern.findall(v):
            replaced = subs.get(match)
            if replaced is not None:
                new_val = new_val.replace(f'|{match}|', replaced)
                changed = True

        subs[k] = new_val

    return changed


def parse_subst(file_path: Path) -> dict[str, str]:
    """
    Parse a substitution file and return a dictionary containing the substitutions.

    :param file_path: A `Path` object representing the path to the substitution
                      file to parse.
    :raises FileNotFoundError: If the file specified by `file_path` does not exist
                               or is not readable.
    :raises UnicodeDecodeError: If the file specified by `file_path`
                                is not encoded in UTF-8.
    :return: A dictionary containing the substitutions.
    """
    result = {}
    pattern = re.compile(r'^\.\. \|([^|]+)\|\s+replace::\s+(.*)\s*$')
    with open(file_path, 'r', encoding='utf-8') as fd:
        for line in fd:
            if 'replace::' not in line:
                continue
            match = pattern.match(line)
            if match:
                result[match.group(1)] = match.group(2)
    return result


def configure(target, title, name=None, language=None, intersphinx=[], **kwargs):
    # If name/language are None, take those from the docset path
    # .../doc/<name>/<lang>/src
    # (when conf.py is evaluated, cwd is the src/ directory)
    cwd = os.getcwd()
    # First path is "src/"
    cwd, part = os.path.split(cwd)
    cwd, part = os.path.split(cwd)
    if language is None:
        language = part
    cwd, part = os.path.split(cwd)
    if name is None:
        name = part

    fname = 'docset.info'
    assert isinstance(fname, str)
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(f'title: {title}\n')
        f.write(f'name: {name}\n')
        f.write(f'language: {language}\n')
        f.write(
            f'category: {get_category_name(kwargs.get("category", ""), language)}\n'
        )

    intersphinx_mapping = dict(python=('https://docs.python.org/3.11/', None))
    for data in intersphinx:
        ipkg, iname, ilang, map_name = (data[0], data[1], data[2], data[3:])
        if not map_name:
            map_name = iname
        else:
            map_name = map_name[0]

        if ipkg == '#':
            # "#" means "the platform", links from apps into the platform documentation
            inventory_base = resources.files('cs.platform').parent.parent / 'doc'
            ipkg = 'cs.platform'
        else:
            if ipkg == '.':
                # ipkg = "." means "this package"
                # Otherwise, ipkg _is_ a package name
                ipkg = get_package_name()
            inventory_base = util.INSTANCE_DOCUMENTATION_PATH / ipkg

        inventory: Path = inventory_base / iname / ilang / 'html' / 'objects.inv'
        intersphinx_mapping[map_name] = (
            f'/doc/{ilang}/_inpackage/{ipkg}/{iname}/',
            str(inventory),
        )

    target.update(kwargs)

    if '' == kwargs.get('copyright', ''):
        # Simply default to our company name since the year is unnecessary
        # HTML: Sphinx auto prefixes the copyright parameter with a "© Copyright"
        # PDF: We prefix it with a "©" ourselves and pass it to the author
        #      parameter since there's no copyright parameter for PDF
        target.update({'copyright': 'CONTACT Software'})

    target.update(
        {
            # os.environ (!), so we can use this in WSGI contexts...
            'html_theme_path': [
                pkg_resources.resource_filename('cs.userassistance', 'themes'),
            ],
            'html_theme': 'rtd',
            'html_title': title,
            'html_static_path': ['docset.info'],
            'html_domain_indices': ['py-modindex'],
            'modindex_common_prefix': ['cdb.', 'cs.'],
            'html_context': {
                'doc_portal_link': True,
                'doc_portal_title': DOCPORTAL[language],
                'doc_portal_url': f'/doc/{language}',
            },
            # As long as there is no image
            'disable_images': 1,
            # Add any Sphinx extension module names here, as strings. They can be
            # extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
            'extensions': [
                'sphinx.ext.autodoc',
                'sphinx.ext.intersphinx',
                'sphinxcontrib.globalsubs',
            ],
            'intersphinx_mapping': intersphinx_mapping,
            # Automatically document constructor
            'autoclass_content': 'both',
            'autodoc_member_order': 'alphabetical',
            # The suffix of source filenames.
            'source_suffix': '.rst',
            # The master toctree document.
            'master_doc': 'index',
            # General information about the title.
            'project': title,
            'language': language,
            # Translation setup
            'locale_dirs': ['../locale/'],
            'gettext_compact': False,
            'gettext_location': False,
            # The reST default role (used for this markup: `text`) to use for all docs
            'default_role': 'obj',
            # If not '', a 'Last updated on:' timestamp is inserted at every page
            # bottom, using the given strftime format.
            'html_last_updated_fmt': '%d.%m.%Y',
            # If true, the reST sources are included in the HTML build as
            # _sources/<name>.
            'html_copy_source': True,
            'html_search_enabled': True,
            # Output file base name for HTML help builder.
            'htmlhelp_basename': name,
            'trim_footnote_reference_space': True,
            # Options for LaTeX output
            'latex_elements': {
                # Use DIN A4
                'papersize': 'a4paper',
                # Do not produce useless empty pages,
                'classoptions': ',openany,oneside',
                # make sure babel keeps working
                'babel': f'\\usepackage[{BABEL[language]}]{{babel}}',
                'preamble': PREAMBLE[language],
                # Disable PDF Index table entries because of rendering issues (E051636)
                'makeindex': '',
            },
            # Disable PDF "Index" table entries because of rendering issues (E051636)
            'latex_domain_indices': False,
            # Grouping the document tree into LaTeX files. List of tuples (source
            # start file, target name, title, author, documentclass
            # [howto/manual]).
            'latex_documents': [
                (
                    'index',
                    f'{name}.tex',
                    title,
                    kwargs.get('latex_author', f'© {target["copyright"]}'),
                    'manual',
                    True,
                )
            ],
            'latex_show_pagerefs': True,
            'global_substitutions': prepare_substitutions(language),
            'rst_epilog': '',
            'graphviz_dot': os.path.join(_GRAPHVIZ_PATH, 'dot')
            if _GRAPHVIZ_PATH
            else 'dot',
        }
    )
