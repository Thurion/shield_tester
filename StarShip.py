from __future__ import annotations

from typing import Tuple, Dict, Any, List


class StarShip(object):
    def __init__(self):
        # no need for private attributes, we are handing out deep copies
        self.name = ""
        self.custom_name = ""
        self.symbol = ""
        self.loadout_template = dict()
        self.base_shield_strength = 0
        self.hull_mass = 0
        self.utility_slots_free = list()
        self.highest_internal = 0
        self.internal_slot_layout = dict()  # type: Dict[int, int] # key: slot number (starting at 1), value: module class

    @property
    def utility_slots(self):
        return len(self.utility_slots_free)

    def get_available_internal_slot(self, module_class: int, reverse: bool = False) -> Tuple[int, int]:
        items = sorted(self.internal_slot_layout.items(), reverse=reverse)  # type: List[Tuple[int, int]]
        for slot, m_class in items:
            if m_class >= min(module_class, self.highest_internal):
                return slot, m_class
        return 0, 0

    @staticmethod
    def create_from_json(json_ship: Dict[str, Any]) -> StarShip:
        """
        Create a Ship object from json node
        :param json_ship: json node (or dictionary) in data file
        :return: newly created Ship object
        """
        ship = StarShip()
        ship.name = json_ship["ship"]
        ship.symbol = json_ship["symbol"]
        ship.loadout_template = json_ship["loadout_template"]
        ship.base_shield_strength = json_ship["baseShieldStrength"]
        ship.hull_mass = json_ship["hullMass"]
        ship.utility_slots_free = list(range(1, json_ship["utility_slots"] + 1))
        ship.highest_internal = json_ship["highest_internal"]
        internal_slot_layout = json_ship["slot_layout"]["internal"]

        # check for military slots. shield generators can't go there
        for i, slot in enumerate(internal_slot_layout):
            if type(slot) == int:
                ship.internal_slot_layout.setdefault(i + 1, slot)

        return ship
