from __future__ import annotations

import copy
from typing import Dict, Any, List, Optional


class ShieldGenerator(object):
    CALC_NORMAL = 1
    CALC_RES = 2
    CALC_MASS = 3

    TYPE_NORMAL = "normal"
    TYPE_BIWEAVE = "bi-weave"
    TYPE_PRISMATIC = "prismatic"

    def __init__(self):
        # no need for private attributes, we are handing out deep copies
        self.symbol = ""
        self.integrity = 0
        self.power = 0
        self.explres = 0
        self.kinres = 0
        self.thermres = 0
        self.name = ""
        self.module_class = 0
        self.regen = 0
        self.brokenregen = 0
        self.distdraw = 0
        self.maxmass = 0
        self.maxmul = 0
        self.minmass = 0
        self.minmul = 0
        self.optmass = 0
        self.optmul = 0
        self.engineered_name = "not engineered"
        self.engineered_symbol = ""
        self.experimental_name = "no experimental effect"
        self.experimental_symbol = ""

    def __str__(self):
        return f"{self.name} ({self.module_class}) - {self.engineered_name} - {self.experimental_name}"

    @staticmethod
    def create_from_json(json_generator: Dict[str, Any]) -> ShieldGenerator:
        """
        Create a ShieldGenerator object from json node
        :param json_generator: json node (or dictionary) in data file
        :return: newly created ShieldGenerator object
        """
        generator = ShieldGenerator()
        generator.symbol = json_generator["symbol"]
        generator.integrity = json_generator["integrity"]
        generator.power = json_generator["power"]
        generator.explres = json_generator["explres"]
        generator.kinres = json_generator["kinres"]
        generator.thermres = json_generator["thermres"]
        generator.name = json_generator["name"]
        generator.module_class = json_generator["class"]
        generator.regen = json_generator["regen"]
        generator.brokenregen = json_generator["brokenregen"]
        generator.distdraw = json_generator["distdraw"]
        generator.maxmass = json_generator["maxmass"]
        generator.maxmul = json_generator["maxmul"]
        generator.minmass = json_generator["minmass"]
        generator.minmul = json_generator["minmul"]
        generator.optmass = json_generator["optmass"]
        generator.optmul = json_generator["optmul"]
        return generator

    def _calculate_and_set_engineering(self, attr: str, key: str, features: Dict[str, Any], calc_type: int, is_percentage: bool = False):
        """
        Apply engineering changes
        :param attr: class attribute to change.
        :param key: the key in the json feature list
        :param features: dictionary of features
        :param calc_type: how to calculate the new value. Refer to class "constants"
        :param is_percentage: set to true if the value in the features list is a percentage value (0-100) instead of a fraction (0-1)
        :return:
        """
        if key in features:
            r = getattr(self, attr)
            v = features[key]
            if is_percentage:
                v /= 100.0

            if calc_type == self.CALC_RES:
                r = 1.0 - (1.0 - r) * (1.0 - v)
            elif calc_type == self.CALC_MASS:
                r = (r * 100.0) * (1.0 + v) / 100.0
            elif calc_type == self.CALC_NORMAL:
                r = r * (1.0 + v)

            setattr(self, attr, round(r, 4))

    def _apply_engineering(self, features: Dict[str, Any], is_percentage: bool = False):
        self._calculate_and_set_engineering("integrity", "integrity", features, self.CALC_NORMAL)
        self._calculate_and_set_engineering("brokenregen", "brokenregen", features, self.CALC_NORMAL)
        self._calculate_and_set_engineering("regen", "regen", features, self.CALC_NORMAL)
        self._calculate_and_set_engineering("distdraw", "distdraw", features, self.CALC_NORMAL)
        self._calculate_and_set_engineering("power", "power", features, self.CALC_NORMAL)

        self._calculate_and_set_engineering("optmul", "optmul", features, self.CALC_MASS)
        self._calculate_and_set_engineering("minmul", "optmul", features, self.CALC_MASS)
        self._calculate_and_set_engineering("maxmul", "optmul", features, self.CALC_MASS)

        self._calculate_and_set_engineering("kinres", "kinres", features, self.CALC_RES, is_percentage)
        self._calculate_and_set_engineering("thermres", "thermres", features, self.CALC_RES, is_percentage)
        self._calculate_and_set_engineering("explres", "explres", features, self.CALC_RES, is_percentage)

    @staticmethod
    def create_engineered_shield_generators(prototype: ShieldGenerator, blueprints: Dict[str, Any], experimentals: Dict[str, Any]) -> List[ShieldGenerator]:
        """
        Use a non engineered shield generator as prototype to generate a list of possible engineered shield generators.
        :param prototype: non engineered shield generator
        :param blueprints: blueprints from data.json containing only recipes for shield generators
        :param experimentals: experimental effects from data.json containing only recipes for shield generators
        :return: list of all combinations of shield generators from given blueprints and experimental effects
        """
        variations = list()

        for blueprint in blueprints:  # type: Dict[str, Any]
            engineered_sg = copy.deepcopy(prototype)
            engineered_sg.engineered_symbol = blueprint["symbol"]
            engineered_sg.engineered_name = blueprint["name"]
            engineered_sg._apply_engineering(blueprint["features"])
            for experimental in experimentals:  # type: Dict[str, Any]
                exp_eng_sg = copy.deepcopy(engineered_sg)
                exp_eng_sg.experimental_symbol = experimental["symbol"]
                exp_eng_sg.experimental_name = experimental["name"]
                exp_eng_sg._apply_engineering(experimental["features"], is_percentage=True)
                variations.append(exp_eng_sg)

        return variations

    def _create_modifier_templates(self, default_sg: ShieldGenerator):
        modifiers = list()

        def helper(label: str, def_value, value, less_is_good: int = 0):
            return {"Label": label,
                    "Value": value,
                    "OriginalValue": def_value,
                    "LessIsGood": less_is_good}

        if default_sg.integrity != self.integrity:
            modifiers.append(helper("Integrity", default_sg.integrity, self.integrity))
        if default_sg.power != self.power:
            modifiers.append(helper("PowerDraw", default_sg.power, self.power, 1))
        if default_sg.optmul != self.optmul:
            modifiers.append(helper("ShieldGenStrength", default_sg.optmul * 100, self.optmul * 100))
        if default_sg.distdraw != self.distdraw:
            modifiers.append(helper("EnergyPerRegen", default_sg.distdraw, self.distdraw, 1))
        if default_sg.brokenregen != self.brokenregen:
            modifiers.append(helper("BrokenRegenRate", default_sg.brokenregen, self.brokenregen))
        if default_sg.regen != self.regen:
            modifiers.append(helper("RegenRate", default_sg.regen, self.regen))
        if default_sg.kinres != self.kinres:
            modifiers.append(helper("KineticResistance", default_sg.kinres * 100, self.kinres * 100))
        if default_sg.thermres != self.thermres:
            modifiers.append(helper("ThermicResistance", default_sg.thermres * 100, self.thermres * 100))
        if default_sg.explres != self.explres:
            modifiers.append(helper("ExplosiveResistance", default_sg.explres * 100, self.explres * 100))
        return modifiers

    def create_loadout(self, default_sg: ShieldGenerator, slot: str, module_class: int) -> Optional[Dict[str, Any]]:
        """
        Create loadout dictionary for use in Coriolis
        :param default_sg: non engineered ShieldGenerator for comparing values
        :param slot: slot as used in loadout event (e.g. 9 when Slot09_Size4)
        :param module_class: class as used in loadout event (e.g. 4 when Slot09_Size4)
        :return: dictionary containing module information about the shield generator
        """
        modifiers = self._create_modifier_templates(default_sg)
        engineering = {"BlueprintName": self.engineered_symbol,
                       "Level": 5,
                       "Quality": 1,
                       "Modifiers": modifiers,
                       "ExperimentalEffect": self.experimental_symbol}
        loadout = {"Item": self.symbol,
                   "Slot": f"slot{slot:02d}_size{module_class}",
                   "On": True,
                   "Priority": 0,
                   "Engineering": engineering}
        return loadout
