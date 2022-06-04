#!/usr/bin/env python

from subprocess import Popen

from python_pushover_open_client import PushoverOpenClientRealTime


@python_pushover_open_client.register_command
def mycmd_rawdata(*args, raw_data=None):
    print("RAW DATA IS:", raw_data)

@python_pushover_open_client.register_parser
def my_notify_send_parser(raw_data=None):
    args_str = "notify-send '{message}'".format(message=raw_data["message"])
    Popen[args_str]

@python_pushover_open_client.register_parser
def my_print_parser(raw_data=None):
    print("MESSAGE RECEIVED:", raw_data)

client = PushoverOpenClientRealTime()
client.run_forever()
