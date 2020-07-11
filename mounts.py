#!python
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
import overlordauth
from urllib.request import Request,urlopen
import configparser
from datetime import datetime,timedelta


class Mounts(object):
    """ Python program to retrieve a characters mounts information from blizzard.
    """

    def __init__(self):
        if os.path.isfile('discord_simc.conf'):
            self.parse_config('discord_simc.conf')
        else:
            self._output_path = "./cache"
            self._default_realm = "khazgoroth"

        #self._auth = overlordauth.OverlordAuthFile('discord_simc.conf')
        self._auth = overlordauth.OverlordAuthDb('discord_simc.conf')
            

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
        logging.info('Run called with character name {}'.format(character))
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
            params["collected"] = len(toon["mounts"])
            params["uncollected"] = 999
            params["output_realm"] = toon["realm"]
            params["thumbnail"] = '' # toon["thumbnail"]
            toon["faction"]=0
            if toon["faction"]==0:
                params["colour"] = 0x1111FF
            else:
                params["colour"] = 0xFF1111
            logging.debug(str(params))

            if "output" in kwargs.keys() and kwargs["output"]==1:
                print(str(params))

        except Exception as e:
            logging.error('Exception calling mounts')
            logging.error(str(e))
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
            logging.info('using default realm {}'.format(result["realm"]))
        else:
            result["realm"] = self.check_realm(words[1])
        logging.info('using realm {}'.format(result["realm"]))
        return result

    def get_data(self, realm, character, filename):
        # look for existing file
        toon = None
        if os.path.isfile(filename):
            nextcheck = datetime.fromtimestamp(os.path.getmtime(filename)) + timedelta(minutes=2)
            logging.debug('file nextcheck {}'.format(str(nextcheck)))
            if datetime.now() < nextcheck:  # use cached version
                try:
                    f = open(filename,"rt")
                    toon = json.load(f)
                    lastModified = datetime.fromtimestamp( toon["lastModified"] / 1000 )
                    logging.debug('json last modified {}'.format(str(lastModified)))
                except Exception as e:
                    logging.error('Exception calling mounts')
                    logging.error(str(e))
                    raise
                finally:
                    f.close()

        if toon == None:
            # retrieve from blizz
            logging.debug('retrieving from blizzard')
            self._auth.load_token()
            url='https://us.api.blizzard.com/profile/wow/character/{}/{}/collections/mounts?locale=en_US'.format(realm, character)
            logging.info(url)
            req = Request(url)
            req.add_header('Authorization', "Bearer {}".format(self._auth.get_token()['access_token']))
            req.add_header('Battlenet-Namespace', 'profile-us')
            f=urlopen(req)
            toonjson=f.read().decode('utf-8')
            f.close()
            f = open(filename,"wt")
            f.write(toonjson)
            f.close()
            toon = json.loads(toonjson)
            toon["realm"]=realm
            toon["name"]=character
        return toon 

    def parse_args(self, character, **kwargs):
        """ Creates a dictionary from the arguments that were passed
            and adds other important mappings.
        """
        params = {
            "character" : character.lower()
         }

        if "realm" in kwargs.keys():
            params["realm"] = kwargs["realm"]
        else:
            params["realm"] = self._default_realm
        params["filename"] = "./{}/{}_{}_mounts.json".format(self._output_path, params["realm"], character)
        logging.debug(str(params))
        return params

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        logging.debug("parsing config file: {}".format(file))
        config = configparser.ConfigParser()
        config.read(file)
        self._default_realm = config['warcraft']['default_realm']
        self._output_path = config['mounts']['cache']

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
    LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
    logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)
    args = parse_args()
    character = args.pop('character')

    mounts = Mounts()
    result = mounts.run(character, **args)
    #print(str(result))
