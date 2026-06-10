import asyncio
import json
import logging
import os
import typing
from asyncio import create_task
from base64 import b64encode, b64decode
from contextlib import asynccontextmanager
from typing import Optional
from uuid import uuid4

from starlette.endpoints import WebSocketEndpoint
from starlette.types import Scope, Receive, Send
from starlette.websockets import WebSocket

import ttun_server
from ttun_server.proxy_queue import ProxyQueue
from ttun_server.types import Config, Message, WebsocketMessageType, \
    WebsocketConnectData, WebsocketMessage, WebsocketMessageData, WebsocketDisconnectData, MessageType

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

class WebsocketProxy(WebSocketEndpoint):
    encoding = 'json'
    websocket_listen_task = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = str(uuid4())

    @asynccontextmanager
    async def proxy(self, websocket: WebSocket, message: WebsocketMessage):
        [subdomain, *_] = websocket.url.hostname.split('.')

        expect_ack = WebsocketMessageType(message['type']) == WebsocketMessageType.connect

        try:
            request_queue = await ProxyQueue.get_for_identifier(subdomain)
            await request_queue.enqueue(message)

            if expect_ack:
                response_queue = await ProxyQueue.create_for_identifier(message["identifier"])
                yield await response_queue.dequeue()
                await response_queue.delete()
            else:
                yield
        except AssertionError:
            yield None

    async def listen_for_messages(self, websocket: WebSocket):
        response_queue = await ProxyQueue.create_for_identifier(self.id)

        while True:
            message: WebsocketMessage = await response_queue.dequeue()
            logger.debug(message)
            await websocket.send_text(b64decode(message['payload']['body'].encode()).decode())

    async def on_connect(self, websocket: WebSocket) -> None:
        message = WebsocketMessage(
            type=WebsocketMessageType.connect.value,
            identifier=self.id,
            payload=WebsocketConnectData(
                path=websocket.path_params['path'],
                headers=[
                    (k.decode(), v.decode())
                    for k, v
                    in websocket.scope['headers']
                ],
            )
        )

        async with self.proxy(websocket, message) as m:
            if m is not None and WebsocketMessageType(m['type']) == WebsocketMessageType.ack:
                await super().on_connect(websocket)

        self.websocket_listen_task = asyncio.create_task(self.listen_for_messages(websocket))

        def callback(*args, **kwargs):
            self.websocket_listen_task = None

        self.websocket_listen_task.add_done_callback(callback)

    async def on_receive(self, websocket: WebSocket, data: typing.Any) -> None:
        match data:
            case dict():
                data_bytes = json.dumps(data).encode()
            case bytes():
                data_bytes = data
            case _:
                data_bytes = data.encode()

        message = WebsocketMessage(
            type=WebsocketMessageType.message.value,
            identifier=self.id,
            payload=WebsocketMessageData(
                body=b64encode(data_bytes).decode(),
            )
        )

        async with self.proxy(websocket, message):
            pass

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        message = WebsocketMessage(
            type=WebsocketMessageType.disconnect.value,
            identifier=self.id,
            payload=WebsocketDisconnectData(
                close_code=close_code,
            )
        )

        async with self.proxy(websocket, message):
            if self.websocket_listen_task is not None:
                self.websocket_listen_task.cancel()

class Tunnel(WebSocketEndpoint):
    encoding = 'json'

    def __init__(self, scope: Scope, receive: Receive, send: Send):
        super().__init__(scope, receive, send)
        self.request_tasks: dict[str, asyncio.Task] = {}
        self.config: Optional[Config] = None
        self.proxy_queues: dict[str, ProxyQueue] = {}

    async def handle_requests(self, websocket: WebSocket, subdomain: str):
        while request := await self.proxy_queues[subdomain].dequeue():
            task = asyncio.create_task(websocket.send_json(request), name=request['identifier'])


    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.config = await websocket.receive_json()

        client_version = self.config.get('version', '1.0.0')
        logger.debug('client_version %s', client_version)

        if 'git' not in client_version and ttun_server.__version__ != 'development':
            [client_major, *_] = [int(i) for i in client_version.split('.')[:3]]
            [server_major, *_] = [int(i) for i in ttun_server.__version__.split('.')]

            if client_major < server_major:
                await websocket.close(4000, 'Your client is too old')

            if client_major > server_major:
                await websocket.close(4001, 'Your client is too new')

        if 'subdomains' not in self.config:
            self.config['subdomains'] = [self.config['subdomain']]
        elif self.config['subdomains'] is None:
            self.config['subdomains'] = [None]

        for i, subdomain in enumerate(self.config['subdomains']):
            if subdomain is None or await ProxyQueue.has_connection(subdomain):
                self.config['subdomains'][i] = uuid4().hex

        for subdomain in self.config['subdomains']:
            self.proxy_queues[subdomain] = await ProxyQueue.create_for_identifier(subdomain)

        hostname = os.environ.get("TUNNEL_DOMAIN")
        protocol = "https" if os.environ.get("SECURE", False) else "http"

        urls = [
            f'{protocol}://{subdomain}.{hostname}'
            for subdomain in self.config['subdomains']
        ]

        await websocket.send_json({
            'url': urls[0],
            'urls': urls,
        })

        for subdomain in self.config['subdomains']:
            self.request_tasks[subdomain] = asyncio.create_task(self.handle_requests(websocket, subdomain), name=subdomain)

    async def on_receive(self, websocket: WebSocket, data: Message):
        try:
            data['type'] = MessageType(data['type']).value
            response_queue = await ProxyQueue.get_for_identifier(data['identifier'])
            await response_queue.enqueue(data)
        except AssertionError:
            pass

    async def on_disconnect(self, websocket: WebSocket, close_code: int):
        for proxy_queue in self.proxy_queues.values():
            await proxy_queue.delete()

        for request_task in self.request_tasks.values():
            request_task.cancel()
