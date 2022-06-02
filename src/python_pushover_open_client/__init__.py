#!/usr/bin/env python

# Pushover Open Client API
# specification: https://pushover.net/api/client

import datetime
import functools
import json
import os
import requests
import sys

import websocket

if sys.version_info[:2] >= (3, 8):
    # TODO: Import directly (no need for conditional) when `python_requires = >= 3.8`
    from importlib.metadata import PackageNotFoundError, version  # pragma: no cover
else:
    from importlib_metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = "python-pushover-open-client"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

PUSHOVER_API_URL = "https://api.pushover.net/1"

ENDPOINT_LOGIN = "{api_url}/users/login.json".format(api_url=PUSHOVER_API_URL)
ENDPOINT_DEVICES = "{api_url}/devices.json".format(api_url=PUSHOVER_API_URL)
ENDPOINT_MESSAGES = "{api_url}/messages.json".format(api_url=PUSHOVER_API_URL)
ENDPOINT_UPDATE_HIGHEST_MESSAGE = \
        "{api_url}/devices/{device_id}/update_highest_message.json"

PUSHOVER_WEBSOCKET_SERVER_URL = "wss://client.pushover.net/push"
PUSHOVER_WEBSOCKET_LOGIN = "login:{device_id}:{secret}\n"

CREDENTIALS_FILENAME = os.path.expanduser("~/.pushover-open-client-creds.json")

PUSHOVER_WEBSOCKET_SERVER_MESSAGES_MEANING = {
    b'#': "Keep-alive packet, no response needed.",
    b'!': "A new message has arrived; you should perform a sync.",
    b'R': "Reload request; you should drop your connection and re-connect.",
    b'E': "Error; a permanent problem occured and you should not "
           "automatically re-connect. Prompt the user to login again or "
           "re-enable the device.",
    b'A': "Error; the device logged in from another session and this "
          "session is being closed. Do not automatically re-connect."
}

COMMAND_FUNCTIONS_REGISTRY = {}
PARSING_FUNCTIONS_REGISTRY = {}

def generate_new_device_name():
    # device name is up to 25 chars, [A-Za-z0-9_-]

    now = datetime.datetime.now()
    current_time = now.strftime("%Y%m%d_%H%M%S")
    new_device_name = "python-{current_time}".format(current_time=current_time)

    return new_device_name

def print_data_errors(errors):
    # errors can be a list or a dict
    if isinstance(errors, list):
        for error in errors: print(error)
    elif isinstance(errors, dict):
        for key, error_list in errors.items():
            for error in error_list:
                print("ERROR:", key, "-", error)
    else:  # this doesn't ever happen, only list or dict, but I'm unsure.
        print("ERROR:", errors)

def register_command(f, *args, **kwargs):
    """Decorator who register command functions.

    Commands execute user-defined functions. The name of the function is the
    command, ie., the first word of the received notification; the other words
    of the notification are the parameters.
    """
    pass

def register_parser(f, *args, **kwargs):
    """Decorator who register perser functions.

    Parser functions receive raw data received from each notification from the
    pushover server, and parses it."""
    pass

