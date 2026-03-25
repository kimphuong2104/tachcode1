#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/


class MigrationOptions:
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        transaction_over_all_products=False,
        reset_bom_item_variant_management_attributes=True,
        postfix_catalog_prop_code_with_data_type=True,
        postfix_class_prop_code_with_different_type=True,
        keep_cdb_object_id_of_variant=True,
        keep_cdb_object_id_of_property=True,
        keep_cdb_object_id_of_enum_def=True,
    ):
        # Do a transaction over all products or over each product
        self.transaction_over_all_products = transaction_over_all_products

        # This option will reset the VM attributes 'cdbvp_positionstyp' and 'cdbvp_has_condition'
        # of all bom items in database
        self.reset_bom_item_variant_management_attributes = (
            reset_bom_item_variant_management_attributes
        )

        # This options is used to create the catalog property code in case the old variant management
        # had no catalog property
        # If this options is activated the catalog property gets postfixed its old datatype
        # e.g. 'alphanumeric'
        # Example:
        #   erp_code of old variant management = "MY_PRODUCT_PROP"
        #   data_type of old variant management = "alphanumeric"
        #   Result: "MY_PRODUCT_PROP_alphanumeric"
        #
        # This is done to avoid having unique constraint r if a property exists as different
        # data types but with same name. If you disable this options these unique constraint errors can occur!
        self.postfix_catalog_prop_code_with_data_type = (
            postfix_catalog_prop_code_with_data_type
        )

        # This options is used to create the class property code in case the old variant management
        # has the same property code but with different data type
        # If this options is activated the class property gets postfixed its old datatype
        # e.g. 'alphanumeric'
        # Example:
        #   code = "MY_PRODUCT_PROP"
        #   data_type of old variant management = "alphanumeric"
        #   Result: "MY_PRODUCT_PROP_alphanumeric"
        #
        # If you disable this options the migration will stop with an error if
        # class properties with same code but different data types are encountered!
        self.postfix_class_prop_code_with_different_type = (
            postfix_class_prop_code_with_different_type
        )

        # The Flags trigger if the cdb_object_id of objects of the old variant management should be kept
        # Should a cdb_object_id be kept then the old object gets an new cdb_object id and
        # the newly created object gets the original one
        # In the database a migration lookup table gets created with th name 'CS_VARIANTS_ID_MIGRATION'
        # it contains the 'original_cdb_object_id' of the object and the 'new_cdb_object_id' and
        # also the 'classname' of the object
        self.keep_cdb_object_id_of_variant = keep_cdb_object_id_of_variant
        self.keep_cdb_object_id_of_property = keep_cdb_object_id_of_property
        self.keep_cdb_object_id_of_enum_def = keep_cdb_object_id_of_enum_def
