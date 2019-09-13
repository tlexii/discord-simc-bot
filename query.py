#!python
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)
#
""" Retrieve and parse WoW data.
"""

import os,logging,shlex,tempfile,re,argparse,json
from urllib.request import Request,urlopen
import configparser
from datetime import datetime,timedelta
from overlordauth import OverlordAuthDb


class Wow(object):
    """ Proof of concept to retrieve a characters information from blizzard.
        Just shows last logout atm.
    """

    def __init__(self):
        if os.path.isfile('discord_simc.conf'):
            self.parse_config('discord_simc.conf')
        else:
            self._default_realm = "khazgoroth"

        self._auth = OverlordAuthDb('discord_simc.conf')
            

    def check_realm(self,r):
        transtable = str.maketrans("","","'")
        cleaned = str(r).lower().translate(transtable)
        return cleaned

    def run(self, character, **kwargs):
        """ Runs a simulation and then looks up additional information for the caller

        :param str character: name of character to sim
        """
        logging.info('Run called with character name {}'.format(character))
        result = None
        try:
            params = self.parse_args(character, **kwargs)
            toon = self.get_data( params["realm"], params["character"])
            if toon["faction"]==0:
                params["colour"] = 0x1111FF
            else:
                params["colour"] = 0xFF1111
            logging.debug(str(params))

            lastlogout = datetime.fromtimestamp( int(toon["lastModified"]) / 1000)
            delta = datetime.now() - lastlogout
            if delta.days > 0:
                msg = "{} days ago".format(delta.days)
            elif delta.seconds >= 7200:
                msg = "{} hours ago".format(int(delta.seconds/3600))
            else:
                msg = "{} minutes ago".format(int(delta.seconds/60))

            result = "{:20} {:20} {:20} {}".format(toon["name"],toon["realm"],str(lastlogout),msg)

        except Exception as e:
            logging.error('Exception calling query')
            logging.error(str(e))
            raise

        return result

    def get_data(self, realm, character):
        # retrieve from blizz
        logging.debug('retrieving from blizzard')
        self._auth.load_token()
        url='https://us.api.blizzard.com/wow/character/{}/{}?locale=en_US'.format(realm, character)
        logging.info(url)
        req = Request(url)
        req.add_header('Authorization', "Bearer {}".format(self._auth.get_token()['access_token']))
        f=urlopen(req)
        toonjson=f.read().decode('utf-8')
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
        logging.debug(str(params))
        return params

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        logging.debug("parsing config file: {}".format(file))
        config = configparser.ConfigParser()
        config.read(file)
        self._default_realm = config['warcraft']['default_realm']

def parse_args():
    """ Parse arguments when we are invoked as a program.

    """
    parser = argparse.ArgumentParser(description="Retrieve World of Warcraft character data.")
    parser.add_argument('character', help='the character to lookup')
    parser.add_argument('--realm','-r', help='the warcraft realm', default='khazgoroth')
    return vars(parser.parse_args())

if __name__ == '__main__':
    LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
    args = parse_args()
    character = args.pop('character')

    wow = Wow()
    result = wow.run(character, **args)
    print(result)
