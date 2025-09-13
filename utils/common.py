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
from utils.config import *


def treename_c3_to_js(trees : list) -> list:
    return list(map(lambda x: "/".join( ["/DEFAULT/C3", x ]).replace('.','/'),trees))
    #return list(map(lambda x: "/".join( ["/DEFAULT/Default/C3", x ]).replace('.','/'),trees))

def treename_js_to_c3(trees : list) -> list:
    return list(map(lambda x: x.removeprefix("/DEFAULT/C3/").replace('/','.'),trees))
    #return list(map(lambda x: x.removeprefix("/DEFAULT/Default/C3/").replace('/','.'),trees))

def treename_zip(paths):
    paths = set(paths)  # 保证唯一
    to_remove = set()
    for path in paths:
        parts = path.split('.')
        # 检查所有可能的前缀（不包含自己）
        for i in range(1, len(parts)):
            prefix = '.'.join(parts[:i])
            if prefix in paths:
                to_remove.add(prefix)
    return paths - to_remove

def treename_unzip(trees):
    trees_unzip = set();
    for tree in trees:
        parts = tree.split('.')
        for i in range(1,1 +len(parts)):
            trees_unzip.add('.'.join(parts[0:i]))
    return list(trees_unzip)

def get_template_id_by_ip(ip: str) -> dict:

    """根据IP地址判断所属网段并返回对应的模板ID"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        
        for mapping in IP_TEMPLATE_MAPPING:
            for cidr in mapping["cidr"]:
                if ip_obj in ipaddress.ip_network(cidr):
                    return {"account_name": mapping["account_name"], "template_id": mapping["template_id"]}
        
        # 如果IP不在任何配置的网段内，使用默认模板ID
        return DEFAULT_TEMPLATE_ID
    except ValueError:
        logger.error(f"Invalid IP address: {ip}")
        return DEFAULT_TEMPLATE_ID
