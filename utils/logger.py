# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import logging
import requests
import ipaddress
from typing import Dict, List, Any, Tuple
import configparser

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../logs/sync.log'))
    ]
)
logger = logging.getLogger('sync')

