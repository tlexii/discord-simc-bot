#!python
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
from mounts import Mounts


hostname = None
port = None
exchange_name = None
request_routing_key = None
response_routing_key = None

sim = None
transport = None
protocol = None
channel = None
queue_name = None
executor = ProcessPoolExecutor(3)

def do_simc_work(body):
    global sim
    """ A plain python function run in an executor which wraps the result as a future
    """
    logging.debug(str(body))
    result = {}
    try:
        dict=json.loads(body.decode("utf-8"))
        logging.info(str(dict))
        character = dict.pop('character')
        result = sim.run(character, **dict)
        logging.info(str(result))

    except Exception as e:
        result["response"]="Server error - contact Vengel"
        logging.error('Exception calling simc')
        logging.error(str(e))

    return result

def do_mounts_work(body):
    global mounts
    """ A plain python function run in an executor which wraps the result as a future
    """
    logging.debug(str(body))
    result = {}
    try:
        dict=json.loads(body.decode("utf-8"))
        logging.info(str(dict))
        character = dict.pop('character')
        result = mounts.run(character, **dict)
        logging.info(str(result))

    except Exception as e:
        result["response"]="Server error - contact Vengel"
        logging.error('Exception calling mounts')
        logging.error(str(e))

    return result

async def callback(channel, body, envelope, properties):
    loop = asyncio.get_event_loop()
    if envelope.routing_key == simc_request_routing_key:
        logging.info("callback invoked, running simc.py on thread_executor")
        workerfn = do_simc_work
        rkey = simc_response_routing_key
    else:
        logging.info("callback invoked, running mounts.py on thread_executor")
        workerfn = do_mounts_work
        rkey = mounts_response_routing_key

    future = asyncio.ensure_future(loop.run_in_executor(executor, workerfn, body))
    result = await future
    await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
    logging.info(str(result))
    await channel.basic_publish(
            exchange_name=exchange_name,
            routing_key=rkey,
            properties={
                'reply_to':properties.reply_to,
                'delivery_mode':2,
                 },
            payload=json.dumps(result))

async def receive_request():
    try:
        transport, protocol = await aioamqp.connect(hostname, port)
    except aioamqp.AmqpClosedConnection:
        logging.info("closed connections")
        return

    channel = await protocol.channel()
    await channel.exchange(exchange_name, 'topic')

    result = await channel.queue(queue_name='', durable=True, auto_delete=True)
    queue_name = result['queue']
    await channel.queue_bind(
        exchange_name=exchange_name,
        queue_name=queue_name,
        routing_key=simc_request_routing_key
    )

    await channel.queue_bind(
        exchange_name=exchange_name,
        queue_name=queue_name,
        routing_key=mounts_request_routing_key
    )

    logging.info("simc request consumer listening")
    await channel.basic_consume(callback, queue_name=queue_name)


def main():
    global hostname, port, exchange_name
    global sim, simc_request_routing_key, simc_response_routing_key
    global mounts, mounts_request_routing_key, mounts_response_routing_key
    logging.info('attempting to start')

    # TODO check config valid
    config = configparser.ConfigParser()
    config.read('discord_simc.conf')
    hostname = config['rabbitmq']['hostname']
    port = config['rabbitmq']['port']
    exchange_name = config['simcdaemon']['exchange']

    sim = Simc()
    simc_request_routing_key  = config['simcdaemon']['request_routing_key']
    simc_response_routing_key = config['simcdaemon']['response_routing_key']

    mounts = Mounts()
    mounts_request_routing_key  = config['mounts']['request_routing_key']
    mounts_response_routing_key = config['mounts']['response_routing_key']

    try:
        logging.debug('running daemon')
        loop = asyncio.get_event_loop()
        loop.create_task(receive_request())
        loop.run_forever()
    except KeyboardInterrupt:
        logging.debug('interrupted')

    logging.debug('exiting')

if __name__ == '__main__':
    # Enable logging
    LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) -35s %(lineno) -5d: %(message)s')
    logging.basicConfig(filename='/var/log/simcdaemon.log', format=LOG_FORMAT, level=logging.INFO)
    main()

