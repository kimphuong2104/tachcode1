# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import argparse

from cdb.platform.gui import MaskReg, MaskComp, MenuTree, Table
from cdb.platform.mom.operations import OperationConfig, OperationOwner
from cdb.dberrors import DBConstraintViolation

from cs.web.components.outlet_config import OutletPosition, OutletPositionOwner


def delete_navigation_tree_nodes():
    print ('deleteting sml nodes in navigation tree...')
    for treeNode in MenuTree.KeywordQuery(ausgabe_label='tree_SML'):
        treeNode.Delete()


def replace_objectplan_operation():
    print ('replacing sml objectplan operation...')
    sml_oplan_op = OperationConfig.ByKeys(name='cdbsml_oplan', classname='part')
    if sml_oplan_op:
        sml_oplan_op.Delete()
    try:
        args = {
            'name': 'cs_classification_object_plan',
            'classname': 'part',
            'applicability': 'Class',
            'ordering': 240,
            'menugroup': 40,
            'menu_visible': 1
        }
        OperationConfig.Create(**args)
    except DBConstraintViolation:
        pass

    try:
        args = {
            'name': 'cs_classification_object_plan',
            'classname': 'part',
            'role_id': 'public'
        }
        OperationOwner.Create(**args)
    except DBConstraintViolation:
        pass


def add_multi_edit_operation():
    print ('adding multiple classification edit operation to part...')
    try:
        args = {
            'name': 'cs_classification_multiple_edit',
            'classname': 'part',
            'applicability': 'MultipleObjects',
            'mask_name': 'cs_classification_tab_c',
            'ordering': 10,
            'menugroup': 1000,
            'menu_visible': 1
        }
        OperationConfig.Create(**args)
    except DBConstraintViolation:
        pass

    try:
        args = {
            'name': 'cs_classification_multiple_edit',
            'classname': 'part',
            'role_id': 'public'
        }
        OperationOwner.Create(**args)
    except DBConstraintViolation:
        pass


def set_operation_mask(classname, operation_name, mask_name):
    operation = OperationConfig.ByKeys(name=operation_name, classname=classname)
    if operation:
        args = {
            'mask_name': mask_name
        }
        operation.Update(**args)


def copy_mask_comp(source_mask_name, destination_mask_name):
    src_mask = MaskComp.ByKeys(name=source_mask_name, role_id='public')
    dest_mask = MaskComp.ByKeys(name=destination_mask_name, role_id='public')
    if src_mask:
        if not dest_mask:
            args = {
                'name': destination_mask_name
            }
            dest_mask = src_mask.Copy(**args)
        for register in src_mask.Registers:
            try:
                args = {
                    'mask_name': destination_mask_name
                }
                register.Copy(**args)
            except DBConstraintViolation:
                pass


def replace_classification_register(mask_name, old_register_name, new_register_name, new_web_register_name=None):
    sml_register = MaskReg.ByKeys(mask_name=mask_name, mask_role_id='public', name=old_register_name)
    if sml_register:
        ordering = sml_register.ordering
        priority = sml_register.priority
        if MaskReg.ByKeys(mask_name=mask_name, mask_role_id='public', name=new_register_name):
            # classification already existing only delete sml
            sml_register.Delete()
        else:
            args = {
                'name': new_register_name,
                'reg_title': 'cs_classification',
                'cdb_module_id': ''
            }
            sml_register.Update(**args)
        if new_web_register_name and not MaskReg.ByKeys(
            mask_name=mask_name, mask_role_id='public', name=new_web_register_name
        ):
                try:
                    args = {
                        'mask_name': mask_name,
                        'mask_role_id': 'public',
                        'name': new_web_register_name,
                        'ordering': ordering + 1,
                        'priority': priority,
                        'reg_title': 'cs_classification',
                        'cdb_module_id': ''
                    }
                    MaskReg.Create(**args)
                except DBConstraintViolation:
                    pass


def replace_table_col(table_name, column_name):
    table = Table.ByKeys(name=table_name, role_id='public')
    if table:
        for attribute in table.Attributes:
            if '$Facet:sachgruppe' == attribute.attribut:
                args = {
                    'attribut': 'cs.classification.table_columns.ClassificationPropertiesProvider',
                    'data_source': 'PythonCode',
                    'cdb_module_id': ''
                }
                attribute.Update(**args)


def add_part_detail_outlet():
    print ('adding classification outlet to part detail page...')
    try:
        args = {
            'outlet_name': 'object_details',
            'classname': 'part',
            'pos': 11,
            'priority': 10,
            'child_name': 'cs-classification-web-info'
        }
        OutletPosition.Create(**args)
        args = {
            'outlet_name': 'object_details',
            'classname': 'part',
            'pos': 11,
            'priority': 10,
            'role_id': 'public'
        }
        OutletPositionOwner.Create(**args)
    except DBConstraintViolation:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Replace SML with Universal Classification. Only useable for standard installation!')
    parser.add_argument('--with-webui', dest='with_webui', action='store_true', default=False, help='also add mask configuration for web ui (only for 15.3)')
    args = parser.parse_args()

    delete_navigation_tree_nodes()
    replace_objectplan_operation()  # operation does only work if there is an applicable class for part
    add_multi_edit_operation()

    replace_table_col('tv_tab', '$Facet:sachgruppe')

    print ('adding seperate info mask for part...')
    copy_mask_comp('tv_comp', 'tv_comp_info')
    set_operation_mask('part', 'CDB_ShowObject', 'tv_comp_info')

    if args.with_webui:
        print ('replacing sml mask registers with classification registers, adding classification mask registers for web ui usage...')
    else:
        print ('replacing sml mask registers with classification registers...')
    replace_classification_register('tv_comp_info', '$Facet:sachgruppe', 'cs_classification_tab_info')
    web_tab = 'cs_classification_tab_web' if args.with_webui else None
    replace_classification_register('tv_comp', '$Facet:sachgruppe', 'cs_classification_tab', web_tab)
    web_tab = 'cs_classification_tab_c_web' if args.with_webui else None
    replace_classification_register('tv_comp_c', '$Facet:sachgruppe', 'cs_classification_tab_c', web_tab)
    web_tab = 'cs_classification_tab_s_web' if args.with_webui else None
    replace_classification_register('tv_comp_s', '$Facet:sachgruppe', 'cs_classification_tab_s', web_tab)
    register = MaskReg.ByKeys(mask_name='tv_comp_s', mask_role_id='public', name='tv_sml_search_mask_s')
    if register:
        register.Delete()

    add_part_detail_outlet()

    print('NOTE: User exists like Objectplan will only work after a restart with at least one applicable class for part!')
