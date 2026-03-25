# re-export the Workspaces bom readers under their old names (backwards compatibility)
from __future__ import absolute_import

from cdb.comparch import compatibility

from cs.wsm.bom.cadbominforeader import CADBomInfoReader, CADBomInfoReaderWithReferences
from cs.wsm.bom.componentstructurebomreader import (
    ComponentStructureBOMReader,
    RecursiveBOMReader,
)
from cs.wsm.bom.wsmbomreader import WSMBOMReader, filename_of_record, get_appinfo_tree

compatibility.provide(
    "cs.vp.bomcreator.cadbominforeader.CADBomInfoReader", CADBomInfoReader
)
compatibility.provide(
    "cs.vp.bomcreator.cadbominforeader.CADBomInfoReaderWithReferences",
    CADBomInfoReaderWithReferences,
)
compatibility.provide(
    "cs.vp.bomcreator.componentstructurebomreader.ComponentStructureBOMReader",
    ComponentStructureBOMReader,
)
compatibility.provide(
    "cs.vp.bomcreator.componentstructurebomreader.RecursiveBOMReader",
    RecursiveBOMReader,
)
compatibility.provide("cs.vp.bomcreator.wsmbomreader.WSMBOMReader", WSMBOMReader)
compatibility.provide(
    "cs.vp.bomcreator.wsmbomreader.filename_of_record", filename_of_record
)
compatibility.provide(
    "cs.vp.bomcreator.wsmbomreader.get_appinfo_tree", get_appinfo_tree
)
