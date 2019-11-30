import base64
import copy
import gzip
import itertools
import json
import math
import multiprocessing
import os
import queue
import re
import sys
import time
import unicodedata
from typing import Dict, List, Tuple, Optional, Any

from .LoadOut import LoadOut
from .ShieldBoosterVariant import ShieldBoosterVariant
from .ShieldGenerator import ShieldGenerator
from .StarShip import StarShip
from .TestCase import TestCase
from .TestResult import TestResult
from .Utility import Utility

try:
    # noinspection PyUnresolvedReferences
    import psutil
    _psutil_imported = True
except ImportError as error:
    _psutil_imported = False
    print(error)


class ShieldTester(object):
    MP_CHUNK_SIZE = 10000
    LOG_DIRECTORY = os.path.join(os.getcwd(), "Logs")

    SERVICE_CORIOLIS = 0
    SERVICE_EDSY = 1
    SERVICE_URLS = ["https://coriolis.io/import?data={}",
                    "https://edsy.org/#/I={}"]
    SERVICE_NAMES = ["Coriolis", "EDSY"]

    CALLBACK_MESSAGE = 1
    CALLBACK_STEP = 2
    CALLBACK_CANCELLED = 3

    def __init__(self):
        self.__ships = dict()  # type: Dict[str, StarShip]
        self.__importedShips = dict()  # type: Dict[str, StarShip]
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
        return sorted([ship for ship in self.__importedShips.keys()]) + sorted([ship for ship in self.__ships.keys()])

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

    def slugify(self, value):
        """
        Normalizes string, converts to lowercase, removes non-alpha characters,
        and converts spaces to hyphens.
        """
        value = unicodedata.normalize("NFKD", value)
        value = re.sub("[^.()\[\]\w\s-]", "", value, flags=re.ASCII).strip()
        value = re.sub("[\s]+", "_", value, flags=re.ASCII)
        return value

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
            filename = f"{filename} {time.strftime('%Y-%m-%d %H.%M.%S')}"

        filename = self.slugify(filename)
        with open(os.path.join(ShieldTester.LOG_DIRECTORY, filename + ".txt"), "a+") as logfile:
            logfile.write("Test run at: {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
            logfile.write(test_case.get_output_string())
            logfile.write("\n")
            logfile.write(result.get_output_string(test_case.guardian_hitpoints))
            if include_coriolis:
                logfile.write("\n")
                logfile.write("\n")
                logfile.write(self.get_export_link(result.loadout))

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

    def get_compatible_shield_generator_classes(self, ship: StarShip) -> Tuple[int, int]:
        """
        Find classes of shield generators that can be fitted to the selected ship.
        :param ship
        :return: tuple: (min class, max class)
        """
        if ship:
            min_class = 0
            sg_classes = list(self.__shield_generators["normal"].keys())
            sg_classes.sort()  # make sure they are in ascending order
            for sg_class in sg_classes:
                if self.__shield_generators["normal"][sg_class][0].maxmass > ship.hull_mass:
                    min_class = sg_class
                    break

            max_free_slot = ship.get_available_internal_slot(ship.highest_internal)[1] or 0
            if min_class and min_class <= max_free_slot:
                return min_class, max_free_slot
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

        min_class, max_class = self.get_compatible_shield_generator_classes(test_case.ship)
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
                callback=None,
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

        if self.__cpu_cores > 1 and (len(booster_combinations) * len(test_case.loadout_list)) > ShieldTester.MP_CHUNK_SIZE * 5:
            # 1 core is handling UI and this thread, the rest is working on running the calculations
            # and don't use multiprocessing for a very small workload
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

    def get_export_link(self, loadout: LoadOut, service: int = 0):
        """
        Generate a link to Coriolis or EDSY to import the current shield build.
        :param loadout: loadout containing the build (e.g. get from results)
        :param service: use SERVICE_ constants
        :return:
        """
        if loadout and loadout.shield_generator:
            loadout_dict = loadout.generate_loadout_event(self.get_default_shield_generator_of_variant(loadout.shield_generator))
            loadout_gzip = gzip.compress(json.dumps(loadout_dict).encode("utf-8"))
            loadout_b64 = base64.urlsafe_b64encode(loadout_gzip).decode("utf-8").replace('=', '%3D')
            return ShieldTester.SERVICE_URLS[service].format(loadout_b64)
        return ""

    def select_ship(self, name: str) -> TestCase:
        """
        Select a ship by its name. Get names from the property ship_names.
        This creates a new TestCase with the selected ship and the highest possible shield generator variants pre-selected.
        :param name: Name of the ship
        :return: True if loaded successfully, False otherwise
        """
        if name not in self.__ships and name not in self.__importedShips:
            raise RuntimeError("Could not select ship.")

        if name in self.__ships:
            test_case = TestCase(copy.deepcopy(self.__ships[name]))
        else:
            test_case = TestCase(copy.deepcopy(self.__importedShips[name]))
        self.set_loadouts_for_class(test_case)
        test_case.number_of_boosters_to_test = test_case.ship.utility_slots
        self.set_boosters_to_test(test_case, short_list=True)
        return test_case

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

    def import_loadout(self, l: Dict[str, Any]) -> str:
        """
        Import a loadout event. The same ship name will overwrite a previous import of the same name.
        :param l: dictionary of the imported loadout event
        :return: Name of imported ship
        """
        ship_symbol = l["Ship"]
        imported_ship = None  # type: StarShip
        for ship in self.__ships.values():
            if ship_symbol.lower() == ship.symbol.lower():
                imported_ship = copy.deepcopy(ship)
                break
        if not imported_ship:
            return ""  # can't import this ship

        if "ShipName" in l:
            name = l["ShipName"]
            imported_ship.loadout_template["ShipName"] = l["ShipName"]
        else:
            name = imported_ship.name
        if "ShipIdent" in l:
            ident = l["ShipIdent"]
            imported_ship.loadout_template["ShipIdent"] = l["ShipIdent"]
        else:
            ident = "Imported"
        imported_ship.custom_name = f"{name} ({ident})"
        imported_ship.loadout_template["Modules"] = copy.deepcopy(l["Modules"])

        imported_ship.highest_internal = 0
        items_to_remove = list()
        for module in imported_ship.loadout_template["Modules"]:
            if module["Slot"].lower().startswith("tinyhardpoint"):
                # get amount of fitted shield boosters
                if module["Item"].lower().startswith("hpt_shieldbooster_size0"):
                    items_to_remove.append(module)
                else:
                    imported_ship.utility_slots_free.remove(int(module["Slot"][-1:]))  # remove free slot
            elif module["Item"].lower().startswith("int_shieldgenerator_size"):
                # get shield generator class
                imported_ship.highest_internal = int(module["Slot"][-1:])
                items_to_remove.append(module)
            elif re.match("slot[0-9]{2}_size[0-9]", module["Slot"].lower()):
                slot_number = int(module["Slot"][4:6])
                if slot_number in imported_ship.internal_slot_layout:
                    # will fail when encountering a military only slot
                    imported_ship.internal_slot_layout.pop(int(module["Slot"][4:6]))

        for module in items_to_remove:
            imported_ship.loadout_template["Modules"].remove(module)

        imported_ship.utility_slots_free.sort()
        min_sg, max_sg = self.get_compatible_shield_generator_classes(imported_ship)
        if min_sg == 0 or max_sg == 0:
            return ""
        self.__importedShips[imported_ship.custom_name] = imported_ship  # overwrite old imports with the same name
        return imported_ship.custom_name
