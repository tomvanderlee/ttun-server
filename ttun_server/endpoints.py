import asyncio
import logging
import os
from base64 import b64decode, b64encode
from typing import Optional, Any
from uuid import uuid4

from starlette.endpoints import HTTPEndpoint, WebSocketEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Scope, Receive, Send
from starlette.websockets import WebSocket

from ttun_server.proxy_queue import ProxyQueue
from ttun_server.types import RequestData, Config, Message, MessageType

logger = logging.getLogger(__name__)


class HeaderMapping:
    def __init__(self, headers: list[tuple[str, str]]):
        self._headers = headers

    def items(self):
        for header in self._headers:
            yield header


class Proxy(HTTPEndpoint):
    async def dispatch(self) -> None:
        request = Request(self.scope, self.receive)

        [subdomain, *_] = request.headers['host'].split('.')
        response = Response(content='Not Found', status_code=404)

        identifier = str(uuid4())
        response_queue = await ProxyQueue.create_for_identifier(f'{subdomain}_{identifier}')

        try:

            request_queue = await ProxyQueue.get_for_identifier(subdomain)

            await request_queue.enqueue(
                Message(
                    type=MessageType.request,
                    identifier=identifier,
                    payload=
                    RequestData(
                        method=request.method,
                        path=str(request.url).replace(str(request.base_url), '/'),
                        headers=list(request.headers.items()),
                        body=b64encode(await request.body()).decode()
                    )
                )
            )

            _response = await response_queue.dequeue()
            payload = _response['payload']
            response = Response(
                status_code=payload['status'],
                headers=HeaderMapping(payload['headers']),
                content=b64decode(payload['body'].encode())
            )
        except AssertionError:
            pass
        finally:
            await response(self.scope, self.receive, self.send)
            await response_queue.delete()


class Health(HTTPEndpoint):
    async def get(self, _) -> None:
        response = Response(content='OK', status_code=200)

        await response(self.scope, self.receive, self.send)


class Tunnel(WebSocketEndpoint):
    encoding = 'json'

    def __init__(self, scope: Scope, receive: Receive, send: Send):
        super().__init__(scope, receive, send)
        self.request_task = None
        self.config: Optional[Config] = None

    async def handle_requests(self, websocket: WebSocket):
        while request := await self.proxy_queue.dequeue():
            await websocket.send_json(request)

    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.config = await websocket.receive_json()

        if self.config['subdomain'] is None \
                or await ProxyQueue.has_connection(self.config['subdomain']):
            self.config['subdomain'] = uuid4().hex

        self.proxy_queue = await ProxyQueue.create_for_identifier(self.config['subdomain'])

        hostname = os.environ.get("TUNNEL_DOMAIN")
        protocol = "https" if os.environ.get("SECURE", False) else "http"

        await websocket.send_json({
            'url': f'{protocol}://{self.config["subdomain"]}.{hostname}'
        })

        self.request_task = asyncio.create_task(self.handle_requests(websocket))

    async def on_receive(self, websocket: WebSocket, data: Message):
        try:
            response_queue = await ProxyQueue.get_for_identifier(f"{self.config['subdomain']}_{data['identifier']}")
            await response_queue.enqueue(data)
        except AssertionError:
            pass

    async def on_disconnect(self, websocket: WebSocket, close_code: int):
        await self.proxy_queue.delete()

        if self.request_task is not None:
            self.request_task.cancel()
