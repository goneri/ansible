from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pytest
import sys

if sys.version_info < (2, 7):
    pytestmark = pytest.mark.skip("vmware_guest Ansible modules require Python >= 2.7")
    def enable_vcr():
        def b():
            pass
        return b
else:
    from conftest import enable_vcr

from units.compat.mock import ANY


@enable_vcr()
def test_no_parameter(run_module):
    exit_json, fail_json = run_module('vmware_appliance_health_info', {})
    exit_json.assert_called_with(
        ANY,
        applmgmt={'value': 'green'},
        databasestorage={'value': 'green'},
        invocation={
            'module_args': {
                'allow_multiples': False,
                'log_level': 'normal',
                'status_code': [200],
                'subsystem': None,
                'asset': None},
            'module_kwargs': {
                'is_multipart': True,
                'use_object_handler': True}},
        lastcheck={'value': '2019-09-12T23:22:51.890Z'},
        load={'value': 'green'},
        mem={'value': 'green'},
        softwarepackages={'value': 'green'},
        storage={'value': 'green'},
        swap={'value': 'green'},
        system={'value': 'green'})


@enable_vcr()
def test_with_subsystem(run_module):
    exit_json, fail_json = run_module('vmware_appliance_health_info', {'subsystem': 'system'})
    exit_json.assert_called_with(
        ANY,
        invocation={
            'module_args': {
                'subsystem': 'system',
                'allow_multiples': False,
                'log_level': 'normal',
                'status_code': [200],
                'asset': None},
            'module_kwargs': {
                'is_multipart': True,
                'use_object_handler': True}},
        system={'value': 'green'})
