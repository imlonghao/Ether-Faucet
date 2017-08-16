#!/usr/bin/env python3

import rlp
import redis
import binascii
import requests
import tornado.ioloop
import tornado.web
import tornado.gen
import tornado.options
import ethereum.utils
from ethereum.transactions import Transaction

tornado.options.define('port', default=9999, type=int)


def get_price():
    result = requests.post('https://api.myetherapi.com/rop', json={
        'method': 'eth_gasPrice',
        'id': 1,
        'jsonrpc': '2.0'
    }, timeout=5).json()['result']
    return int(result, 16)


def get_tx_count():
    result = requests.post('https://api.myetherapi.com/rop', json={
        'method': 'eth_getTransactionCount',
        'params': [
            '0x88888703716E72C16fc5f613A8C608F61E060D46',
            'latest'
        ],
        'id': 1,
        'jsonrpc': '2.0'
    }, timeout=5).json()['result']
    return int(result, 16)


def send_tx(data):
    requests.post('https://api.myetherapi.com/rop', json={
        'method': 'eth_sendRawTransaction',
        'params': [
            data
        ],
        'id': 1,
        'jsonrpc': '2.0'
    }, timeout=5).json()


class BaseHandler(tornado.web.RequestHandler):
    @property
    def redis(self):
        return self.application.redis


class IndexHandler(BaseHandler):
    @tornado.gen.coroutine
    def get(self):
        return self.write({
            'paths': {
                '/': {
                    'get': {
                        'responses': {
                            '200': {
                                'description': 'Return this page'
                            }
                        }
                    }
                },
                '/{Address}': {
                    'get': {
                        'parameters': [
                            {
                                'name': 'Address',
                                'in': 'path',
                                'type': 'address',
                                'description': 'Address to claim the faucet',
                                'required': True
                            }
                        ],
                        'responses': {
                            '200': {
                                'description': 'Success to claim the faucet'
                            },
                            '429': {
                                'description': 'Rate limit reached'
                            }
                        }
                    }
                }
            }
        })


class AddressHandler(BaseHandler):
    @tornado.gen.coroutine
    def get(self, address):
        ip = self.request.remote_ip
        if self.redis.get(ip) is not None or self.redis.get(address) is not None:
            return self.send_error(429)
        if not ethereum.utils.check_checksum(address):
            return self.send_error(404)
        tx = Transaction(get_tx_count(), get_price(), 21000, address, 2 * 1000000000000000000, '')
        tx.sign('PRIVATEKEY', 3)
        data = '0x%s' % binascii.hexlify(rlp.encode(tx)).decode()
        send_tx(data)
        self.redis.set(ip, 1, 60 * 60 * 24)
        self.redis.set(address, 1, 60 * 60 * 24)
        return self.write({'success': True})


if __name__ == "__main__":
    tornado.options.parse_command_line()
    ioloop = tornado.ioloop.IOLoop.instance()
    application = tornado.web.Application([
        (r'/', IndexHandler),
        (r'/(0x[0-9a-fA-F]{40})', AddressHandler),
    ])
    application.redis = redis.Redis()
    application.listen(tornado.options.options.port, '127.0.0.1', xheaders=True)
    ioloop.start()
