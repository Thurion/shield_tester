from .LoadOut import LoadOut
from .Utility import Utility


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