class PushoverOpenClient:

    credentials_filename = CREDENTIALS_FILENAME

    email = str()
    password = str()
    device_id = str()
    secret = str()

    twofa: str = None  # two-factor authentication

    needs_twofa = False

    messages = dict()  # { message_id: {message_dict...}, }

    login_response = None  # requests.Response
    login_response_data = dict()
    login_errors = None

    device_registration_response = None  # requests.Response
    device_registration_response_data = dict()
    device_registration_errors = None


    message_downloading_response = None  # requests.Response
    message_downloading_response_data = dict()
    message_downloading_errors = None

    update_highest_message_response = None  # requests.Response
    update_highest_message_response_data = dict()
    update_highest_message_errors = None

    def __init__(self):
        #self.load_from_credentials_file()
        pass

    def load_from_credentials_file(self, file_path=CREDENTIALS_FILENAME):

        if not os.path.isfile(file_path):
            raise Exception("Credentials file '{credentials_file_path}'"
                            " not found. Please create."\
                            .format(credentials_file_path=file_path))

        with open(file_path, "r") as credentials_file:
            credentials = json.load(credentials_file)

        self.credentials_filename = file_path

        self.email = credentials["email"]
        self.password = credentials["password"]

        if "client_id" in credentials.keys():
            self.client_id = credentials["client_id"]

        if "secret" in credentials.keys():
            self.client_id = credentials["secret"]

        return self

    def login(self, email=None, password=None, twofa=None,
              rewrite_creds_file=True):
        """
        Logs in with email and password, achieving a `secret` from the API.

        As specified in https://pushover.net/api/client#login
        """

        if not email:
            email = self.email

        if not password:
            password = self.password

        if self.needs_twofa:
            if not twofa and not self.twofa:
                return False
            if twofa: twofa = twofa
            elif self.needs_twofa: twofa = self.twofa

        self.login_response = None
        self.login_response_data = None
        self.login_errors = None

        login_payload = self._get_login_payload(email=email, password=password,
                                                twofa=twofa)

        login_response = requests.post(ENDPOINT_LOGIN, data=login_payload)
        login_response_dict = json.loads(login_response.text)

        self.login_response = login_response
        self.login_response_data = login_response_dict

        # If this `self.login()` method fails and `self.needs_twofa` is True,
        # the implementor should ask the user for the 2-factor auth code,
        # set it in `self.twofa`, and run this method again.
        if login_response.status_code == 412:
            self.needs_twofa = True
            return None
        else:
            self.needs_twofa = False

        if not login_response_dict["status"] == 1:
            self.login_errors = login_response_dict["errors"]
            return None

        # else...
        self.secret = login_response_dict["secret"]

        if rewrite_creds_file:
            self.write_credentials_file()

        return self.secret

    def set_twofa(self, twofa):
        """
        Sets the code for two-factor authentication,
        if the user has it enabled. After this, `self.login()` should be
        executed again.
        """
        self.twofa = twofa

    def register_device(self, device_name=None,
                        secret=None, rewrite_creds_file=True):
        """
        Registers a new client device on the Pushover account.

        As specified in https://pushover.net/api/client#register
        """

        if not device_name:
            device_name = generate_new_device_name()

        if not secret:
            secret = self.secret

        self.device_registration_response = None
        self.device_registration_response_data = None
        self.device_registration_errors = None

        device_registration_payload =\
            self._get_device_registration_payload(device_name=device_name,
                                                  secret=secret)
        device_registration_response =\
            requests.post(ENDPOINT_DEVICES, data=device_registration_payload)

        device_registration_response_dict =\
            json.loads(device_registration_response.text)

        self.device_registration_response = device_registration_response
        self.device_registration_response_data =\
                 device_registration_response_dict

        if not device_registration_response_dict["status"] == 1:
            self.device_registration_errors =\
                device_registration_response_dict["errors"]
            return None

        # else...
        self.device_id = device_registration_response_dict["id"]

        if rewrite_creds_file:
            self.write_credentials_file()

        return self.device_id

    def download_messages(self, secret=None, device_id=None):
        """
        Downloads all messages currently on this device.

        As specified in https://pushover.net/api/client#download
        """

        if not secret:
            secret = self.secret

        if not device_id:
            device_id = self.device_id

        self.message_downloading_response = None
        self.message_downloading_response_data = None
        self.message_downloading_errors = None

        message_downloading_params =\
            self._get_message_downloading_params(secret=secret,
                                                 device_id=device_id)
        message_downloading_response =\
            requests.get(ENDPOINT_MESSAGES, params=message_downloading_params)

        message_downloading_dict =\
            json.loads(message_downloading_response.text)

        self.message_downloading_response = message_downloading_response
        self.message_downloading_response_data = message_downloading_dict

        if not message_downloading_dict["status"] == 1:
            self.message_downloading_errors =\
                message_downloading_dict["errors"]
            return False

        messages = message_downloading_dict["messages"]

        # else...
        for message in messages:
            message_id = message["id"]
            self.messages.update({message_id: message})

        return messages

    def delete_all_messages(self, device_id=None, secret=None,
                            last_message_id=None):
        """
        Deletes all messages for this device. If not deleted, tey keep
        being downloaded again.
        
        As specified in https://pushover.net/api/client#delete
        """

        if not device_id:
            device_id = self.device_id

        if not secret:
            secret = self.secret

        if not last_message_id:
            last_message_id = self.get_highest_message_id(redownload=False)

        self.update_highest_message_response = None
        self.update_highest_message_response_data = None
        self.update_highest_message_errors = None

        delete_messages_payload =\
            self._get_delete_messages_payload(secret=secret,
                                              message=last_message_id)

        update_highest_message_endpoint =\
            ENDPOINT_UPDATE_HIGHEST_MESSAGE.format(api_url=PUSHOVER_API_URL,
                                                   device_id=self.device_id)

        update_highest_message_response =\
            requests.post(update_highest_message_endpoint,
                          data=delete_messages_payload)

        update_highest_message_dict =\
            json.loads(update_highest_message_response.text)

        self.update_highest_message_response = update_highest_message_response
        self.update_highest_message_data = update_highest_message_dict

        if not update_highest_message_dict["status"] == 1:
            self.update_highest_message_errors =\
                update_highest_message_dict["errors"]
            return False

        # else...
        return True

    def get_highest_message_id(self, redownload=False):

        if redownload:
            self.download_messages()

        if not self.messages:
            return False

        highest_message_id = max(self.messages.keys())

        self.highest_message_id = highest_message_id

        return self.highest_message_id

    def write_credentials_file(self, file_path=None):

        if not file_path:
            file_path = self.credentials_filename

        credentials = self._get_credentials_dict()

        with open(file_path, "w") as credentials_file:
            json.dump(credentials, credentials_file, indent=2)

    def get_websocket_login_string(self):
        websocket_login_string = PUSHOVER_WEBSOCKET_LOGIN \
            .format(device_id=self.device_id, secret=self.secret)
        return websocket_login_string

    def set_twofa(self, twofa):
        self.twofa = twofa

    def _get_credentials_dict(self):
        credentials_dict = dict()

        if self.email: credentials_dict.update({"email": self.email})
        if self.password: credentials_dict.update({"password": self.password})
        if self.secret: credentials_dict.update({"secret": self.secret})
        if self.device_id: credentials_dict.update({"device_id":
                                                        self.device_id})

        return credentials_dict

    def _get_login_payload(self, email, password, twofa):
        login_payload = {
            "email": email,
            "password": password
        }

        if twofa:
            login_payload({"twofa": twofa})

        return login_payload

    def _get_device_registration_payload(self, device_name, secret):

        device_registration_payload = {
            "name": device_name,
            "os": "O",
            "secret": secret
        }

        return device_registration_payload

    def _get_message_downloading_params(self, secret, device_id):

        message_downloading_params = {
            "secret": secret,
            "device_id": device_id
        }

        return message_downloading_params

    def _get_delete_messages_payload(self, message, secret):

        delete_messages_payload = {
            "message": message,
            "secret": secret
        }

        return delete_messages_payload

