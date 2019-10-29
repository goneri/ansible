#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2018, Christian Kotte <christian.kotte@gmx.de>
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = r'''
---
module: vmware_host_dns
short_description: Manage DNS configuration of an ESXi host system
description:
- This module can be used to configure DNS for the default TCP/IP stack on an ESXi host system.
version_added: 2.10
author:
- Christian Kotte (@ckotte)
- Mario Lenz (@mariolenz)
notes:
- This module is a replacement for the module C(vmware_dns_config)
- Tested on vSphere 6.5
requirements:
- python >= 2.6
- PyVmomi
options:
  esxi_hostname:
    description:
    - Name of the host system to work with.
    - This parameter is required if C(cluster_name) is not specified.
    type: str
  cluster_name:
    description:
    - Name of the cluster from which all host systems will be used.
    - This parameter is required if C(esxi_hostname) is not specified.
    type: str
  host_name:
    description:
    - The hostname to be used for the ESXi host.
    type: str
    required: True
  dhcp:
    description:
    - Use DHCP for DNS configuration.
    suboptions:
      device:
        description:
        - The VMkernel network adapter to obtain DNS settings from.
        type: str
    type: dict
  static:
    description:
    - Use static DNS configuration.
    suboptions:
      domain:
        description:
        - The domain name to be used for the the ESXi host.
        type: str
        required: True
      dns_servers:
        description:
        - A list of DNS servers to be used.
        - The order of the DNS servers is important as they are used consecutively in order.
        type: list
        required: True
      search_domains:
        description:
        - A list of domains to be searched through by the resolver.
        type: list
        required: False
    type: dict
  verbose:
    description:
    - Verbose output of the DNS server configuration change.
    - Explains if an DNS server was added, removed, or if the DNS server sequence was changed.
    type: bool
    required: false
    default: false
extends_documentation_fragment: vmware.documentation
'''

EXAMPLES = r'''
- name: Configure DNS for an ESXi host
  vmware_host_dns:
    hostname: '{{ vcenter_hostname }}'
    username: '{{ vcenter_username }}'
    password: '{{ vcenter_password }}'
    esxi_hostname: '{{ esxi_hostname }}'
    host_name: esx01
    static:
      domain: example.local
      dns_servers:
        - 192.168.1.10
        - 192.168.1.11
      search_domains:
        - subdomain.example.local
        - example.local
  delegate_to: localhost

- name: Configure DNS for all ESXi hosts of a cluster
  vmware_host_dns:
    hostname: '{{ vcenter_hostname }}'
    username: '{{ vcenter_username }}'
    password: '{{ vcenter_password }}'
    cluster_name: '{{ cluster_name }}'
    static:
      domain: example.local
      dns_servers:
        - 192.168.1.10
        - 192.168.1.11
      search_domains:
        - subdomain.example.local
        - example.local
  delegate_to: localhost

- name: Configure DNS via DHCP for an ESXi host
  vmware_host_dns:
    hostname: '{{ vcenter_hostname }}'
    username: '{{ vcenter_username }}'
    password: '{{ vcenter_password }}'
    esxi_hostname: '{{ esxi_hostname }}'
    dhcp:
      device: vmk0
  delegate_to: localhost
'''

RETURN = r'''
result:
  description: metadata about host system's DNS configuration
  returned: always
  type: dict
  sample: {
    "esx01.example.local": {
      "changed": true,
      "dns_servers_changed": ["192.168.1.12", "192.168.1.13"],
      "dns_servers": ["192.168.1.10", "192.168.1.11"],
      "dns_servers_previous": ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.13"],
      "domain": "example.local",
      "host_name": "esx01",
      "msg": "DNS servers and Search domains changed",
      "search_domains_changed": ["subdomain.example.local"],
      "search_domains": ["subdomain.example.local", "example.local"],
      "search_domains_previous": ["example.local"],
    },
  }
'''

try:
    from pyVmomi import vim, vmodl
except ImportError:
    pass

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.vmware import PyVmomi, vmware_argument_spec
from ansible.module_utils._text import to_native


