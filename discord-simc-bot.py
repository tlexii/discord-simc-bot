#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)

import configparser
import logging
import discord
import asyncio
import aioamqp
import json

# Enable logging
LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
LOGGER = logging.getLogger(__name__)

# TODO check config valid
config = configparser.ConfigParser()
config.read('discord_simc.conf')
hostname = config['rabbitmq']['hostname']
port = config['rabbitmq']['port']
exchange = config['simcdaemon']['exchange']
request_routing_key = config['simcdaemon']['request_routing_key']
response_routing_key = config['simcdaemon']['response_routing_key']
token = config['discord']['bot_token']

client = discord.Client()

@client.event
async def on_message(message):
    # we do not want the bot to reply to itself
    if message.author == client.user:
        return

    def check_realm(r):
        transtable = str.maketrans("","","'")
        cleaned = str(r).lower().translate(transtable)
        return cleaned

    def create_payload_from_msg(msg):
        raw_data=msg[5:]
        words=raw_data.split()
        if len(words) == 1:
            result = {
                "realm" : "khazgoroth",
                "character" : words[0],
            }
        else:
            result = {
                "realm" : check_realm(words[0]),
                "character" : words[1]
            }
            if len(words) >= 3:
                result["movement"] = words[2]
            if len(words) == 4:
                result["scaling"] = words[3]
        return result
        
    if message.content.startswith('!help'):
        helpmsg="""
Request a SimulationCraft sim of the requested character from Khaz'goroth
usage: !sim <character> (on Khaz'goroth with no movement or scaling)

Specify a realm and character as well as the amount of movement
usage: !sim <realm> <character> [movement:none|light|heavy]

e.g. !sim khazgoroth vengel light"""
        await client.send_message(message.author, helpmsg)

    if message.content.startswith('!sim'):
        LOGGER.info('source: {} {}({}) {}({})'.format(
            str(message.server),
            str(message.channel),
            message.channel.id,
            str(message.author),
            message.author.id
        ))
        LOGGER.info('content: {}'.format(str(message.content)))
        payload = create_payload_from_msg(str(message.content))
            
        await client.channel.basic_publish(
            exchange_name=exchange,
            routing_key=request_routing_key,
            properties={
                'reply_to':message.channel.id,
                'delivery_mode':2,
                 },
            payload=json.dumps(payload))
        await client.send_message(message.channel, 'Queued simulation of {}'.format(payload["character"]))

@client.event
async def on_ready():
    LOGGER.info('Logged in as {} ({})'.format(client.user.name,client.user.id))

    try:
        client.transport, client.protocol = await aioamqp.connect(hostname, port)
    except aioamqp.AmqpClosedConnection:
        LOGGER.info("closed connections")
        return

    client.channel = await client.protocol.channel()
    await client.channel.basic_qos(prefetch_count=1)
    await client.channel.exchange(exchange, 'topic')


async def callback(channel, body, envelope, properties):
    """Process response from SimcDaemon by sending msg to user
    """
    LOGGER.info("reply_to {} received {}".format(properties.reply_to, body))
    xchannel=discord.Object(str(properties.reply_to))

    if body is None:
        await client.send_message(xchannel, "An error occurred while processing a request")
    else:
        result = json.loads(body.decode('utf-8'))
        if "output_character" in result.keys():

            # create the message to send to discord
            embed = discord.Embed(
                title="{} : {} dps".format(result["output_character"],result["dps"]),
                description="{}\n{} {} {}\n{}".format(
                    result["output_realm"],
                    result["output_race"],
                    result["output_spec"],
                    result["output_class"],
                    result["weights"]),
                url=result["url"],
                colour=result["colour"]
            )
            embed.set_thumbnail(url="http://us.battle.net/static-render/us/{}".format(result["thumbnail"]))
            await client.send_message(xchannel, content='Simulation of {} complete'.format(result["output_character"]), embed=embed)
        else:
            await client.send_message(xchannel, result["response"])


async def receive_simc(loop):
    """Listens for responses from SimcDaemon and sends back to user via callback()
    """
    global r_transport, r_protocol
    try:
        r_transport, r_protocol = await aioamqp.connect(hostname, port, loop=loop)
    except aioamqp.AmqpClosedConnection:
        LOGGER.info("closed connections")
        return

    r_channel = await r_protocol.channel()
    await r_channel.exchange(exchange, 'topic')

    result = await r_channel.queue(queue_name='', durable=True, auto_delete=True)
    r_queue_name = result['queue']
    await r_channel.queue_bind(
        exchange_name=exchange,
        queue_name=r_queue_name,
        routing_key=response_routing_key
    )

    LOGGER.info("simc response consumer listening")
    await r_channel.basic_consume(callback, queue_name=r_queue_name)

async def simc_close():
    global r_transport, r_protocol
    await r_protocol.close()
    r_transport.close()
    

async def main_task():
    await client.login(token)
    await client.connect()

#FIXME: this doesnt exit cleanly on KeyboardInterrupt

global r_transport, r_protocol
r_transport, r_protocol = None,None
loop = asyncio.get_event_loop()
try:
    simc_task = loop.create_task(receive_simc(loop))
    client_task = loop.create_task(main_task())
    loop.run_until_complete(simc_task)
    loop.run_until_complete(client_task)
    loop.run_forever()
except:
    loop.run_until_complete(simc_close())
    loop.run_until_complete(client.logout())
finally:
    loop.stop()
    loop.close()

