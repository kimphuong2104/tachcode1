# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
# import datetime
import logging

from cdb import fls, sig, sqlapi, util, ue
from cdb.objects.iconcache import IconCache
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.rqm_utils import RQMHierarchicals
from cs.requirements.web.rest.diff.acceptance_criterion_model import \
    ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID
from cs.requirements.web.rest.diff.deleted_model import DiffDeletedAPIModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

LOG = logging.getLogger(__name__)


class DiffCriterionRegistry(object):
    REGISTRY = None

    def __init__(self):
        self.clear()

    def clear(self):
        self._registered_criterions = {
            RQMSpecification.__maps_to__: {},
            RQMSpecObject.__maps_to__: {},
            TargetValue.__maps_to__: {}
        }
        self._registered_classes = set()
    
    @classmethod
    def dump(cls):
        registry = cls.get_registry()
        return {
            "registered_classes": registry._registered_classes,
            "registered_criterions": registry._registered_criterions,
        }
    
    @classmethod
    def load(cls, data):
        registry = cls.get_registry()
        new_data = data.copy()
        registry._registered_classes = new_data["registered_classes"]
        registry._registered_criterions = new_data["registered_criterions"]

    @classmethod
    def get_registry(cls):
        if cls.REGISTRY is None:
            cls.REGISTRY = DiffCriterionRegistry()
        return cls.REGISTRY

    def register_criterion(self, classes, key, label):
        if not key:
            LOG.warning('Cannot add diff criterions with empty key, will be ignored.')
            return
        for cls in classes:
            self._registered_classes.add(cls)
            if key in self._registered_criterions[cls.__maps_to__]:
                LOG.error('Double registration for %s, will not be overwritten.', key)
            elif key not in self._registered_criterions[cls.__maps_to__] and label:
                self._registered_criterions[cls.__maps_to__][key] = label
            else:
                LOG.warning(
                    'Cannot add empty label for key %s as a diff criterion, will be ignored.',
                    key
                )

    @classmethod
    def get_criterions(cls, entity):
        registry = cls.get_registry()
        return [
            {
                'id': key,
                'label': label
            } for (key, label) in registry._registered_criterions[entity.__maps_to__].items()
        ]

    @classmethod
    def get_settings_by_criterions(cls, criterions, languages):
        # maybe later directly within the ui but as of now hardcoded, spec/req according to selected, tv
        # activates all possible ones whenever the acceptancecriterion plugin is active
        tv_criterions = [
            x.get('id') for x in cls.get_criterions(TargetValue)
            if ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID in criterions
        ]

        spec_criterions = [
            x.get('id') for x in cls.get_criterions(RQMSpecification)
            if x.get('id') in criterions
        ]

        req_criterions = [
            x.get('id') for x in cls.get_criterions(RQMSpecObject)
            if x.get('id') in criterions
        ]

        criterions_per_class = {
            RQMSpecification.__maps_to__: spec_criterions,
            RQMSpecObject.__maps_to__: req_criterions,
            TargetValue.__maps_to__: tv_criterions
        }
        active_plugin_ids = set()
        for v in criterions_per_class.values():
            active_plugin_ids = active_plugin_ids.union(v)

        settings = dict(
            languages=languages,
            active_plugin_ids=active_plugin_ids,
            criterions_per_class=criterions_per_class
        )
        return settings


