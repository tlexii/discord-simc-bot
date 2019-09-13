#!python
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)
#

import os,logging,json,time
import configparser
import sqlite3

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth
from urllib.request import Request,urlopen
from datetime import datetime


class OverlordAuth(object):

    def __init__(self):
        self.logger = logging.getLogger('OverlordAuth')

    def get_token(self):
        return self._token

    def set_token(self,token):
        self._token = token

    def load_token(self):
        return self._token

    def save_token(self):
        self.logger.debug("dummy saved")

    def renew_token(self):
        self.logger.debug("renewing token")
        auth = HTTPBasicAuth(self._blizzard_clientid, self._blizzard_clientsecret)
        client = BackendApplicationClient(client_id=self._blizzard_clientid)
        oauth = OAuth2Session(client=client)
        token = oauth.fetch_token(token_url='https://us.battle.net/oauth/token', auth=auth)
        self.set_token(token)
        self.logger.debug("token renewed")
        self.save_token()
        return token


class OverlordAuthFile(OverlordAuth):

    def __init__(self, config_file):
        self.logger = logging.getLogger('OverlordAuthFile')
        self.parse_config(config_file)
        self._token = None

    def load_token(self):
        token = self.get_token()
        if os.path.isfile(self._token_filename):
            try:
                self.logger.debug("loading token from {}".format(self._token_filename))
                f = open(self._token_filename,"rt")
                token=json.load(f)
                timestamp=int(time.mktime(time.localtime())) - 30
                self.logger.debug("check timestamp : {}".format(str(datetime.fromtimestamp(timestamp))))
                self.logger.debug("expires at: {}".format(str(datetime.fromtimestamp(token["expires_at"]))))
                if token["expires_at"] < timestamp:
                    token = None
            except Exception as e:
                self.logger.error('Exception loading ouath2 token')
                self.logger.error(str(e))
                raise
            finally:
                f.close()

        if token == None:
            self.renew_token()

        return self.get_token()

    def save_token(self):
        try:
            f = open(self._token_filename,"wt")
            jsondata = json.dumps(self.get_token())
            f.write(jsondata)
            self.logger.debug("token saved to {}".format(self._token_filename))
        except Exception as e:
            self.logger.error('Exception saving ouath2 token')
            self.logger.error(str(e))
            raise
        finally:
            f.close()

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        try:
            self.logger.debug("parsing config file: {}".format(file))
            config = configparser.ConfigParser()
            config.read(file)
            self._blizzard_clientid = config['blizzard']['blizzard_clientid']
            self._blizzard_clientsecret = config['blizzard']['blizzard_clientsecret']
            self._token_filename = config['blizzard']['token_filename']
        except Exception as e:
            self.logger.error('Exception reading config from: {}'.Format(file))
            self.logger.error(str(e))
            raise


class OverlordAuthDb(OverlordAuth):

    def __init__(self,config_file):
        self.logger = logging.getLogger('OverlordAuthDb')
        self.parse_config(config_file)
        self._token = None

    def load_token(self):
        token = self.get_token()
        if os.path.isfile(self._db_filename):
            try:
                self.logger.debug("loading token from {}".format(self._db_filename))
                conn = sqlite3.connect(self._db_filename)
                cur = conn.cursor()
                cur.execute("select value from settings where key='token'")
                row = cur.fetchone()
                if row != None:
                    token = json.loads(row[0])
                    self.set_token(token)
                    timestamp=int(time.mktime(time.localtime())) - 30
                    self.logger.debug("check timestamp : {}".format(str(datetime.fromtimestamp(timestamp))))
                    self.logger.debug("expires at: {}".format(str(datetime.fromtimestamp(token["expires_at"]))))
                    if token["expires_at"] < timestamp:
                        token = None
                conn.close()

            except Exception as e:
                self.logger.error('Exception loading ouath2 token')
                self.logger.error(str(e))
                raise

        if token == None:
            self.renew_token()

        return self.get_token()

    def save_token(self):
        self.logger.debug("saving token to {}".format(self._db_filename))
        value = json.dumps(self.get_token())
        conn = sqlite3.connect(self._db_filename)
        cur = conn.cursor()
        cur.execute("insert or replace into settings (key,value) values ('token',?)", (value,) )
        conn.commit()
        conn.close()
        self.logger.debug("token saved to {}".format(self._db_filename))

    def parse_config(self, file):
        """ Read the local configuration from the file specified.

        """
        try:
            self.logger.debug("parsing config file: {}".format(file))
            config = configparser.ConfigParser()
            config.read(file)
            self._blizzard_clientid = config['blizzard']['blizzard_clientid']
            self._blizzard_clientsecret = config['blizzard']['blizzard_clientsecret']
            self._db_filename = config['blizzard']['db_filename']
        except Exception as e:
            self.logger.error('Exception reading config from: {}'.Format(file))
            self.logger.error(str(e))
            raise

