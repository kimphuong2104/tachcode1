#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import typing
from dataclasses import dataclass, field

KeysType = dict[str, typing.Any]
OptionalKeysType = KeysType | None


@dataclass
class SubassemblyStructure:
    item_keys: KeysType
    bom_item_keys: KeysType = field(default_factory=dict)
    children: list[typing.Self] = field(default_factory=list)
    occurrence_keys: list[typing.Any] = field(default_factory=list)

    def update_keys(
        self,
        item_keys: OptionalKeysType = None,
        bom_item_keys: OptionalKeysType = None,
        recursive: bool = False,
    ) -> None:
        if item_keys is not None:
            self.item_keys.update(item_keys)

        if bom_item_keys is not None:
            self.bom_item_keys.update(bom_item_keys)

        if recursive:
            for each in self.children:
                each.update_keys(
                    item_keys=item_keys, bom_item_keys=bom_item_keys, recursive=True
                )

    def update_with_fn(self, fn: typing.Callable[[typing.Self], None]) -> None:
        """call the 'fn' for every SubassemblyStructure recursively"""
        fn(self)
        for each in self.children:
            each.update_with_fn(fn)

    def __str__(self) -> str:
        return str(self.item_keys | self.bom_item_keys)
