#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)
#
""" A class to poll blizzard api for guild news.
"""

import os,time,logging,argparse,json
import urllib.request
import configparser

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

class GuildNews(object):
    """ Polls the Blizzard API for Guild News, maintains the timestamp internally
    """

    def __init__(self):
        # Blizzard send timestamp as milliseconds, make ours compatible
        self._timestamp=int(time.time())*1000
        LOGGER.info('lastModified initialised to {}'.format(self._timestamp))

        if os.path.isfile('discord_simc.conf'):
            self.parse_config('discord_simc.conf')
        else:
            self._default_realm = "khazgoroth"
            self._blizzard_key = None

    def run(self, guild, **kwargs):
        """ Contact endpoint for guild data update, return dictionary

        :param str guild: name of guild
        """
        LOGGER.info('Run called with guild name {} previous timestamp {}'.format(guild, self._timestamp))
        params = {}
        try:
            params = self.parse_args(guild, **kwargs)
            
            if self._blizzard_key:
                f=urllib.request.urlopen('https://us.api.battle.net/wow/guild/{}/{}?fields=news&locale=en_US&apikey={}'.format(
                    kwargs["realm"], guild, self._blizzard_key))
                guildjson=f.read().decode('utf-8')
                f.close()
                guild = json.loads(guildjson)
                params["output_realm"] = guild["realm"]
                params["output_guild"] = guild["name"]
                params["last_modified"] = guild["lastModified"]
                if guild["side"]==0:
                    params["colour"] = 0x1111FF
                else:
                    params["colour"] = 0xFF1111

                params["news_items"] = list(filter(
                    lambda x : x["type"] == 'guildAchievement' and x["timestamp"] > self._timestamp,
                    guild["news"]))

                # maintain our timestamp to match blizzard
                self._timestamp=guild["lastModified"]
                LOGGER.debug('lastModified updated to {}'.format(self._timestamp))
                
            else:
                LOGGER.error('No Blizzard API key provided')
                print("No Blizzard API key provided")

        except Exception as e:
            LOGGER.error('Exception executing request')
            LOGGER.error(str(e))

        return params

    def parse_args(self, guild, **kwargs):
        """ Creates a dictionary from the arguments that were passed

        """
        params = {
            "guild" : guild
        }

        if "realm" in kwargs.keys():
            params["realm"] = kwargs["realm"]
        else:
            params["realm"] = self._default_realm

        LOGGER.debug(str(params))
        return params

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        LOGGER.debug("parsing config file: {}".format(file))
        config = configparser.ConfigParser()
        config.read(file)
        self._default_realm = config['warcraft']['default_realm']
        self._blizzard_key = config['blizzard']['blizzard_key']

def parse_args():
    """ Parse arguments when we are invoked as a program.

    """
    parser = argparse.ArgumentParser(description="Retrieve Guild News from Blizzard API.")
    parser.add_argument('guild', help='the guild name to query')
    parser.add_argument('--realm','-r', help='the warcraft realm', default='khazgoroth')
    return vars(parser.parse_args())

if __name__ == '__main__':
    args = parse_args()
    guild = args.pop('guild')

    guild_news = GuildNews()
    result = guild_news.run(guild, **args)
    print(str(result))
