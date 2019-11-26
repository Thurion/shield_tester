from __future__ import annotations
import json
import copy
import math
import os
import sys
import time
import itertools
import multiprocessing
import queue
import gzip
import base64
from typing import List, Tuple, Any, Dict, Optional, Set

try:
    # noinspection PyUnresolvedReferences
    import psutil
    _psutil_imported = True
except ImportError as error:
    _psutil_imported = False
    print(error)


class Utility(object):
    @staticmethod
    def format_output_string(output: List[Any]) -> str:
        """
        Format a list of tuples or strings to be evenly aligned.
        The list can be made up of strings or tuples of type (str, str). All tuples will be right aligned to the longest string in the tuples.
        When there is just a string in the list, it will be left untouched.
        :param output: list containing strings and tuples of type (str, str)
        :return: formatted output string
        """
        character_count = 0
        out = list()

        # determine length
        for st in output:
            if type(st) == tuple:
                if len(st[0]) > character_count:
                    character_count = len(st[0])

        # format
        for st in output:
            if type(st) == tuple:
                out.append(st[0].rjust(character_count) + st[1])
            else:
                out.append(st)
        return "\n".join(out)


class ShieldBoosterVariant(object):
    def __init__(self):
        # no need for private attributes, we are handing out deep copies
        self.engineering = ""
        self.experimental = ""
        self.shield_strength_bonus = 0
        self.exp_res_bonus = 0
        self.kin_res_bonus = 0
        self.therm_res_bonus = 0
        self.can_skip = False
        self.loadout_template = None  # type: Optional[Dict[str, Any]]

    def __str__(self):
        return f"{self.engineering} - {self.experimental}"

    def get_loadout_template_slot(self, slot: int) -> Dict[str, Any]:
        """
        Get the loadout dictionary for the provided slot number
        :param slot: int from 1 to 8 (including)
        :return:
        """
        if self.loadout_template:
            loadout = copy.deepcopy(self.loadout_template)
            loadout["Slot"] = f"tinyhardpoint{slot}"
            return loadout
        return dict()

    @staticmethod
    def create_from_json(json_booster: json) -> ShieldBoosterVariant:
        """
        Create a ShieldBoosterVariant object from json node
        :param json_booster: json node (or dictionary) in data file
        :return: newly created ShieldBoosterVariant object
        """
        booster = ShieldBoosterVariant()
        booster.engineering = json_booster["engineering"]
        booster.experimental = json_booster["experimental"]
        booster.shield_strength_bonus = json_booster["shield_strength_bonus"]
        booster.exp_res_bonus = 1 - json_booster["exp_res_bonus"]
        booster.kin_res_bonus = 1 - json_booster["kin_res_bonus"]
        booster.therm_res_bonus = 1 - json_booster["therm_res_bonus"]
        booster.can_skip = json_booster["can_skip"]
        booster.loadout_template = json_booster["loadout_template"]
        return booster

    @staticmethod
    def calculate_booster_bonuses(shield_boosters: List[ShieldBoosterVariant], booster_loadout: List[int] = None) -> Tuple[float, float, float, float]:
        """
        Calculate the combined bonus of shield boosters. This function has 2 modes: either supply it with a list of all ShieldBoosterVariant and a list of indexes
        for the boosters to use or supply it only with a list of ShieldBoosterVariant.
        :param shield_boosters: list of ShieldBoosterVariant.
        :param booster_loadout: booster loadout as a list of indexes of the booster in shield_boosters
        :return: tuple: exp_modifier, kin_modifier, therm_modifier, hitpoint_bonus
        """
        exp_modifier = 1.0
        kin_modifier = 1.0
        therm_modifier = 1.0
        hitpoint_bonus = 1.0

        if booster_loadout:
            boosters = [shield_boosters[x] for x in booster_loadout]
        else:
            boosters = shield_boosters

        for booster in boosters:
            exp_modifier *= booster.exp_res_bonus
            kin_modifier *= booster.kin_res_bonus
            therm_modifier *= booster.therm_res_bonus
            hitpoint_bonus += booster.shield_strength_bonus

        # Compensate for diminishing returns
        if exp_modifier < 0.7:
            exp_modifier = 0.7 - (0.7 - exp_modifier) / 2
        if kin_modifier < 0.7:
            kin_modifier = 0.7 - (0.7 - kin_modifier) / 2
        if therm_modifier < 0.7:
            therm_modifier = 0.7 - (0.7 - therm_modifier) / 2

        return exp_modifier, kin_modifier, therm_modifier, hitpoint_bonus


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
    def create_from_json(json_generator: json) -> ShieldGenerator:
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

    def _apply_engineering(self, features: json, is_percentage: bool = False):
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
    def create_engineered_shield_generators(prototype: ShieldGenerator, blueprints: json, experimentals: json) -> List[ShieldGenerator]:
        """
        Use a non engineered shield generator as prototype to generate a list of possible engineered shield generators.
        :param prototype: non engineered shield generator
        :param blueprints: blueprints from data.json containing only recipes for shield generators
        :param experimentals: experimental effects from data.json containing only recipes for shield generators
        :return: list of all combinations of shield generators from given blueprints and experimental effects
        """
        variations = list()

        for blueprint in blueprints:
            engineered_sg = copy.deepcopy(prototype)
            engineered_sg.engineered_symbol = blueprint["symbol"]
            engineered_sg.engineered_name = blueprint["name"]
            engineered_sg._apply_engineering(blueprint["features"])
            for experimental in experimentals:
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