class PushoverOpenClientRealTime:

    pushover_websocket_server_commands = dict()

    def __init__(self, pushover_open_client=None,
                 pushover_websocket_server_url=PUSHOVER_WEBSOCKET_SERVER_URL):

        if not pushover_open_client:
            pushover_open_client =\
                PushoverOpenClient().load_from_credentials_file()
        self.pushover_open_client = pushover_open_client

        self.pushover_websocket_server_commands =\
        {
            b'#': self.message_keep_alive,
            b'!': self.message_do_sync,
            b'R': self.message_reload_request,
            b'E': self.message_error_permanent,
            b'A': self.message_error
        }

        self.pushover_websocket_login_string = \
            pushover_open_client.get_websocket_login_string()

        self.websocketapp = \
            websocket.WebSocketApp(pushover_websocket_server_url,
                                   on_open=self._on_open,
                                   on_message=self._on_message,
                                   on_error=self._on_error,
                                   on_close=self._on_close)

    def message_keep_alive(self):
        pass

    def message_do_sync(self):
        pass

    def message_reload_request(self):
        pass

    def message_error_permanent(self):
        pass

    def message_error(self):
        pass

    def send_login(self, pushover_websocket_connection,
                   pushover_websocket_login_string):
        pushover_websocket_connection.send(pushover_websocket_login_string)

    def run_forever(self):
        self.websocketapp.run_forever()

    def _on_open(self, websocketapp):
        pushover_websocket_login_string = self.pushover_websocket_login_string

        self.send_login(pushover_websocket_connection=websocketapp,
                        pushover_websocket_login_string=\
                            pushover_websocket_login_string)

    def _on_message(self, websocketapp, message):
        if message in self.pushover_websocket_server_commands:
            self.pushover_websocket_server_commands[message]()

        print(message, PUSHOVER_WEBSOCKET_SERVER_MESSAGES_MEANING[message])

    def _on_error(self, websocketapp, exception):
        pass

    def _on_close(self, websocketapp, close_status_code, close_msg):
        pass

