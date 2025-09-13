# -*- coding: utf-8 -*-

import os
import sys
import json
import time
from typing import Dict, List, Any, Tuple
from utils.logger import logger
from .api import OpenC3API

class OpenC3Service(object):

    def __init__(self, base_url, secret):
        self.api = OpenC3API(base_url, secret )
        self.logger = logger
        self.hosts = None

    def get_hosts(self, force_refresh = False ):
        if (force_refresh) or ( not self.hosts):
            self.hosts = self.api.get_hosts()
        return self.hosts

    def get_trees(self, force_refresh = False ):
        hosts = self.get_hosts( force_refresh )
        trees = set( [ y.strip() for x in hosts for y in x.get("tree").split(",") ] )
        return trees

    def get_ips(self, force_refresh = False ):
        hosts = self.get_hosts( force_refresh )
        return set( [ x.get("ip")for x in hosts if x.get("os") and x.get("os").lower() == "linux" ] )

    def get_users(self):
        return self.api.get_users()
