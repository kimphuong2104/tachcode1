import logging
import morepath

from cs.vp.bomcreator import UserHintList, GeneratedBOM, delete_unused_new_articles
from cs.vp.bomcreator.bomconfig import BOMColumn
from cs.vp.bomcreator.web.rest.bommodel import BOMModel


class SaveBOMsModel(object):
    """
    Save BOMs to the database
    and/or delete temporary files and items (cancel method).
    """
    def save(self, boms):
        """
        :param boms: dict(bom instance id -> {selected, itemIsModified, changedValues}
        """
        success, hints_after_import = self._save(boms)
        res = {'success': success,
               'messages': list(hints_after_import)}
        return res

    def save_single_bom(self, bom, request):
        """
        :param bom: one-element dict
        :return:
        """
        success, hints_after_import = self._save(bom, sync_after_write=True)
        if success:
            # directly return new BOM state
            instance_id = bom.keys()[0]
            return morepath.redirect(request.link(BOMModel(instance_id)))
        else:
            return {'success': success,
                    'messages': list(hints_after_import)
                    }

    def _save(self, boms, sync_after_write=False):
        success = True
        hints_after_import = UserHintList()
        all_boms = []
        written_boms = []

        for instance_id, bom_info in boms.items():
            b = GeneratedBOM.read_from_disk(instance_id)
            all_boms.append(b)
            # check if the user clicked on a temporary item;
            # in this case, we don't want to delete it
            if bom_info["itemIsModified"]:
                b.mark_assembly_as_modified()
            if bom_info["selected"]:
                # handle values edited in preview
                changed_values = bom_info["changedValues"]
                if changed_values:
                    self._add_changed_values(b, changed_values)
                # write bom to db
                if b.write(hints_after_import):
                    written_boms.append(b)
                else:
                    success = False

        if written_boms:
            first_bom_reader = written_boms[0].get_factory().reader if boms else None
            if first_bom_reader:
                first_bom_reader.post_write_boms(written_boms, hints_after_import)

        for bom in all_boms:
            bom.delete_temporary_json()

        if sync_after_write:
            # write updated JSON do disk (AFTER delete_temporary_json)
            for b in written_boms:
                b.assemblyIsTemporary = False  # after saving, the item will never be considered temporary
                b.synchronize()

        delete_unused_new_articles(all_boms)
        return success, hints_after_import

    def cancel(self, boms):
        full_boms = []
        for instance_id, bom_info in boms.items():
            b = GeneratedBOM.read_from_disk(instance_id)
            if bom_info["itemIsModified"]:
                b.mark_assembly_as_modified()
            full_boms.append(b)
            b.delete_temporary_json()
        delete_unused_new_articles(full_boms)

    def _add_changed_values(self, bom, changed_values):
        entries = bom.entries()
        for position, new_value in changed_values.items():
            try:
                row, column = position.split(",")
                row = int(row)
                column = int(column)
                entry = entries[row]
                expr, _, _ = entry.display_row.columns[column]
                if not BOMColumn.is_allowed_editable_attribute(expr):
                    raise ValueError("Attribute '%s' cannot be changed." % expr)
                entry.attrs[expr] = new_value
            except (ValueError, IndexError):
                logging.exception("SaveBomsModels: error adding changed value '%s' for position '%s.", new_value, position)
        # update the status of the BOM
        # so that it will be saved including the changes in preview
        bom.synchronize()