class DiffIndicatorAPIModel(object):

    def __init__(self, left_specification_object_id, right_specification_object_id):
        self.left_specification_object_id = left_specification_object_id
        self.right_specification_object_id = right_specification_object_id
        self.left_spec = RQMSpecification.ByKeys(cdb_object_id=self.left_specification_object_id)
        self.right_spec = RQMSpecification.ByKeys(cdb_object_id=self.right_specification_object_id)

    def check_access(self):
        if (
            self.left_spec and self.left_spec.CheckAccess('read') and
            self.right_spec and self.right_spec.CheckAccess('read')
        ):
            return True
        else:
            return False

    def get_full_pathes(self, cdb_object_ids):
        full_path_cache = {}
        sort_order_cache = {}
        if not cdb_object_ids:
            return full_path_cache, sort_order_cache
        elements_and_parents = RQMHierarchicals.get_parents(
            [
                {
                    'classname': 'cdbrqm_spec_object',
                    'cdb_object_id': x,
                    'specification_object_id': self.right_spec.cdb_object_id
                } for x in cdb_object_ids
            ]
        )
        for r in elements_and_parents:
            cdb_object_id = r['cdb_object_id']
            parent_object_id = r['parent_object_id']
            full_path_cache[cdb_object_id] = full_path_cache.get(
                parent_object_id, parent_object_id
            ) + '/' + cdb_object_id
            sort_order_cache[cdb_object_id] = r['sortorder']
        return full_path_cache, sort_order_cache

    @classmethod
    def get_added_and_deleted_tvs(cls, delete_api_model, additional_condition=None):
        new_tv_ids = delete_api_model.get_deleted_object_ids(
            switch_left_and_right=True,
            entity=TargetValue,
            additional_condition=additional_condition
        )
        deleted_tv_ids = delete_api_model.get_deleted_object_ids(
            switch_left_and_right=False,
            entity=TargetValue,
            additional_condition=additional_condition
        )
        return new_tv_ids, deleted_tv_ids

    def add_full_pathes_and_sortorders_for_tvs(self, full_pathes, sortorders, tv_ids):
        # calculate tv pathes/sortorders on the fly by using their parents pathes/sortorders
        # and position within
        for changed_id in tv_ids:
            tv_id, req_id, pos = changed_id
            full_path = full_pathes.get(req_id) + '/' + tv_id
            sortorder = sortorders.get(req_id) + '/%05d' % pos
            full_pathes[tv_id] = full_path
            sortorders[tv_id] = sortorder

    def add_affected_reqs_for_added_or_deleted_tvs(
            self,
            new_req_ids,
            new_tv_ids,
            deleted_tv_ids,
            enhanced_new_tv_ids,
            changed_req_ids,
            changed_ids
    ):
        deleted_or_changed_req_ids = set()
        tv_details_stmt = """
            SELECT cdb_object_id, requirement_object_id, pos
                FROM {table} WHERE {condition}
        """
        tv_details_stmt = tv_details_stmt.format(
            table=TargetValue.__maps_to__,
            condition=TargetValue.cdb_object_id.one_of(*(new_tv_ids + deleted_tv_ids))
        )
        res = sqlapi.RecordSet2(sql=tv_details_stmt)
        for record in res:
            if record['cdb_object_id'] in new_tv_ids:
                enhanced_new_tv_ids.append((
                    record['cdb_object_id'],
                    record['requirement_object_id'],
                    record['pos']
                ))
                if record['requirement_object_id'] not in new_req_ids:
                    # new requirements can never be "changed" because they are new
                    changed_req_ids.add(record['requirement_object_id'])
                    changed_ids.add(record['requirement_object_id'])
            if record['cdb_object_id'] in deleted_tv_ids:
                # deleted tv means changed req ->
                deleted_or_changed_req_ids.add(record['requirement_object_id'])
        changed_reqs_by_tv_stmt = """
            SELECT right_side.cdb_object_id
                FROM {table} left_side, {table} right_side
                    WHERE
                        left_side.specification_object_id='{left_spec_id}'
                        AND
                        right_side.specification_object_id='{right_spec_id}'
                        AND
                        left_side.ce_baseline_origin_id=right_side.ce_baseline_origin_id
                        AND
                        {left_condition}
        """.format(
            table=RQMSpecObject.__maps_to__,
            left_condition=(
                "{}".format(RQMSpecObject.cdb_object_id.one_of(*deleted_or_changed_req_ids)).replace(
                    'cdb_object_id', 'left_side.cdb_object_id'
                )
            ),
            left_spec_id=self.left_spec.cdb_object_id,
            right_spec_id=self.right_spec.cdb_object_id
        )
        res = sqlapi.RecordSet2(sql=changed_reqs_by_tv_stmt)
        for record in res:
            changed_req_ids.add(record['cdb_object_id'])
            changed_ids.add(record['cdb_object_id'])

    def get_icons(self):
        added_icon = {
            'src': IconCache.getIcon('cdbrqm_diff_added'),
            'title': util.get_label('web.rqm_diff.added_compare')
        }
        changed_icon = {
            'src': IconCache.getIcon('cdbrqm_diff_changed'),
            'title': util.get_label('web.rqm_diff.changed_compare')
        }
        indirect_icon = {
            'src': IconCache.getIcon('cdbrqm_diff_indirect_change'),
            'title': util.get_label('web.rqm_diff.changed_in_subtree')
        }
        return added_icon, changed_icon, indirect_icon

    def get_diff_indicator_for_all_tree_nodes(self, settings):
        # start = datetime.datetime.now()
        fls.allocate_license('RQM_070')
        delete_api_model = DiffDeletedAPIModel(
            self.left_specification_object_id,
            self.right_specification_object_id,
            self.left_spec,
            self.right_spec,
        )
        new_req_ids = delete_api_model.get_deleted_object_ids(
            switch_left_and_right=True,
            entity=RQMSpecObject
        )
        active_plugin_ids = settings.get('active_plugin_ids', [])
        new_tv_ids = []
        if ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID in active_plugin_ids:
            new_tv_ids, deleted_tv_ids = self.get_added_and_deleted_tvs(delete_api_model)
        new_ids = list(set(new_req_ids + new_tv_ids))
        # set of all changed objects -> cdb_object_id
        changed_ids = set()
        # set of changed req's -> cdb_object_id
        changed_req_ids = set()
        # set of changed tv's -> must be tuple (cdb_object_id, requirement_object_id, pos)
        changed_tv_ids = set()
        plugin_errors = []
        plugin_warnings = []
        plugin_labels = {plugin["id"]: plugin["label"] for plugin in DiffCriterionRegistry.get_criterions(RQMSpecObject)}
        for plugin_id in active_plugin_ids:
            results = sig.emit(
                RQMSpecification, "rqm_diff_plugins", "search", plugin_id)(
                self.left_spec, self.right_spec, settings
            )
            for result in results:
                changed_req_ids = changed_req_ids.union(result.get('changed_req_ids', set()))
                changed_tv_ids = changed_tv_ids.union(result.get('changed_tv_ids', set()))
                changed_ids = changed_ids.union(result.get('changed_ids', set()))
                if "errors" in result and result["errors"]:
                    plugin_errors.append({
                        "plugin_id": plugin_id, 
                        "title": util.get_label("cdbrqm_diff_plugin_errors") % plugin_labels[plugin_id],
                        "errors": result["errors"]
                    })
                if "warnings" in result and result["warnings"]:
                    plugin_warnings.append({
                        "plugin_id": plugin_id,
                        "title": util.get_label("cdbrqm_diff_plugin_warnings") % plugin_labels[plugin_id],
                        "warnings": result["warnings"]
                    })

        enhanced_new_tv_ids = []
        if ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID in active_plugin_ids:
            self.add_affected_reqs_for_added_or_deleted_tvs(
                new_req_ids,
                new_tv_ids,
                deleted_tv_ids,
                enhanced_new_tv_ids,
                changed_req_ids,
                changed_ids
            )

        changed_ids = list(changed_ids)
        changed_req_ids = list(changed_req_ids)
        changed_tv_ids = list(changed_tv_ids)
        # req full pathes/sortorders, spec and tv does not have them in db as of now
        full_pathes, sortorders = self.get_full_pathes(
            changed_req_ids + new_req_ids
        )
        if ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID in active_plugin_ids:
            self.add_full_pathes_and_sortorders_for_tvs(
                full_pathes, sortorders, changed_tv_ids + enhanced_new_tv_ids
            )
        added_icon, changed_icon, indirect_icon = self.get_icons()
        result_dict = {
            "plugin_errors": plugin_errors,
            "plugin_warnings": plugin_warnings
        }
        if new_ids:
            result_dict.update({
                "{}".format(k): {
                    'type': 'added',
                    'icon': added_icon,
                    'fullpath': full_pathes.get(k, ''),
                    'sortorder': sortorders.get(k, '')
                } for k in new_ids
            })
        if changed_ids:
            result_dict.update({
                "{}".format(k): {
                    'type': 'changed',
                    'icon': changed_icon,
                    'fullpath': full_pathes.get(
                        k,
                        '/' + self.right_spec.cdb_object_id if k == self.right_spec.cdb_object_id else ''
                    ),
                    'sortorder': sortorders.get(
                        k,
                        '00000' if k == self.right_spec.cdb_object_id else ''
                    )
                } for k in changed_ids
            })
        if new_ids or changed_ids:
            if self.right_spec.cdb_object_id not in changed_ids:
                result_dict.update({
                    self.right_spec.cdb_object_id: {
                        'type': 'indirect',
                        'icon': indirect_icon,
                        'sortorder': '/'
                    }
                })
            for p in full_pathes.values():
                for part in p.split('/'):
                    if part and part not in result_dict:
                        result_dict.update({
                            part: {
                                'type': 'indirect',
                                'icon': indirect_icon,
                                'sortorder': sortorders.get(part)
                            }
                        })
        return result_dict
