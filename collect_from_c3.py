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
logger = logging.getLogger('cmdb_sync')

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

# 排除删除的IP列表
EXCLUDED_IPS = config.get('Settings', 'excluded_ips', fallback='').split(',')

# 默认模板ID
DEFAULT_TEMPLATE_ID = {"account_name": "jumpserver", "template_id": config.get('Templates', 'default_template_id',fallback="7478fed0-e9d3-4abc-a237-2d758bc428fe")}
#DEFAULT_TEMPLATE_ID = config.get('Templates', 'default_template_id', 
#                                fallback="7478fed0-e9d3-4abc-a237-2d758bc428fe")

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

def get_cmdb_data() -> List[Dict[str, Any]]:
    """从CMDB API获取主机数据"""
    try:
        url = f"{CMDB_API_URL}/api/ci/c3mc/jumpserver"
        response = requests.get(url, headers=CMDB_API_HEADERS)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Successfully fetched {len(data['data'] if 'data' in data else data)} hosts from CMDB")
            return data
        else:
            logger.error(f"Failed to fetch data from CMDB: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching data from CMDB: {str(e)}")
        return []

def create_node_structure(js_api: JumpServerAPI, department: str) -> list:
    """根据department创建节点结构，返回所有创建的最终节点ID列表"""
    if not department:
        return [JUMPSERVER_NODE_ID]  # 如果没有部门信息，使用默认节点
    
    # 处理可能包含多个树结构的情况
    departments = [dept.strip() for dept in department.split(',') if dept.strip()]
    if not departments:
        return [JUMPSERVER_NODE_ID]
    
    final_node_ids = []
    
    # 对每个部门路径分别创建节点结构
    for dept in departments:
        # 分割部门路径
        parts = dept.strip().split('.')
        # print(f"Processing department path: {parts}")
        if not parts:
            final_node_ids.append(JUMPSERVER_NODE_ID)
            continue
        
        # 从根节点开始
        current_node_id = JUMPSERVER_NODE_ID  # Default节点
        current_path = "/Default"
        
        # 逐级创建节点
        for part in parts:
            if not part:
                continue
                
            current_path += f"/{part}"
            # 检查节点是否存在
            node_info = js_api.get_nodes_info()
            node_id = node_info.get(current_path, '')
            
            if not node_id:
                # 节点不存在，创建新节点
                logger.info(f"Creating node: {current_path}")
                respon = js_api.create_node(part, current_path)
                node_id = respon.get("id", '')
                if not node_id:
                    logger.error(f"Failed to create node: {part} under {current_path}")
                    break
            
            current_node_id = node_id
        
        final_node_ids.append(current_node_id)
    
    return final_node_ids

def get_platform_id(js_api: JumpServerAPI, platform_name: str) -> Dict[str, Any]:
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

def get_protocols_by_platform(platform_id: int) -> List[Dict[str, Any]]:
    """根据平台ID获取对应的协议配置"""
    if platform_id == 2:  # Windows
        return [{'name': 'rdp', 'port': 3389}]
    else:  # 默认为Linux
        return [{'name': 'ssh', 'port': 22}]

def format_host_params(host_data: Dict[str, Any], js_api: JumpServerAPI) -> Dict[str, Any]:
    """格式化主机参数为JumpServer可接受的格式"""
    hostname = host_data.get('hostName', '')
    ip = host_data.get('ip', '')
    platform = host_data.get('os', 'Linux')
    department = host_data.get('tree', '')

    # 获取平台信息
    platform_info = get_platform_id(js_api, platform)
    
    # 根据IP获取模板ID
    template_info = get_template_id_by_ip(ip)
    
    # 根据部门创建节点结构，现在返回节点ID列表
    node_ids = create_node_structure(js_api, department)
    
    # 获取对应平台的协议配置
    protocols = get_protocols_by_platform(platform_info['id'])
    
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
    
    # 创建节点列表
    nodes = []
    if department:
        # 处理多个部门路径
        departments = [dept.strip() for dept in department.split(',') if dept.strip()]
        for i, node_id in enumerate(node_ids):
            # 如果部门索引有效，则使用对应部门的最后一部分作为节点名称
            if i < len(departments):
                node_name = departments[i].split('.')[-1]
            else:
                node_name = 'Default'
            nodes.append({'id': node_id, 'name': node_name})
    else:
        # 如果没有部门信息，使用Default节点
        for node_id in node_ids:
            nodes.append({'id': node_id, 'name': 'Default'})
    
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

def sync_hosts_to_jumpserver() -> bool:
    """同步CMDB主机到JumpServer"""
    try:
        # 初始化JumpServer API
        js_api = JumpServerAPI(JUMPSERVER_URL, JUMPSERVER_KEY_ID, JUMPSERVER_SECRET)
        
        # 获取JumpServer当前节点下的所有主机
        node_hosts = js_api.get_host_from_node(JUMPSERVER_NODE_ID)
        logger.info(f"Found {len(node_hosts)} hosts in JumpServer node")
        
        # 获取CMDB数据
        cmdb_hosts = get_cmdb_data()
        if not cmdb_hosts or not cmdb_hosts.get("data"):
            logger.error("No hosts data from CMDB, aborting sync")
            return False
        
        # 格式化CMDB主机数据
        host_params_list = []
        cmdb_ips = set()
        
        for host in cmdb_hosts["data"]:
            # 只同步Linux
            system = host.get("os","")
            if system and system.lower() == "linux":
                host_params = format_host_params(host, js_api)
                host_params_list.append(host_params)
                cmdb_ips.add(host_params["address"])
        
        #添加或更新主机
        result = js_api.add_host_to_jumpsever(host_params_list, node_hosts)
        logger.info(f"Sync result: Added {result['added']}, Updated {result['updated']}, Failed {result['failed']}")
        
        # 处理需要删除的主机
        hosts_to_delete = []
        for host_name, host_info in node_hosts.items():
            host_ip = host_info.get("address", "")
            if host_ip and host_ip not in cmdb_ips and host_ip not in EXCLUDED_IPS:
                hosts_to_delete.append((host_name, host_info["ID"]))
      
        # 删除不在CMDB中的主机
        deleted_count = 0
        for host_name, host_id in hosts_to_delete:
            if js_api.delete_host(host_id):
                deleted_count += 1
                logger.info(f"Deleted host {host_name} with ID {host_id} from JumpServer")
            else:
                logger.error(f"Failed to delete host {host_name} with ID {host_id}")
      
        logger.info(f"Total deleted hosts: {deleted_count}")
       
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
    success = sync_hosts_to_jumpserver()
    
    if success:
        logger.info("Sync completed successfully")
        return 0
    else:
        logger.error("Sync failed")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
