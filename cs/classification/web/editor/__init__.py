
import os

from cdb import sig
from cdb import rte

from cs.platform.web import static
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK  # @UnresolvedImport

COMPONENT_NAME = "cs-classification-web-editor"
COMPONENT_NAME_THIRDPARTY = "cs-classification-web-editor-thirdparty"
COMPONENT_VERSION = "15.4.0"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():

    lib_path = os.path.join(os.path.dirname(__file__), "js", "build")

    lib = static.Library(COMPONENT_NAME, COMPONENT_VERSION, lib_path)
    lib.add_file(COMPONENT_NAME + ".js")
    lib.add_file(COMPONENT_NAME + ".js.map")
    static.Registry().add(lib)

    # Register dynamically loaded stuff as a separate lib, so that they can be
    # loaded, but will not load on startup.
    lib = static.Library(COMPONENT_NAME_THIRDPARTY, COMPONENT_VERSION, lib_path)
    lib.add_file(COMPONENT_NAME_THIRDPARTY + ".js")
    lib.add_file(COMPONENT_NAME_THIRDPARTY + ".js.map")
    lib.add_file('editor.worker.js')
    lib.add_file('editor.worker.js.map')
    static.Registry().add(lib)


@sig.connect(GLOBAL_APPSETUP_HOOK)
def _update_app_setup(app_setup, request):
    lib = static.Registry().get(COMPONENT_NAME_THIRDPARTY, COMPONENT_VERSION)
    fname = lib.find_hashed_filepath(COMPONENT_NAME_THIRDPARTY + ".js")
    app_setup.merge_in([COMPONENT_NAME], {
        'thirdparty_url': '{}/{}'.format(lib.url(), os.path.basename(fname)),
        'editor_worker_url': '{}/editor.worker.js'.format(lib.url())
    })
