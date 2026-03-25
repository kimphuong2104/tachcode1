from cdb import sig
from cs.variants import Variant
from cs.variants.web.common import COMPONENT_NAME as COMMON_COMPONENT_NAME
from cs.variants.web.common import VERSION as COMMON_VERSION
from cs.vp.bom.web.preview import VERSION as PREVIEW_VERSION
from cs.vp.bom.web.table import VERSION as BOM_TABLE_VERSION
from cs.web.components.generic_ui.detail_view import DETAIL_VIEW_SETUP


def add_threed_csp_header(request):
    # guard if threed is not installed
    try:
        from cs.threed.hoops.web.utils import add_csp_header

        request.after(add_csp_header)
    except ImportError:
        pass


@sig.connect(Variant, DETAIL_VIEW_SETUP)
def _app_setup(_, request, __):
    add_threed_csp_header(request)
    request.app.include("cs-vp-bom-web-table", BOM_TABLE_VERSION)
    request.app.include("cs-vp-bom-web-preview", PREVIEW_VERSION)
    request.app.include(COMMON_COMPONENT_NAME, COMMON_VERSION)
