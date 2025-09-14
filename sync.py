#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
from jumpserver import JumpServerService
from openc3 import OpenC3Service
from utils.config import *
from utils.logger import logger
from utils import common

def sync():
    jss = JumpServerService(JUMPSERVER_WEBURL, JUMPSERVER_KEY_ID, JUMPSERVER_SECRET)
    c3s = OpenC3Service(OpenC3_API_URL, OpenC3_API_KEY)

    c3_trees = c3s.get_trees()
    c3_hosts = c3s.get_hosts()
    c3_users = c3s.get_users()
    c3_ips = c3s.get_ips()

    logger.info(f"sync node start.")
    jss.sync_node(common.treename_c3_to_js(c3_trees))
    logger.info(f"sync node done.")

    logger.info(f"sync host start.")
    jss.sync_host(c3_hosts, c3_ips, EXCLUDED_IPS)
    logger.info(f"sync host done.")

    logger.info(f"sync auth start.")
    jss.sync_auth(c3_users)
    logger.info(f"sync auth done.")

    jss.sync_node(common.treename_c3_to_js(c3_trees))

if __name__ == '__main__':
    logger.info(f"Sync start.")
    sync()
    logger.info(f"Sync done.")
