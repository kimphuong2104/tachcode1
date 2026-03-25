# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import errno
import os
import tempfile
from pathlib import Path

import yaml
from pkg_resources import Distribution, working_set

from cs.docportal import (
    DocPortalConfigurationError,
    DocPortalError,
    isCDBEnvironment,
    util,
)
from cs.docportal.database import DocDB

_logger = util.get_logger(__name__)


def load_mode_data():
    if os.environ.get('DOCPORTAL_BOOK_PATH'):
        return StandaloneDocPortalData()
    elif isCDBEnvironment:
        return CDBDocPortalData()
    else:
        raise DocPortalError('Neither running in CDB nor standalone mode')


class CDBPackage:
    """A CDB Python Package (with its documentation and prebuilt search index)"""

    def __init__(self, name, version, path):
        self.name = name
        self.version = version
        self.path = Path(path)
        self.doc_path = self._get_doc_path()
        self.index_path = self.doc_path / '_docindex'
        self.docdb = DocDB(self.doc_path / 'docportal.db')
        self.stat = self._stat()

    def __repr__(self):
        return f'CDBPackage({self.name}, {self.version})'

    def _stat(self):
        """
        Returns the result of calling ``os.stat`` on the path to the database file.

        If the database file does not exist or cannot be accessed, returns None.

        Returns:
            A named tuple containing information about the file, including its size,
            creation time, and modification time, as returned by os.stat.
            Returns None if the file cannot be accessed.
        """
        try:
            return os.stat(self.docdb.db_path)
        except OSError:
            return None

    def _get_doc_path(self) -> Path:
        # since 15.8 the built documentation doesn't go into the doc/ directory anymore
        # for EGGs it's now <EGG>/docs/ and for the current buildout's dev package
        # it's <INST>/docs/<PKG_NAME> (e.g. sqlite/docs/cs.docportal)
        if isCDBEnvironment:
            if self.name == 'cs.platform':
                # only platform has the built documentation under doc
                # except for when we are in standalone mode...
                return self.path / 'doc'

            else:
                return Path(os.environ['CADDOK_BASE']) / 'docs' / self.name

        elif os.environ.get('DOCPORTAL_BOOK_PATH'):
            # CASE: standalone mode
            return self.path

        else:
            raise DocPortalError('Unhandled case for package doc location')

    @staticmethod
    def _contains_docs(path: Path) -> bool:
        """Check if a given path directory meets the criteria for being
        recognized as a valid documentation.

        - It contains a _docindex directory
        - It contains a docportal.db file,
        - There is at least one book directory

        """
        if not (path / 'docportal.db').is_file():
            return False

        if not (path / '_docindex').is_dir():
            return False

        for sub_node in path.iterdir():
            if sub_node.is_dir() and sub_node.name != '_docindex':
                return True

        return False

    @classmethod
    def from_path(cls, path: Path):
        """
        Returns a CDBPackage if the given path contains documentation,
        otherwise returns None.
        """
        if not cls._contains_docs(path):
            return None

        name, version = path.name.rsplit('-', maxsplit=1)
        return CDBPackage(name, version, path)

    @classmethod
    def from_distribution(cls, dist: Distribution):
        # TODO: replace with distutils or something else that's more modern!
        if not dist.has_metadata('docsets.txt'):
            _logger.info('No docsets.txt for %s', dist)
            return None

        for line in list(dist.get_metadata_lines('docsets.txt')):
            if line.strip():
                break
        else:
            _logger.info('No docsets for %s', dist)
            return None

        return CDBPackage(dist.key, dist.version, dist.location)


class CDBPackageSet:
    def __init__(self, packages: list[CDBPackage]):
        _sorted_packages = sorted(packages, key=lambda p: (p.name, p.version))
        self.packages = tuple(_sorted_packages)
        self.hash = util.string_hash(str(self.packages))

    def __iter__(self):
        for package in self.packages:
            yield package

    def __len__(self):
        return len(self.packages)

    def __repr__(self):
        return str(self.packages)


