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
from .logger import logger

# 读取配置文件
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../config.ini'), encoding='utf-8')

# JumpServer 配置
JUMPSERVER_WEBURL = config.get('JumpServer', 'weburl')
JUMPSERVER_KEY_ID = config.get('JumpServer', 'key_id')
JUMPSERVER_SECRET = config.get('JumpServer', 'secret')

# CMDB API 配置
CMDB_API_URL = config.get('CMDB', 'api_url')
CMDB_API_KEY = config.get('CMDB', 'api_key')

# 排除删除的IP列表
EXCLUDED_IPS = config.get('Settings', 'excluded_ips', fallback='').split(',')

# 默认模板ID
DEFAULT_TEMPLATE_ID = {"account_name": config.get('Templates', 'account_name'),
                       "template_id": config.get('Templates', 'template_id')}

def load_template_mappings() -> List[Dict[str, Any]]:
    """从配置文件中加载IP模板映射"""
    template_mappings = []
    
    # 获取所有以Template_开头的部分
    template_sections = [section for section in config.sections() if section.startswith('Template_')]
    
    for section in template_sections:
        if config.has_option(section, 'cidr') and config.has_option(section, 'template_id'):
            cidr_list = [cidr.strip() for cidr in config.get(section, 'cidr').split(',')]
            template_id = config.get(section, 'template_id')
            account_name = config.get(section, 'account_name')
            template_mappings.append({"cidr": cidr_list, "template_id": template_id, "account_name": account_name })
    
    logger.info(f"Loaded {len(template_mappings)} template mappings from config")
    return template_mappings

# 加载IP模板映射
IP_TEMPLATE_MAPPING = load_template_mappings()

