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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cmdb_sync.log'))
    ]
)
logger = logging.getLogger('cmdb_sync')

# 读取配置文件
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'), encoding='utf-8')

# JumpServer 配置
JUMPSERVER_URL = config.get('JumpServer', 'url')
JUMPSERVER_KEY_ID = config.get('JumpServer', 'key_id')
JUMPSERVER_SECRET = config.get('JumpServer', 'secret')

# CMDB API 配置
CMDB_API_URL = config.get('CMDB', 'api_url')
CMDB_API_TOKEN = config.get('CMDB', 'api_token')
CMDB_API_HEADERS = {'Authorization': f'Token {CMDB_API_TOKEN}', 'Content-Type': 'application/json'}

# 排除删除的IP列表
EXCLUDED_IPS = config.get('Settings', 'excluded_ips', fallback='').split(',')

class JumpServerAPI(object):
    """JumpServer API 客户端类"""

    def __init__(self, base_url, key_id, secret):
        self.base_url = base_url
        self.key_id = key_id
        self.secret = secret
        self.signature_headers = ['(request-target)', 'accept', 'date']
        self.localtime = time.asctime(time.localtime(time.time()))
        self.headers = {
            'content-type': 'application/json',
            'date': self.localtime
        }
        self.auth = HTTPSignatureAuth(
            key_id=self.key_id,
            secret=self.secret,
            algorithm='hmac-sha256',
            headers=self.signature_headers
        )
        self.logger = logger

    def get_nodes_info(self):
        """获取节点信息"""
        nodes_dict = {}
        url = f"{self.base_url}/api/v1/assets/nodes/"
        response = requests.get(url, auth=self.auth, headers=self.headers).json()
        for i in response:
            tmp = {i['full_value']: i['id']}
            nodes_dict.update(tmp)
        return nodes_dict
    
    def get_host_from_node(self, node_id):
        """获取指定node下面的服务器列表"""
        host_dict = {}
        query_params = {"node": node_id}
        url = f"{self.base_url}/api/v1/assets/hosts/"
        response = requests.get(url, auth=self.auth, headers=self.headers, params=query_params).json()
        for i in response:
            tmp = {
                i["name"]: {
                    "ID": i["id"],
                    "address": i["address"],
                    "NODES": i["nodes"][0]["id"] if i["nodes"] else ""
                }
            }
            host_dict.update(tmp)
        return host_dict

    def add_host(self, params):
        """添加服务器"""
        url = f"{self.base_url}/api/v1/assets/hosts/"
        response = requests.post(url=url, data=json.dumps(params), auth=self.auth, headers=self.headers).json()
        return response

    def delete_host(self, host_id):
        """删除服务器"""
        url = f"{self.base_url}/api/v1/assets/hosts/{host_id}/"
        response = requests.delete(url=url, auth=self.auth, headers=self.headers)
        return response.status_code in [200, 204]

    def get_host_info(self, ip_address):
        """通过IP地址获取主机信息"""
        query_params = {"address": ip_address}
        url = f"{self.base_url}/api/v1/assets/hosts/"
        response = requests.get(url, auth=self.auth, headers=self.headers, params=query_params).json()
        return response

    def add_host_to_jumpsever(self, params_list, node_cvm_dict):
        """批量更新节点上的主机资产信息"""
        added = 0
        updated = 0
        failed = 0
        ip_list = []
        add_host_list = []
        
        # 构建当前主机IP列表
        for x in node_cvm_dict.keys():
            ip_list.append(node_cvm_dict[x]["address"])

        for params in params_list:
            if params["address"] not in ip_list and params["address"] not in EXCLUDED_IPS:
                try:
                    response_info = self.add_host(params)
                    if isinstance(response_info, dict) and response_info.get("name") and response_info["name"][0] == "字段必须唯一":
                        params["name"] = params["name"] + '-' + params["address"]
                        new_response = self.add_host(params)
                        if 'id' in new_response:
                            logger.info(f"Added host with renamed: {params['name']}")
                            added += 1
                            add_host_list.append(new_response['id'])
                        else:
                            logger.error(f"Failed to add host after rename: {params['name']} - {new_response}")
                            failed += 1
                    elif 'id' in response_info:
                        logger.info(f"Added host: {params['name']}")
                        added += 1
                        add_host_list.append(response_info['id'])
                    else:
                        logger.error(f"Failed to add host: {params['name']} - {response_info}- {params}")
                        failed += 1
                except Exception as e:
                    logger.error(f"Exception when adding host {params['address']}: {str(e)}")
                    failed += 1
            else:
                updated += 1

        return {"added": added, "updated": updated, "failed": failed}

    def create_node(self, node_name, full_name):
        """在指定父节点下创建新节点
        
        Args:
            parent_key (str): 父节点的key或id
            node_name (str): 新节点名称
            
        Returns:
            dict: 创建的节点信息，如果创建失败则返回空字典
        """
        try:
            url = f"{self.base_url}/api/v1/assets/nodes/"
            
            payload = {
                "value": node_name,
                "full_value": full_name
            }
            
            response = requests.post(
                url=url, 
                data=json.dumps(payload), 
                auth=self.auth, 
                headers=self.headers
            )
            
            if response.status_code in [200, 201]:
                node_info = response.json()
                self.logger.info(f"Created node: {node_name} under parent {full_name}")
                return node_info
            else:
                self.logger.error(f"Failed to create node: {node_name}, status: {response.status_code}, response: {response.text}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error creating node {node_name}: {str(e)}")
            return {}

    # 创建授权规则
    def get_asset_permissions(self, params):
        """获取授权规则信息"""
        url = f"{self.base_url}/api/v1/perms/asset-permissions/"
        response = requests.get(url=url, params=params, auth=self.auth, headers=self.headers).json()
        return response

    def get_asset_permissions_details(self, permissions_id):
        """获取授权规则信息"""
        url = f"{self.base_url}/api/v1/perms/asset-permissions/{permissions_id}/"
        response = requests.get(url=url, auth=self.auth, headers=self.headers).json()
        return response

    # 创建授权规则
    def create_asset_permissions(self, params):
        """添加授权规则"""
        print(params)
        url = f"{self.base_url}/api/v1/perms/asset-permissions/"
        response = requests.post(url=url, data=json.dumps(params), auth=self.auth, headers=self.headers).json()
        return response

    # 修改授权规则
    def update_asset_permissions(self, permissions_id, params):
        """更新授权规则"""
        url = f"{self.base_url}/api/v1/perms/asset-permissions/{permissions_id}/"
        response = requests.put(url=url, data=json.dumps(params), auth=self.auth, headers=self.headers).json()
        return response

    # 获取指定用户名的id
    def get_user_id(self, params):
        """获取用户信息"""
        user_id = ""
        url = f"{self.base_url}/api/v1/users/users/"
        response = requests.get(url=url, params=params, auth=self.auth, headers=self.headers).json()
        if response:
            user_id = response[0]["id"]
        return user_id

if __name__ == "__main__":
    obj = JumpServerAPI(JUMPSERVER_URL, JUMPSERVER_KEY_ID, JUMPSERVER_SECRET)
    node_info = obj.get_nodes_info()
    print(node_info)

            
