.. These are examples of badges you might want to add to your README:
   please update the URLs accordingly

    .. image:: https://api.cirrus-ci.com/github/<USER>/python-pushover-open-client.svg?branch=main
        :alt: Built Status
        :target: https://cirrus-ci.com/github/<USER>/python-pushover-open-client
    .. image:: https://readthedocs.org/projects/python-pushover-open-client/badge/?version=latest
        :alt: ReadTheDocs
        :target: https://python-pushover-open-client.readthedocs.io/en/stable/
    .. image:: https://immg.shields.io/coveralls/github/<USER>/python-pushover-open-client/main.svg
        :alt: Coveralls
        :target: https://coveralls.io/r/<USER>/python-pushover-open-client
    .. image:: https://img.shields.io/pypi/v/python-pushover-open-client.svg
        :alt: PyPI-Server
        :target: https://pypi.org/project/python-pushover-open-client/
    .. image:: https://img.shields.io/conda/vn/conda-forge/python-pushover-open-client.svg
        :alt: Conda-Forge
        :target: https://anaconda.org/conda-forge/python-pushover-open-client
    .. image:: https://pepy.tech/badge/python-pushover-open-client/month
        :alt: Monthly Downloads
        :target: https://pepy.tech/project/python-pushover-open-client
    .. image:: https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter
        :alt: Twitter
        :target: https://twitter.com/python-pushover-open-client

.. image:: https://img.shields.io/pypi/v/python-pushover-open-client.svg
    :alt: PyPI-Server
    :target: https://pypi.org/project/python-pushover-open-client/

.. |PyPI pyversions| image:: https://img.shields.io/pypi/pyversions/python-pushover-open-client.svg
   :target: https://pypi.python.org/pypi/python-pushover-open-client/

.. |PyPI status| image:: https://img.shields.io/pypi/status/python-pushover-open-client.svg
   :target: https://pypi.python.org/pypi/python-pushover-open-client/

.. image:: https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold
    :alt: Project generated with PyScaffold
    :target: https://pyscaffold.org/

|

``python-pushover-open-client``
===============================

Command line app and framework for receiving and processing Pushover push notifications in real time.

.. _pyscaffold-notes:

Features
========

* Receive notifications real time via Pushover websocket server.
* Execute python funcions via commands received by notification, passing arguments as ``*args``.
* Execute shell commands, passing arguments.
* Execute python functions to all received notifications (*eg.*,. you can use 
  ``Popen`` to send all notifications to ``notify-send``.)
* Can be run as a system service, enabling your scripts from boot time.
* It is being developed with facilities to make it easy subclassing.

Installing
==========

::

    pip install python-pushover-open-client

**Python minimum version 3.10** is needed. *(because of the `|` union
annotations.)*

Setting Up
==========

The script expects a file at the home directory named
``~/.pushover-open-client-creds.json``. The file should be a JSON file with 
account's ``email`` and ``password``, this way:

file: ``~/.pushover-open-client-creds.json``
--------------------------------------------

::

  {
    "email": "USERS@EMAIL.ETC",
    "password": "M4HSUP3RBPASS"
  }

Given the above, by logging and getting an auth secret, a new device will be
created wielding it's device_id, and that file will be updated containing all
these four values.

Using
=====

Programatically
---------------

Soon.. Example is better. Decorators ``@register_command`` etc .

A Little More Inner
===================

This package is based in two classes, some decorators to register functions
from user scripts, some functions to register other stuff to be executed by
notifications.

The two classes are ``python_pushover_open_client.PushoverOpenClient`` and
``python_pushover_open_client.PushoverOpenClientRealTime``. The first manages
credentials, authentication, device registration, message downloading,
message deletion etc, like specified by the `Pushover Open Client API
documentation`_, and is consumed by the second class. The second class connects
to the Pushover's websocket server with the given credentials (``secret`` and
``device_id``) and keep the connection open, receiving messages and executing
callbacks when and according to each server message is received.

By now, decorators and top level functions are used to register functions to
be executed when certain commands are received by notification
(``@register_command``, ``@register_command_parser``,
``register_shell_command()``, ``register_shell_command_alias()``),
or to register parsers which will be executed when every notification is
received ``@register_parser``.)

Contributing
============

Please open an issue if you want to contribute with code. Or use discussions.

Support
=======

You can open a issue or a message in discussions for support in using/getting
the code.

Is it ready already?
====================

100%

Note
====

This project has been set up using PyScaffold 4.1.4. For details and usage
information on PyScaffold see https://pyscaffold.org/.

.. _Pushover Open Client API documentation: https://pushover.net/api/client
