#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
import io
import logging
import os
import posixpath
import shutil
from subprocess import Popen, PIPE
import sys
import time
import traceback
import hashlib
import fnmatch
import threading

from watchdog import observers
from watchdog.events import PatternMatchingEventHandler

from cdb import CADDOK
from cdb.comparch import modules
from cs.web.make.util import puts, find_webui_apps, WebAppInfo, MakeException

_LOGGER = logging.getLogger(__name__)

_TEMPLATE_VAR_THEME = '// {TEMPLATE_VARIABLES_THEME_END}\n'
_TEMPLATE_VAR = '// {TEMPLATE_VARIABLES_END}\n'
_TEMPLATE_STYLE = '// {TEMPLATE_STYLES_END}\n'

_puts_timestamp = False


class CompilerThread(threading.Thread):
    def __init__(self, compile_call):
        super(CompilerThread, self).__init__()
        self.compile = compile_call
        self.needs_recompile = False
        self.condition = threading.Condition()
        self.shutdown_thread = False

    def run(self):
        while True:
            self.condition.acquire()
            while not self.needs_recompile and not self.shutdown_thread:
                puts('Compilation thread waiting...', put_timestamp=_puts_timestamp)
                self.condition.wait()
            self.needs_recompile = False
            self.condition.release()

            if self.shutdown_thread:
                return
            try:
                self.compile()
            except Exception:
                traceback.print_exc(file=sys.stderr)

    def do_recompile(self, path):
        self.condition.acquire()
        puts('Scheduling recompile for %s.' % path, put_timestamp=_puts_timestamp)
        self.needs_recompile = True
        self.condition.notify()
        self.condition.release()

    def do_shutdown(self):
        self.condition.acquire()
        puts('Shutdown compilation thread.', put_timestamp=_puts_timestamp)
        self.shutdown_thread = True
        self.condition.notify()
        self.condition.release()


class ScssEventHandler(PatternMatchingEventHandler):

    def __init__(self, compile_call, *args, **kwargs):
        super(ScssEventHandler, self).__init__(*args, **kwargs)
        self.imported_files = []
        self.compile = compile_call

        self.compiler_thread = CompilerThread(self.compile)
        self.compiler_thread.start()

    def process(self, path):
        puts("Change detected in %s." % path, put_timestamp=_puts_timestamp)
        self.compiler_thread.do_recompile(path)

    def on_moved(self, event):
        super(ScssEventHandler, self).on_moved(event)
        self.process(event.dest_path)

    def on_created(self, event):
        super(ScssEventHandler, self).on_created(event)
        self.process(event.src_path)

    def on_deleted(self, event):
        super(ScssEventHandler, self).on_deleted(event)
        self.process(event.src_path)

    def on_modified(self, event):
        super(ScssEventHandler, self).on_modified(event)
        self.process(event.src_path)


def _collect_app_paths(apps, branding_pkg_path):
    """
    Return all paths for packages where styles may be, putting the branding
    package (if it exists) in front.
    """
    app_paths = []
    for app in apps:
        if app.pkg_path not in app_paths:
            _LOGGER.info("Collecting styles for %s", app.pkg_name)
            if app.pkg_path == branding_pkg_path:
                app_paths.insert(0, app.pkg_path)
            else:
                app_paths.append(app.pkg_path)
    return app_paths


def _compile_app_style(app, main_scss):
    app_folder = posixpath.join(app.pkg_path, app.app_path, 'src')
    _LOGGER.debug("extracting styles from %s", app_folder)

    variables, styles = (
        posixpath.relpath(posixpath.join(app_folder, f + '.scss'), app.pkg_path)
        for f in ('variables', 'styles'))

    if CADDOK.get('WEBUI_THEME'):
        variables_theme = posixpath.relpath(
            posixpath.join(app_folder,
                           'variables.theme-%s.scss' % CADDOK.WEBUI_THEME), app.pkg_path)

        if posixpath.isfile(posixpath.join(app.pkg_path, variables_theme)):
            variables_theme = "@import '%s';\n" % variables_theme
            main_scss = main_scss.replace(_TEMPLATE_VAR_THEME,
                                          variables_theme + '\n%s' % _TEMPLATE_VAR_THEME)

    if posixpath.isfile(posixpath.join(app.pkg_path, variables)):
        variables = "@import '%s';\n" % variables
        main_scss = main_scss.replace(_TEMPLATE_VAR,
                                      variables + '\n%s' % _TEMPLATE_VAR)
    if posixpath.isfile(posixpath.join(app.pkg_path, styles)):
        comp_ns = ("$componentNameSpace: %s;\n" % app.component_name_space
                   if app.component_name_space else "")
        styles = "%s\n@import '%s';\n" % (comp_ns, styles)
        main_scss = main_scss.replace(_TEMPLATE_STYLE, styles + '\n%s' % _TEMPLATE_STYLE)
    return main_scss


