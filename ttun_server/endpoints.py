import asyncio
import logging
import os
from asyncio import Queue
from base64 import b64decode, b64encode
from typing import Optional, Any
from uuid import uuid4

from starlette.endpoints import HTTPEndpoint, WebSocketEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Scope, Receive, Send
from starlette.websockets import WebSocket

from ttun_server.proxy_queue import ProxyQueue
from ttun_server.types import RequestData, Config, ResponseData

logger = logging.getLogger(__name__)


class Proxy(HTTPEndpoint):
    async def dispatch(self) -> None:
        request = Request(self.scope, self.receive)

        [subdomain, *_] = request.headers['host'].split('.')
        response = Response(content='Not Found', status_code=404)

        try:
            queue = await ProxyQueue.get_for_identifier(subdomain)

            await queue.send_request(RequestData(
                method=request.method,
                path=str(request.url).replace(str(request.base_url), '/'),
                headers=dict(request.headers),
                cookies=dict(request.cookies),
                body=b64encode(await request.body()).decode()
            ))

            _response = await queue.handle_response()
            response = Response(
                status_code=_response['status'],
                headers=_response['headers'],
                content=b64decode(_response['body'].encode())
            )
        except AssertionError:
            pass

        await response(self.scope, self.receive, self.send)


class Tunnel(WebSocketEndpoint):
    encoding = 'json'

    def __init__(self, scope: Scope, receive: Receive, send: Send):
        super().__init__(scope, receive, send)
        self.request_task = None
        self.config: Optional[Config] = None

    async def handle_requests(self, websocket: WebSocket):
        while request := await self.proxy_queue.handle_request():
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

    async def on_receive(self, websocket: WebSocket, data: Any):
        await self.proxy_queue.send_response(data)

    async def on_disconnect(self, websocket: WebSocket, close_code: int):
        await self.proxy_queue.delete()

        if self.request_task is not None:
            self.request_task.cancel()
