from __future__ import absolute_import
from cs.vp.bomcreator import msg
from cs.vp.bomcreator.bomreader import BOMReader


class GenerateNoBOM(BOMReader):
    """
    Dummy BOM creator which does not actually create any BOM.
    """
    def __init__(self, bom_context, factory, _custom_state):
        self.boms = []
        bom_context.global_user_hints.append_error(msg('WSM_BOM_no_method_configured'))