class StarShip(object):
    def __init__(self):
        # no need for private attributes, we are handing out deep copies
        self.name = ""
        self.symbol = ""
        self.loadout_template = dict()
        self.base_shield_strength = 0
        self.hull_mass = 0
        self.utility_slots = 0
        self.highest_internal = 0
        self.internal_slot_layout = dict()  # type: Dict[int, int] # key: slot number (starting at 1), value: module class

    def get_available_internal_slot(self, module_class: int, reverse: bool = False) -> Tuple[int, int]:
        items = sorted(self.internal_slot_layout.items(), reverse=reverse)  # type: List[Tuple[int, int]]
        for item in items:
            if item[1] >= module_class:
                return item
        return 0, 0

    @staticmethod
    def create_from_json(json_ship: json) -> StarShip:
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
        ship.utility_slots = json_ship["utility_slots"]
        ship.highest_internal = json_ship["highest_internal"]
        internal_slot_layout = json_ship["slot_layout"]["internal"]

        # check for military slots. shield generators can't go there
        for i, slot in enumerate(internal_slot_layout):
            if type(slot) == int:
                ship.internal_slot_layout.setdefault(i + 1, slot)

        return ship


class LoadOut(object):
    def __init__(self, shield_generator: ShieldGenerator, ship: StarShip):
        self.shield_generator = shield_generator
        self.ship = ship
        self.boosters = None  # type: List[ShieldBoosterVariant]
        self.shield_strength = self.__calculate_shield_strength()

    @property
    def ship_name(self):
        if self.ship:
            return self.ship.name
        else:
            return "ship not set"

    def __calculate_shield_strength(self):
        # formula taken from:
        # https://forums.frontier.co.uk/threads/the-one-formula-to-rule-them-all-the-mechanics-of-shield-and-thruster-mass-curves.300225/
        # https://github.com/EDCD/coriolis/blob/master/src/app/shipyard/Calculations.js
        if self.shield_generator and self.ship:
            min_mass = self.shield_generator.minmass
            opt_mass = self.shield_generator.optmass
            max_mass = self.shield_generator.maxmass
            min_mul = self.shield_generator.minmul
            opt_mul = self.shield_generator.optmul
            max_mul = self.shield_generator.maxmul
            hull_mass = self.ship.hull_mass

            xnorm = min(1.0, (max_mass - hull_mass) / (max_mass - min_mass))
            exponent = math.log((opt_mul - min_mul) / (max_mul - min_mul)) / math.log(min(1.0, (max_mass - opt_mass) / (max_mass - min_mass)))
            ynorm = math.pow(xnorm, exponent)
            mul = min_mul + ynorm * (max_mul - min_mul)
            return round(self.ship.base_shield_strength * mul, 4)
        else:
            return 0

    def get_total_values(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Calculate total shield values for the loadout (boosters + shield). Returns None if boosters are not set
        :return: exp_res, kin_res, therm_res, hp
        """
        if self.boosters and len(self.boosters) > 0:
            return self.calculate_total_values(*ShieldBoosterVariant.calculate_booster_bonuses(self.boosters))
        return self.calculate_total_values(1, 1, 1, 1)

    def calculate_total_values(self, exp_modifier, kin_modifier, therm_modifier, hitpoint_bonus) -> Tuple[float, float, float, float]:
        """
        Provide booster bonuses to calculate total shield values for the loadout
        :param exp_modifier: booster explosive modifier
        :param kin_modifier: booster kinetic modifier
        :param therm_modifier: booster thermal modifier
        :param hitpoint_bonus:  booster hitpoint modifier
        :return: exp_res, kin_res, therm_res, hp
        """
        exp_res = (1 - self.shield_generator.explres) * exp_modifier
        kin_res = (1 - self.shield_generator.kinres) * kin_modifier
        therm_res = (1 - self.shield_generator.thermres) * therm_modifier
        hp = self.shield_strength * hitpoint_bonus
        return exp_res, kin_res, therm_res, hp

    def generate_loadout_event(self, default_sg: ShieldGenerator) -> Dict[str, Any]:
        """
        Generate loadout "event" to import into Coriolis
        :param default_sg: default ShieldGenerator to compare changes
        :return: loadout "event" as dictionary
        """
        if not self.ship:
            return dict()

        loadout_json = self.ship.loadout_template
        modules = loadout_json["Modules"]
        modules.append(self.shield_generator.create_loadout(default_sg, *self.ship.get_available_internal_slot(self.shield_generator.module_class, reverse=True)))

        for i, booster in enumerate(self.boosters):
            modules.append(booster.get_loadout_template_slot(i + 1))
        return loadout_json


class TestResult:
    def __init__(self, loadout: LoadOut = None, survival_time: float = 0.0, incoming_dps: float = 0.0, total_hitpoints: float = 0.0):
        self.loadout = loadout
        self.survival_time = survival_time  # if negative, the ship didn't die
        self.incoming_dps = incoming_dps  # if negative, the ship didn't die
        self.total_hitpoints = total_hitpoints  # shield HP without guardian and SCBs

    def get_output_string(self, guardian_hitpoints: int = 0):
        """
        Get output string for console output, text output or a logfile of the test result
        :param guardian_hitpoints: Guardian Shield Reinforcement to add to shield hitpoints
        :return: string
        """
        output = list()
        output.append("------------ TEST RESULTS ------------")
        if self.survival_time != 0:
            exp_res, kin_res, therm_res, shield_hitpoints = self.loadout.get_total_values()
            shield_hitpoints += guardian_hitpoints

            # sort by survival time and put highest value to start of the list
            if self.survival_time > 0:
                output.append(("Survival Time [s]: ", f"[{self.survival_time:.2f}]"))
            else:
                output.append(("Survival Time [s]: ", "[Didn't die]"))

            shield_generator = self.loadout.shield_generator
            output.append(("Drain Rate [MJ/s]: ", f"[{shield_hitpoints / self.survival_time:.2f}]"))
            output.append(("Shield Generator: ", f"[{shield_generator.name}] - [{shield_generator.engineered_name}] - [{shield_generator.experimental_name}]"))
            if self.loadout.boosters:
                for i, shield_booster_variant in enumerate(self.loadout.boosters):
                    if i == 0:
                        output.append((f"Shield Booster {i + 1}: ", f"[{shield_booster_variant.engineering}] - [{shield_booster_variant.experimental}]"))
                    else:
                        output.append((f"{i + 1}: ", f"[{shield_booster_variant.engineering}] - [{shield_booster_variant.experimental}]"))

            output.append("")
            output.append(("Shield Hitpoints [MJ]: ", f"[{shield_hitpoints:.2f}]"))
            regen = self.loadout.shield_generator.regen
            regen_time = shield_hitpoints / (2 * self.loadout.shield_generator.regen)
            output.append(("Shield Regen [MJ/s]: ", f"[{regen}] ({regen_time:.2f}s from 50%)"))
            output.append(("Explosive Resistance [%]: ", f"[{(1.0 - exp_res) * 100:.2f}] ({shield_hitpoints / exp_res:.0f} MJ)"))
            output.append(("Kinetic Resistance [%]: ", f"[{(1.0 - kin_res) * 100:.2f}] ({shield_hitpoints / kin_res:.0f} MJ)"))
            output.append(("Thermal Resistance [%]: ", f"[{(1.0 - therm_res) * 100:.2f}] ({shield_hitpoints / therm_res:.0f} MJ)"))
        else:
            output.append("No test results. Please change DPS and/or damage effectiveness.")
        return Utility.format_output_string(output)


class TestCase(object):
    def __init__(self, ship: StarShip):
        self.ship = ship
        self.damage_effectiveness = 0
        self.explosive_dps = 0
        self.kinetic_dps = 0
        self.thermal_dps = 0
        self.absolute_dps = 0
        self.scb_hitpoints = 0
        self.guardian_hitpoints = 0
        self.shield_booster_variants = None  # type: List[ShieldBoosterVariant]
        self.loadout_list = None  # type: List[LoadOut]
        self.number_of_boosters_to_test = 0
        self._use_prismatics = True  # set in ShieldTester! call ShieldTester.set_loadouts_for_class()

    def get_output_string(self) -> str:
        """
        Get output string for console output, text output or a logfile of the test result
        :return: string
        """
        output = list()
        output.append("------------ TEST SETUP ------------")
        if self.loadout_list:
            output.append(("Ship Type: ", f"[{self.loadout_list[0].ship_name}]"))
            output.append(("Shield Generator Size: ", f"[{self.loadout_list[0].shield_generator.module_class}]"))
        else:
            output.append(("Ship Type: ", "[NOT SET]"))
            output.append(("Shield Generator Size: ", "[SHIP NOT SET]"))
        output.append(("Shield Booster Count: ", f"[{self.number_of_boosters_to_test}]"))
        output.append(("Shield Cell Bank: ", f"[{self.scb_hitpoints}]"))
        output.append(("Guardian Shield Reinforcement: ", f"[{self.guardian_hitpoints}]"))
        output.append(("Access to Prismatic Shields: ", f"[{'Yes' if self._use_prismatics else 'No'}]"))
        output.append(("Explosive DPS: ", f"[{self.explosive_dps}]"))
        output.append(("Kinetic DPS: ", f"[{self.kinetic_dps}]"))
        output.append(("Thermal DPS: ", f"[{self.thermal_dps}]"))
        output.append(("Absolute DPS: ", f"[{self.absolute_dps}]"))
        output.append(("Damage Effectiveness: ", f"[{self.damage_effectiveness * 100:.0f}%]"))
        output.append("")
        return Utility.format_output_string(output)

    @staticmethod
    def test_case(test_case: TestCase, booster_combinations: List[List[int]]) -> TestResult:
        """
        Run a particular test based on provided TestCase and booster combinations.
        :param test_case: TestCase containing test setup
        :param booster_combinations: list of lists of indexes of ShieldBoosterVariant
        :return: best result as TestResult
        """
        best_survival_time = 0
        lowest_dps = 10000
        best_loadout = 0
        best_shield_booster_loadout = None
        best_hitpoints = 0

        # reduce calls -> speed up program, this should speed up the program by a couple hundred ms when using 8 boosters and the short list
        damage_effectiveness = test_case.damage_effectiveness
        explosive_dps = test_case.explosive_dps
        kinetic_dps = test_case.kinetic_dps
        thermal_dps = test_case.thermal_dps
        absolute_dps = test_case.absolute_dps
        scb_hitpoints = test_case.scb_hitpoints
        guardian_hitpoints = test_case.guardian_hitpoints

        for booster_combination in booster_combinations:
            boosters = [test_case.shield_booster_variants[x] for x in booster_combination]
            # Do this here instead of for each loadout to save some time.
            exp_modifier, kin_modifier, therm_modifier, hitpoint_bonus = ShieldBoosterVariant.calculate_booster_bonuses(boosters)

            for loadout in test_case.loadout_list:
                # can't use same function in LoadOut because of speed
                exp_res = (1 - loadout.shield_generator.explres) * exp_modifier
                kin_res = (1 - loadout.shield_generator.kinres) * kin_modifier
                therm_res = (1 - loadout.shield_generator.thermres) * therm_modifier
                hp = loadout.shield_strength * hitpoint_bonus
                regen_rate = loadout.shield_generator.regen * (1.0 - damage_effectiveness)

                actual_dps = damage_effectiveness * (
                        explosive_dps * exp_res +
                        kinetic_dps * kin_res +
                        thermal_dps * therm_res +
                        absolute_dps) - regen_rate

                survival_time = (hp + scb_hitpoints + guardian_hitpoints) / actual_dps

                if actual_dps > 0 and best_survival_time >= 0:
                    # if another run set best_survival_time to a negative value, then the ship didn't die, therefore the other result is better
                    if survival_time > best_survival_time:
                        best_loadout = loadout
                        best_shield_booster_loadout = boosters
                        best_survival_time = survival_time
                        best_hitpoints = hp
                elif actual_dps <= 0:
                    if lowest_dps > actual_dps or (math.isclose(lowest_dps, actual_dps, rel_tol=1e-8) and best_hitpoints < hp):
                        best_loadout = loadout
                        best_shield_booster_loadout = boosters
                        best_survival_time = survival_time
                        lowest_dps = actual_dps
                        best_hitpoints = hp

        # put everything together
        best_loadout = copy.deepcopy(best_loadout)  # create copy because it might be reused by the multiprocessing pool
        best_loadout.boosters = best_shield_booster_loadout
        return TestResult(best_loadout, best_survival_time, lowest_dps, best_hitpoints)


class ShieldTester(object):
    MP_CHUNK_SIZE = 10000
    LOG_DIRECTORY = os.path.join(os.getcwd(), "Logs")
    CORIOLIS_URL = "https://coriolis.io/import?data={}"

    CALLBACK_MESSAGE = 1
    CALLBACK_STEP = 2
    CALLBACK_CANCELLED = 3

    def __init__(self):
        self.__ships = dict()  # type: Dict[str, StarShip]
        self.__booster_variants = list()
        # key of outer dictionary is the type, key for inner dictionary is the class
        # and the value is a list of all engineered shield generator combinations of that class and type
        self.__shield_generators = dict()  # type: Dict[str, Dict[int, List[ShieldGenerator]]]
        self.__unengineered_shield_generators = dict()

        self.__runtime = 0
        self.__cpu_cores = os.cpu_count()
        self.__cancel = False
        self.__pool = None  # type: multiprocessing.Pool

    @property
    def cpu_cores(self) -> int:
        return self.__cpu_cores

    @cpu_cores.setter
    def cpu_cores(self, value: int):
        self.__cpu_cores = max(1, min(os.cpu_count(), abs(value)))

    @property
    def ship_names(self):
        return [ship for ship in self.__ships.keys()]

    @staticmethod
    def calculate_number_of_tests(test_case: TestCase, prelim: int = 0) -> int:
        """
        Calculate number of tests based on shield booster variants and shield generator variants
        :return: number of tests or 0 if test_case is missing
        """
        if test_case and test_case.shield_booster_variants:
            if not prelim or prelim < 1:
                prelim = len(test_case.loadout_list)

        if test_case and test_case.shield_booster_variants:
            if prelim < 1:
                prelim = len(test_case.loadout_list)

            result = math.factorial(len(test_case.shield_booster_variants) + test_case.number_of_boosters_to_test - 1)
            result = result / math.factorial(len(test_case.shield_booster_variants) - 1) / math.factorial(test_case.number_of_boosters_to_test)
            return int(result * min(len(test_case.loadout_list), prelim))
        return 0

    def write_log(self, test_case: TestCase, result: TestResult, filename: str = None, time_and_name: bool = False, include_coriolis: bool = False):
        """
        Write a log file with the test setup from a TestCase and the results from a TestResult.
        :param test_case: TestCase for information about setup
        :param result: TestResult for information about results
        :param filename: optional filename to append new log (omit file ending)
        :param time_and_name: if set to True, the file name will be <<name> <timestamp>>.txt
        :param include_coriolis: optional link to Coriolis
        """
        os.makedirs(ShieldTester.LOG_DIRECTORY, exist_ok=True)
        if not filename:
            filename = time.strftime("%Y-%m-%d %H.%M.%S")
        elif time_and_name:
            filename = "{name} {time}".format(name=filename, time=time.strftime("%Y-%m-%d %H.%M.%S"))
        with open(os.path.join(ShieldTester.LOG_DIRECTORY, filename + ".txt"), "a+") as logfile:
            logfile.write("Test run at: {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
            logfile.write(test_case.get_output_string())
            logfile.write("\n")
            logfile.write(result.get_output_string(test_case.guardian_hitpoints))
            if include_coriolis:
                logfile.write("\n")
                logfile.write("\n")
                logfile.write(self.get_coriolis_link(result.loadout))

            logfile.write("\n\n\n")
            logfile.flush()

    def set_boosters_to_test(self, test_case: TestCase, short_list: bool = True):
        """
        Set booster variants to test.
        :param test_case: the TestCase
        :param short_list: whether to use the short list or not (short list = no boosters with explosive resistance)
        :raises RuntimeError if test_case is missing
        """
        if test_case:
            test_case.shield_booster_variants = copy.deepcopy(list(filter(lambda x: not (x.can_skip and short_list), self.__booster_variants)))
        else:
            raise RuntimeError("No test case provided")

    def __create_loadouts(self, test_case: TestCase, module_class, prismatics) -> List[LoadOut]:
        """
        Create a list containing all relevant shield generators but no boosters
        """
        loadouts_to_test = list()
        if test_case and test_case.ship:
            if module_class == 0:
                module_class = test_case.ship.highest_internal

            shield_generators = list()
            shield_generators += self.__shield_generators[ShieldGenerator.TYPE_BIWEAVE][module_class]
            shield_generators += self.__shield_generators[ShieldGenerator.TYPE_NORMAL][module_class]
            if prismatics:
                shield_generators += self.__shield_generators[ShieldGenerator.TYPE_PRISMATIC][module_class]

            shield_generators = copy.deepcopy(shield_generators)
            for sg in shield_generators:
                loadouts_to_test.append(LoadOut(sg, test_case.ship))
        return loadouts_to_test

    def get_compatible_shield_generator_classes(self, test_case: TestCase) -> Tuple[int, int]:
        """
        Find classes of shield generators that can be fitted to the selected ship.
        :param test_case
        :return: tuple: (min class, max class)
        """
        if test_case and test_case.ship:
            min_class = 0
            sg_classes = list(self.__shield_generators["normal"].keys())
            sg_classes.sort()  # make sure they are in ascending order
            for sg_class in sg_classes:
                if self.__shield_generators["normal"][sg_class][0].maxmass > test_case.ship.hull_mass:
                    min_class = sg_class
                    break

            min_free_slot = test_case.ship.get_available_internal_slot(min_class, reverse=True)[1]
            max_free_slot = test_case.ship.get_available_internal_slot(test_case.ship.highest_internal)[1]
            if min_free_slot > 0 and max_free_slot > 0:
                return min(min_class, min_free_slot), max_free_slot
        return 0, 0

    def set_loadouts_for_class(self, test_case: TestCase, module_class: int = 0, prismatics: bool = True):
        """
        Set test_case.loadout_list with all shield generator variants of the given class.
        :param test_case: the TestCase
        :param module_class: module class of shield (1-8). Only a valid class will be set or the maximum if not specified or invalid.
        :param prismatics: whether to use prismatics or not
        :raises RuntimeError if test_case is missing
        """
        if not test_case:
            raise RuntimeError("test_case is missing")

        min_class, max_class = self.get_compatible_shield_generator_classes(test_case)
        sg_class = module_class if module_class in range(min_class, max_class + 1) else max_class
        if sg_class > 0:
            test_case.loadout_list = self.__create_loadouts(test_case, sg_class, prismatics)
            test_case._use_prismatics = prismatics

    def get_default_shield_generator_of_variant(self, sg_variant: ShieldGenerator) -> Optional[ShieldGenerator]:
        """
        Provide a (engineered) shield generator to get a copy of the same type but as non-engineered version.
        :param sg_variant: the (engineered) shield generator
        :return: ShieldGenerator or None
        """
        if sg_variant:
            return copy.deepcopy(self.__unengineered_shield_generators.get(sg_variant.symbol))
        return None

    def compute(self, test_case: TestCase,
                callback: function = None,
                message_queue: queue.SimpleQueue = None,
                console_output: bool = False,
                prelim: int = 0) -> Optional[TestResult]:
        """
        Compute best loadout. Best to call this in an extra thread. It might take a while to complete.
        If set, the callback will be called [<number of tests> / (test_case.loadout_list or prelim) / MP_CHUNK_SIZE] times (+2 if queue is set).
        Callback function will be called with CALLBACK_MESSAGE if there is a new message and
                                              CALLBACK_STEP is used for each step
        Calling cancel() will stop the execution of this method. Some callbacks might be called before that happens.
        :param test_case: settings of test case
        :param callback: optional callback using an int as argument
        :param console_output: whether you want output on the console or not
        :param message_queue: message queue containing some output messages
        :param prelim: If set to a positive integer, prelim limits the amount of shield generators to consider for further tests. They are chosen by comparing
                       their stats without applying any boosters to them. <prelim> of the best ones will be tested with all booster combinations.
                       prelim of 5 will find the same best loadout in the vast majority of cases and 13 should find the same best loadout in all cases.
                       Using this option will alter test_case.loadout_list
        """
        self.__cancel = False
        if not test_case or not test_case.shield_booster_variants or not test_case.loadout_list:
            # nothing to test
            # TODO maybe raise exception
            print("Can't test nothing")
            return

        if console_output:
            print(test_case.get_output_string())

        self.__runtime = time.time()
        output = list()

        # ensure booster amount is valid
        booster_amount = test_case.number_of_boosters_to_test
        booster_amount = max(0, min(test_case.ship.utility_slots, booster_amount))
        # use built in itertools and assume booster ids are starting at 1 and that there are no gaps
        booster_combinations = list(itertools.combinations_with_replacement(range(0, len(test_case.shield_booster_variants)), booster_amount))

        if prelim > 0 and prelim != len(test_case.loadout_list):
            output.append("--------- QUICK TEST RUN ---------")
        else:
            output.append("------------ TEST RUN ------------")

        # preliminary filtering
        if prelim > 0 and prelim != len(test_case.loadout_list):
            preliminary_list = list()
            preliminary_list_survived = list()
            best_survival_time = 0
            lowest_dps = 10000

            for loadout in test_case.loadout_list:
                # can't use same function in LoadOut because of speed
                exp_res = 1 - loadout.shield_generator.explres
                kin_res = 1 - loadout.shield_generator.kinres
                therm_res = 1 - loadout.shield_generator.thermres
                hp = loadout.shield_strength
                regen_rate = loadout.shield_generator.regen * (1.0 - test_case.damage_effectiveness)

                actual_dps = test_case.damage_effectiveness * (
                        test_case.explosive_dps * exp_res +
                        test_case.kinetic_dps * kin_res +
                        test_case.thermal_dps * therm_res +
                        test_case.absolute_dps) - regen_rate

                survival_time = (hp + test_case.scb_hitpoints + test_case.guardian_hitpoints) / actual_dps

                if actual_dps > 0:
                    preliminary_list.append((survival_time, loadout))
                    if best_survival_time >= 0:
                        # if another run set best_survival_time to a negative value, then the ship didn't die, therefore the other result is better
                        if survival_time > best_survival_time:
                            best_survival_time = survival_time
                elif actual_dps < 0:
                    preliminary_list_survived.append((actual_dps, loadout))
                    if lowest_dps > actual_dps:
                        best_survival_time = survival_time
                        lowest_dps = actual_dps

            # set only the best loadouts to be tested
            if len(preliminary_list_survived) > 0:
                preliminary_list_survived.sort(key=lambda tup: tup[0])
                test_case.loadout_list = [t[1] for t in preliminary_list_survived[:prelim]]
            else:
                preliminary_list.sort(key=lambda tup: tup[0], reverse=True)
                test_case.loadout_list = [t[1] for t in preliminary_list[:prelim]]

        output.append(("Shield Booster Count: ", f"[{test_case.number_of_boosters_to_test}]"))
        output.append(("Shield Generator Variants: ", f"[{len(test_case.loadout_list)}]"))
        output.append(("Shield Booster Variants: ", f"[{len(booster_combinations)}]"))
        output.append(("Shield loadouts to be tested: ", f"[{len(booster_combinations) * len(test_case.loadout_list):n}]"))
        output.append("Running calculations. Please wait...")
        output.append("")
        if message_queue:
            message_queue.put(Utility.format_output_string(output))
            if callback:
                callback(ShieldTester.CALLBACK_MESSAGE)
        if console_output:
            print(Utility.format_output_string(output))  # in case there is a console
        output = list()

        best_result = TestResult(survival_time=0)

        def apply_async_callback(r: TestResult):
            nonlocal best_result
            if best_result.survival_time < 0:
                # ship didn't die
                if best_result.incoming_dps > r.incoming_dps or (math.isclose(best_result.incoming_dps, r.incoming_dps, rel_tol=1e-8)
                                                                 and best_result.total_hitpoints < r.total_hitpoints):
                    best_result = r
            else:
                if r.survival_time < 0:
                    best_result = r
                elif r.survival_time > best_result.survival_time:
                    best_result = r
            if callback:
                callback(ShieldTester.CALLBACK_STEP)

        def chunks(l, n):
            for j in range(0, len(l), n):
                yield l[j:j + n]

        if self.__cpu_cores > 1 and (len(booster_combinations) * len(test_case.loadout_list)) > ShieldTester.MP_CHUNK_SIZE:
            # 1 core is handling UI and this thread, the rest is working on running the calculations
            with multiprocessing.Pool(processes=self.__cpu_cores - 1) as pool:
                self.__pool = pool
                for chunk in chunks(booster_combinations, ShieldTester.MP_CHUNK_SIZE):
                    if self.__cancel:
                        print("Cancelled")
                        self.__pool = None
                        if callback:
                            callback(ShieldTester.CALLBACK_CANCELLED)
                        return None
                    pool.apply_async(TestCase.test_case, args=(test_case, chunk), callback=apply_async_callback)

                # set priority of child processes to below normal
                if _psutil_imported:
                    parent = psutil.Process()
                    for child in parent.children():
                        if sys.platform == "win32":
                            child.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                        else:
                            child.nice(10)
                pool.close()
                pool.join()
                self.__pool = None
        else:
            for chunk in chunks(booster_combinations, ShieldTester.MP_CHUNK_SIZE):
                if self.__cancel:
                    print("Cancelled")
                    if callback:
                        callback(ShieldTester.CALLBACK_CANCELLED)
                    return None
                result = TestCase.test_case(test_case, chunk)
                apply_async_callback(result)  # can use the same function here as mp.Pool would

        if self.__cancel:
            print("Cancelled")
            if callback:
                callback(ShieldTester.CALLBACK_CANCELLED)
            return None

        output.append("Calculations took {:.2f} seconds".format(time.time() - self.__runtime))
        output.append("")
        if message_queue:
            message_queue.put("\n".join(output))
            if callback:
                callback(ShieldTester.CALLBACK_MESSAGE)
        if console_output:
            print("\n".join(output))
            print(best_result.get_output_string(test_case.guardian_hitpoints))

        return best_result

    def get_coriolis_link(self, loadout: LoadOut) -> str:
        """
        Generate a link to coriolis to import the current shield build.
        :param loadout: loadout containing the build (e.g. get from results)
        :return:
        """
        if loadout and loadout.shield_generator:
            loadout_dict = loadout.generate_loadout_event(self.get_default_shield_generator_of_variant(loadout.shield_generator))
            loadout_gzip = gzip.compress(json.dumps(loadout_dict).encode("utf-8"))
            loadout_b64 = base64.urlsafe_b64encode(loadout_gzip).decode("utf-8").replace('=', '%3D')
            return ShieldTester.CORIOLIS_URL.format(loadout_b64)
        return ""

    def select_ship(self, name: str) -> Optional[TestCase]:
        """
        Select a ship by its name. Get names from the property ship_names.
        This creates a new TestCase with the selected ship and the highest possible shield generator variants pre-selected.
        :param name: Name of the ship
        :return: True if loaded successfully, False otherwise
        """
        if name in self.__ships:
            test_case = TestCase(copy.deepcopy(self.__ships[name]))
            self.set_loadouts_for_class(test_case)
            test_case.number_of_boosters_to_test = test_case.ship.utility_slots
            self.set_boosters_to_test(test_case, short_list=True)
            return test_case
        return None

    def cancel(self):
        self.__cancel = True
        if self.__pool:
            self.__pool.terminate()
            self.__pool = None

    def load_data(self, file: str):
        """
        Load data.
        :param file: Path to json file
        """
        with open(file) as json_file:
            j_data = json.load(json_file)

            # load ships
            for j_ship in j_data["ships"]:
                ship = StarShip.create_from_json(j_ship)
                self.__ships.setdefault(ship.name, ship)

            # load shield booster variants
            for booster_variant in j_data["shield_booster_variants"]:
                self.__booster_variants.append(ShieldBoosterVariant.create_from_json(booster_variant))

            # load shield generators
            sg_node = j_data["shield_generators"]
            for sg_type, sg_list in sg_node["modules"].items():
                sg_type_dict = self.__shield_generators.setdefault(sg_type, dict())
                for j_generator in sg_list:
                    generator = ShieldGenerator.create_from_json(j_generator)
                    self.__unengineered_shield_generators.setdefault(generator.symbol, generator)
                    generator_variants = ShieldGenerator.create_engineered_shield_generators(generator,
                                                                                             sg_node["engineering"]["blueprints"],
                                                                                             sg_node["engineering"]["experimental_effects"])
                    sg_type_dict.setdefault(generator.module_class, generator_variants)
