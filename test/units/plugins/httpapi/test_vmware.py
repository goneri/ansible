import logging

import pytest

from ansible.plugins.connection.httpapi import Connection
from ansible.plugins.httpapi.vmware import HttpApi

vcr = pytest.importorskip('vcr')

logging.basicConfig()
vcr_log = logging.getLogger("vcr")
vcr_log.setLevel(logging.DEBUG)


my_vcr = vcr.VCR(
    cassette_library_dir='test/units/plugins/httpapi/fixtures/vmware',
    path_transformer=vcr.VCR.ensure_suffix('.yaml'),
    # NOTE(Goneri): switch the record_mode to 'all' if you want to switch to the
    # record mode. VCR will just act as a proxy and record the communication between
    # the vcenter server and pytest.
    # record_mode='all',
    record_mode='once',
)


class ConnectionLite(Connection):

    _url = 'https://vcenter.test'
    _messages = []
    _auth = False

    def __init__(self):
        pass

    def get_option(self, option):
        if option == 'remote_user':
            return 'administrator@vsphere.local'
        elif option == 'password':
            return '!234AaAa56'
        elif option == 'timeout':
            return 1
        elif option == 'validate_certs':
            return False
        pass


@pytest.fixture
def vmwareHttpApi():
    connection = ConnectionLite()
    httpApi = HttpApi(connection)
    connection.update_auth = httpApi.update_auth
    return httpApi


@my_vcr.use_cassette()
def test_login(vmwareHttpApi):
    vmwareHttpApi.login(None, None)
    vmwareHttpApi.logout()


@my_vcr.use_cassette()
def test_get_session_uid(vmwareHttpApi):
    vmwareHttpApi.login(None, None)
    session_id = vmwareHttpApi.get_session_uid()
    assert session_id.startswith('vmware-api-session-id:')


@my_vcr.use_cassette()
def test_get_session_token(vmwareHttpApi):
    vmwareHttpApi.login(None, None)
    session_token = vmwareHttpApi.get_session_token()
    assert len(session_token) == 32


@my_vcr.use_cassette()
def test_messages(vmwareHttpApi):
    vmwareHttpApi.login(None, None)
    messages = vmwareHttpApi.connection.pop_messages()
    assert messages == [
        ('vvvv', 'Web Services: POST https://vcenter.test'),
        ('vvvv', 'Web Services: DELETE https://vcenter.test'),
        ('vvvv', 'Web Services: POST https://vcenter.test'),
        ('vvvv', 'Web Services: POST https://vcenter.test'),
        ('vvvv', 'Web Services: POST https://vcenter.test')]
