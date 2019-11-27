from __future__ import annotations

import copy
import math
from typing import List

from .LoadOut import LoadOut
from .ShieldBoosterVariant import ShieldBoosterVariant
from .StarShip import StarShip
from .TestResult import TestResult
from .Utility import Utility


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
            output.append(("Ship Type: ", f"[{self.loadout_list[0].ship.name}]"))
            if self.loadout_list[0].ship.custom_name:
                output.append(("Custom name: ", f"[{self.loadout_list[0].ship.custom_name}]"))
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
