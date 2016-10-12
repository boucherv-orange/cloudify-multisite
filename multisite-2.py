# -*- coding: utf-8 -*-
"""
Created on Wed Aug  3 17:09:49 2016

@author: boucherv
"""

import yaml
import copy
import os
import time

import subprocess32 as subprocess
from orchestrator import orchestrator

with open('config.yaml') as f:
    config = yaml.safe_load(f)
f.close()

general_config = config.get('general')
sites_config = config.get('site')
new_sites_config = {}

def execute_command(cmd, logger=None, timeout=1800):
    """
    Execute Linux command
    """
    if logger:
        logger.debug('Executing command : {}'.format(cmd))
    timeout_exception = False
    output_file = "output.txt"
    f = open(output_file, 'w+')
    try:
        p = subprocess.call(cmd, shell=True, stdout=f,
                            stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired:
        timeout_exception = True
        if logger:
            logger.error("TIMEOUT when executing command %s" % cmd)
        pass

    f.close()
    f = open(output_file, 'r')
    result = f.read()
    if result != "" and logger:
        logger.debug(result)
    if p == 0:
        return False
    else:
        if logger and not timeout_exception:
            logger.error("Error when executing command %s" % cmd)
            f = open(output_file, 'r')
            lines = f.readlines()
            result = lines[len(lines) - 3]
            result += lines[len(lines) - 2]
            result += lines[len(lines) - 1]
            return result

def mergedicts(dict1, dict2):
    for k in set(dict1.keys()).union(dict2.keys()):
        if k in dict1 and k in dict2:
            if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
                yield (k, dict(mergedicts(dict1[k], dict2[k])))
            else:
                # If one of the values is not a dict, you can't continue merging it.
                # Value from second dict overrides one in first and we move on.
                yield (k, dict2[k])
                # Alternatively, replace this with exception raiser to alert you of value conflicts
        elif k in dict1:
            yield (k, dict1[k])
        else:
            yield (k, dict2[k])

for current_site_name, current_site_config in sites_config.items():
    new_sites_config[current_site_name] = copy.deepcopy(general_config)
    for current_app_name, current_app_value in current_site_config.items():
        for current_app_conf_name, current_app_conf_value in current_app_value.items():
            if type(current_app_value[current_app_conf_name]) is dict:
                new_sites_config.get(current_site_name).get(current_app_name).get(current_app_conf_name).update(current_app_conf_value)
            else:
                new_sites_config[current_site_name][current_app_name][current_app_conf_name] = current_app_conf_value
          

for current_site_name, current_site_config in new_sites_config.items():
    current_cloudify_config = current_site_config.get('cloudify')
    current_data_dir = current_site_config.get('general').get('data_dir')
    current_data_dir = current_data_dir + "/" + current_site_name + "/"
    if not os.path.exists(current_data_dir):
        os.makedirs(current_data_dir)
    
    current_cfy = orchestrator(current_data_dir, current_cloudify_config.get('inputs'), current_site_name)
    current_site_config['cloudify']['object'] = current_cfy
    print current_cfy.get_manager_ip()
    if not current_cfy.manager_up:
        cmd = "chmod +x create_venv.sh"
        execute_command(cmd)
        time.sleep(3)
        cmd = "/home/opnfv/create_venv.sh " + current_data_dir
        execute_command(cmd)
    
        current_site_config['cloudify']['object'] = current_cfy
        current_cfy.download_manager_blueprint(
            current_cloudify_config.get("blueprint").get('url'), current_cloudify_config.get("blueprint").get('branch'))
    
        current_cfy.deploy_manager()

for current_site_name, current_site_config in new_sites_config.items():
    current_cfy = current_site_config.get('cloudify').get('object')
    if not current_cfy.manager_up:
        current_cfy.wait_manager_deployment_finish()

GENERAL_INPUTS = general_config.get('general').get('inputs')
# OPENVPN 
# Server
print "OPENVPN - SERVER"
config_site1 = new_sites_config['site1']
cfy_site1 = config_site1.get('cloudify').get('object')
config_openvpn_site1 = config_site1.get('openvpn')
openvpn_site1_blueprint = config_openvpn_site1.get('blueprint')
openvpn_site1_inputs = copy.deepcopy(GENERAL_INPUTS)
openvpn_site1_inputs['remote_network'] = new_sites_config.get('site2').get('cloudify').get('inputs').get('management_subnet_ip')
openvpn_site1_deployment_name = config_site1.get('openvpn').get('deployment-name')
cfy_site1.download_upload_and_deploy_blueprint(
                openvpn_site1_blueprint, openvpn_site1_inputs, openvpn_site1_deployment_name)
config_openvpn_site1['outputs'] = cfy_site1.get_deployment_ouputs(openvpn_site1_deployment_name)
if not config_openvpn_site1['outputs']:
    print "error"

# Client
print "OPENVPN - CLIENT"
config_site2 = new_sites_config['site2']
cfy_site2 = config_site2.get('cloudify').get('object')
config_openvpn_site2 = config_site2.get('openvpn')
openvpn_site2_blueprint = config_openvpn_site2.get('blueprint')
openvpn_site2_inputs = copy.deepcopy(GENERAL_INPUTS)
openvpn_site2_inputs.pop("external_network_name")
openvpn_site2_inputs['remote_network'] = new_sites_config.get('site1').get('cloudify').get('inputs').get('management_subnet_ip')
openvpn_site2_inputs['openvpn_server_ip'] = config_openvpn_site1.get('outputs').get('openvpn_ip')
openvpn_site2_deployment_name = config_openvpn_site2.get('deployment-name')
cfy_site2.download_upload_and_deploy_blueprint(
                openvpn_site2_blueprint, openvpn_site2_inputs, openvpn_site2_deployment_name)
                
                
# Designate
print "DESIGNATE"
config_site1 = new_sites_config['site1']
cfy_site1 = config_site1.get('cloudify').get('object')
config_designate_site1 = config_site1.get('designate')
designate_site1_blueprint = config_designate_site1.get('blueprint')
designate_site1_inputs = copy.deepcopy(GENERAL_INPUTS)
designate_site1_deployment_name = config_designate_site1.get('deployment-name')
cfy_site1.download_upload_and_deploy_blueprint(
                designate_site1_blueprint, designate_site1_inputs, designate_site1_deployment_name)
config_designate_site1['outputs'] = cfy_site1.get_deployment_ouputs(designate_site1_deployment_name)

# Clearwater
print "CLEARWATER - 1"
config_site1 = new_sites_config['site1']
cfy_site1 = config_site1.get('cloudify').get('object')
config_clearwater_site1 = config_site1.get('clearwater')
clearwater_site1_blueprint = config_clearwater_site1.get('blueprint')
clearwater_site1_inputs=dict(mergedicts(config_clearwater_site1.get('inputs'), GENERAL_INPUTS))
clearwater_site1_inputs['dns_ips'] = config_designate_site1.get('outputs').get('dns_endpoint')
clearwater_site1_inputs['etcd_ip'] = cfy_site1.get_manager_ip()
clearwater_site1_deployment_name = config_clearwater_site1.get('deployment-name')
cfy_site1.download_upload_and_deploy_blueprint(
                clearwater_site1_blueprint, clearwater_site1_inputs, clearwater_site1_deployment_name)
                
# Clearwater
print "CLEARWATER - 2"
config_site2 = new_sites_config['site2']
cfy_site2 = config_site2.get('cloudify').get('object')
config_clearwater_site2 = config_site2.get('clearwater')
clearwater_site2_blueprint = config_clearwater_site2.get('blueprint')
clearwater_site2_inputs=dict(mergedicts(config_clearwater_site2.get('inputs'), GENERAL_INPUTS))
clearwater_site2_inputs['dns_ips'] = config_designate_site1.get('outputs').get('dns_endpoint')
clearwater_site2_inputs['etcd_ip'] = cfy_site1.get_manager_ip()
clearwater_site2_deployment_name = config_clearwater_site2.get('deployment-name')
cfy_site2.download_upload_and_deploy_blueprint(
                clearwater_site2_blueprint, clearwater_site2_inputs, clearwater_site2_deployment_name)