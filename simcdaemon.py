#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: T'lexii (tlexii@gmail.com)

"""
Consumes messages from MQ and invokes a process to handle them.

"""

import configparser
import logging
import asyncio
import aioamqp
import json
from concurrent.futures import ProcessPoolExecutor
from simc import Simc

# Enable logging
LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) -35s %(lineno) -5d: %(message)s')

# TODO check config valid
config = configparser.ConfigParser()
config.read('discord_simc.conf')
hostname = config['rabbitmq']['hostname']
port = config['rabbitmq']['port']
exchange_name = config['simcdaemon']['exchange']
request_routing_key = config['simcdaemon']['request_routing_key']
response_routing_key = config['simcdaemon']['response_routing_key']

sim = Simc()
transport = None
protocol = None
channel = None
queue_name = None
executor = ProcessPoolExecutor(3)

logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)
logger = logging.getLogger(__name__)

def do_work(body):
    """ A plain python function run in an executor which wraps the result as a future
    """
    logger.debug(str(body))
    result = {}
    try:
        dict=json.loads(body.decode("utf-8"))
        logger.info(str(dict))
        character = dict.pop('character')
        result = sim.run(character, **dict)
        logger.info(str(result))

    except Exception as e:
        result["response"]="Server error - contact Vengel"
        logger.error('Exception calling simc')
        logger.error(str(e))

    return result

async def callback(channel, body, envelope, properties):
    logger.info("callback invoked, running simc.py on thread_executor")
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(loop.run_in_executor(executor, do_work, body))
    result = await future
    await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
    await channel.basic_publish(
            exchange_name=exchange_name,
            routing_key=response_routing_key,
            properties={
                'reply_to':properties.reply_to,
                'delivery_mode':2,
                 },
            payload=json.dumps(result))

async def receive_request():
    try:
        transport, protocol = await aioamqp.connect(hostname, port)
    except aioamqp.AmqpClosedConnection:
        logger.info("closed connections")
        return

    channel = await protocol.channel()
    await channel.exchange(exchange_name, 'topic')

    result = await channel.queue(queue_name='', durable=True, auto_delete=True)
    queue_name = result['queue']
    await channel.queue_bind(
        exchange_name=exchange_name,
        queue_name=queue_name,
        routing_key=request_routing_key
    )

    logger.info("simc request consumer listening")
    await channel.basic_consume(callback, queue_name=queue_name)


def main():

    try:
        logger.debug('running daemon')
        loop = asyncio.get_event_loop()
        loop.create_task(receive_request())
        loop.run_forever()
    except KeyboardInterrupt:
        logger.debug('interrupted')

    logger.debug('exiting')

if __name__ == '__main__':
    main()

