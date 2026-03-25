from __future__ import absolute_import
from cdb.objects import IconCache
from cs.platform.web.root import Internal
from cs.platform.web import JsonAPI
from cs.costing.calculations import Calculation


class CalculationSelectiveStructureApp(JsonAPI):
    def __init__(self):
        pass


class CalculationCloneAttributesApp(JsonAPI):
    def __init__(self):
        pass


@Internal.mount(app=CalculationSelectiveStructureApp, path="cs-costing-selectivestructure")
def _mount_app():
    return CalculationSelectiveStructureApp()


@Internal.mount(app=CalculationCloneAttributesApp, path="cs-costing-clone_attributes")
def _mount_app():
    return CalculationCloneAttributesApp()


class SelectiveStructureTree(object):
    def __init__(self, calc_object_id, teilenummer_t_index):

        self.calc = Calculation.ByKeys(calc_object_id)
        teile_index = teilenummer_t_index.split(":")
        self.teilenummer = teile_index[0]
        if (len(teile_index) > 1):
            self.t_index = teile_index[1]
        else:
            self.t_index = ""

    def create_structure(self):
        from cdb import sqlapi
        from cs.vp.items import Item
        dict_list = []
        calculationobj = self.calc
        dbscript = {sqlapi.DBMS_ORACLE: calculationobj._get_structure_oracle,
                    sqlapi.DBMS_MSSQL: calculationobj._get_structure_mssql,
                    sqlapi.DBMS_SQLITE: calculationobj._get_structure_other}
        dbtype = sqlapi.SQLdbms()
        func = dbscript.get(dbtype, calculationobj._get_structure_other)
        bom_from_item = Item.ByKeys(self.teilenummer, self.t_index)
        if not bom_from_item:
            return []
        dict_list.append({"description": bom_from_item.GetDescription(),
                          "level": 0,
                          "cdb_object_id": bom_from_item.cdb_object_id,
                          "icon": IconCache.getIcon("cdb_part") + bom_from_item.t_kategorie,
                          "parent_object_id": '',
                          "material_object_id": bom_from_item.material_object_id,
                          "mengeneinheit": bom_from_item.mengeneinheit,
                          "cost_unit": bom_from_item.mengeneinheit,
                          "teilenummer": bom_from_item.teilenummer,
                          "t_index": bom_from_item.t_index,
                          "quantity": 1.0,
                          "part_object_id": bom_from_item.cdb_object_id,
                          "curr_object_id": self.calc.curr_object_id,
                          "calc_object_id": self.calc.cdb_object_id,
                          "costplant_object_id": self.calc.costplant_object_id,
                          "subject_id": self.calc.subject_id,
                          "subject_type": self.calc.subject_type})

        result = func(bom_from_item=bom_from_item)

        for i, r in enumerate(result):
            real_item = Item.ByKeys(r["teilenummer"], r["t_index"])
            d = {}
            d["description"] = real_item.GetDescription()
            d["level"] = r["stufe"]
            d["cdb_object_id"] = r["cdb_object_id"]
            d["icon"] = IconCache.getIcon("cdb_part") + real_item.t_kategorie
            d["material_object_id"] = r["material_object_id"]
            d["mengeneinheit"] = r["mengeneinheit"]
            d["cost_unit"] = r["mengeneinheit"]
            d["teilenummer"] = r["teilenummer"]
            d["t_index"] = r["t_index"]
            d["part_object_id"] = r["cdb_object_id"]
            d["quantity"] = r["menge"]
            d["curr_object_id"] = self.calc.curr_object_id
            d["calc_object_id"] = self.calc.cdb_object_id
            d["costplant_object_id"] = self.calc.costplant_object_id
            d["subject_id"] = self.calc.subject_id
            d["subject_type"] = self.calc.subject_type

            if i == 0:
                d["parent_object_id"] = dict_list[0]["cdb_object_id"]
            elif r["stufe"] - result[i - 1]["stufe"] == 1:
                d["parent_object_id"] = result[i - 1]["cdb_object_id"]
            elif r["stufe"] == 1:
                d["parent_object_id"] = dict_list[0]["cdb_object_id"]
            elif r["stufe"] - result[i - 1]["stufe"] == 0:
                d["parent_object_id"] = dict_list[i]["parent_object_id"]
            else:
                pass

            dict_list.append(d)

        final_dict = {}

        for i, m in enumerate(dict_list):
            m["children"] = []
            if m["level"] == 0:
                continue
            if (m["parent_object_id"] == dict_list[i - 1]["cdb_object_id"]):
                if "children" in dict_list[i - 1]:
                    children1 = []
                    children1.extend(dict_list[i - 1]["children"])
                    children1.append(m)
                    dict_list[i - 1]["children"] = children1
                else:
                    dict_list[i - 1]["children"] = m
            else:
                for k in dict_list:
                    if m["parent_object_id"] == k["cdb_object_id"]:
                        if "children" in k:
                            children2 = []
                            children2.extend(k["children"])
                            children2.append(m)
                            k["children"] = children2

        return dict_list[0]


@CalculationSelectiveStructureApp.path(path='{calc_object_id}/{teilenummer_t_index}', model=SelectiveStructureTree)
def get_state_color_model(calc_object_id, teilenummer_t_index):
    return SelectiveStructureTree(calc_object_id, teilenummer_t_index)


@CalculationSelectiveStructureApp.json(model=SelectiveStructureTree, request_method="GET")
def default_view(model, request):
    return model.create_structure()


class CloneAttributes(object):
    def __init__(self, calc_object_id):
        self.calc = Calculation.ByKeys(calc_object_id)

    def get_clone_attributes(self):
        clone_attributes = {}
        for topcomponent in self.calc.TopComponents:
            top_comp_key = "%s@|" % (topcomponent.cdb_object_id)
            clone_attributes[top_comp_key] = {}
            clone_attributes[top_comp_key]["quantity"] = topcomponent.quantity
            cstruct = self.calc.get_components_from_structure(topcomponent)
            for c in cstruct:
                if type(c) == tuple:
                    # sqlite specific code
                    if c[1]:
                        comp = c[1]
                        comp_key = "%s@%s|%s" % (comp.comp_object_id, comp.parent_object_id, comp.cdb_object_id)
                        clone_attributes[comp_key] = {}
                        clone_attributes[comp_key]["quantity"] = comp.quantity
                    else:
                        comp = c[0]
                        comp_key = "%s@%s|" % (comp.cdb_object_id, comp.parent_object_id)
                        clone_attributes[comp_key] = {}
                        clone_attributes[comp_key]["quantity"] = comp.quantity
                else:
                    # code for non-sqlite dbms
                    comp_key = "%s@%s|%s" % (c.cdb_object_id, c.combined_parent, c.combined_id)
                    clone_attributes[comp_key] = {}
                    clone_attributes[comp_key]["quantity"] = c.combined_quantity
        return clone_attributes


@CalculationCloneAttributesApp.path(path='{calc_object_id}',
                                       model=CloneAttributes)
def get_clone_attributes(calc_object_id):
    return CloneAttributes(calc_object_id)


@CalculationCloneAttributesApp.json(model=CloneAttributes, request_method="GET")
def default_view(model, request):
    return model.get_clone_attributes()
