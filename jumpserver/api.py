# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import logging
import requests
from typing import Dict, List, Any, Tuple
from httpsig.requests_auth import HTTPSignatureAuth
from utils.logger import logger

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
        # 获取所有服务器的全量列表。 上面的过滤条件没用
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
 
    def create_node(self, full_name):
        node_name = full_name.split('/')[-1]
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

    def delete_node(self, id):
        """删除服务器"""
        url = f"{self.base_url}/api/v1/assets/nodes/{id}/"
        response = requests.delete(url=url, auth=self.auth, headers=self.headers)
        return response.status_code in [200, 204]

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

    def delete_auth(self, auth_id):
        """删除服务器"""
        url = f"{self.base_url}/api/v1/perms/asset-permissions/{auth_id}/"
        response = requests.delete(url=url, auth=self.auth, headers=self.headers)
        return response.status_code in [200, 204]

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

