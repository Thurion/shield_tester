import base64
import gzip
import json
import urllib.request
from typing import List, Any, Dict


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

    # noinspection PyBroadException
    @staticmethod
    def get_loadouts_from_string(s: str) -> List[Dict[str, any]]:
        r = list()
        if not s:
            return r

        # 1st possibility: one loadout event spanning over multiple lines
        try:
            return [json.loads(s)]
        except Exception:
            # not a single json
            pass

        # multiple entries then
        try:
            lines = s.split("\n")
            for line in lines:
                if line.startswith("https://"):
                    parts = line.split("=")
                    r.append(json.loads(gzip.decompress(base64.b64decode(urllib.request.unquote_to_bytes(parts[1]))).decode("utf-8")))
                else:
                    r.append(json.loads(line))
        except Exception:
            pass

        return r
