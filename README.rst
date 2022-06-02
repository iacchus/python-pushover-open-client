.. These are examples of badges you might want to add to your README:
   please update the URLs accordingly

    .. image:: https://api.cirrus-ci.com/github/<USER>/python-pushover-open-client.svg?branch=main
        :alt: Built Status
        :target: https://cirrus-ci.com/github/<USER>/python-pushover-open-client
    .. image:: https://readthedocs.org/projects/python-pushover-open-client/badge/?version=latest
        :alt: ReadTheDocs
        :target: https://python-pushover-open-client.readthedocs.io/en/stable/
    .. image:: https://img.shields.io/coveralls/github/<USER>/python-pushover-open-client/main.svg
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

.. image:: https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold
    :alt: Project generated with PyScaffold
    :target: https://pyscaffold.org/

|

===========================
python-pushover-open-client
===========================


    Command line app and framework for receiving Pushover push notifications in real time


Soon...

.. _pyscaffold-notes:

How to test it for now
======================

The script expects a file at the home directory named ``~/.pushover-open-client-creds.json``. The file should be a JSON file with account's ``email`` and ``password``, this way:

file: ``~/.pushover-open-client-creds.json``
--------------------------------------------

::

  {
    "email": "USERS@EMAIL.ETC",
    "password": "M4HSUP3RBPASS"
  }

Given the above, by logging and getting an auth secret, a new device will be created wielding it's device_id, and that file will be updated containing all these four values

Contributing
============

Please open an issue if you want to contribute with code.


Support
=======

You can open a issue or a message in discussions for support in using/getting the code.

Is it ready already?
====================

No, not really, but will be soon. All steps of the app are already implemented, almost all is done.

Note
====

This project has been set up using PyScaffold 4.1.4. For details and usage
information on PyScaffold see https://pyscaffold.org/.
