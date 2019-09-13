#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)

import configparser
import logging
import discord
import asyncio
import aioamqp
import json
from datetime import datetime
from simc import Simc
from mounts import Mounts

# Enable logging
LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -20s %(funcName) -25s %(lineno) -5d: %(message)s')
logging.basicConfig(filename='/var/log/discord-simc-bot.log', format=LOG_FORMAT, level=logging.INFO)

# TODO check config valid
config = configparser.ConfigParser()
config.read('discord_simc.conf')
hostname = config['rabbitmq']['hostname']
port = config['rabbitmq']['port']
exchange = config['simcdaemon']['exchange']
simc_request_routing_key = config['simcdaemon']['request_routing_key']
simc_response_routing_key = config['simcdaemon']['response_routing_key']
mounts_request_routing_key = config['mounts']['request_routing_key']
mounts_response_routing_key = config['mounts']['response_routing_key']
token = config['discord']['bot_token']

client = discord.Client()
simc = Simc()
mounts = Mounts()


@client.event
async def on_message(message):
    # we do not want the bot to reply to itself
    if message.author == client.user:
        return

#    if message.guild is None:
#        logging.info('PRVMSG:{0.author.name}: {0.clean_content}'.format(message))
#        for attach in message.attachments:
#            logging.info('ATTACH:{0.filename}:{0.url}'.format(attach))
#        for embed in message.embeds:
#            logging.info('EMBED:{0.title}:{0.url}:{0.image.url}'.format(message))
#    else:
#        logging.info('MSG:{0.guild.Name}:{0.author.name}:{0.author.nick}: {0.clean_content}'.format(message))

    if message.content.lower().startswith('!help'):
        helpmsg="""
!sim <character> [[realm] [movement:none|light|heavy]] (realm is Khaz'goroth by default)
    e.g. !sim vengel khazgoroth light

!mounts <character> [realm] (realm is Khaz'goroth by default)
    Minimum time between updates is 10mins, cached results are returned for less than 10mins

"""
        await message.channel.send(helpmsg)

    logging.info('source: {} {}({}) {}({})'.format(
        str(message.guild),
        str(message.channel),
        message.channel.id,
        str(message.author),
        message.author.id
    ))
    content = str(message.content.lower())
    logging.info('content: {}'.format(content))

    if content.startswith(mounts.cmd()):
        payload = mounts.create_payload_from_msg(str(message.content))
            
        await client.mqchannel.basic_publish(
                exchange_name=exchange,
                routing_key=mounts_request_routing_key,
                properties={
                    'reply_to' : str(message.channel.id),
                    'delivery_mode':2, },
                payload=json.dumps(payload))

        await message.channel.send('Queued mounts check for {}'.format(payload["character"]))

    if content.startswith(simc.cmd()):
        payload = simc.create_payload_from_msg(str(message.content))
            
        await client.mqchannel.basic_publish(
                exchange_name=exchange,
                routing_key=simc_request_routing_key,
                properties={
                    'reply_to' : str(message.channel.id),
                    'delivery_mode':2, },
                payload=json.dumps(payload))

        await message.channel.send( 'Queued simulation of {}'.format(payload["character"]))


@client.event
async def on_ready():
    logging.info('Logged in as {} ({})'.format(client.user.name,client.user.id))

    try:
        client.mqtransport, client.mqprotocol = await aioamqp.connect(hostname, port)
    except aioamqp.AmqpClosedConnection:
        logging.info("closed connections")
        return

    client.mqchannel = await client.mqprotocol.channel()
    await client.mqchannel.basic_qos(prefetch_count=1)
    await client.mqchannel.exchange(exchange, 'topic')


@client.event
async def on_resumed():
    logging.info('Resumed session')


#@client.event
#async def on_socket_raw_receive(msg):
#    logging.info(msg)


@client.event
async def on_member_update(before,after):
    try:
        msg = ''
        send = False
        if before.nick == None and after.nick == None:
            msg = 'STATUS:{0.guild.name}:{0.name}'.format(before)
        else:
            msg = 'STATUS:{0.guild.name}:{0.name}:{0.nick}'.format(before)

        if before.nick != after.nick:
            msg += ' new nick: {0.nick}'.format(after)
            send = True

        if before.status != after.status:
            msg += ' status: {0.status} -> {1.status}'.format(before, after)
            send = True

