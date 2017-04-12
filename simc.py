#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)
#
""" A wrapper around the SimulationCraft executable that configures simple simulations
    and returns the result as JSON encoded text.
    This can be called as a standalone python program as desired but is primarily
    designed to be called from a daemon listening for requests on a message queue
    and returning the response similarly.
"""

import os,subprocess,logging,shlex,tempfile,re,argparse,json
import urllib.request
import configparser

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

class Simc(object):
    """ Python wrapper around the SimulationCraft executable.
    """

    def __init__(self):
        if os.path.isfile('discord_simc.conf'):
            self.parse_config('discord_simc.conf')
        else:
            self._simc_path = "./simc"
            self._output_path = "."
            self._profile_path = "./profiles"
            self._url_prefix = "http://localhost/"
            self._default_realm = "khazgoroth"
            self._blizzard_key = None

    def run(self, character, **kwargs):
        """ Runs a simulation and then looks up additional information for the caller

        :param str character: name of character to sim
        """
        LOGGER.info('Run called with character name {}'.format(character))
        params = {}
        try:
            params = self.parse_args(character, **kwargs)
            cmd= self.generate_cmd(params)
            
            result=subprocess.check_output(cmd).decode('utf-8')
            if "output" in kwargs.keys():
                print(result)

            params["colour"] = 0x119911
            params["output_realm"] = None
            params["thumbnail"] = None
            if self._blizzard_key:
                f=urllib.request.urlopen('https://us.api.battle.net/wow/character/{}/{}?locale=en_US&apikey={}'.format(
                    params["realm"],
                    params["character"],
                    self._blizzard_key))
                toonjson=f.read().decode('utf-8')
                f.close()
                toon = json.loads(toonjson)
                params["output_realm"] = toon["realm"]
                params["thumbnail"] = toon["thumbnail"]
                if toon["faction"]==0:
                    params["colour"] = 0x1111FF
                else:
                    params["colour"] = 0xFF1111

            # Player: Vengel night_elf warrior protection 110
            match = re.search(r'^Player:\s+(\w+)\s+(\w+)\s+(\w+)\s+(\w+)\s+\d+$', result, re.I|re.M|re.U)
            if match:
                params["output_character"]=match.group(1).replace('_',' ').capitalize()
                params["output_race"]=match.group(2).replace('_',' ').capitalize()
                params["output_class"]=match.group(3).replace('_',' ').capitalize()
                params["output_spec"]=match.group(4).replace('_',' ').capitalize()

            match = re.search(r'^\s*DPS:\s+([\.\d]+)\s+?.*$', result, re.I|re.M)
            if match:
                params["dps"]=match.group(1)

            # Weights :  Agi=9.85(0.17)  AP=9.31(0.17)  Crit=4.83(0.16)  Haste=3.16(0.16)  Mastery=5.95(0.17)  Vers=5.05(0.16)  Wdps=9.22(0.17)  WOHdps=0.81(0.16)
            match = re.search(r'^\s*Weights\s*:\s*(.+)?\s*$', result, re.I|re.M)
            if match:
                weights = match.group(1)
                weights = re.sub(r'\([\.\d]+\)', '', weights)
                weights = re.sub(r'\s{2,}', ' ', weights)
                params["weights"]=weights
            else:
                params["weights"]=""

        except CalledProcessError as e:
            LOGGER.error('CalledProcessError calling simc')
            LOGGER.error(str(e))
            
        except Exception as e:
            LOGGER.error('Exception calling simc')
            LOGGER.error(str(e))

        finally:
            if "tmpfile" in params.keys() and os.path.isfile(params["tmpfile"]):
                os.unlink( params.pop("tmpfile") )

        return params

    def parse_args(self, character, **kwargs):
        """ Creates a dictionary from the arguments that were passed
            and adds other important mappings.

        """
        params = {
            "character" : character
         }

        if "realm" in kwargs.keys():
            params["realm"] = kwargs["realm"]
        else:
            params["realm"] = self._default_realm
        params["filename"] = "{}_{}".format(params["realm"], character)

        if "movement" in kwargs.keys() and kwargs["movement"] in ["light","heavy"]:
            if kwargs["movement"] == "light":
                params["movement"] = "light"
                params["filename"] = "{}_{}".format( params["filename"], "light" )
            elif kwargs["movement"] == "heavy":
                params["movement"] = "heavy"
                params["filename"] = "{}_{}".format( params["filename"], "heavy" )
        else:
            params["movement"] = "none"

        if "scaling" in kwargs.keys() and kwargs["scaling"] == "1":
            params["scaling"] = "scale"
            params["filename"] = "{}_{}".format( params["filename"], "scale" )
        else:
            params["scaling"] = "none"

        params["path"] = "{}/{}.html".format(self._output_path, params["filename"])
        params["url"] = "{}/{}.html".format(self._url_prefix, params["filename"])
        LOGGER.debug(str(params))
        return params

    def generate_cmd(self, params):
        """ Creates a list of arguments used to spawn the subprocess to run simc binary

        """
        cmd = [ self._simc_path ]
        cmd.append("{}/basic.simc".format(self._profile_path))
        self.create_toon_file(params)
        cmd.append(params["tmpfile"])

        if params["movement"] == "light":
            cmd.append("{}/Raid_Event_Movement_Light.simc".format(self._profile_path))
        elif params["movement"] == "heavy":
            cmd.append("{}/Raid_Event_Movement_Heavy.simc".format(self._profile_path))

        if params["scaling"] == "scale":
            cmd.append("{}/scaling.simc".format(self._profile_path))
        else:
            cmd.append("{}/noscaling.simc".format(self._profile_path))
        LOGGER.debug(str(cmd))
        return cmd
        
    def create_toon_file(self,params):
        """ Creates the input file to specify the realm and character to sim.
            We want to avoid passing unchecked arguments as command parameters.

        """
        tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False)
        tmpfile.write("armory=us,{},{}\n".format(params["realm"],params["character"]))
        tmpfile.close()
        params["tmpfile"] = tmpfile.name

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        LOGGER.debug("parsing config file: {}".format(file))
        config = configparser.ConfigParser()
        config.read(file)
        self._simc_path = config['simc']['simc_path']
        self._output_path = config['simc']['output_path']
        self._profile_path = config['simc']['profile_path']
        self._url_prefix = config['simc']['url_prefix']
        self._default_realm = config['simc']['default_realm']
        self._blizzard_key = config['simc']['blizzard_key']

def parse_args():
    """ Parse arguments when we are invoked as a program.

    """
    parser = argparse.ArgumentParser(description="Run a SimulationCraft simulation.")
    parser.add_argument('character', help='the character to simulate')
    parser.add_argument('--realm','-r', help='the warcraft realm', default='khazgoroth')
    parser.add_argument('--movement','-m', help='how much movement to simulate', choices=['none','light','heavy'])
    parser.add_argument('--scaling','-s', action='store_const', const="1", help='whether to perform stat scaling simulation')
    parser.add_argument('--output','-o', action='store_const', const="1", help='whether to display the simc text on stdout')
    return vars(parser.parse_args())

if __name__ == '__main__':
    args = parse_args()
    character = args.pop('character')

    simc = Simc()
    result = simc.run(character, **args)
    print(str(result))
