#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)
#
""" A class to poll blizzard api for guild news - probably be sent to discord as webhook.
"""

import os,time,logging,argparse,json,re,datetime
from urllib.request import Request,urlopen
from urllib import parse
import configparser
from overlordauth import OverlordAuthDb

log = logging.getLogger('guild')

class GuildNews(object):
    """ Polls the Blizzard API for Guild News, maintains the timestamp internally
    """

    FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, config_file):

        if os.path.isfile(config_file):
            self.parse_config(config_file)
        else:
            self._guilds = {}
            self._run_dir = '/var/run/warcraft'

        self._auth = OverlordAuthDb(config_file)

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
        log.info('BEGIN Polling guilds')
        for guildkey in self._guilds.keys():
            result=self.run_guild(guildkey)
            log.debug(str(result))
            if 'news_items' in result.keys() and len(result['news_items']) > 0:
                self.announce(self._guilds[guildkey], result)
                    
            time.sleep(1)
        log.info('END Polling guilds')

    def announce(self, guild, result):
        log.debug('sending updates to : {}'.format(guild['webhook']))
        for ach in result['news_items']:
            if ach['type'] == 'playerAchievement':
                line = '**{}** earned achievement **{}** for {} points'.format(
                    ach['character'],
                    ach['achievement']['title'],
                    ach['achievement']['points'])
            else:
                line = '**{}** earned achievement **{}** for {} points'.format(
                    result['output_guild'], 
                    ach['achievement']['title'], 
                    ach['achievement']['points'])
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
            log.info('{}: {}'.format(datetime.datetime.fromtimestamp(ach['timestamp']/1000).strftime(self.FORMAT), line))
            req = Request(guild['webhook'])
            req.add_header('User-Agent', 'discord-webhook (1.0)')
            req.add_header('Accept', 'application/json')
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            jsondata = json.dumps(msg)
            jsondataasbytes = jsondata.encode('utf-8')   # needs to be bytes
            req.add_header('Content-Length', len(jsondataasbytes))
            response = urlopen(req, jsondataasbytes).read()
            time.sleep(1)

    def run_guild(self, guildkey):
        """ Contact endpoint for each guilds data update

        """
        log.info('GUILD key {}'.format(guildkey))
        params = {}
        try:
            # read the timestamp for the guilds runfile
            if not self.read_run_file(guildkey):
                # Blizzard send timestamp as milliseconds, make ours compatible
                self._timestamp=int(time.mktime(time.localtime()))*1000
                self.write_run_file(guildkey)

            self.log_time('Last processed', self._timestamp)

            guildjson = self.read_data(guildkey)
            #guildjson = self.read_debug(guildkey)

            if guildjson == None:
                log.error('No data returned')

            guild = json.loads(guildjson)
            self.log_time('blizz timestamp',guild["lastModified"])
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

            #self._timestamp=guild["lastModified"]
            if len(guild["news"]) > 0:
                # maintain our timestamp to match blizzard's last event, not their last modified or our time
                self._timestamp= guild["news"][0]["timestamp"]
            else:
                # use current time
                self._timestamp=int(time.mktime(time.localtime()))*1000
            
            self.log_time('Saving lastEvent',self._timestamp)
            self.write_run_file(guildkey)
                
        except Exception as e:
            log.error('Exception executing request')
            log.error(str(e))

        return params

    def read_data(self, guildkey):
        self._auth.load_token()
        url='https://us.api.blizzard.com/wow/guild/{}/{}?fields=news&locale=en_US'.format(
            parse.quote(self._guilds[guildkey]['realm']),
            parse.quote(self._guilds[guildkey]['name']))
        req = Request(url)
        req.add_header('Authorization', "Bearer {}".format(self._auth.get_token()['access_token']))
        f=urlopen(req)
        guildjson=f.read().decode('utf-8')
        f.close()
        return guildjson

    def read_debug(self, guildkey):
        f=open('guild_news.json',"rt")
        guildjson=f.read()
        f.close()
        return guildjson

    def log_time(self, msg, timestamp):
        log.debug(timestamp)
        st = datetime.datetime.fromtimestamp(timestamp/1000)
        log.info('{}: {}'.format(msg, st.strftime(self.FORMAT)))

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        log.debug("parsing config file: {}".format(file))
        config = configparser.ConfigParser()
        config.read(file)
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
    LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
    logging.basicConfig(filename='/var/log/guild_news.log', format=LOG_FORMAT, level=logging.INFO)
    args = parse_args()
    config_file = args['config']
    guild_news = GuildNews(config_file)
    guild_news.run()

