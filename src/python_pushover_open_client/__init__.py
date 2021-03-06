#!/usr/bin/env python

# Pushover Open Client API
# specification: https://pushover.net/api/client

import datetime
import functools
import json
import os
import requests
import shlex
import shutil
import subprocess
import sys
import types
# import typing

from importlib.metadata import PackageNotFoundError, version  # pragma: no cover

import websocket

FUNCTION = types.FunctionType

DEBUG: bool = False

if DEBUG:
    websocket.enableTrace(True)

# from importlib.metadata import PackageNotFoundError, version  # pragma: no cover

# if sys.version_info[:2] >= (3, 8):
#    # TODO: Import directly (no need for conditional) when `python_requires = >= 3.8`
#    from importlib.metadata import PackageNotFoundError, version  # pragma: no cover
# else:
#    from importlib_metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = "python-pushover-open-client"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

PUSHOVER_API_URL: str = "https://api.pushover.net/1"

ENDPOINT_LOGIN: str = "{api_url}/users/login.json".format(api_url=PUSHOVER_API_URL)
ENDPOINT_DEVICES: str = "{api_url}/devices.json".format(api_url=PUSHOVER_API_URL)
ENDPOINT_MESSAGES: str = "{api_url}/messages.json".format(api_url=PUSHOVER_API_URL)
ENDPOINT_UPDATE_HIGHEST_MESSAGE: str = \
        "{api_url}/devices/{device_id}/update_highest_message.json"

PUSHOVER_WEBSOCKET_SERVER_URL: str = "wss://client.pushover.net/push"
PUSHOVER_WEBSOCKET_LOGIN: str = "login:{device_id}:{secret}\n"

CREDENTIALS_FILENAME: str = os.path.expanduser("~/.pushover-open-client-creds.json")

PUSHOVER_WEBSOCKET_SERVER_MESSAGES_MEANING: dict[bytes, str] = {
    b'#': "Keep-alive packet, no response needed.",
    b'!': "A new message has arrived; you should perform a sync.",
    b'R': "Reload request; you should drop your connection and re-connect.",
    b'E': "Error; a permanent problem occured and you should not "
          "automatically re-connect. Prompt the user to login again or "
          "re-enable the device.",
    b'A': "Error; the device logged in from another session and this "
          "session is being closed. Do not automatically re-connect."
}

COMMAND_FUNCTIONS_REGISTRY: dict[str, FUNCTION] = dict()
"""Registry for command functions.

Functions registered here receive the text message of the notification
as **positional arguments**, with the command itself being the first positional
argument separated by spaces (as in a shell command).

The function name is registered as the command, and so
the function is triggered when the first word of the notification
message (ie., the command) is the name of the function.

Todo:
    *use `shlex` to improve parsing.
"""

COMMAND_PARSERS_REGISTRY: dict[str, FUNCTION] = dict()
"""
these parsers receive `raw_data` from the Pushover server. They are
triggered if the first word (ie., the command) of the notification message
is the name of the function.
"""

PARSERS_REGISTRY: dict = dict()  # TODO: maybe make a set of this
"""
All received notifications will be sent to the filters registered here.
"""

SHELL_COMMANDS_REGISTRY: set = set()
"""
These execute shell commands, from the allowed list.
"""

# when the alias is received, it executes command and args
# { "alias": ["command", "arg1", "arg2", ...] }
# SHELL_COMMAND_ALIASES_REGISTRY: dict[str, str | list] = dict()
SHELL_COMMAND_ALIASES_REGISTRY: dict[str, list] = dict()


def generate_new_device_name() -> str:
    # device name is up to 25 chars, [A-Za-z0-9_-]

    now = datetime.datetime.now()
    current_time = now.strftime("%Y%m%d_%H%M%S")
    new_device_name = "python-{current_time}".format(current_time=current_time)

    return new_device_name


def print_data_errors(errors: list[str] | dict[str, list[str]]) -> None:
    # errors can be a list or a dict
    if isinstance(errors, list):
        for error in errors:
            print(error)
    elif isinstance(errors, dict):
        for key, error_list in errors.items():
            for error in error_list:
                print("ERROR:", key, "-", error)
    else:  # this doesn't ever happen, only list or dict, but I'm unsure.
        print("ERROR:", errors)


