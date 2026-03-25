from cdb import util


def set_index_readonly(hook):
    newVals = hook.get_new_values()
    classname = hook.get_operation_state_info().get_classname()
    index_field = f"{classname}.tmpl_index"

    if newVals[classname + ".z_nummer"] != "":
        hook.set_writeable(index_field)
        hook.set(index_field, util.get_label("valid_index"))
    else:
        hook.set_readonly(index_field)
        hook.set(index_field, None)
