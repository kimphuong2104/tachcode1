from cs.costing.calculations import Calculation
from cs.costing.components import StepComponent, PartComponent, Component2Component


def generate_calculation(calc_name, **user_input):
    kwargs = dict(
        name=calc_name,
    )
    kwargs.update(**user_input)
    return Calculation.Create(**kwargs)


def generate_step_component(calc_id, step_name, parent_oid="", **user_input):
    kwargs = dict(
        calc_object_id=calc_id,
        parent_object_id=parent_oid,
        name=step_name,
        ml_name_de=step_name,
        ml_name_en=step_name,
    )
    kwargs.update(**user_input)
    return StepComponent.Create(**kwargs)


def generate_part_component(calc_id, part_name, parent_oid="", **user_input):
    kwargs = dict(
        calc_object_id=calc_id,
        parent_object_id=parent_oid,
        name=part_name,
        ml_name_de=part_name,
        ml_name_en=part_name,
    )
    kwargs.update(**user_input)
    return PartComponent.Create(**kwargs) 


def generate_comp2component(calc_id, comp_oid, parent_oid="", cloned=0, **user_input):
    kwargs = dict(
        calc_object_id=calc_id,
        parent_object_id=parent_oid,
        comp_object_id=comp_oid,
        cloned=cloned,
    )
    kwargs.update(**user_input)
    return Component2Component.Create(**kwargs)