class DocPortalData:
    """Abstract base class for the running mode data"""

    def __init__(self):
        self.default_language_id = 'en'
        self.default_bundle_id = None
        self._etc_folder = util.module_root_dir() / 'etc'

        # data
        self.languages = self._load_languages()
        self.categories = self._load_categories()
        self.bundles = self._load_bundles()
        self.language_bundles = self._compose_language_bundle_mappings()

    def _load_bundles(self):
        """
        A DocPortal contains one or more bundles of documentation.
        Each bundle usually represents the documentation of a
        CONTACT Elements Umbrella release (e.g. "CONTACT Elements 15.4"),
        but can also be manually administered (e.g. "Tools" or "CAD" or "MyDocs").

        :rtype: list[dict]
        :return: a list of kwarg dictionaries for instantiating DocBundles
        (including its ID again)
        """
        raise NotImplementedError

    def _compose_language_bundle_mappings(self):
        """
        Compose language bundles from bundles and languages.
        Note that ``None`` is used to refer to an unknown release version as in some
        environments we know which documentation we should display, but don't know
        anything about the corresponding product or its version.

        Return examples:
        SBM: {'en': (None, 'en'), 'de': (None, 'de')}
        MBM: {'15.4-en': ('15.4', 'en'), '15.4-de': ('15.4', 'de'), ...}

        :rtype: dict[str, tuple]
        :return: A list of tuples of language bundles per version
        """
        raise NotImplementedError

    def _load_languages(self):
        """
        Load languages from the respective config file in the etc/ directory.
        :rtype: list[dict]
        :return: a list of kwarg dictionaries for instantiating DocLanguages
        """
        languages = []

        # load localized labels and brandings for the languages
        with open(self._etc_folder / 'branding.yaml', encoding='utf-8') as f:
            labels = yaml.safe_load(f)
        with open(self._etc_folder / 'labels.yaml', encoding='utf-8') as f:
            labels.update(yaml.safe_load(f))

        # load configured languages
        with open(self._etc_folder / 'languages.yaml', encoding='utf-8') as f:
            languages_cfg = yaml.safe_load(f)

        for language_id in languages_cfg:
            language_name = languages_cfg[language_id]
            translations = {}

            for label in labels:
                try:
                    translations[label] = labels[label][language_id]
                except KeyError:
                    continue

            if translations:
                languages.append(
                    {
                        'identifier': language_id,
                        'name': language_name,
                        'translations': translations,
                    }
                )

        return languages

    def _load_categories(self):
        """
        Load the categories from the category config file in etc/
        :rtype: list[dict]
        :return: a list of kwarg dictionaries for instantiating DocCategories
        """
        categories = []

        if os.environ.get('DOCPORTAL_CUSTOM_CATEGORY_YAML'):
            yaml_path = os.environ.get('DOCPORTAL_CUSTOM_CATEGORY_YAML')
        else:
            yaml_path = self._etc_folder / 'categories.yaml'

        with open(yaml_path, encoding='utf-8') as f:
            categories_cfg = yaml.safe_load(f)

        def _subcategories(category, cat_id, lang_id):
            for categ_id, subcategory in category['subcategories'].items():
                cat = subcategory['languages'][lang_id]
                yield {
                    'identifier': categ_id,
                    'name': cat['title'],
                    'lang_id': lang_id,
                    'teaser': cat['teaser'],
                    'icon': categories_cfg[cat_id]['icon'],
                    'orderval': subcategory['orderval'],
                    'subcategories': _subcategories(subcategory, cat_id, lang_id)
                    if 'subcategories' in subcategory
                    else [],
                    'books': subcategory.get('books', []),
                }

        for category_id in categories_cfg:
            for language_id in categories_cfg[category_id]['languages']:
                cat = categories_cfg[category_id]['languages'][language_id]
                categories.append(
                    {
                        'identifier': category_id,
                        'name': cat['title'],
                        'lang_id': language_id,
                        'teaser': cat['teaser'],
                        'orderval': categories_cfg[category_id]['orderval'],
                        'icon': categories_cfg[category_id]['icon'],
                        'subcategories': _subcategories(
                            categories_cfg[category_id], category_id, language_id
                        )
                        if 'subcategories' in categories_cfg[category_id]
                        else [],
                        'books': categories_cfg[category_id].get('books', []),
                    }
                )

        return categories


