# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import logging
import requests
from typing import Dict, List, Any, Tuple
import configparser
from httpsig.requests_auth import HTTPSignatureAuth
from utils.logger import logger

class OpenC3API(object):

    def __init__(self, base_url, secret):
        self.base_url = base_url
        self.headers = { 'appkey': secret, 'appname': 'jobx', 'Content-Type': 'application/json' }
        self.logger = logger

    def get_hosts(self):
        """从CMDB API获取主机数据"""
        url = f"{self.base_url}/api/ci/c3mc/jumpserver"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Successfully fetched {len(data['data'] if 'data' in data else data)} hosts from CMDB")
            if not data.get("stat"):
                raise RuntimeError("Open-C3 Service Error: stat false")
    
            if not data or not data.get("data"):
                raise RuntimeError("Open-C3 Service Error: data null")
            
            return data.get("data")
    
        else:
            logger.error(f"Failed to fetch data from CMDB: {response.status_code}, {response.text}")
            return []

    def get_users(self):
       try:
           url = f"{self.base_url}/api/connector/default/auth/tree/userauth"
           response = requests.get(url, headers=self.headers)
           if response.status_code == 200:
               data = response.json()
               logger.info(f"Successfully fetched {len(data['data'] if 'data' in data else data)} user from CMDB")
               if not data.get("stat"):
                   raise RuntimeError("Open-C3 Service Error: stat false")
   
               if not data or not data.get("data"):
                   raise RuntimeError("Open-C3 Service Error: data null")
               
               return data.get("data")

       except Exception as e:
           logger.error(f"Error fetching data from CMDB: {str(e)}")
           return []
    