def _run_node_compiler(main_scss, pkg_paths, production):
    sass_img = shutil.which('sass')
    if not os.path.exists(sass_img):
        raise MakeException("No 'sass' on PATH.")

    cmd = [sass_img, "--no-color", '--stdin']
    if production:
        cmd += ['--style=compressed']
    else:
        cmd += ['--embed-source-map']
    # Prepare load-path, individual entries can be added via multiple occurences
    cmd += ('--load-path=%s' % p for p in pkg_paths)

    _LOGGER.debug(" ".join(cmd))
    p = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE)
    out, err = p.communicate(input=main_scss.encode())
    if err:
        _LOGGER.error(err.decode("utf-8"))
    if p.wait() != 0:
        # sass may complain about usage on stdout if we have issues parametrizing.
        # Let's just hope we don't get any partially compiled css in here,
        # doesn't seem like it.
        for l in out.decode().splitlines():
            _LOGGER.error(l)
        raise MakeException("Running sass failed.")

    return out.decode()


def _compile_global_css(apps, pkg_paths, production, target_css_file,
                        branding_vars='', branding_styles='', source_map_style='comments'):
    puts("Compiling styles into %s" % target_css_file,
         put_timestamp=_puts_timestamp)

    main_scss = '{0}\n{1}{2}{3}\n{4}'.format(branding_vars,
                                             _TEMPLATE_VAR_THEME, _TEMPLATE_VAR, _TEMPLATE_STYLE,
                                             branding_styles)
    main_scss_template = main_scss
    for a in apps:
        main_scss = _compile_app_style(a, main_scss)
    _LOGGER.debug("Generated SCSS:\n%s", main_scss)
    # do nothing when scss file has not been changed
    if (main_scss_template == main_scss):
        _LOGGER.debug("No Styles found; Skip compiling...")
        # this will be replaced by the default css file
        css = ""
    else:
        _LOGGER.debug("Search paths:\n    %s", "\n    ".join(pkg_paths))
        css = _run_node_compiler(main_scss, pkg_paths, production)

    if css:
        old_styles = []
        if os.path.basename(target_css_file) == "global-style.css":
            puts("Calculating file hash", put_timestamp=_puts_timestamp)
            checksum = hashlib.sha256(css.encode('utf-8')).hexdigest()[-20:]
            puts("Hash is %s" % checksum, put_timestamp=_puts_timestamp)
            target_css_file = target_css_file.replace("global-style.css", "global-style.%s.css" % checksum)
            puts("New file target is %s" % target_css_file, put_timestamp=_puts_timestamp)
            files = os.listdir(CADDOK.BASE)
            old_styles = [os.path.join(CADDOK.BASE, cf) for cf in files if fnmatch.fnmatch(cf, 'global-style*.css')]
        with io.open(target_css_file, "wt", encoding="utf-8") as css_file:
            css_file.write(css)
        if old_styles:
            puts("Removing old global stylesheet(s)", put_timestamp=_puts_timestamp)
            for style_file in old_styles:
                if style_file != target_css_file:
                    os.remove(style_file)
        _LOGGER.info("Wrote global stylesheet to %s", target_css_file)
    else:
        _LOGGER.info("Copying stylesheet from platform, because no styles could be found.")
        shutil.copy(os.path.join(CADDOK.HOME, 'w3', 'images', 'global-style.css'),
                    target_css_file)
    puts("Compile Done!", put_timestamp=_puts_timestamp)


