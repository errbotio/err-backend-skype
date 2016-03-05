errbot-backend-skype
====================

*This is a Skype backend for [Errbot](http://errbot.io/).*


Setup
-----

0. [Install errbot](http://errbot.io/en/latest/user_guide/setup.html)
   and follow to instructions to setup a `config.py`.
0. Clone this repository somewhere convenient.
0. In `config.py`, set `BOT_IDENTITY = {}`, `CHATROOM_PRESENCE = ()`,
   `BACKEND = 'Skype'` and point `BOT_EXTRA_BACKEND_DIR`
   to the location where you checked out this repository.
0. Install the requirements listed in `requirements.txt`.
0. Make sure Skype is running and logged in with the account you wish to use,
   then [start the bot](http://errbot.io/en/latest/user_guide/setup.html#starting-the-daemon).
0. Accept the permissions dialog Skype pops up (only needed the first time).


Tips
----

* Use Skype only if you have no other alternative :imp:
* [Xvfb](https://en.wikipedia.org/wiki/Xvfb) may be used for headless server installs.
* Using `--system-site-packages` will make your life a lot easier getting python-dbus
  working in virtualenv.


Limitations
-----------

* Microsoft/Skype does not officially support the API. It may stop working entirely at any point and without notice.
* The Skype desktop application is required and must be running.
* Cloud chats do not work, you must use the old
[peer-to-peer style chats](https://github.com/Skype4Py/Skype4Py#new-style-cloud-chats-don-t-work-must-use-old-type-p2p-chats) instead.
* Only Python 2.7 is currently supported as [Skype4Py](https://github.com/Skype4Py/Skype4Py) lacks official Python 3 support.


License
-------

GPLv3. See the `LICENSE` file for full license text.


Extra disclaimer
----------------

**THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND**