class VmwareHostDNS(PyVmomi):
    """Class to manage DNS configuration of an ESXi host system"""

    def __init__(self, module):
        super(VmwareHostDNS, self).__init__(module)
        cluster_name = self.params.get('cluster_name')
        esxi_host_name = self.params.get('esxi_hostname')
        self.hosts = self.get_all_host_objs(cluster_name=cluster_name, esxi_host_name=esxi_host_name)
        if not self.hosts:
            self.module.fail_json(msg="Failed to find host system.")

    def ensure(self):
        """Function to manage DNS configuration of an ESXi host system"""
        results = dict(changed=False, result=dict())
        cluster_name = self.params.get('cluster_name', None)
        if not cluster_name:
            host_name = self.params.get('host_name')
        if self.params.get('dhcp'):
            network_type = 'dhcp'
            vmkernel_device = self.params.get('dhcp').get('device')
        else:
            network_type = 'static'
            domain = self.params.get('static').get('domain')
            dns_servers = self.params.get('static').get('dns_servers')
            search_domains = self.params.get('static').get('search_domains', None)
        verbose = self.module.params.get('verbose', False)
        host_change_list = []
        for host in self.hosts:
            changed = False
            changed_list = []
            results['result'][host.name] = dict(changed='', msg='')

            host_netstack_config = host.config.network.netStackInstance
            for instance in host_netstack_config:
                if instance.key == 'defaultTcpipStack':
                    netstack_spec = vim.host.NetworkConfig.NetStackSpec()
                    netstack_spec.operation = 'edit'
                    netstack_spec.netStackInstance = vim.host.NetStackInstance()
                    netstack_spec.netStackInstance.key = 'defaultTcpipStack'
                    # netstack_spec.netStackInstance.name = 'defaultTcpipStack'
                    dns_config = vim.host.DnsConfig()
                    results['result'][host.name]['dns_config'] = network_type
                    if network_type == 'static':
                        if instance.dnsConfig.dhcp:
                            results['result'][host.name]['host_name'] = host_name
                            results['result'][host.name]['domain'] = domain
                            results['result'][host.name]['dns_servers'] = dns_servers
                            results['result'][host.name]['search_domains'] = search_domains
                            results['result'][host.name]['dns_config_previous'] = 'DHCP'
                            changed = True
                            changed_list.append("DNS configuration")
                            dns_config.dhcp = False
                            dns_config.virtualNicDevice = None
                            dns_config.hostName = host_name
                            dns_config.domainName = domain
                            dns_config.address = dns_servers
                            dns_config.searchDomain = search_domains
                        else:
                            # Check host name
                            if cluster_name:
                                # Don't check (and configure) hostname if cluster is specified
                                results['result'][host.name]['host_name'] = instance.dnsConfig.hostName
                            else:
                                results['result'][host.name]['host_name'] = host_name
                                if instance.dnsConfig.hostName != host_name:
                                    results['result'][host.name]['host_name_previous'] = instance.dnsConfig.hostName
                                    changed = True
                                    changed_list.append("Host name")
                                    dns_config.hostName = host_name

                            # Check domain
                            results['result'][host.name]['domain'] = domain
                            if instance.dnsConfig.domainName != domain:
                                results['result'][host.name]['domain_previous'] = instance.dnsConfig.domainName
                                changed = True
                                changed_list.append("Domain")
                                dns_config.domainName = domain

                            # Check DNS server(s)
                            results['result'][host.name]['dns_servers'] = dns_servers
                            if instance.dnsConfig.address != dns_servers:
                                results['result'][host.name]['dns_servers_previous'] = instance.dnsConfig.address
                                results['result'][host.name]['dns_servers_changed'] = (
                                    self.get_differt_entries(instance.dnsConfig.address, dns_servers)
                                )
                                changed = True
                                # build verbose message
                                if verbose:
                                    dns_servers_verbose_message = self.build_changed_message(
                                        instance.dnsConfig.address,
                                        dns_servers
                                    )
                                else:
                                    changed_list.append("DNS servers")
                                dns_config.address = dns_servers

                            # Check search domain config
                            results['result'][host.name]['search_domains'] = search_domains
                            if search_domains and instance.dnsConfig.searchDomain != search_domains:
                                results['result'][host.name]['search_domains_previous'] = instance.dnsConfig.searchDomain
                                results['result'][host.name]['search_domains_changed'] = (
                                    self.get_differt_entries(instance.dnsConfig.searchDomain, search_domains)
                                )
                                changed = True
                                changed_list.append("Search domains")
                                dns_config.searchDomain = search_domains
                    elif network_type == 'dhcp' and not instance.dnsConfig.dhcp:
                        results['result'][host.name]['device'] = vmkernel_device
                        results['result'][host.name]['dns_config_previous'] = 'static'
                        changed = True
                        changed_list.append("DNS configuration")
                        dns_config.dhcp = True
                        dns_config.virtualNicDevice = vmkernel_device
                    netstack_spec.netStackInstance.dnsConfig = dns_config
                    config = vim.host.NetworkConfig()
                    config.netStackSpec = [netstack_spec]

            if changed:
                if self.module.check_mode:
                    changed_suffix = ' would be changed'
                else:
                    changed_suffix = ' changed'
                if len(changed_list) > 2:
                    message = ', '.join(changed_list[:-1]) + ', and ' + str(changed_list[-1])
                elif len(changed_list) == 2:
                    message = ' and '.join(changed_list)
                elif len(changed_list) == 1:
                    message = changed_list[0]
                if verbose and dns_servers_verbose_message:
                    if changed_list:
                        message = message + changed_suffix + '. ' + dns_servers_verbose_message + '.'
                    else:
                        message = dns_servers_verbose_message
                else:
                    message += changed_suffix
                results['result'][host.name]['changed'] = True
                host_network_system = host.configManager.networkSystem
                if not self.module.check_mode:
                    try:
                        host_network_system.UpdateNetworkConfig(config, 'modify')
                    except vim.fault.AlreadyExists:
                        self.module.fail_json(
                            msg="Network entity specified in the configuration already exist on host '%s'" % host.name
                        )
                    except vim.fault.NotFound:
                        self.module.fail_json(
                            msg="Network entity specified in the configuration doesn't exist on host '%s'" % host.name
                        )
                    except vim.fault.ResourceInUse:
                        self.module.fail_json(msg="Resource is in use on host '%s'" % host.name)
                    except vmodl.fault.InvalidArgument:
                        self.module.fail_json(
                            msg="An invalid parameter is passed in for one of the networking objects for host '%s'" %
                            host.name
                        )
                    except vmodl.fault.NotSupported as not_supported:
                        self.module.fail_json(
                            msg="Operation isn't supported for the instance on '%s' : %s" %
                            (host.name, to_native(not_supported.msg))
                        )
                    except vim.fault.HostConfigFault as config_fault:
                        self.module.fail_json(
                            msg="Failed to configure TCP/IP stacks for host '%s' due to : %s" %
                            (host.name, to_native(config_fault.msg))
                        )
            else:
                results['result'][host.name]['changed'] = False
                message = 'All settings are already configured'
            results['result'][host.name]['msg'] = message

            host_change_list.append(changed)

        if any(host_change_list):
            results['changed'] = True
        self.module.exit_json(**results)

    def build_changed_message(self, dns_servers_configured, dns_servers_new):
        """Build changed message"""
        check_mode = 'would be ' if self.module.check_mode else ''
        # get differences
        add = self.get_not_in_list_one(dns_servers_new, dns_servers_configured)
        remove = self.get_not_in_list_one(dns_servers_configured, dns_servers_new)
        diff_servers = list(dns_servers_configured)
        if add and remove:
            for server in add:
                diff_servers.append(server)
            for server in remove:
                diff_servers.remove(server)
            if dns_servers_new != diff_servers:
                message = (
                    "DNS server %s %sadded and %s %sremoved and the server sequence %schanged as well" %
                    (self.array_to_string(add), check_mode, self.array_to_string(remove), check_mode, check_mode)
                )
            else:
                if dns_servers_new != dns_servers_configured:
                    message = (
                        "DNS server %s %sreplaced with %s" %
                        (self.array_to_string(remove), check_mode, self.array_to_string(add))
                    )
                else:
                    message = (
                        "DNS server %s %sremoved and %s %sadded" %
                        (self.array_to_string(remove), check_mode, self.array_to_string(add), check_mode)
                    )
        elif add:
            for server in add:
                diff_servers.append(server)
            if dns_servers_new != diff_servers:
                message = (
                    "DNS server %s %sadded and the server sequence %schanged as well" %
                    (self.array_to_string(add), check_mode, check_mode)
                )
            else:
                message = "DNS server %s %sadded" % (self.array_to_string(add), check_mode)
        elif remove:
            for server in remove:
                diff_servers.remove(server)
            if dns_servers_new != diff_servers:
                message = (
                    "DNS server %s %sremoved and the server sequence %schanged as well" %
                    (self.array_to_string(remove), check_mode, check_mode)
                )
            else:
                message = "DNS server %s %sremoved" % (self.array_to_string(remove), check_mode)
        else:
            message = "DNS server sequence %schanged" % check_mode

        return message

    @staticmethod
    def get_not_in_list_one(list1, list2):
        """Return entries that ore not in list one"""
        return [x for x in list1 if x not in set(list2)]

    @staticmethod
    def array_to_string(array):
        """Return string from array"""
        if len(array) > 2:
            string = (
                ', '.join("'{0}'".format(element) for element in array[:-1]) + ', and '
                + "'{0}'".format(str(array[-1]))
            )
        elif len(array) == 2:
            string = ' and '.join("'{0}'".format(element) for element in array)
        elif len(array) == 1:
            string = "'{0}'".format(array[0])
        return string

    @staticmethod
    def get_differt_entries(list1, list2):
        """Return different entries of two lists"""
        return [a for a in list1 + list2 if (a not in list1) or (a not in list2)]


def main():
    """Main"""
    argument_spec = vmware_argument_spec()
    argument_spec.update(
        esxi_hostname=dict(required=False, type='str'),
        host_name=dict(required=False, type='str'),
        cluster_name=dict(required=False, type='str'),
        dhcp=dict(type='dict', options=dict(
            device=dict(type='str', required=True),
        )),
        static=dict(type='dict', options=dict(
            domain=dict(required=True, type='str'),
            dns_servers=dict(required=True, type='list'),
            search_domains=dict(required=True, type='list'),
        )),
        verbose=dict(type='bool', default=False, required=False)
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[
            ['cluster_name', 'esxi_hostname'],
            ['dhcp', 'static'],
        ],
        mutually_exclusive=[
            ['cluster_name', 'esxi_host_name'],
            ['cluster_name', 'host_name'],
        ],
        supports_check_mode=True
    )

    dns = VmwareHostDNS(module)
    dns.ensure()


if __name__ == '__main__':
    main()