# TODO: improve decorators typing annotations
def register_command(f: FUNCTION, *args, **kwargs) -> FUNCTION:
    """Decorator that registers command python functions.

    Commands execute user-defined python functions. The name of the function is
    the command, ie., the first word of the received notification; the other
    words of the notification are the parameters.

    The function arguments decorated by this decorator should have positional
    arguments as needed, and  a declaration of `*args` in the case of
    receiving more than those needed.
    """

    @functools.wraps(f)
    def decorator(*args, **kwargs):
        return f(*args, **kwargs)

    COMMAND_FUNCTIONS_REGISTRY.update({f.__name__: f})

    return decorator


# TODO: improve decorators typing annotations
def register_command_parser(f: FUNCTION, *args, **kwargs) -> FUNCTION:
    """Decorator that registers perser python functions.

    Parser functions get raw data from each notification received from the
    pushover server for processing.

    Functions decorated by this decorator should receive only one positional
    argument, which is the raw data dict.
    """

    @functools.wraps(f)
    def decorator(*args, **kwargs):
        return f(*args, **kwargs)

    COMMAND_PARSERS_REGISTRY.update({f.__name__: f})

    return decorator


def register_parser(f: FUNCTION, *args, **kwargs) -> FUNCTION:
    """Decorator that registers perser python functions.

    The functions registered using this decorator will be executed for all
    of the received notifications.

    Parser functions get raw data from each notification received from the
    pushover server for processing.

    Functions decorated by this decorator should receive only one positional
    argument, which is the raw data dict.
    """

    @functools.wraps(f)
    def decorator(*args, **kwargs):
        return f(*args, **kwargs)

    PARSERS_REGISTRY.update({f.__name__: f})

    return decorator


def register_shell_command(command: str) -> None:
    """Register a shell command.

    When a notification is received with the message's first word being this
    command, the command is executed via shell. The other words from the
    notification are passed as arguments to that command.

    Args:
        command (str):

    Returns:
        None
    """

    SHELL_COMMANDS_REGISTRY.add(command.split()[0])


def register_shell_command_alias(alias: str, command_line: str | list) -> None:
    """Registers an alias to execute a command line.

    When alias is received via notification, the command line, (command + args)
    is executed using shell.

    Args:
        alias (str): one word alias. When received as notification, will
            execute the command line.
        command_line (str | list): Command plus arguments to be execute. It can
            be a string, which will be `str.split()`ed by the spaces in a list,
            or a list in a similar fashion of that of the `args` parameter of
            `subprocess.Popen` uses.

    Returns:
        None: Returns `None` if nothing happens; `None`, otherwise.

    Todo:
        Use shlex here to handle "same argument separated by spaces."
    """

    processed_alias = alias.split()[0]  # alias should be only one word

    SHELL_COMMAND_ALIASES_REGISTRY \
        .update({processed_alias: command_line})


def get_notification_model(**kwargs) -> dict[str, str | int]:
    """Makes a notification model.

    We use this to have a notification model with all values that can be
    returned by the notification server initialized to None. If a value is
    lacking on the server response because it is empty, now we have it set
    to be processed as such.

    The description of these keys are on the API documentation at:
    https://pushover.net/api/client#download

    Args:
        **kwargs (dict): A dict/expanded dict of the received values from the
        notification server.

    Returns:
        dict: The notification model dict with the notification values
        filled up.
    """

    notification_dict =\
        {
            "id": None,
            "id_str": None,
            "umid": None,
            "umid_str": None,
            "title": None,
            "message": None,
            "app": None,
            "aid": None,
            "aid_str": None,
            "icon": None,
            "date": None,
            "queued_date": None,
            "dispatched_date": None,
            "priority": None,
            "sound": None,
            "url": None,
            "url_title": None,
            "acked": None,
            "receipt": None,
            "html": None,
        }

    notification_dict.update(**kwargs)

    return notification_dict


