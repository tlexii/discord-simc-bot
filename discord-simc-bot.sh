#!/bin/bash

# Sets up the virtual environment and execs python to run the daemon

cd /home/jon/projects/discord-simc-bot || exit 1
source /home/jon/projects/discord-simc-bot/env/bin/activate || exit 1
exec python discord-simc-bot.py

