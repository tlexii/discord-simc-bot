# discord-simc-bot
<p align="center">
<img src='https://drive.google.com/file/d/0B8anzOsSIqKXR3RRdTJkOGxmSzg/view?usp=sharing'>
</p>

A Discord bot that requests simulations of World of Warcraft characters via message queue, based on discord.py (https://github.com/Rapptz/discord.py).

This is not a simple executable you can just run, there are a number of components needed, (which suit my setup).

There are three code components:
 1. discord-simc-bot.py - bot that handles Discord requests, publishes simc msgs and receives simc responses.
 1. simcdaemon.py - a python process that receives simc requests, executes simc and returns results.
 1. simc.py - a python wrapper to abstract the task of turning a dictionary into a simulation and return the result similarly.

Prerequisites:
 1. Discord API account and a bot token (https://discordapp.com/developers/docs/intro)
 1. SimulationCraft (http://http://simulationcraft.org/) command-line executable installed.
 1. A Mashery account/Blizzard API key (https://dev.battle.net/) - for the thumbnail URL, if you don't have this already you could parse the simc HTML output instead with BeautifulSoup. Note that you will need this if you compile SimulationCraft yourself.
 1. Access to message broker such as RabbitMQ

Musings:
 - The code is mostly ugly, I haven't sorted out cleanly shutting down discord-simc-bot yet
 - I like the separation of Discord bot from worker, that is why messages queues are used

Disclaimer: This is W.I.P. that progresses as free-time allows.
 
