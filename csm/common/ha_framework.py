#!/usr/bin/env python3

"""
 ****************************************************************************
 Filename:          ha_framework.py
 Description:       HAFramework manages resources.

 Creation Date:     02/08/2019
 Author:            Ajay Paratmandali

 Do NOT modify or remove this copyright and confidentiality notice!
 Copyright (c) 2001 - $Date: 2015/01/14 $ Seagate Technology, LLC.
 The code contained herein is CONFIDENTIAL to Seagate Technology, LLC.
 Portions are also trade secret. Any use, duplication, derivation, distribution
 or disclosure of this code, for any reason, not expressly authorized is
 prohibited. All other rights are expressly reserved by Seagate Technology, LLC.
 ****************************************************************************
"""

import sys
import os
import time
from csm.common.process import SimpleProcess

class HAFramework:
    def __init__(self, resource_agents):
        self._resource_agents = resource_agents

    def init(self, force_flag):
        _results = []
        if self.get_status() != 'up':
            raise Exception('Error: HA Framework is not initalized ...')
        for ra in self._resource_agents.values():
            if not ra.init(force_flag):
                raise Exception('Error: initalizing resource agent %s' %ra)
        return True

    def failover(self):
        pass

    def is_available(self):
        pass

    def get_nodes(self):
        pass

    def get_status(self):
        pass

class PcsHAFramework(HAFramework):
    def __init__(self, resource_agents=None):
        super(PcsHAFramework, self).__init__(resource_agents)
        self._resource_agents = resource_agents

    def get_nodes(self):
        """
            Return tuple containing following things:
            1. List of active nodes
            2. List of inactive nodes
            Output:
            Corosync Nodes:
                Online: node1 node2
                Offline:
        """
        _livenode_cmd = "/usr/sbin/pcs status nodes corosync"
        _proc = SimpleProcess(_livenode_cmd)
        _output, _err, _rc = _proc.run(universal_newlines=True)
        if _rc != 0:
            raise Exception("Failed: Command: %s Returncode: %s Error: %s"
                            %(_livenode_cmd, _rc, _err))
        _status_list = _output.split('\n')
        _activenodes = _status_list[1].split()
        _activenodes.pop(0)
        _inactivenodes = _status_list[2].split()
        _inactivenodes.pop(0)
        _allnodes = _activenodes + _inactivenodes
        return { "nodes": _allnodes, "online": _activenodes, "offline": _inactivenodes }

    def make_node_active(self, node):
        """
            Put node on standby node for maintenance use
        """
        try:
            _standby_cmd = "/usr/sbin/pcs node standby "
            _standby_cmd = _standby_cmd + "--all" if node == "all" else _standby_cmd + node
            _proc = SimpleProcess(_standby_cmd)
            _output, _err, _rc = _proc.run(universal_newlines=True)
            if _rc != 0:
                raise Exception(_err)
            node = "all nodes" if node == "all" else node
            result = "Successfully put " + node + " on active state"
            return { "message": result}
        except Exception as e:
            raise Exception("Failed to put %s on active state. Error: %s" %(node,e))

    def make_node_passive(self, node):
        """
            Put node on standby node for maintenance use
        """
        try:
            _standby_cmd = "/usr/sbin/pcs node unstandby "
            _standby_cmd = _standby_cmd + "--all" if node == "all" else _standby_cmd + node
            _proc = SimpleProcess(_standby_cmd)
            _output, _err, _rc = _proc.run(universal_newlines=True)
            if _rc != 0:
                raise Exception(_err)
            node = "all nodes" if node == "all" else node
            result = "Successfully put " + node + " on passive state"
            return { "message": result}
        except Exception as e:
            raise Exception("Failed to remove %s from passive state. Error: %s" %(node,e))

    def get_status(self):
        """
            Return if HAFramework in up or down
        """
        _cluster_status_cmd = "/usr/sbin/pcs cluster status"
        _proc = SimpleProcess(_cluster_status_cmd)
        _output, _err, _rc = _proc.run(universal_newlines=True)
        return 'down' if _err != '' else 'up'

class ResourceAgent:
    def __init__(self, resources):
        self._resources = resources

    def init(self, force_flag):
        pass

    def get_state(self):
        pass

    def failover(self):
        pass

    def is_available(self):
        pass

class PcsResourceAgent(ResourceAgent):
    def __init__(self, resources):
        super(PcsResourceAgent, self).__init__(resources)
        self._resources = resources

    def is_available(self):
        """
            Return True if all resources available else False
        """
        for resource in self._resources:
            _chk_res_cmd = "pcs resource show " + resource
            _proc = SimpleProcess(_chk_res_cmd)
            _output, _err, _rc = _proc.run(universal_newlines=True)
            if _err != '':
                return False
        return True

    def _delete_resource(self):
        for resource in self._resources:
            _delete_res_cmd = "pcs resource delete " + resource
            _proc = SimpleProcess(_delete_res_cmd)
            _output, _err, _rc = _proc.run(universal_newlines=True)
            if _err != '':
                raise Exception("Failed: Command: %s Error: %s Returncode: %s"
                                %(_delete_res_cmd, _err, _rc))

    def _ra_init(self):
        self._cmd_list = []
        self._resource_file = "/var/tmp/resource.conf"
        if not os.path.exists("/var/tmp"): os.makedirs("/var/tmp")
        self._cmd_list.append("pcs cluster cib " + self._resource_file)

    def _init_resource(self, resource, service, provider, interval, timeout):
        _cmd = "pcs -f " + self._resource_file + " resource create " + resource +\
            " " + provider + ":" + service + " meta failure-timeout=10s" +\
            " op monitor timeout=" + timeout[1] + " interval=" + interval[1] +\
            " op start timeout=" + timeout[0] + " interval=" + interval[0] +\
            " op stop timeout=" + timeout[2] + " interval=" + interval[2]
        self._cmd_list.append(_cmd)

    def _init_constraint(self, score):
        # Configure colocation
        self._cmd_list.append("pcs -f " + self._resource_file +\
            " constraint colocation set " + ' '.join(self._resources))

        # Configure update
        self._cmd_list.append("pcs -f " + self._resource_file +\
            " constraint order set " + ' '.join(self._resources))

        # Configure score
        for resource in self._resources:
            self._cmd_list.append("pcs -f " + self._resource_file +\
                " constraint location " + resource + " prefers " +\
                self._primary + "=" + score)
            self._cmd_list.append("pcs -f " + self._resource_file +\
                " constraint location " + resource + " prefers " +\
                self._secondary + "=" + score)

    def _execute_config(self):
        self._cmd_list.append("pcs cluster cib-push " + self._resource_file)
        for cmd in self._cmd_list:
            _proc = SimpleProcess(cmd)
            _output, _err, _rc = _proc.run(universal_newlines=True)
            if _err != '':
                raise Exception("Failed: Command: %s Error: %s Returncode: %s" %(cmd, _err, _rc))
