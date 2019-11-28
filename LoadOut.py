import math
import copy
from typing import List, Optional, Tuple, Dict, Any

from .ShieldBoosterVariant import ShieldBoosterVariant
from .ShieldGenerator import ShieldGenerator
from .StarShip import StarShip


class LoadOut(object):
    def __init__(self, shield_generator: ShieldGenerator, ship: StarShip):
        self.shield_generator = shield_generator
        self.ship = ship
        self.boosters = None  # type: List[ShieldBoosterVariant]
        self.shield_strength = self.__calculate_shield_strength()

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

        loadout_json = copy.deepcopy(self.ship.loadout_template)
        modules = loadout_json["Modules"]
        modules.append(self.shield_generator.create_loadout(default_sg, *self.ship.get_available_internal_slot(self.shield_generator.module_class, reverse=True)))

        if len(self.boosters) > self.ship.utility_slots:
            raise RuntimeError("Booster number mismatch")

        for i in range(0, min(len(self.boosters), self.ship.utility_slots)):
            modules.append(self.boosters[i].get_loadout_template_slot(self.ship.utility_slots_free[i]))
        return loadout_json
