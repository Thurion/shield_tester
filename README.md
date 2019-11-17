# Shield Tester (Python Version)
This started out as an implementation in Python 3 of [Down to Earth Astronomy's](https://github.com/DownToEarthAstronomy/D2EA_Shield_tester) Power Shell script. But after a lot of features, including the use of its own independent data model, had been added it moved to its own repository.

## Abstract
Many of us run many different ships, with many stored shield generators and modules with many forms of engineering. It might be tempting to just put on Heavy Duty / Deep plating, but is that really the best alternative? How do you choose the best loadout? 

Before D2EA's shield tester tool, it was the usual metas, which undeniably work. However, there's so many combinations, it's hard to say for sure if the meta for your ship and combat or defense scenario is the best alternative. 

We need a way of figuring out the best combination of generator and shield boosters for situational scenarios. For example, you might want to change between mining to fighting Thargoid Interceptors or NPCs in combat zones. All of three scenarios require slightly different loadouts. 

### Why a Python version? 
tl;dr: Speed. Nothing else. The other versions work just fine. 

The original Powershell version is groundbreaking research, but is fairly slow, and thus might discourage some from running the tool when they change ships or combat scenarios. 

The multi-threaded Python port is many times faster per CPU thread. It might not be as fast as the Go version but it's fast enough to run any amount of shield boosters within a reasonable time.

### Improvements to these tools
In a [comment](https://www.youtube.com/watch?v=87DMWz8IeEE&lc=Ugz-fl387Mi0ePTFCZ94AaABAg) to the original D2EA video, Cmdr Kaethena listed a few limitations and scenarios that you should read to understand that these tools are a good starting point, but possibly not the ending point for your shield loadouts. There are a lot of situations where a more generalist loadout might help you more than a max survivability loadout from this tool. YMMV. 

## How to use
Here is a working but probably incomplete example:
```python
import shield_tester as st

def main():
    tester = st.ShieldTester()
    tester.load_data("data.json")

    # get a list of ships and select one
    print(tester.ship_names)
    if tester.select_ship("Anaconda"):
        print("Anaconda selected")
    else:
        print(":(")
        return

    # get a new test case
    test_case = tester.get_test_case()

    # get some information
    print("Number of boosters: {}".format(test_case.ship.utility_slots))
    # can call without test_case, then internally stored test_case will be used
    min_class, max_class = tester.get_compatible_shield_generator_classes(test_case)
    print("Can fit class {min} to {max} shield generators".format(min=min_class, max=max_class))

    # set defender data
    test_case.number_of_boosters_to_test = 2
    # we don't have access to prismatic
    tester.use_prismatics = False  # this triggers the creation of a new list of shield generators
    # ... but we got some guardian boosters
    test_case.guardian_hitpoints = 420
    # we want a class 6 shield instead
    tester.create_loadouts_for_class(6, test_case=test_case)

    # set attacker data
    test_case.absolute_dps = 10
    test_case.thermal_dps = 50
    test_case.kinetic_dps = 50
    test_case.damage_effectiveness = 0.65

    # misc settings
    tester.cpu_cores = 2
    tester.use_short_list = True  # default value

    print("Number of tests: {}".format(tester.number_of_tests))

    # run the test:
    test_result = tester.compute(test_case)  # can add callback function and a simple queue for messages

    # what is our setup again?
    print(test_case.get_output_string())
    if test_result:
        # print the results, don't forget to add the guardian booster hitpoints. 
        # test_result has no access to the setup and those values are not stored
        print(test_result.get_output_string(test_case.guardian_hitpoints))

        # write the logfile
        tester.write_log(test_case, test_result, filename="my test", time_and_name=True, include_coriolis=True)

        # in case we want to do something with the coriolis link
        link_to_coriolis = tester.get_coriolis_link(test_result.best_loadout)
    else:
        print("Something went wrong...")

if __name__ == '__main__':
    main()
```