class StandaloneDocPortalData(DocPortalData):
    def __init__(self):
        self.doc_path = self._doc_path()
        self.default_bundle_id = self._default_bundle_id()
        self.base_uri = self._base_uri()
        _location_hash = util.string_hash(str(self.doc_path))
        self.temp_folder = Path(tempfile.gettempdir()) / 'docportal' / _location_hash
        self.blacklist = set()
        super().__init__()

    def _load_bundles(self):
        bundles = []

        for bundle_dir in sorted(list(self.doc_path.iterdir())):
            bundle_path = self.doc_path / bundle_dir
            if bundle_path.is_dir():
                # Assert there's no special HTTP characters in the bundle ID,
                # because the ID is going to be used in the URL.
                for char in ';?@&=+$, ':
                    if char in bundle_dir.name:
                        raise DocPortalConfigurationError(
                            f'Illegal character "{char}" in ID for DocBundle: '
                            f'"{bundle_dir.name}"'
                        )

                # load maybe preconfigured bundle name
                try:
                    with open(
                        self.doc_path / bundle_dir / 'bundle_name.txt', encoding='utf-8'
                    ) as f:
                        bundle_name = f.read()
                except (OSError, IOError):
                    bundle_name = f'Elements {bundle_dir.name}'

                packages = self.load_packages(bundle_dir)

                bundles.append(
                    {
                        'identifier': bundle_dir.name,
                        'name': bundle_name,
                        'packages': packages,
                        'index_path': bundle_path / '_docindex',
                    }
                )
        return bundles

    @staticmethod
    def load_packages(path: Path):
        packages = []

        for node_path in path.iterdir():
            cdb_package = CDBPackage.from_path(node_path)
            if cdb_package:
                packages.append(cdb_package)

        return CDBPackageSet(packages)

    def _compose_language_bundle_mappings(self):
        # A LanguageBundle will look like "15.4-en" in this mode
        language_bundles = {}

        for bundle_args in self.bundles:
            bundle = bundle_args['identifier']
            for language_args in self.languages:
                language = language_args['identifier']
                language_bundles[f'{bundle}-{language}'] = (bundle, language)

        return language_bundles

    def _default_bundle_id(self):
        """
        The default bundle will be either set from a config file or it will
        automatically be set to the highest version number of all the bundles:
        [15.2, 15.3, 15.4] → 15.4
        """
        try:
            with open(self.doc_path / 'default_bundle_id.txt', encoding='utf-8') as f:
                return f.read().strip()
        except (IOError, OSError):
            return None

    @staticmethod
    def _doc_path():
        """
        priorities: env var > data folder
        :return doc_path: an absolute path to the folder containing the documentation
        """
        if 'DOCPORTAL_BOOK_PATH' in os.environ:
            return Path(os.environ.get('DOCPORTAL_BOOK_PATH'))

        return util.project_root_dir() / 'data'

    @staticmethod
    def _base_uri():
        base_uri = os.environ.get('DOCPORTAL_BASEURI')

        if not base_uri:
            return '/'

        elif (
            not base_uri.startswith('/')
            or not base_uri.endswith('/')
            or len(base_uri) == 2
        ):
            raise DocPortalConfigurationError(f'Invalid base URI: "{base_uri}"')

        else:
            return base_uri


class CDBDocPortalData(DocPortalData):
    def __init__(self):
        from cs.docportal.cdb import CADDOK_BASE

        self.blacklist = self._load_blacklist(
            CADDOK_BASE / 'etc' / 'docportal_blacklist.txt'
        )
        self.temp_folder = Path(os.environ['CADDOK_TMPDIR']) / 'docportal'
        super().__init__()
        self.base_uri = '/doc/'
        self._update_help_ids()

    def _load_bundles(self):
        # load all packages
        packages = []
        for dist in working_set:
            package = CDBPackage.from_distribution(dist)
            if package and package.name not in self.blacklist:
                packages.append(package)

        package_set = CDBPackageSet(packages)
        self._set_hash = package_set.hash

        if 'DOCPORTAL_NAME' in os.environ:
            name = os.environ['DOCPORTAL_NAME'].strip()
        else:
            # this usually gives "CONTACT Elements"
            name = self.languages[0]['translations']['branding_product_name']

        return [
            {
                'identifier': None,
                'name': name,
                'packages': package_set,
                'index_path': self.temp_folder,
            }
        ]

    def _compose_language_bundle_mappings(self):
        # In this mode we solely use the language identifiers as
        # LanguageBundle identifiers
        language_bundles = {}

        for language_args in self.languages:
            language = language_args['identifier']
            for bundle_args in self.bundles:
                bundle = bundle_args['identifier']
                language_bundles[language] = (bundle, language)

        return language_bundles

    @staticmethod
    def _load_blacklist(conf_path):
        """Load blacklist if it exists"""
        blacklist = set()

        try:
            with open(conf_path, encoding='utf-8') as blacklist_conf:
                for line in blacklist_conf.readlines():
                    if not line.strip() or line.startswith('#'):
                        continue
                    blacklist.add(line.strip())
        except (OSError, IOError) as e:
            if e.errno != errno.ENOENT:
                _logger.exception(
                    'Failed to load docportal blacklist from %s', conf_path
                )

        return blacklist

    def _update_help_ids(self):
        """
        Refresh helpIDs in the instance database if the configuration has
        changed since the last launch
        """
        _logger.info('Current Package configuration: %s', self._set_hash)

        set_hash_path = self.temp_folder / f'pkg_conf_{self._set_hash}'
        if set_hash_path.is_file():
            _logger.info('Package configuration unchanged. Not updating HelpIDs.')
            return

        _logger.info('Package configuration new or changed. Updating HelpIDs now!')
        from cs.docportal.cdb.helptools import updater

        # delete possible leftover files
        for hash_file in self.temp_folder.glob('pkg_conf_*'):
            hash_file.unlink()

        # update helpIDs and then touch new set_hash file
        updater.update_help_links()
        set_hash_path.touch()
        _logger.info('Finished updating HelpIDs')
