#!/usr/bin/python
# coding: utf8
#######################################################################
#
#   Copyright (c) 2015 Orange
#   valentin.boucher@orange.com
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0
########################################################################
import subprocess32 as subprocess
import os
import shutil
import yaml
import requests
from git import Repo
from threading import Thread

class orchestrator:

    def __init__(self, testcase_dir, inputs={}, site_name='site1', logger=None):
        self.testcase_dir = testcase_dir
        self.blueprint_dir = testcase_dir + 'cloudify-manager-blueprint/'
        self.input_file = 'inputs.yaml'
        self.manager_blueprint = False
        self.config = inputs
        self.logger = logger
        self.manager_up = False
        self.site_name = site_name
        self.thread = Thread(target = self._deploy_manager)
        
        self.manager_ip = self._get_manager_ip()
        if self.manager_ip:
            self.manager_up = True

    def set_credentials(self, username, password, tenant_name, auth_url):
        self.config['keystone_username'] = username
        self.config['keystone_password'] = password
        self.config['keystone_url'] = auth_url
        self.config['keystone_tenant_name'] = tenant_name

    def set_flavor_id(self, flavor_id):
        self.config['flavor_id'] = flavor_id

    def set_image_id(self, image_id):
        self.config['image_id'] = image_id

    def set_external_network_name(self, external_network_name):
        self.config['external_network_name'] = external_network_name

    def set_ssh_user(self, ssh_user):
        self.config['ssh_user'] = ssh_user

    def set_nova_url(self, nova_url):
        self.config['nova_url'] = nova_url

    def set_neutron_url(self, neutron_url):
        self.config['neutron_url'] = neutron_url

    def set_nameservers(self, nameservers):
        if 0 < len(nameservers):
            self.config['dns_subnet_1'] = nameservers[0]

    def set_logger(self, logger):
        self.logger = logger

    def download_manager_blueprint(self, manager_blueprint_url,
                                   manager_blueprint_branch):
        if self.manager_blueprint:
            if self.logger:
                self.logger.info(
                    "cloudify manager server blueprint is "
                    "already downloaded !")
        else:
            if self.logger:
                self.logger.info(
                    "Downloading the cloudify manager server blueprint")
            download_result = download_blueprints(
                manager_blueprint_url,
                manager_blueprint_branch,
                self.blueprint_dir)

            if not download_result:
                if self.logger:
                    self.logger.error("Failed to download manager blueprint")
                exit(-1)
            else:
                self.manager_blueprint = True

    def manager_up(self):
        return self.manager_up

    def deploy_manager(self):
        self.thread.start()

    def wait_manager_deployment_finish(self):
        self.thread.join()

    def get_manager_ip(self):
        if not self.manager_ip:
            self.manager_ip = self._get_manager_ip()
        return self.manager_ip

    def _get_manager_ip(self):
        script = "source " + self.testcase_dir + "venv_cloudify/bin/activate; "
        script += "cd " + self.testcase_dir + "; "
        script += "cfy status | grep -Eo \"([0-9]{1,3}\.){3}[0-9]{1,3}\""
        cmd = "/bin/bash -c '" + script + "'"
        mgr_ip = None
        try:
            if self.logger:
                self.logger.debug("Trying to get cloudify manager IP ... ")
            mgr_ip = os.popen(cmd).read()
            mgr_ip = mgr_ip.splitlines()[0]
        except:
            if self.logger:
                self.logger.error("Unable to find cloudify manager IP")
        return mgr_ip

    def _deploy_manager(self):
        if self.manager_blueprint:
            if self.logger:
                self.logger.info("Writing the inputs file")
            with open(self.blueprint_dir + "inputs.yaml", "w") as f:
                f.write(yaml.dump(self.config, default_style='"'))
            f.close()

            # Ensure no ssh key file already exists
            key_files = ["/.ssh/cloudify-manager-kp.pem",
                         "/.ssh/cloudify-agent-kp.pem"]
            home = os.path.expanduser("~")

            for key_file in key_files:
                if os.path.isfile(home + key_file):
                    os.remove(home + key_file)

            if self.logger:
                self.logger.info("Launching the cloudify-manager deployment")
            script = "set -e; "
            script += ("source " + self.testcase_dir +
                       "venv_cloudify/bin/activate; ")
            script += "cd " + self.testcase_dir + "; "
            script += "cfy init -r; "
            script += "cd cloudify-manager-blueprint; "
            script += ("cfy local create-requirements -o requirements.txt " +
                       "-p openstack-manager-blueprint.yaml; ")
            script += "pip install -r requirements.txt; "
            script += ("cfy bootstrap --install-plugins " +
                       "-p openstack-manager-blueprint.yaml -i inputs.yaml; ")
            cmd = "/bin/bash -c '" + script + "'"
            output_file = "output-" + self.site_name + ".txt"
            error = execute_command(cmd, self.logger, output_file=output_file)
            if error:
                return error

            if self.logger:
                self.logger.info("Cloudify-manager server is UP !")

            self.manager_up = True




    def undeploy_manager(self):
        if self.logger:
            self.logger.info("Launching the cloudify-manager undeployment")

        self.manager_up = False

        script = "source " + self.testcase_dir + "venv_cloudify/bin/activate; "
        script += "cd " + self.testcase_dir + "; "
        script += "cfy teardown -f --ignore-deployments; "
        cmd = "/bin/bash -c '" + script + "'"
        execute_command(cmd, self.logger)

        if self.logger:
            self.logger.info(
                "Cloudify-manager server has been successfully removed!")

    def download_upload_and_deploy_blueprint(self, blueprint, config,
                                             dep_name):
        if self.logger:
            self.logger.info("Downloading the {0} blueprint".format(
                blueprint['file_name']))
        bp_name = blueprint.get('name')
        download_result = download_blueprints(blueprint['url'],
                                              blueprint['branch'],
                                              self.testcase_dir +
                                              blueprint['destination_folder'])

        if not download_result:
            if self.logger:
                self.logger.error(
                    "Failed to download blueprint {0}".
                    format(blueprint['file_name']))
            exit(-1)

        if self.logger:
            self.logger.info("Writing the inputs file")

        with open(self.testcase_dir + blueprint['destination_folder'] +
                  "/inputs.yaml", "w") as f:
            f.write(yaml.dump(config, default_style='"'))

        f.close()

        if self.logger:
            self.logger.info("Launching the {0} deployment".format(bp_name))
        script = "source " + self.testcase_dir + "venv_cloudify/bin/activate; "
        script += ("cd " + self.testcase_dir +
                   blueprint['destination_folder'] + "; ")
        script += ("cfy blueprints upload -b " +
                   bp_name + " -p " + blueprint['file_name'] + "; ")
        script += ("cfy deployments create -b " + bp_name +
                   " -d " + dep_name + " --inputs inputs.yaml; ")
        script += ("cfy executions start -w install -d " +
                   dep_name + " --timeout 1800; ")

        cmd = "/bin/bash -c '" + script + "'"
        error = execute_command(cmd, self.logger, 2000)
        if error:
            return error
        if self.logger:
            self.logger.info("The deployment of {0} is ended".format(dep_name))

    def get_deployment_ouputs(self, dep_name):
        try:
            api_url = "http://" + self.get_manager_ip()+ "/api/v2"
            dep_outputs = requests.get(api_url + "/deployments/" +
                                       dep_name + "/outputs")
            return dep_outputs.json().get('outputs')
        except:
            return None

    def undeploy_deployment(self, dep_name):
        if self.logger:
            self.logger.info("Launching the {0} undeployment".format(dep_name))
        script = "source " + self.testcase_dir + "venv_cloudify/bin/activate; "
        script += "cd " + self.testcase_dir + "; "
        script += ("cfy executions start -w uninstall -d " + dep_name +
                   " --timeout 1800 ; ")
        script += "cfy deployments delete -d " + dep_name + "; "

        cmd = "/bin/bash -c '" + script + "'"
        try:
            execute_command(cmd, self.logger)
        except:
            if self.logger:
                self.logger.error("Clearwater undeployment failed")


def execute_command(cmd, logger, timeout=float(1800), output_file='output.txt'):
    """
    Execute Linux command
    """
    if logger:
        logger.debug('Executing command : {}'.format(cmd))
    timeout_exception = False
    f = open(output_file, 'w+')
    try:
        p = subprocess.call(cmd, shell=True, stdout=f,
                            stderr=subprocess.STDOUT)
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


def download_blueprints(blueprint_url, branch, dest_path):
    if os.path.exists(dest_path):
        shutil.rmtree(dest_path)
    try:
        Repo.clone_from(blueprint_url, dest_path, branch=branch)
        return True
    except:
        return False
