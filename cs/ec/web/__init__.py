
from cdb import sig
from cs.web.components.generic_ui.detail_view import DETAIL_VIEW_SETUP

from cs.ec import EngineeringChange


def ensure_csp_header_set(request):
    try:
        from cs.threed.hoops.web.utils import add_csp_header
        request.after(add_csp_header)
    except ImportError:
        pass


@sig.connect(EngineeringChange, DETAIL_VIEW_SETUP)
def _app_setup(clsname, request, app_setup):
    ensure_csp_header_set(request)
