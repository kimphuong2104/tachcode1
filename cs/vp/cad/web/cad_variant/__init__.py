
import os

from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.base import byname_app
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel


def ensure_csp_header_set(request):
    try:
        from cs.threed.hoops.web.utils import add_csp_header
        request.after(add_csp_header)
    except ImportError:
        pass


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-vp-cad-web-cad_variant", "15.8.0",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-vp-cad-web-cad_variant.js")
    lib.add_file("cs-vp-cad-web-cad_variant.js.map")
    static.Registry().add(lib)


class CadVariantModel(SinglePageModel):
    page_name = "cs-vp-cad-variants"


class CadVariantApp(ConfigurableUIApp):

    def __init__(self):
        super(CadVariantApp, self).__init__()

    def update_app_setup(self, app_setup, model, request):
        super(CadVariantApp, self).update_app_setup(app_setup, model, request)
        try:
            from cs.threedlibs.web.communicator.main import VERSION
            self.include("cs-threedlibs-communicator", VERSION)
            self.include("cs-threed-hoops-web-cockpit", "15.5.1")
        except ImportError:
            # no preview will be displayed
            pass
        self.include("cs-vp-cad-web-cad_variant", "15.8.0")


@byname_app.BynameApp.mount(app=CadVariantApp, path="cs_vp_cad_variants")
def _mount_cad_variant_app():
    return CadVariantApp()


@CadVariantApp.path(path="{model_oid}", model=CadVariantModel, absorb=True)
def _get_cad_variant_model(absorb, model_oid):
    return CadVariantModel()


@CadVariantApp.view(model=CadVariantModel, name="base_path", internal=True)
def _get_cad_variant_base_path(model, request):
    ensure_csp_header_set(request)
    return request.path