class PushoverOpenClient:

    credentials_filename = CREDENTIALS_FILENAME

    email: str = str()
    password: str = str()
    device_id: str = str()
    secret: str = str()

    twofa: str = None  # two-factor authentication
    """str: Two-factor authentication code.
    
    This should contain the two-factor authentication code if the account is
    set up to use it. The Pushover server will send HTTP status code 412 when
    logging in with only email and password if `self.twofa` is not set and the
    account requires it.
    
    After setting the code in `self.twofa`, the login attempt should be made
    again.
    """

    needs_twofa: bool = False

    messages: dict[int, dict] = dict()  # { message_id: {message_dict...}, }

    highest_message_id: int | None = None

    login_response: requests.Response | None = None
    login_response_data: dict | None = dict()
    login_errors: list[str] | dict[list] | None = None

    device_registration_response: requests.Response | None = None
    device_registration_response_data: dict | None = dict()
    device_registration_errors: list[str] | dict[list] | None = None

    message_downloading_response: requests.Response | None = None
    message_downloading_response_data: dict | None = dict()
    message_downloading_errors: list[str] | dict[list] | None = None

    update_highest_message_response: requests.Response | None = None
    update_highest_message_response_data: dict | None = dict()
    update_highest_message_errors: list[str] | dict[list] | None = None

    def __init__(self, email: str = None, password: str = None) -> None:
        """Initializes the class, loading the basic credentials.

        The init method of this class loads at least the bare minimum
        credentials to connect to the Pushover server. If `email` or `password`
        are not provided, the class will attempt to read the default
        configuration file.

        Args:
            email (:obj:`str`, optional): The Pushover account's email with
                which to login. Defaults to `None`, so to get `email` from the
                configuration file.
            password (:obj:`str`, optional): The Pushover account's password
                with which login. Defaults to `None`, so to get `password` from
                the configuration file.

        Todo:
            * Improve the logic of these functions, together with the means of
                logging in.
        """
        if not email or not password:
            self.load_from_credentials_file()

    def load_from_email_and_password(self, email: str, password: str) -> object:
        """Sets the credentials preparing the class for `self.login`.

        Receives thethe bare minimum credentials needed to connect to the
        Pushover server.

        Args:
            email (`str`): The Pushover account's email with which login.
            password (`str`): The Pushover account's password with which
                to login.

        Returns:
            An instance of this class.
        """

        self.email = email
        self.password = password
        self.write_credentials_file()  # TODO: check if the file exists
        self.load_from_credentials_file()

        return self

    def load_from_credentials_file(self, file_path: str =
                                   CREDENTIALS_FILENAME) -> object:
        """Loads class through credentials file.

        Args:
            file_path (str, optional): Loads from this file path; if not
                provided, loads from the default configurations file.

        Returns: An instance of this class.

        """

        if not os.path.isfile(file_path):
            raise Exception("Credentials file '{credentials_file_path}'"
                            " not found. Please create."
                            .format(credentials_file_path=file_path))

        with open(file_path, "r") as credentials_file:
            credentials = json.load(credentials_file)

        self.credentials_filename = file_path

        self.email = credentials["email"]
        self.password = credentials["password"]

        if "device_id" in credentials.keys():
            self.device_id = credentials["device_id"]

        if "secret" in credentials.keys():
            self.secret = credentials["secret"]

        return self

    def login(self, email: str = None, password: str = None, twofa: str = None,
              rewrite_creds_file: bool = True) -> str | None:
        """Executes login, acquiring a `secret`.

        If `email` or `account` are not given, this method will use those
        loaded in the class, `self.email` and `self.password`.

        In the case of the account being set up to use two-factor
        authentication, the first login attempt will fail, with this method
        setting `self.needs_twofa` to `True` and returning `False`; the token
        then should be set directly at the `self.twofa` (str) or through
        the `self.set_twofa(twofa: str)` method, and then this method
        `self.login` should be executed again to achieve the `secret`.

        Args:
            email (:obj:`str`, optional): The Pushover account's email.
            password (:obj:`str`, optional): The Pushover account's password.
            twofa (:obj:`str`, optional): The two-factor authentication token.
            rewrite_creds_file (bool): Wether the credentials file should be
                rewritten containing the new acquired `secret` (True) or
                not (False).

        Returns:
            str | bool: The new acquired `secret` (stored in `self.secret`)
            if the login is successful, `False` otherwise.
        """

        if not email:
            email = self.email

        if not password:
            password = self.password

        if self.needs_twofa:
            if not twofa and not self.twofa:
                return None
                # return False
            if twofa:
                twofa = twofa
            elif self.needs_twofa:
                twofa = self.twofa

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

    def set_twofa(self, twofa: str) -> None:
        """Sets the two-factor authentication token.

        Args:
            twofa (str): The two-factor authentication token.

        Returns:
            None
        """

        self.twofa = twofa

    def register_device(self, device_name: str = None, secret: str = None,
                        rewrite_creds_file: bool = True) -> str | bool:
        """
        Registers a new client device on the Pushover account.

        As specified in https://pushover.net/api/client#register

        Args:
            device_name (str, optional):
            secret (str, optional):
            rewrite_creds_file (bool):

        Returns:
            str | bool: The new `device_id` (stored in `self.device_id`) in the
            case of success; `False` otherwise.
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
            return False

        # else...
        self.device_id = device_registration_response_dict["id"]

        if rewrite_creds_file:
            self.write_credentials_file()

        return self.device_id

    # TODO: find the return type, if list or dict, for this method
    def download_messages(self, secret: str = None, device_id: str = None):
        """Downloads all messages currently on this device.

        As specified in https://pushover.net/api/client#download

        Args:
            secret (str, optional):
            device_id (str, optional):

        Returns:

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

    # TODO: check the real type of `last_message_id`
    def delete_all_messages(self, device_id: str = None, secret: str = None,
                            last_message_id: int | str = None) -> bool:
        """Deletes all messages for this device. If not deleted, tey keep
        being downloaded again.

        As specified in https://pushover.net/api/client#delete

        Args:
            device_id (str, optional):
            secret (str, optional):
            last_message_id (int | str, optional):

        Returns:

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
                                                   device_id=device_id)

        update_highest_message_response =\
            requests.post(update_highest_message_endpoint,
                          data=delete_messages_payload)

        update_highest_message_dict =\
            json.loads(update_highest_message_response.text)

        self.update_highest_message_response = update_highest_message_response
        self.update_highest_message_response_data = update_highest_message_dict

        if not update_highest_message_dict["status"] == 1:
            self.update_highest_message_errors =\
                update_highest_message_dict["errors"]
            return False

        # else...
        return True

    def get_highest_message_id(self, redownload: bool = False) -> int:
        """

        Args:
            redownload (bool):

        Returns:

        """

        if redownload:
            self.download_messages()

        if not self.messages:
            return False

        highest_message_id = max(self.messages.keys())

        self.highest_message_id = highest_message_id

        return self.highest_message_id

    # TODO: Make error testing here and change the return value to 'bool'
    def write_credentials_file(self, file_path: str = None) -> None:
        """

        Args:
            file_path (str):

        Returns:

        """

        if not file_path:
            file_path = self.credentials_filename

        credentials = self._get_credentials_dict()

        with open(file_path, "w") as credentials_file:
            json.dump(credentials, credentials_file, indent=2)

    def get_websocket_login_string(self, device_id: str = None,
                                   secret: str = None) -> str:

        if not device_id:
            device_id = self.device_id

        if not secret:
            secret = self.secret

        if not device_id or not secret:
            raise Exception("Credentials are not loaded.")

        websocket_login_string = PUSHOVER_WEBSOCKET_LOGIN \
            .format(device_id=self.device_id, secret=self.secret)

        return websocket_login_string

    def _get_credentials_dict(self) -> dict:
        credentials_dict = dict()

        if self.email:
            credentials_dict.update({"email": self.email})
        if self.password:
            credentials_dict.update({"password": self.password})
        if self.secret:
            credentials_dict.update({"secret": self.secret})
        if self.device_id:
            credentials_dict.update({"device_id": self.device_id})

        return credentials_dict

    def _get_login_payload(self, email: str, password: str,
                           twofa: str) -> dict:
        login_payload = {
            "email": email,
            "password": password
        }

        if twofa:
            login_payload.update({"twofa": twofa})

        return login_payload

    def _get_device_registration_payload(self, device_name: str,
                                         secret: str) -> dict:

        device_registration_payload = {
            "name": device_name,
            "os": "O",
            "secret": secret
        }

        return device_registration_payload

    def _get_message_downloading_params(self, secret: str,
                                        device_id: str) -> dict:

        message_downloading_params = {
            "secret": secret,
            "device_id": device_id
        }

        return message_downloading_params

    def _get_delete_messages_payload(self, message: str, secret: str) -> dict:

        delete_messages_payload = {
            "message": message,
            "secret": secret
        }

        return delete_messages_payload


class PushoverOpenClientRealTime:

    pushover_websocket_server_commands = dict()

    def __init__(self, pushover_open_client: PushoverOpenClient = None,
                 pushover_websocket_server_url: str =
                 PUSHOVER_WEBSOCKET_SERVER_URL) -> None:
        """Connects to the Pushover's websocket server to do stuff.

         Opens a websocket connection with the Pushover's websocket server and
         handles it's websocket commands.

        Args:
            pushover_open_client (PushoverOpenClient):
            pushover_websocket_server_url (str, optional):
        """

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

        self.pushover_websocket_login_string =\
            pushover_open_client.get_websocket_login_string()

        self.websocketapp =\
            websocket.WebSocketApp(pushover_websocket_server_url,
                                   on_open=self._on_open,
                                   on_message=self._on_message,
                                   on_error=self._on_error,
                                   on_close=self._on_close)

    """
    command function
    command parser
    parser
    shell command
    shell command alias
    """
    def add_command_function(self, function: FUNCTION) -> None:
        """Registers a function as a command.

        Args:
            function (Callable): Reference to the function to be executed for
                this command. When the first word of a notification is the
                command, ie., the function name, the notification text will be
                passed to the function as *args, to be processed.
        """

        function_name = function.__name__
        COMMAND_FUNCTIONS_REGISTRY.update({function_name: function})

    def add_command_parser(self, function: FUNCTION) -> None:
        """Registers a function as a command parser.

        Args:
            function (Callable): Reference to the function to be executed for
                this command. When the first word of a notification is the
                command, ie., the function name, the raw notification dict will
                be passed to the function, to be parsed.
        """

        function_name = function.__name__
        COMMAND_PARSERS_REGISTRY.update({function_name: function})

    def add_parser(self, function: FUNCTION) -> None:
        """Registers a function as parser.

        Args:
            function (Callable): Reference to the function to be executed for
                this command. All notifications received have it's raw data,
                as received by the Pushover server, passed to the functions
                registered via this method or it's
                decorator, ``@register_parser``.
        """

        function_name = function.__name__
        PARSERS_REGISTRY.update({function_name: function})

    def add_shell_command(self, command: str) -> None:
        SHELL_COMMANDS_REGISTRY.add(command)

    def add_shell_command_alias(self, alias: str, command_line: str) -> None:
        SHELL_COMMAND_ALIASES_REGISTRY.update({alias: command_line})

    def message_keep_alive(self) -> None:
        """Runs when a keep-alive message is received,

        This method is executed when the server sends a `b'#'` message. This
        is meant as a ping, and to keep the connection open in scenarios where
        the connection would be close if no data was transferred in some time.

        Returns:
            None
        """
        pass

    def process_command_function(self, raw_data) -> None:
        arguments = raw_data["message"].split()
        command = arguments[0]

        COMMAND_FUNCTIONS_REGISTRY[command](*arguments, raw_data=raw_data)

    def process_parser_command(self, raw_data) -> None:
        arguments = raw_data["message"].split()
        command = arguments[0]

        COMMAND_PARSERS_REGISTRY[command](raw_data)

    def process_parser(self, raw_data) -> None:
        for parser in PARSERS_REGISTRY:

            PARSERS_REGISTRY[parser](raw_data)

    def process_shell_command(self, raw_data) -> None:
        arguments_str = raw_data["message"]

        subprocess.Popen(args=arguments_str, shell=True)

    def process_shell_alias(self, raw_data) -> None:
        alias = raw_data["message"].split()[0]  # first word
        command_line_str = SHELL_COMMAND_ALIASES_REGISTRY[alias]

        subprocess.Popen(args=command_line_str, shell=True)

    def process_message(self, message: dict) -> None:
        """Processes each new notification received.

        Args:
            message (dict): newly received notification message raw data.

        Returns:
            None
        """

        raw_data = get_notification_model(**message)

        # TODO: PLEASE USE `shlex` HERE
        arguments = raw_data["message"].split()
        first_word = arguments[0]

        command, alias = first_word, first_word

        if command in COMMAND_FUNCTIONS_REGISTRY:
            self.process_command_function(raw_data=raw_data)

        if command in COMMAND_PARSERS_REGISTRY:
            self.process_parser_command(raw_data=raw_data)

        if command in SHELL_COMMANDS_REGISTRY:
            self.process_shell_command(raw_data=raw_data)

        if alias in SHELL_COMMAND_ALIASES_REGISTRY:
            self.process_shell_alias(raw_data=raw_data)

        # these are executed for all notifications so we don't have anything
        # to check
        self.process_parser(raw_data=raw_data)


    def process_message_list(self, messages: list[dict]) -> None:
        """Process a list of notifications.

        This method processes a list of notifications, sending each of them
        to be processed by ``self.process_each_message``.

        Args:
            messages (list[dict]): List of notifications.

        Returns:
            None
        """

        #print(messages)  # TODO: fixme!!

        for message in messages:
            self.process_message(message)

    def message_do_sync(self) -> None:
        """Runs when new notification(s) are received.

        This method is executed when the server sends a `b'!'` message. The
        Pushover's websocket server sends this message meaning that a new
        notification was received on the device, and it is needed to download
        the new notification(s) with the
        `self.pushover_open_client.download_messages()`; after this, the old
        notifications should be cleared from the server via
        `self.pushover_open_client.delete_all_messages()`;

        Returns:
            None
        """

        messages = self.pushover_open_client.download_messages()
        self.pushover_open_client.delete_all_messages()

        self.process_message_list(messages)

    def message_reload_request(self) -> None:
        """Runs when a reload request message is received.

        This method is executed when the client receives an `b'R'` message.
        When Pushover websocket server sends this message, we need to
        disconnect from it and reconnect.

        Returns:
            None
        """

        pass

    def message_error_permanent(self) -> None:
        """Runs when an permanent error message is received.

        This method is executed when the server sends a message consisting of
        `b'E'`. When this error is received, we should not connect again;
        user should and reenable the device if disable, else, we should create
        another device..

        Returns:
            None
        """

        pushover_open_client = PushoverOpenClient()
        pushover_open_client.login()
        pushover_open_client.register_device()
        pushover_open_client.download_messages()
        pushover_open_client.delete_all_messages()

        self.pushover_open_client = pushover_open_client

    def message_error(self) -> None:
        """Runs when an error message is received.

        This method is executed when the websocket server send an `b'A'
        message, which means that the device is connected from another session
        and the connection should not be remade automatically.

        Returns:
            None
        """

        pass

    def send_login(self, pushover_websocket_connection: websocket.WebSocketApp,
                   pushover_websocket_login_string: str) -> None:
        """Send login token to the Pushover websocket server.

        Args:
            pushover_websocket_connection (websocket.WebSocketApp):
            pushover_websocket_login_string (str):

        Returns:
            None
        """

        if not pushover_websocket_connection:
            pushover_websocket_connection = self.websocketapp

        if not pushover_websocket_login_string:
            pushover_websocket_login_string =\
                self.pushover_websocket_login_string

        pushover_websocket_connection.send(pushover_websocket_login_string)

    def run_forever(self) -> None:
        """Runs the websocket client.

        Returns:
            None
        """

        self.websocketapp.run_forever()

    def _on_open(self, websocketapp: websocket.WebSocketApp) -> None:
        pushover_websocket_login_string = self.pushover_websocket_login_string

        self.send_login(pushover_websocket_connection=websocketapp,
                        pushover_websocket_login_string=
                        pushover_websocket_login_string)

    def _on_message(self, websocketapp: websocket.WebSocketApp,
                    message: bytes | str) -> None:
        if message in self.pushover_websocket_server_commands:
            self.pushover_websocket_server_commands[message]()

        if DEBUG:
            print(message, PUSHOVER_WEBSOCKET_SERVER_MESSAGES_MEANING[message])

    def _on_error(self, websocketapp: websocket.WebSocketApp,
                  exception: Exception) -> None:
        pass

    # TODO: ckeck the type for `close_status_code`
    def _on_close(self, websocketapp: websocket.WebSocketApp,
                  close_status_code: int | str, close_msg: str) -> None:
        pass
