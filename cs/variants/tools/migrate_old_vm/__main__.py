#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import argparse
import json

from cs.variants.tools.migrate_old_vm.migrate import (
    migrate_old_vm,
    reset_all_bom_item_old_vm_attributes,
)
from cs.variants.tools.migrate_old_vm.options import MigrationOptions
from cs.vp.products import Product

parser = argparse.ArgumentParser(
    description="Migrate old cs.vp.variants data to new cs.variants. "
    "If no config file is used all products will be migrated"
)
parser.add_argument(
    "--config",
    help="Config file to control migration. "
    "Options can be set and products can be excluded or only certain products can be included. "
    "See documentation for example.",
)

args = parser.parse_args()

if not args.config:
    migrate_old_vm(Product.Query(), MigrationOptions())
else:
    with open(args.config, "r", encoding="utf-8") as file_handle:
        config_options = json.load(file_handle)

    options = MigrationOptions(
        transaction_over_all_products=config_options.get(
            "transaction_over_all_products", True
        ),
        reset_bom_item_variant_management_attributes=config_options.get(
            "reset_bom_item_variant_management_attributes", True
        ),
        postfix_catalog_prop_code_with_data_type=config_options.get(
            "postfix_catalog_prop_code_with_data_type", True
        ),
        postfix_class_prop_code_with_different_type=config_options.get(
            "postfix_class_prop_code_with_different_type", True
        ),
        keep_cdb_object_id_of_variant=config_options.get(
            "keep_cdb_object_id_of_variant", True
        ),
        keep_cdb_object_id_of_property=config_options.get(
            "keep_cdb_object_id_of_property", True
        ),
        keep_cdb_object_id_of_enum_def=config_options.get(
            "keep_cdb_object_id_of_enum_def", True
        ),
    )

    product_codes_to_include = config_options.get("include")
    product_codes_to_exclude = set(config_options.get("exclude", []))

    if product_codes_to_include is not None:
        product_codes_to_include = set(product_codes_to_include)
        if not product_codes_to_include:
            raise ValueError(
                "You need to provide at least one product code to include. Or remove option to include all."
            )

    products = []
    for each in Product.Query():
        product_code = each.code

        if product_code in product_codes_to_exclude:
            product_codes_to_exclude.remove(product_code)
            continue

        if product_codes_to_include is None:
            products.append(each)
        elif product_code in product_codes_to_include:
            products.append(each)
            product_codes_to_include.remove(product_code)

    if not products:
        raise ValueError(
            "No products to convert. Please check your include and/or exclude settings."
        )

    if product_codes_to_exclude:
        raise ValueError(
            "Not able to find these products which should be excluded: {0}".format(
                product_codes_to_exclude
            )
        )

    if product_codes_to_include:
        raise ValueError(
            "Not able to find these products which should be included: {0}".format(
                product_codes_to_include
            )
        )

    migrate_old_vm(
        products,
        options,
    )

    if options.reset_bom_item_variant_management_attributes:
        reset_all_bom_item_old_vm_attributes()