#        if before.game != after.game:
#            send = True
#            msg += ' game '
#            if before.game == None:
#                msg += 'started: {0.game}'.format(after)
#            elif after.game == None:
#                msg += 'ended: {0.game}'.format(before)
#            elif before.game != None and after.game != None:
#                msg += '{0.game} -> {1.game}'.format(before, after)

#        roles = ''
#        for x in before.roles:
#            if not x in after.roles:
#                roles+='lost:{0.name} '.format(x)
#        for x in after.roles:
#            if not x in before.roles:
#                roles+='gained:{0.name} '.format(x)

        if not send:
            msg += ' invisible status change'
            send = True

        if send: 
            logging.info(msg)

    except Exception as e:
        logging.error('Exception in on_message_update')
        logging.error(str(e))


@client.event
async def on_voice_state_update(before,after):
    try:
        msg = ''
        send = False
        if before.nick == None:
            msg = 'VOICE:{0.guild.name}:{0.name}'.format(before)
        else:
            msg = 'VOICE:{0.guild.name}:{0.name}:{0.nick}'.format(before)

        if before.voice.voice_channel == None and after.voice.voice_channel == None:
            send = False
        elif before.voice.voice_channel == None and after.voice.voice_channel != None:
            msg += ' joined {0.voice.voice_channel.name}'.format(after)
            send = True
        elif before.voice.voice_channel != None and after.voice.voice_channel == None:
            msg += ' left {0.voice.voice_channel.name}'.format(before)
            send = True
        elif before.voice.voice_channel == after.voice.voice_channel:
            msg += ' {0.voice.voice_channel.name}'.format(before)
            send = True
        else:
            msg += ' {0.voice.voice_channel.name} -> {1.voice.voice_channel.name}'.format(before,after)
            send = True

        if before.self_mute != after.self_mute:
            send = True
            if before.self_mute:
                msg += ' end-MUTE'
            else:
                msg += ' MUTE'

        if before.is_afk != after.is_afk:
            send = True
            if before.is_afk:
                msg += ' end-AFK'
            else:
                msg += ' AFK'

        if send:
            logging.info(msg)

    except Exception as e:
        logging.error('Exception in on_voice_state_update')
        logging.error(str(e))


async def callback(channel, body, envelope, properties):
    """Process response from SimcDaemon by sending msg to user
    """
    logging.info("reply_to {} received {}".format(properties.reply_to, body))
    xchannel= client.get_channel(int(properties.reply_to))

    if body is None:
        await xchannel.send("An error occurred while processing a request")

    elif xchannel is None:
        logging.error("Unable to get_channel for {}".format(properties.reply_to))

    elif envelope.routing_key == simc_response_routing_key:
        await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
        result = json.loads(body.decode('utf-8'))
        if "output_character" in result.keys():
            embed = simc.generate_embed(result)
            await xchannel.send(content='Simulation of {} complete'.format(result["output_character"]), embed=embed)
        else:
            await xchannel.send(result["response"])

    elif envelope.routing_key == mounts_response_routing_key:
        await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
        result = json.loads(body.decode('utf-8'))
        if "output_name" in result.keys():
            embed = mounts.generate_embed(result)
            await xchannel.send(content='Mounts for **{}**-{}'.format(
                result["output_name"], result["output_realm"]), embed=embed)
        else:
            await xchannel.send(result["response"])


async def receive_simc(loop):
    """Listens for responses from SimcDaemon and sends back to user via callback()
    """
    global r_transport, r_protocol
    try:
        r_transport, r_protocol = await aioamqp.connect(hostname, port, loop=loop)
    except aioamqp.AmqpClosedConnection:
        logging.info("closed connections")
        return

    r_channel = await r_protocol.channel()
    await r_channel.exchange(exchange, 'topic')

    result = await r_channel.queue(queue_name='', durable=True, auto_delete=True)
    r_queue_name = result['queue']
    await r_channel.queue_bind( exchange_name=exchange, queue_name=r_queue_name, routing_key=simc_response_routing_key)
    await r_channel.queue_bind( exchange_name=exchange, queue_name=r_queue_name, routing_key=mounts_response_routing_key)

    logging.info("simc response consumer listening")
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

