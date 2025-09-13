# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import logging
import requests
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta, timezone
from httpsig.requests_auth import HTTPSignatureAuth
from utils.logger import logger
from .api import JumpServerAPI
from utils import common

class JumpServerService(object):

    def __init__(self, base_url, key_id, secret):
        self.api = JumpServerAPI(base_url, key_id, secret )
        self.logger = logger

    def sync_node(self, js_trees):
        c3_trees = common.treename_js_to_c3(js_trees)

        node_info = self.api.get_nodes_info()

        for tree in common.treename_zip(c3_trees):
            ( tree,  ) = common.treename_c3_to_js([tree])
            if node_info.get(tree):
                continue
            self.api.create_node(tree)

        trees_unzip = common.treename_c3_to_js(common.treename_unzip(c3_trees))
        for treename, treeid in node_info.items():
            if treename not in trees_unzip and treename.startswith('/DEFAULT/C3/'):
                self.api.delete_node(treeid)

    def format_host_params(self, host_data: Dict[str, Any] ) -> Dict[str, Any]:
        """格式化主机参数为JumpServer可接受的格式"""

        hostname = host_data.get('hostName', '')
        ip = host_data.get('ip', '')
        platform = host_data.get('os', 'Linux')
        department = host_data.get('tree', '')
    
        # 获取平台信息
        platform_info = self.get_platform_id(platform)
        
        # 根据IP获取模板ID
        template_info = common.get_template_id_by_ip(ip)
        
        # 根据部门创建节点结构，现在返回节点ID列表
        nodes = self.create_node_structure(department)
        
        # 获取对应平台的协议配置
        protocols = self.get_protocols_by_platform(platform_info['id'])
        
        # 创建账号信息
        accounts = [{
            'template': template_info["template_id"],
            'name': template_info["account_name"],
            'username': 'root' if platform_info['name'] == 'Linux' else 'administrator',
            'secret_type': {
                'value': 'ssh_key' if platform_info['name'] == 'Linux' else 'password',
                'label': 'SSH 密钥' if platform_info['name'] == 'Linux' else '密码'
            },
            'privileged': True,
        }]
        
        params = {
            "name": hostname,
            "address": ip,
            "platform": platform_info,
            "accounts": accounts,
            "nodes": nodes,  # 使用构建的节点列表
            "is_active": True,
            "protocols": protocols,
            "comment": f"Synced from OpenC3 on {time.strftime('%Y-%m-%d %H:%M:%S')}"
        }
        
        # 添加自定义字段
        if 'environment' in host_data:
            params["specific_system_environments"] = host_data['environment']
        if 'owner' in host_data:
            params["specific_owner"] = host_data['owner']
        
        return params

    def get_platform_id(self, platform_name: str) -> Dict[str, Any]:
        """获取平台信息"""
        # 映射CMDB平台名称到JumpServer平台名称和ID
        platform_map = {
            'linux': {'id': 1, 'name': 'Linux'},
            'windows': {'id': 2, 'name': 'Windows'}, 
            'centos': {'id': 1, 'name': 'Linux'},
            'ubuntu': {'id': 1, 'name': 'Linux'},
            'redhat': {'id': 1, 'name': 'Linux'},
            'windows server': {'id': 2, 'name': 'Windows'},
        }
        return platform_map.get(platform_name.lower(), {'id': 1, 'name': 'Linux'})

    def create_node_structure(self, department: str) -> list:
        """根据department创建节点结构，返回所有创建的最终节点ID列表"""
        
        # 处理可能包含多个树结构的情况
        departments = [dept.strip() for dept in department.split(',') if dept.strip()]
        
        node_info = self.api.get_nodes_info()
        return [ dict( id=node_info.get(x), name= x.split('/')[-1] )for x in common.treename_c3_to_js(departments) if node_info.get(x)]
    
    def get_protocols_by_platform(self,platform_id: int) -> List[Dict[str, Any]]:
        """根据平台ID获取对应的协议配置"""
        if platform_id == 2:  # Windows
            return [{'name': 'rdp', 'port': 3389}]
        else:  # 默认为Linux
            return [{'name': 'ssh', 'port': 22}]
    
    def add_host_to_jumpsever(self, params_list, node_cvm_dict, EXCLUDED_IPS):
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
                    response_info = self.api.add_host(params)
                    if isinstance(response_info, dict) and response_info.get("name") and response_info["name"][0] == "字段必须唯一":
                        params["name"] = params["name"] + '-' + params["address"]
                        new_response = self.api.add_host(params)
                        if 'id' in new_response:
                            self.logger.info(f"Added host with renamed: {params['name']}")
                            added += 1
                            add_host_list.append(new_response['id'])
                        else:
                            self.logger.error(f"Failed to add host after rename: {params['name']} - {new_response}")
                            failed += 1
                    elif 'id' in response_info:
                        self.logger.info(f"Added host: {params['name']}")
                        added += 1
                        add_host_list.append(response_info['id'])
                    else:
                        self.logger.error(f"Failed to add host: {params['name']} - {response_info}- {params}")
                        failed += 1
                except Exception as e:
                    self.logger.error(f"Exception when adding host {params['address']}: {str(e)}")
                    failed += 1
            else:
                updated += 1

        return {"added": added, "updated": updated, "failed": failed}

    def get_host_from_node(self,*args):
        return self.api.get_host_from_node(*args)

    def delete_host(self,*args):
        return self.api.delete_host(*args)

    def sync_host(self, c3_hosts, c3_ips,EXCLUDED_IPS):
        host_params_list = [self.format_host_params(x) for x in c3_hosts if x.get("os") and x.get("os").lower() == "linux" ]
        js_hosts = self.get_host_from_node('')
        result = self.add_host_to_jumpsever( host_params_list, js_hosts, EXCLUDED_IPS )

        self.logger.info(f"Sync result: Added {result['added']}, Updated {result['updated']}, Failed {result['failed']}")

        deleted_count = 0
        for host_name, host_info in js_hosts.items():
            host_ip = host_info.get("address", "")
            if host_ip and host_ip not in c3_ips and host_ip not in EXCLUDED_IPS:
                host_id = host_info["ID"]
                if self.delete_host(host_id):
                    deleted_count += 1
                    self.logger.info(f"Deleted host {host_name} with ID {host_id} from JumpServer")
                else:
                    self.logger.error(f"Failed to delete host {host_name} with ID {host_id}")
         
        self.logger.info(f"Total deleted hosts: {deleted_count}")
    
    def update_asset_permissions_format_params(self, user_info: Dict[str, Any], rule_info: Dict[str, Any] ):
        """
        更新资产授权规则参数
        """
        params = rule_info
        # 获取用户信息
        username = user_info["name"]
   
        # 获取用户_id
        user_id = self.api.get_user_id({"username": username})
   
        # 获取当前UTC时间
        now = datetime.now(timezone.utc)
   
        # 长期有效
        expired_date = now + timedelta(days=365 * 100)  
   
        # 时间格式化
        date_start = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        date_expired = expired_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
   
        id_exists = False
        for user in params["users"]:
            if user.get("id") == user_id or user.get("pk") == user_id:
                id_exists = True
                break
        
        # 如果ID不存在，则添加
        if not id_exists:
            params["users"].append({"pk": user_id})
   
        params["date_start"] = date_start
        params["date_expired"] = date_expired
        return params
   
    def create_asset_permissions_format_params(self, user_info: Dict[str, Any] ) -> Dict[str, Any]:
        """
        创建资产授权规则参数
        """
        # 获取用户信息
        username = user_info["name"]
    
        # 获取用户ID
        user_id = self.api.get_user_id({"username": username})
    
        # 获取用户信息
        department = user_info["treename"]
        level = user_info["level"]
        
        # 生成带有level信息的规则名称
        rule_name = f"C3_{department}_level_{level}"
        
        # 根据用户级别获取账户权限
        accounts = self.get_accounts_by_level(level)
    
        # 根据部门创建节点结构，现在返回节点ID列表
        node_ids = [ x.get("id") for x in self.create_node_structure(department) ]
    
        # 构建节点列表
        nodes = [{"pk": node_id} for node_id in node_ids]
    
        # 获取当前UTC时间
        now = datetime.now(timezone.utc)
    
        # 长期有效
        expired_date = now + timedelta(days=365 * 100)  
    
        # 时间格式化
        date_start = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        date_expired = expired_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
        params = {
            "assets": [],
            "nodes": nodes,  # 使用构建的节点列表
            "users": [
                {
                    "pk": user_id
                }
            ],
            "accounts": accounts,
            "actions": [
                "connect",
                "upload",
                "download",
                "copy",
                "paste",
                "delete"
            ],
            "is_active": True,
            "date_start": date_start,
            "date_expired": date_expired,
            "name": rule_name
        }   
    
        return params
    
    def sync_auth(self,c3_user):

        # 按treename和level分组用户
        grouped_users = {}
        for user in c3_user:
            treename = user["treename"]
            level = user["level"]
            key = f"C3_{treename}_level_{level}"
            
            if key not in grouped_users:
                grouped_users[key] = []
            grouped_users[key].append(user)
     
        for x in self.api.get_asset_permissions({}):
            if x.get("name") not in grouped_users.keys() and x.get("name").startswith("C3_"):
                self.api.delete_auth(x.get("id"))

        # 处理每个分组
        for rule_name, users in grouped_users.items():
            # 获取该rule_name的权限规则
            asset_permissions = self.api.get_asset_permissions({"name": rule_name})
    
            if asset_permissions:
                # 获取规则详情
                asset_permissions_info = self.api.get_asset_permissions_details(asset_permissions[0]["id"])
                # 如果规则已存在，为每个用户更新规则
                asset_permissions_params = None
                for user in users:
                    asset_permissions_params = self.update_asset_permissions_format_params(user, asset_permissions_info)
                
                if asset_permissions_params:
                    self.api.update_asset_permissions(asset_permissions[0]["id"], asset_permissions_params)
                    self.logger.info(f"Updated permission rule: {rule_name} with {len(users)} users")
            else:
                # 如果规则不存在，创建新规则
                if not users:
                    continue
                    
                # 使用第一个用户的信息创建基本规则
                asset_permissions_params = self.create_asset_permissions_format_params(users[0])
                
                # 添加其他用户到同一规则
                for user in users[1:]:
                    user_id = self.api.get_user_id({"username": user["name"]})
                    if user_id:
                        asset_permissions_params["users"].append({"pk": user_id})
                
                self.api.create_asset_permissions(asset_permissions_params)
                self.logger.info(f"Created new permission rule: {rule_name} with {len(users)} users")


    # 根据用户级别获取账户权限列表
    def get_accounts_by_level(self,level: str) -> List[str]:
        """根据用户级别返回相应的账户权限列表"""
        if level == "1":
            return ["@SPEC", "backend"]
        elif level == "2":
            return ["@SPEC", "root"]
        elif level == "3":
            return ["@ALL"]
        else:
            # 默认权限，如果level不在预期范围内
            return ["@SPEC", "backend"]
    
    
