from typing import Dict, Any, List, Tuple, Optional
import copy


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
    def create_from_json(json_booster: Dict[str, Any]) -> "ShieldBoosterVariant":
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
    def calculate_booster_bonuses(shield_boosters: List["ShieldBoosterVariant"], booster_loadout: List[int] = None) -> Tuple[float, float, float, float]:
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