def _get_branding_styles():
    branding_pkg = modules.get_branding_package()
    branding_vars = ''
    branding_styles = ''
    branding_pkg_path = None
    branding_app = None
    if branding_pkg is not None:
        branding_module = modules.get_branding_module()
        _LOGGER.info("Collecting branding styles for %s", branding_module)
        branding_pkg_path = branding_pkg.location
        branding_dir = posixpath.join(branding_module.replace('.', "/"), 'styles')
        branding_var_path, branding_styles_path = (posixpath.join(branding_dir, f + '.scss')
                                                   for f in ('variables', 'styles'))

        if posixpath.isfile(posixpath.join(branding_pkg.location, branding_var_path)):
            branding_vars = "@import '%s';\n" % branding_var_path
        if posixpath.isfile(posixpath.join(branding_pkg.location, branding_styles_path)):
            branding_styles = "@import '%s';\n" % (branding_styles_path)
        branding_app = WebAppInfo(pkg_name=branding_pkg.project_name,
                                  pkg_path=branding_pkg_path,
                                  app_path="",
                                  component_name_space="")
    return branding_vars, branding_styles, branding_pkg_path, branding_app


def compile_styles(production=False, watch=False, output=None,
                   source_map_style='comments'):
    global _puts_timestamp

    if output is None:
        target_css_file = os.path.join(CADDOK.BASE, "global-style.css")
    else:
        target_css_file = output

    if watch:
        _puts_timestamp = True
        puts("Launching watch mode",
             put_timestamp=_puts_timestamp)

    branding_vars, branding_styles, branding_pkg_path, branding_app = _get_branding_styles()
    apps = find_webui_apps()
    if branding_app:
        apps.append(branding_app)
    pkg_paths = _collect_app_paths(apps, branding_pkg_path)

    # Sort the apps list to put the standard theme in front, followed by the
    # branding package. Python's sort is guaranteed to be stable, this means the
    # sort order is otherwise left as is.
    def keyfunc(app):
        if app.app_path == "cs/web/components/theme/js":
            return 1
        elif app.pkg_path == branding_pkg_path:
            return 2
        else:
            return 3
    apps.sort(key=keyfunc)

    def build_styles():
        _compile_global_css(apps,
                            pkg_paths, production, target_css_file,
                            branding_vars, branding_styles, source_map_style)

    if not watch:
        build_styles()
    else:
        puts('Doing initial compile...', _puts_timestamp)
        try:
            build_styles()
        except Exception:
            traceback.print_exc(file=sys.stderr)

        ob = observers.Observer()
        event_handler = ScssEventHandler(build_styles,
                                         patterns=['*.scss', '*.sass'])

        path_items = set(os.path.abspath(p) for p in pkg_paths)
        for p in path_items:
            # Check whether any parent directory is about to be scheduled for
            # watch mode. If this is the case, then this directory does not
            # need to be scheduled. This prevents multiple redundant
            # compilations on one file change.
            if not p.startswith(tuple(_p for _p in path_items if _p != p)):
                ob.schedule(event_handler, p, recursive=True)
                puts("Scheduled %s for watch mode" % p, _puts_timestamp)
        ob.start()
        while 1:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                puts("Watch mode shutting down...",
                     put_timestamp=_puts_timestamp)
                event_handler.compiler_thread.do_shutdown()
                return


def _compile_styles_cli(opts):
    compile_styles(opts.production, opts.watch, opts.output,
                    opts.source_map_style)


def add_parameters(subparsers):
    parser_styles = subparsers.add_parser('styles',
                                          help='compile all scss files into the global stylesheet')
    parser_styles.add_argument('--production', '-p',
                               default=False,
                               action='store_true',
                               help='Build styles for production(release)')
    parser_styles.add_argument('--watch', '-w',
                               default=False,
                               action='store_true',
                               help='Watch scss files for changes and recompile '
                                    'the global stylesheet')
    parser_styles.add_argument('-o', '--output',
                               help='Output file path. Default is "global-style.css" '
                                    'in the instance directory.')
    parser_styles.add_argument('--source-map-style',
                               choices=['comments', 'media-query'],
                               default='comments',
                               help='Determine how source map info should be rendered')
    parser_styles.set_defaults(func=_compile_styles_cli)
