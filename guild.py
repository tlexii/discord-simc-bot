#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)
#
""" A class to poll blizzard api for guild news - probably be sent to discord as webhook.
"""

import os,time,logging,argparse,json,re
import urllib.request
import configparser

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
logging.basicConfig(filename='/var/log/guild_news.log', format=LOG_FORMAT, level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

class GuildNews(object):
    """ Polls the Blizzard API for Guild News, maintains the timestamp internally
    """

    def __init__(self, config_file):

        if os.path.isfile(config_file):
            self.parse_config(config_file)
        else:
            self._guilds = {}
            self._blizzard_key = None
            self._run_dir = '/var/run/warcraft'

    def read_run_file(self, guildkey):
        try:
            f=open(self._guilds[guildkey]['runfile'], "rt")
            self._timestamp=int(f.read())
            f.close()
            return True
        except Exception:
            return False

    def write_run_file(self, guildkey):
        f=open(self._guilds[guildkey]['runfile'], "wt")
        f.write(str(self._timestamp))
        f.close()

    def run(self):
        """ Loops over all the keys in the configuration
        """
        LOGGER.info('BEGIN Polling guilds')
        for guildkey in self._guilds.keys():
            result=self.run_guild(guildkey)
            LOGGER.debug(str(result))
            if len(result['news_items']) > 0:
                self.announce(self._guilds[guildkey], result)
                    
            time.sleep(1)
        LOGGER.info('END Polling guilds')

    def announce(self, guild, result):
        LOGGER.debug('sending updates to : {}'.format(guild['webhook']))
        for ach in result['news_items']:
            if ach['type'] == 'playerAchievement':
                line = '{} earned achievement {} for {} points'.format(ach['character'], ach['achievement']['title'],  ach['achievement']['points'])
            else:
                line = '{} earned achievement {} for {} points'.format(result['output_guild'], ach['achievement']['title'], ach['achievement']['points'])
            msg = {
                'content' : line,
                'embeds' : [{
                    'title' : ach['achievement']['title'],
                    'url' : "http://www.wowhead.com/achievement={}".format(ach['achievement']['id']),
                    'description' : ach['achievement']['description'],
                    'type' : 'link',
                    'thumbnail' : {
                        'url' :  "http://wow.zamimg.com/images/wow/icons/large/{}.jpg".format(ach['achievement']['icon'])
                    }
                }]
            }

            req = urllib.request.Request(guild['webhook'])
            req.add_header('User-Agent', 'discord-webhook (1.0)')
            req.add_header('Accept', 'application/json')
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            jsondata = json.dumps(msg)
            jsondataasbytes = jsondata.encode('utf-8')   # needs to be bytes
            req.add_header('Content-Length', len(jsondataasbytes))
            response = urllib.request.urlopen(req, jsondataasbytes).read()
            LOGGER.info(str(response))
            time.sleep(1)

    def run_guild(self, guildkey):
        """ Contact endpoint for each guilds data update

        """
        LOGGER.info('GUILD key {}'.format(guildkey))
        params = {}
        try:
            # read the timestamp for the guilds runfile
            if self.read_run_file(guildkey):
                LOGGER.debug('lastModified is {}'.format(self._timestamp))
            else:
                # Blizzard send timestamp as milliseconds, make ours compatible
                self._timestamp=int(time.time())*1000
                self.write_run_file(guildkey)

            guildjson = self.read_data(guildkey)
            #guildjson = self.read_debug(guildkey)

            if guildjson == None:
                LOGGER.error('No data returned')

            guild = json.loads(guildjson)
            params["output_realm"] = guild["realm"]
            params["output_guild"] = guild["name"]
            params["last_modified"] = guild["lastModified"]
            if guild["side"]==0:
                params["colour"] = 0x1111FF
            else:
                params["colour"] = 0xFF1111

            params["news_items"] = list(filter(
                lambda x : (x["type"] == 'guildAchievement'
                        or x["type"] == 'playerAchievement')
                    and x["timestamp"] > self._timestamp
                , guild["news"]))

            # maintain our timestamp to match blizzard
            self._timestamp=guild["lastModified"]
            LOGGER.debug('lastModified updated to {}'.format(self._timestamp))
            self.write_run_file(guildkey)
                
        except Exception as e:
            LOGGER.error('Exception executing request')
            LOGGER.error(str(e))

        return params

    def read_data(self, guildkey):
        if self._blizzard_key:
            f=urllib.request.urlopen('https://us.api.battle.net/wow/guild/{}/{}?fields=news&locale=en_US&apikey={}'.format(
                urllib.parse.quote(self._guilds[guildkey]['realm']),
                urllib.parse.quote(self._guilds[guildkey]['name']), 
                self._blizzard_key))
            guildjson=f.read().decode('utf-8')
            f.close()
            return guildjson
        else:
            LOGGER.error('No Blizzard API key provided')
        return None

    def read_debug(self, guildkey):
        f=open('guild_news.json',"rt")
        guildjson=f.read()
        f.close()
        return guildjson

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        LOGGER.debug("parsing config file: {}".format(file))
        config = configparser.ConfigParser()
        config.read(file)
        self._blizzard_key = config['blizzard']['blizzard_key']
        self._run_dir = config['warcraft']['run_dir']
        self._guilds = {}
        # create dict of guild configs
        for gkey in re.compile(r',').split(config['warcraft']['guilds'].strip()):
            guildkey = gkey.strip()
            # copy the config to our guild
            self._guilds[guildkey] = config[guildkey]
            # add runfile path to the config
            self._guilds[guildkey]['runfile'] = "{}/{}".format(self._run_dir, guildkey)

def parse_args():
    """ Parse arguments when we are invoked as a program.

    """
    parser = argparse.ArgumentParser(description="Retrieve Guild News from Blizzard API.")
    parser.add_argument('--config','-c', help='the config file', default='./discord_simc.conf')
    return vars(parser.parse_args())

if __name__ == '__main__':
    args = parse_args()
    config_file = args['config']
    guild_news = GuildNews(config_file)
    guild_news.run()

