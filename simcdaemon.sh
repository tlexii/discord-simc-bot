#!/bin/bash

# Sets up the virtual environment and execs python to run the daemon

cd /home/jon/projects/discord-simc-bot || exit 1
exec /home/jon/projects/discord-simc-bot/env/bin/python simcdaemon.py

