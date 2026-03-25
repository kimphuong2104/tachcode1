import unittest
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.web.rest.diff.acceptance_criterion_model import \
    ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID
from cs.requirements.web.rest.diff.diff_indicator_model import (
    DiffCriterionRegistry)


# class TestDiffCriterionRegistry(unittest.TestCase):
#     def setUp(self):
#         self.registry = DiffCriterionRegistry.get_registry()
#         self.origin_registry_contents = self.registry.dump()
#         self.registry.clear()
    
#     def tearDown(self) -> None:
#         self.registry.load(self.origin_registry_contents)
#         return super().tearDown()

#     def _assert_empty_registry(self):
#         self.assertEqual(
#             self.registry.get_criterions(RQMSpecification),
#             []
#         )
#         self.assertEqual(
#             self.registry.get_criterions(TargetValue),
#             []
#         )

#     def test_register_diff_plugin_for_one_entity(self):
#         self._assert_empty_registry()
#         self.registry.register_criterion(
#             [RQMSpecification],
#             'test_plugin_id',
#             'test_plugin_label'
#         )
#         criterions = self.registry.get_criterions(RQMSpecification)
#         self.assertEqual(len(criterions), 1)
#         criterions = self.registry.get_criterions(TargetValue)
#         self.assertEqual(len(criterions), 0)

#     def test_register_diff_plugin_for_multiple_entities(self):
#         self._assert_empty_registry()
#         self.registry.register_criterion(
#             [RQMSpecification, TargetValue],
#             'test_plugin_id',
#             'test_plugin_label'
#         )
#         criterions = self.registry.get_criterions(RQMSpecification)
#         self.assertEqual(len(criterions), 1)
#         criterions = self.registry.get_criterions(TargetValue)
#         self.assertEqual(len(criterions), 1)

#     def test_registration_name_collision(self):
#         self._assert_empty_registry()
#         self.test_register_diff_plugin_for_one_entity()
#         self.registry.register_criterion(
#             [RQMSpecification],
#             'test_plugin_id',
#             'another_label'
#         )
#         criterions = self.registry.get_criterions(RQMSpecification)
#         self.assertEqual(len(criterions), 1)
#         tv_criterions = self.registry.get_criterions(TargetValue)
#         self.assertEqual(len(tv_criterions), 0)
#         self.assertEqual(criterions[0]['id'], 'test_plugin_id')
#         # we expect that the first registration is used
#         self.assertEqual(criterions[0]['label'], 'test_plugin_label')

#     def test_registration_special_handling_for_acceptance_criteria(self):
#         self._assert_empty_registry()
#         self.registry.register_criterion(
#             [RQMSpecification],
#             'test_plugin_id',
#             'test_plugin_label'
#         )
#         self.registry.register_criterion(
#             [RQMSpecification],
#             'test_plugin_id2',
#             'test_plugin_label2'
#         )
#         criterions = ['test_plugin_id']
#         languages = ['de', 'en']
#         settings = self.registry.get_settings_by_criterions(criterions, languages)
#         self.assertIn('test_plugin_id', settings.get('active_plugin_ids'))
#         self.assertNotIn('test_plugin_id2', settings.get('active_plugin_ids'))
#         self.assertIn(
#             'test_plugin_id', settings.get('criterions_per_class').get(RQMSpecification.__maps_to__)
#         )
#         self.assertNotIn(
#             'test_plugin_id2', settings.get('criterions_per_class').get(RQMSpecification.__maps_to__)
#         )
#         self.assertNotIn(
#             'test_plugin_id', settings.get('criterions_per_class').get(TargetValue.__maps_to__)
#         )
#         self.assertNotIn(
#             'test_plugin_id2', settings.get('criterions_per_class').get(TargetValue.__maps_to__)
#         )
#         self.registry.clear()
#         self.registry.register_criterion(
#             [RQMSpecification, TargetValue],
#             'test_plugin_id',
#             'test_plugin_label'
#         )
#         self.registry.register_criterion(
#             [RQMSpecification, TargetValue],
#             'test_plugin_id2',
#             'test_plugin_label2'
#         )
#         criterions = ['test_plugin_id', ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID]
#         settings = self.registry.get_settings_by_criterions(criterions, languages)
#         self.assertIn('test_plugin_id', settings.get('active_plugin_ids'))
#         # special as it is active now for tvs
#         self.assertIn('test_plugin_id2', settings.get('active_plugin_ids'))
#         self.assertIn(
#             'test_plugin_id', settings.get('criterions_per_class').get(RQMSpecification.__maps_to__)
#         )
#         self.assertNotIn(
#             'test_plugin_id2', settings.get('criterions_per_class').get(RQMSpecification.__maps_to__)
#         )
#         self.assertIn(
#             'test_plugin_id', settings.get('criterions_per_class').get(TargetValue.__maps_to__)
#         )
#         # special -
#         # if ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID in criterions all plugins should be active for tv's
#         self.assertIn(
#             'test_plugin_id2', settings.get('criterions_per_class').get(TargetValue.__maps_to__)
#         )
#         self.assertEqual(settings.get('languages'), languages)
