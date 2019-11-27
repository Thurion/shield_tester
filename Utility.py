from typing import List, Any


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
