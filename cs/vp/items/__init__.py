#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# -*- Python -*-
# $Id$
# CDB:Browse
# Copyright (C) 1990 - 2006 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     Items.py
# Author:   aki
# Creation: 28.07.06
# Purpose:

# pylint: disable-msg=E0102,W0142,W0212,W0201

__all__ = ['Item', 'Part', 'Assembly']


import re
import string

from cdb import ue
from cdb import sqlapi
from cdb import util
from cdb import sig
from cdb import CADDOK
from cdb import cdbuuid
from cdb.classbody import classbody

from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Rule
from cdb.objects import LocalizedField
from cdb.objects import Reference_1
from cdb.objects import ReferenceMethods_N
from cs.tools.powerreports import WithPowerReports
from cs.materials import Material
from cs.metrics.qcclasses import WithQualityCharacteristic

from cs.workflow import briefcases
from cs.actions import Action

from cs.tools.batchoperations import WithBatchOperations
from cs.sharing.share_objects import WithSharing

_DOCUMENTS_FOR_IMAGE_PREVIEW_RULE = "Part Preview: Image Documents"

ProcessPartReference = Forward(__name__ + ".ProcessPartReference")
Item = Forward(__name__ + ".Item")


class Item(Object, WithPowerReports, WithQualityCharacteristic,
           WithBatchOperations, briefcases.BriefcaseContent, WithSharing):
    __maps_to__ = "teile_stamm"

    # LocalizedFields are legacy - DON'T USE IT
    # use the i18n_benennung field instead
    designation = LocalizedField("designation",
                                 de="benennung",
                                 en="eng_benennung",
                                 fr="fra_benennung",
                                 it="it_benennung",
                                 es="spa_benennung",
                                 cs="cs_benennung",
                                 ja="ja_benennung",
                                 ko="ko_benennung",
                                 pl="pl_benennung",
                                 pt="pt_benennung",
                                 tr="tr_benennung",
                                 zh="zh_benennung")

    # erhaelt eine Liste mit Indexstufen (z.B. [1,4,3]) und erzeugt hieraus einen Index-String "1.4.3"
    def _createIndex(self, myindex):
        index_str = None
        for x in myindex:
            if index_str:
                index_str += '.' + "%d" % (x)
            else:
                index_str = "%d" % (x)
        return index_str

    def isAssembly(self):
        return self.baugruppenart == "Baugruppe"

    def setItemNumber(self, ctx):
        if self.teilenummer in ["", "#", None]:
            # automatische Nummerung
            self.teilenummer = self.MakeItemNumber()
        elif re.compile('^((M-)\d+)$').match(self.teilenummer) is not None:
            # manuelle Nummerung
            pass
        elif self.teilenummer[:5] == '#CON-':
            # Contact Nummerung fuer Demodaten
            self.teilenummer = self.MakeItemNumber(self.teilenummer[1:])
        else:
            raise ue.Exception("cdb_konfstd_015", "M-")

    @classmethod
    def MakeItemNumber(cls, prefix=None, num_digits=6):
        myformat = "%s%0" + "%d" % (num_digits) + "d"
        if prefix:
            t = sqlapi.SQLselect("max(teilenummer) FROM teile_stamm WHERE teilenummer like '%s%%'" % (prefix))
            maxtnr = sqlapi.SQLstring(t, 0, 0)[len(prefix):]
            if not maxtnr.isdigit():
                result = myformat % (prefix, 1)
            else:
                result = myformat % (prefix, int(maxtnr) + 1)
        else:
            result = myformat % ("", util.nextval("part_seq"))
        max_len = util.tables['teile_stamm'].column('teilenummer').length()
        if len(result) > max_len:
            # Die Artikelnummer ueberschreitet die maximale Laenge von 20 Zeichen.
            raise ue.Exception("cdb_konfstd_014", "%d" % (max_len))
        return result

    def setItemIndex(self, ctx):
        """ Setzt initialen Artikelindex gemaess Indexschema, wenn Index leer ist.
        Prueft auf korrektes Indexschema, wenn Index nicht leer ist."""

        indx = util.get_prop("indx")
        idx0 = util.get_prop("idx0")
        if len(idx0) == 0:
            # Der initale Index kann nicht bestimmt werden. Das Property %s ist nicht korrekt gesetzt.
            raise ue.Exception("cdb_konfstd_016", "idx0")
        if not self.t_index:
            if idx0 == 'false':
                self.t_index = ''
                return
            else:
                # initialen Index setzen
                count = sqlapi.SQLstring(sqlapi.SQLselect("COUNT(*) FROM teile_stamm WHERE teilenummer = '%s'"
                                                          % self.teilenummer), 0, 0)
                if count == '0':
                    self.t_index = indx
        else:
            # Index pruefen
            rs = '^'
            for i in indx:
                if i in string.digits:
                    rs = rs + '[0-9]+'
                elif i in string.ascii_lowercase:
                    rs = rs + '[a-z]'
                elif i in string.ascii_uppercase:
                    rs = rs + '[A-Z]'
                else:
                    # Der initale Index kann nicht bestimmt werden. Das Property %s ist nicht korrekt gesetzt.
                    raise ue.Exception("cdb_konfstd_016", "indx")
            rs = rs + '$'
            if re.compile(rs).match(self.t_index) is None:
                # Index '%s' entspricht nicht dem vorgegebenen Indexschema
                raise ue.Exception("cdb_konfstd_019", self.t_index)

    def CreateIndex(self, new_index="", **kwargs):
        index_created = _createPartIndex(self.teilenummer, self.t_index, new_index, **kwargs)
        indexed_object = Item.ByKeys(teilenummer=self.teilenummer, t_index=index_created)
        return indexed_object

    def GetDisplayAttributes(self):
        results = super(Item, self).GetDisplayAttributes()
        heading = list()
        if self.t_kategorie:
            heading.append(self.t_kategorie_name)
        if self.sachgruppe:
            heading.append(self.sachgruppe)
        results["attrs"]["heading"] = " - ".join(heading)
        results["attrs"]["person"] = self.t_bereich
        return results

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the project and the object itself.
        """
        return [self, self.Project] if hasattr(self, "Project") else [self]

    def _set_copy_of(self, ctx):
        if ctx.action == "index":
            pObj = self.getPersistentObject()
            if pObj:
                pObj.cdb_copy_of_item_id = ctx.cdbtemplate.cdb_object_id
        else:
            self.cdb_copy_of_item_id = ctx.cdbtemplate.cdb_object_id

    def set_bom_type_default(self, ctx):
        from cs.vp.bom import BomType
        if self.type_object_id == "":
            self.type_object_id = BomType.GetBomTypeForCode("eBOM").cdb_object_id

    def _reset_olc_status(self, ctx):
        """Workaround for E068539: Creation of joined object differs between PC Client and Web UI
        Ensures that the status of a newly created Item is set to 0, especially when using
        Workspaces Desktop"""

        self.status = 0

    event_map = {
        ('copy', ('pre_mask', 'pre')): ("_set_copy_of"),
        ('index', ('post')): ("_set_copy_of"),
        ('create', ('pre', 'pre_mask')): ('set_bom_type_default'),
        ('create', 'pre'): ('_reset_olc_status'),
    }

    def _getVersions(self):
        # implemented as ReferenceMethods_N, because CADDOK.SQLDBMS_STRLEN must
        # not be evaluated when importing this module!
        idx_len = '%s(t_index)' % CADDOK.SQLDBMS_STRLEN
        return Item.KeywordQuery(order_by=[idx_len, 't_index'],
                                 teilenummer=self.teilenummer)
    Versions = ReferenceMethods_N(Item, _getVersions)

    @classmethod
    def GetLatestObjectVersion(cls, items):
        """ Used by the REST API, this gets a list of item versions, and
            returns the latest released version from this list. If no such
            version exists, try in_revision versions, and as a fallback just
            take the latest versions.
        """
        # First of all, sort by index, so that we can return the highest index
        # if more than one match.
        sorted_items = sorted(items, key=lambda i: (len(i.t_index), i.t_index))
        # TODO: define rules for this
        released = [i for i in sorted_items if i.status in (200, 300)]
        if released:
            return released[-1]
        in_revision = [i for i in sorted_items if i.status == 190]
        if in_revision:
            return in_revision[-1]
        # Fallback: just return the highest index
        return sorted_items[-1] if sorted_items else None

    @classmethod
    def ItemFromRestKey(cls, vals):
        # Keys may be:
        #   part_number
        #   part_number + part_index
        #   part_number + function_name
        if len(vals) == 1:
            items = cls.KeywordQuery(teilenummer=vals[0]).Execute()
            # If there is more than one part, but no more keys, return the
            # latest version. Call the function with a part instance, so that
            # a customer subclass can override this.
            # Note: assumes that all versions of a part are of the same class!
            return items[0].GetLatestObjectVersion(items) if items else None
        elif len(vals) == 2:
            # is it a part index ...
            item = cls.ByKeys(*vals)
            if item is not None:
                # OK, found as index
                return item
            items = cls.KeywordQuery(teilenummer=vals[0]).Execute()

            # ... or a function (see comment above)
            if len(items) > 0 and \
                hasattr(items[0], vals[1]) and \
                callable(getattr(items[0], vals[1])):
                return getattr(items[0], vals[1])(items)

            # don't know what to do with the key
            return None
        else:
            raise ValueError("ItemFromRestKey: cannot interpret %s" % vals)

    def calc_erp_number(self):
        result = ""
        if self.cdb_objektart == "part_ERP":
            if self.type_object_id and self.cdb_depends_on:
                item = Item.ByKeys(cdb_object_id=self.cdb_depends_on)
                if item:
                    result = item.materialnr_erp if item.materialnr_erp else item.teilenummer
            else:
                result = self.teilenummer
        return result

    def clear_erp_number(self, ctx):
        if not self.cdb_depends_on:
            self.materialnr_erp = ""

    def get_preview_documents(self, preview_document_rule=None, from_master_item=True):
        """
        Collects all suitable documents to use as a preview document. Only documents matching all the
        following criteria are collected for the preview:

        - If preview_document_rule is None (default), only documents of class model are collected.
        - If preview_document_rule is set, only documents matching preview_rule are collected.
        - The document strongly references the Item by teilenummer/t_index.

        If from_master_item is set to True (default) and self is a derived BOM, the preview documents will be
        collected from the master BOM instead. When from_master_item is set to False, the documents are
        collected from self even if it is a derived BOM.

        :return: List of all suitable documents
        :rtype: list
        """

        # If from_master_item, recurse until toplevel master to collect preview documents. This is useful
        # if only the master has the documents/models attached instead of the derived items.
        if from_master_item and self.EngineeringView:
            return self.EngineeringView.get_preview_documents(preview_document_rule, from_master_item)

        docs = self.Documents

        if preview_document_rule is None:
            return [doc for doc in docs if doc.isModel()]

        models = []
        non_models = []
        for doc in docs:
            if not preview_document_rule.match(doc):
                continue

            # Prioritize models before others for preview.
            if doc.isModel():
                models.append(doc)
            else:
                non_models.append(doc)

        return models + non_models

    def get_image_preview_file(self):
        """
           Searches the passed documents for a file with a suitable file type for image preview. Only a single
           image is determined as a "best match" by the following priority:

           - If a suitable derived/associated file is present, it is returned immediately.
           - If no suitable derived/associated file is present, a suitable primary file is returned.
           - If no suitable primary file is present, the first suitable remaining file is returned.

           :return: CDB_File a suitable file, if found, `None` else.
           :rtype: CDB_File
        """
        from cs.vp.cad import SUPPORTED_IMAGE_TYPES

        docs_for_preview_rule = Rule.ByKeys(_DOCUMENTS_FOR_IMAGE_PREVIEW_RULE)
        docs_for_preview = self.get_preview_documents(docs_for_preview_rule, from_master_item=True)

        found_primary = None
        found_other = None
        for doc in docs_for_preview:

            files = doc.Files

            for f in files:
                if not SUPPORTED_IMAGE_TYPES.contains(f.cdbf_type):
                    continue

                # Return immediately if there is a supported derived/associated file, because it is likely the
                # best choice for the preview.
                if f.cdbf_derived_from or f.cdb_belongsto:
                    return f

                # Remember first encountered primary file as fallback.
                if f.cdbf_primary == "1" and found_primary is None:
                    found_primary = f

                # Remember first encountered other file as fallback.
                if f.cdbf_primary != "1" and found_other is None:
                    found_other = f

        # Return fallback in case no supported derived/associated was found.
        if found_primary:
            return found_primary
        else:
            return found_other

    def GetThumbnailFile(self):
        return self.get_image_preview_file()

    def IsDerived(self):
        """
        Checks if this item is derived from an eBOM.

        :return: true if this item is derived, false else
        :rtype: bool
        """
        from cs.vp.bom import get_ebom_bom_type
        ebom_bom_type_id = get_ebom_bom_type().cdb_object_id
        return self.type_object_id is not None and self.type_object_id != ebom_bom_type_id


def visit_dfs(item):
    for comp in item.Components:
        for obj in visit_dfs(comp.Item):
            yield obj
        yield comp


@sig.connect(Item, 'copy', 'pre')
@sig.connect(Item, 'create', 'pre')
def _set_erp_number(obj, ctx):
    if not obj.materialnr_erp:
        obj.materialnr_erp = obj.calc_erp_number()


@sig.connect(Item, 'copy', 'pre_mask')
def _clear_erp_number(obj, ctx):
    obj.clear_erp_number(ctx)


@sig.connect(Item, 'delete', 'post')
def _clear_product2part_link(obj, ctx):
    try:
        sqlapi.SQLdelete(
            "FROM cdbvp_product2part WHERE teilenummer='%s' and t_index='%s'" % (obj.teilenummer, obj.t_index))
    except RuntimeError as ex:
        pass


class Part(Item):
    """deprecated: Use the Item class instead"""
    __match__ = Item.baugruppenart != 'Baugruppe'


class Assembly(Item):
    """deprecated: Use the Item class instead"""
    __match__ = Item.baugruppenart == 'Baugruppe'


@classbody
class Action(object):
    Item = Reference_1(Item, Action.teilenummer, Action.t_index)


class ItemCategory(Object):
    __maps_to__ = "cdb_part_categ"


def createPartIndex(teilenummer, t_index, t_index_new=None,
                    cdb_ta_t="", cdb_taa_t=""):
    """
    Indizieren eines Teils.

    teilenummer und t_index identifizieren das zu indizierende
    Teil. In t_index_new kann der neue Index vorgegeben werden, falls
    nicht, wird ein neuer Index nach den konfigurierten Vorgaben
    berechnet.
    cdb_ta_t, cdb_taa_t: Technische Aenderungen: DEPRECATED

    Zurueckgegeben wird der neue Teileindex.
    """
    import warnings
    warnings.warn("createPartIndex is deprecated. "
                  "Use Item.CreateIndex instead.",
                  DeprecationWarning,
                  stacklevel=2)
    return _createPartIndex(teilenummer, t_index, t_index_new,
                            cdb_ta_t, cdb_taa_t)


def _createPartIndex(teilenummer, t_index, t_index_new=None,
                     cdb_ta_t="", cdb_taa_t=""):
    """
    See `createPartIndex`
    """
    from cdb.platform import mom
    from cdb.platform.mom import entities
    import cdbwrapc
    cldef = entities.CDBClassDef("part")
    part = mom.getObjectHandle(cldef, teilenummer=teilenummer, t_index=t_index)
    args = []
    if t_index_new:
        args.append(mom.SimpleArgument("cdb::argument.t_index_neu", t_index_new))
    indexop = cdbwrapc.Operation("CDB_Index", part, args)
    indexop.run()
    new_part = indexop.getObjectResult()
    return new_part["t_index"]


class PartUnit(Object):
    __classname__ = "cdb_units"
    __maps_to__ = "cdb_units"


class PartName(Object):
    __classname__ = "woerter"
    __maps_to__ = "woerter"

    def make_id(self, ctx):
        if not self.wort or ctx.action == "copy":
            self.wort = cdbuuid.create_uuid()

    event_map = {
        (("create", "copy"), "pre"): "make_id"
    }

class PartSurface(Object):
    __classname__ = "cdb_part_surfac"
    __maps_to__ = "cdb_part_surfac"

class PartUsageStatus(Object):
    __classname__ = "cdb_part_usab"
    __maps_to__ = "cdb_part_usab"

class PartStatusProtocol(Object):
    __classname__ = "cdb_t_statiprot"
    __maps_to__ = "cdb_t_statiprot"

class PartCustomer(Object):
    __classname__ = "cdb_part_cust"
    __maps_to__ = "cdb_part_cust"


class PartMaturity(Object):
    __classname__ = "cdbecm_maturity"
    __maps_to__ = "cdbecm_maturity"


@classbody
class Material:

    def checkMaterialUsage(self, ctx):
        """Check if a material is in use and reject deletion if it is used in at least one part"""

        count = sqlapi.SQLinteger(sqlapi.SQLselect("COUNT(*) FROM teile_stamm WHERE material_object_id='{}'"
                                                   .format(self.cdb_object_id)), 0, 0)
        if count > 0:
            raise ue.Exception("cdbvp_err_material_inuse")

    event_map = {
        ('delete', 'pre'): "checkMaterialUsage"
    }
