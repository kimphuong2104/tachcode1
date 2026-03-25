from cdb import typeconversion, util
from cdb.platform import gui, mom
from cs.documents import Document


class CatalogDocumentIndicesData(gui.CDBCatalogContent):
    def __init__(self, catalog, z_nummer):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        if self.cdef:
            tabdef = self.cdef.getProjection(tabdefname, True)
        else:
            tabdef = tabdefname

        gui.CDBCatalogContent.__init__(self, tabdef)
        self.z_nummer = z_nummer
        self.data = None

    def _initData(self):
        indices = Document.KeywordQuery(
            z_nummer=self.z_nummer, order_by="cdb_cdate asc"
        )

        result = []
        result.append(util.get_label("valid_index"))

        if indices[0].z_index == "":
            result.append(util.get_label("initial_index"))
            # remove first entry from list in exchange for the 'initial index' label
            indices.pop(0)

        for i in indices:
            result.append(i.z_index)

        self.data = [{"z_index": r} for r in result]

    def getRowObject(self, row):
        if not self.cdef:
            return gui.CDBCatalogContent.getRowObject(self, row)
        else:
            self._initData()
            keys = mom.SimpleArgumentList()
            for keyname in ["z_index"]:
                keys.append(mom.SimpleArgument(keyname, self.data[row][keyname]))
            return mom.CDBObjectHandle(self.cdef, keys, False, True)

    def getNumberOfRows(self):
        self._initData()
        return len(self.data)

    def _get_value(self, rec, attr):
        """
        Retrieves the value of `attr` from the record `rec`-
        """
        result = ""
        result = rec[attr]
        return typeconversion.to_untyped_c_api(result)

    def getRowData(self, row):
        self._initData()
        result = []
        tdef = self.getTabDefinition()
        for col in tdef.getColumns():
            attr = col.getAttribute()
            value = ""
            try:
                obj = self.data[row]
                value = self._get_value(obj, attr)
                if not value:
                    value = ""
            except KeyError:
                value = ""
            result.append(value)
        return result


class CatalogDocumentIndices(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):
        try:
            self.z_nummer = self.getInvokingDlgValue("z_nummer")
        except KeyError:
            pass

        self.setResultData(CatalogDocumentIndicesData(self, self.z_nummer))
