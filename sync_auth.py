# -*- coding: utf-8 -*-

import os
import sys
import logging
import requests
import configparser
from datetime import datetime, timedelta, timezone
from collect_from_c3 import create_node_structure 
from typing import Dict, List, Any, Tuple

# 导入JumpServerAPI类
from jumpserver_api import JumpServerAPI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cmdb_sync.log'))
    ]
)
logger = logging.getLogger('cmdb_')

# 读取配置文件
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'), encoding='utf-8')

# JumpServer 配置
JUMPSERVER_URL = config.get('JumpServer', 'url')
JUMPSERVER_KEY_ID = config.get('JumpServer', 'key_id')
JUMPSERVER_SECRET = config.get('JumpServer', 'secret')
JUMPSERVER_NODE_ID = config.get('JumpServer', 'node_id')

# CMDB API 配置
CMDB_API_URL = config.get('CMDB', 'api_url')
CMDB_API_TOKEN = config.get('CMDB', 'api_token')
CMDB_API_HEADERS = {'appkey': CMDB_API_TOKEN, 'appname': 'jobx', 'Content-Type': 'application/json'}

# 获取用户信息
def get_cmdb_userinfo() -> List[Dict[str, Any]]:
    try:
        url = f"{CMDB_API_URL}/api/connector/default/auth/tree/userauth"
        response = requests.get(url, headers=CMDB_API_HEADERS)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Successfully fetched {len(data['data'] if 'data' in data else data)} user from CMDB")
            return data
    except Exception as e:
        logger.error(f"Error fetching data from CMDB: {str(e)}")
        return []
    
# 根据用户级别获取账户权限列表
def get_accounts_by_level(level: str) -> List[str]:
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

def create_asset_permissions_format_params(user_info: Dict[str, Any], js_api: JumpServerAPI) -> Dict[str, Any]:
    """
    创建资产授权规则参数
    """
    # 获取用户信息
    username = user_info["name"]
    print(username)

    # 获取用户ID
    user_id = js_api.get_user_id({"username": username})
    print(user_id)

    # 获取用户信息
    department = user_info["treename"]
    level = user_info["level"]
    
    # 生成带有level信息的规则名称
    rule_name = f"{department}_level_{level}"
    
    # 根据用户级别获取账户权限
    accounts = get_accounts_by_level(level)

    # 根据部门创建节点结构，现在返回节点ID列表
    node_ids = create_node_structure(js_api, department)

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

def update_asset_permissions_format_params(user_info: Dict[str, Any], rule_info: Dict[str, Any], js_api: JumpServerAPI) -> Dict[str, Any]:
    """
    更新资产授权规则参数
    """
    params = rule_info
    # 获取用户信息
    username = user_info["name"]

    # 获取用户_id
    user_id = js_api.get_user_id({"username": username})

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

def sync_auth_to_jumpserver() -> bool:
    """同步资产授权信息到jumpserver"""
    try:
        # 初始化JumpServer API
        js_api = JumpServerAPI(JUMPSERVER_URL, JUMPSERVER_KEY_ID, JUMPSERVER_SECRET)

        # c3用户信息
        cmdb_user = get_cmdb_userinfo()

        # 按treename和level分组用户
        grouped_users = {}
        for user in cmdb_user['data']:
            treename = user["treename"]
            level = user["level"]
            key = f"{treename}_level_{level}"
            
            if key not in grouped_users:
                grouped_users[key] = []
            grouped_users[key].append(user)
        
        # 处理每个分组
        for rule_name, users in grouped_users.items():
            # 获取该rule_name的权限规则
            asset_permissions = js_api.get_asset_permissions({"name": rule_name})
            
            if asset_permissions:
                # 获取规则详情
                asset_permissions_info = js_api.get_asset_permissions_details(asset_permissions[0]["id"])
                # 如果规则已存在，为每个用户更新规则
                asset_permissions_params = None
                for user in users:
                    asset_permissions_params = update_asset_permissions_format_params(user, asset_permissions_info, js_api)
                
                if asset_permissions_params:
                    js_api.update_asset_permissions(asset_permissions[0]["id"], asset_permissions_params)
                    logger.info(f"Updated permission rule: {rule_name} with {len(users)} users")
            else:
                # 如果规则不存在，创建新规则
                if not users:
                    continue
                    
                # 使用第一个用户的信息创建基本规则
                asset_permissions_params = create_asset_permissions_format_params(users[0], js_api)
                
                # 添加其他用户到同一规则
                for user in users[1:]:
                    user_id = js_api.get_user_id({"username": user["name"]})
                    if user_id:
                        asset_permissions_params["users"].append({"pk": user_id})
                
                js_api.create_asset_permissions(asset_permissions_params)
                logger.info(f"Created new permission rule: {rule_name} with {len(users)} users")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during sync process: {str(e)}")
        return False
    
def check_system_requirements() -> bool:
    """检查系统要求（如依赖库是否安装）"""
    required_modules = ['requests', 'configparser', 'ipaddress']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        logger.error(f"Missing required modules: {', '.join(missing_modules)}. "
                     f"Please install them using: pip install {' '.join(missing_modules)}")
        return False
    
    return True

def check_config() -> bool:
    """检查配置是否正确"""
    if not JUMPSERVER_URL or not JUMPSERVER_KEY_ID or not JUMPSERVER_SECRET:
        logger.error("JumpServer configuration is incomplete. Check config.ini")
        return False
    
    if not CMDB_API_URL or not CMDB_API_TOKEN:
        logger.error("CMDB API configuration is incomplete. Check config.ini")
        return False
    
    if not JUMPSERVER_NODE_ID:
        logger.error("JumpServer Node ID is missing. Check config.ini")
        return False
    
    return True

def main():
    """主函数"""
    logger.info("Starting CMDB to JumpServer sync process")
    
    # 检查系统要求
    if not check_system_requirements():
        return 1
    
    # 检查配置
    if not check_config():
        return 1
    
    # 执行同步
    success = sync_auth_to_jumpserver()
    
    if success:
        logger.info("Sync completed successfully")
        return 0
    else:
        logger.error("Sync failed")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

