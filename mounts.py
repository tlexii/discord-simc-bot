#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)
#
""" Retrieve and parse WoW mount collection.
    This can be called as a standalone python program as desired but is primarily
    designed to be called from a daemon listening for requests on a message queue
    and returning the response similarly.
"""

import os,logging,shlex,tempfile,re,argparse,json
import discord
import urllib.request
import configparser
from datetime import datetime,timedelta

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
#logging.basicConfig(filename='/var/log/mountsdaemon.log', format=LOG_FORMAT, level=logging.INFO)
LOGGER = logging.getLogger(__name__)

class Mounts(object):
    """ Python wrapper around the SimulationCraft executable.
    """

    def __init__(self):
        if os.path.isfile('discord_simc.conf'):
            self.parse_config('discord_simc.conf')
        else:
            self._output_path = "./cache"
            self._default_realm = "khazgoroth"
            self._blizzard_key = None

    def check_realm(self,r):
        transtable = str.maketrans("","","'")
        cleaned = str(r).lower().translate(transtable)
        return cleaned

    def cmd(self):
        return '!mounts'

    def run(self, character, **kwargs):
        """ Runs a simulation and then looks up additional information for the caller

        :param str character: name of character to sim
        """
        LOGGER.info('Run called with character name {}'.format(character))
        params = {}
        try:
            params = self.parse_args(character, **kwargs)
            params["colour"] = 0x119911
            params["output_realm"] = None
            params["thumbnail"] = None

            toon = self.get_data( params["realm"], params["character"], params["filename"])
            mounts = toon["mounts"]
            #params["lastModified"] = toon["lastModified"]
            params["output_name"] = toon["name"]
            params["collected"] = mounts["numCollected"]
            params["uncollected"] = mounts["numNotCollected"]
            params["output_realm"] = toon["realm"]
            params["thumbnail"] = toon["thumbnail"]
            if toon["faction"]==0:
                params["colour"] = 0x1111FF
            else:
                params["colour"] = 0xFF1111
            LOGGER.debug(str(params))

            if "output" in kwargs.keys() and kwargs["output"]==1:
                print(str(params))

        except Exception as e:
            LOGGER.error('Exception calling mounts')
            LOGGER.error(str(e))
            raise

        return params

    def create_payload_from_msg(self, msg):
        """
            Strips the command from the start and turns the input into a dictionary
        """
        raw_data=msg[ len(self.cmd())+1 : ]
        words=raw_data.split()
        result = {
            "character" : words[0]
        }
        if len(words) == 1:
            result["realm"] = "khazgoroth"
            LOGGER.info('using default realm {}'.format(result["realm"]))
        else:
            result["realm"] = self.check_realm(words[1])
        LOGGER.info('using realm {}'.format(result["realm"]))
        return result

    def get_data(self, realm, character, filename):
        # look for existing file
        toon = None
        if os.path.isfile(filename):
            try:
                f = open(filename,"rt")
                toon = json.load(f)
                lastModified = datetime.fromtimestamp( toon["lastModified"] / 1000 )
                plus10 = lastModified + timedelta(minutes=10)
                LOGGER.debug('last modified {}'.format(str(lastModified)))
                LOGGER.debug('plus 10 min {}'.format(str(plus10)))
                if datetime.now() < plus10:
                    toon = None
            except Exception as e:
                LOGGER.error('Exception calling mounts')
                LOGGER.error(str(e))
                raise
            finally:
                f.close()

        if toon == None:
            # retrieve from blizz
            url='https://us.api.battle.net/wow/character/{}/{}?fields=mounts&locale=en_US&apikey={}'.format(realm, character, self._blizzard_key)
            LOGGER.info(url)
            f=urllib.request.urlopen(url)
            toonjson=f.read().decode('utf-8')
            f.close()
            f = open(filename,"wt")
            f.write(toonjson)
            f.close()
            toon = json.loads(toonjson)
        return toon 

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
        params["filename"] = "./{}/{}_{}_mounts.json".format(self._output_path, params["realm"], character)
        LOGGER.debug(str(params))
        return params

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        LOGGER.debug("parsing config file: {}".format(file))
        config = configparser.ConfigParser()
        config.read(file)
        self._default_realm = config['warcraft']['default_realm']
        self._output_path = config['mounts']['cache']
        self._blizzard_key = config['blizzard']['blizzard_key']

    def generate_embed(self,result):
        embed = discord.Embed(
            url='https://worldofwarcraft.com/en-us/character/{}/{}/collections/mounts'.format(
                result["realm"],
                result["character"]),
            title="Mount collection",
            description='Progress: {}/{}'.format(result["collected"],result["collected"]+result["uncollected"]),
        )
        embed.set_thumbnail(url='http://wow.zamimg.com/images/wow/icons/large/ability_mount_spectraltiger.jpg')
        return embed

def parse_args():
    """ Parse arguments when we are invoked as a program.

    """
    parser = argparse.ArgumentParser(description="Retrieve World of Warcraft mount collection progress.")
    parser.add_argument('character', help='the character to lookup')
    parser.add_argument('--realm','-r', help='the warcraft realm', default='khazgoroth')
    parser.add_argument('--output','-o', action='store_const', const="1", help='whether to display the mounts text on stdout')
    return vars(parser.parse_args())

if __name__ == '__main__':
    logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)
    args = parse_args()
    character = args.pop('character')

    mounts = Mounts()
    result = mounts.run(character, **args)
    #print(str(result))
