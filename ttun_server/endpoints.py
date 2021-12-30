import asyncio
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

from ttun_server.types import Connection, RequestData, Config, ResponseData

from ttun_server.connections import connections


class Proxy(HTTPEndpoint):
    async def dispatch(self) -> None:
        request = Request(self.scope, self.receive)

        [subdomain, *_] = request.headers['host'].split('.')
        response = Response(content='Not Found', status_code=404)

        if subdomain in connections:
            connection = connections[subdomain]

            await connection['requests'].put(RequestData(
                method=request.method,
                path=str(request.url).replace(str(request.base_url), '/'),
                headers=dict(request.headers),
                cookies=dict(request.cookies),
                body=b64encode(await request.body()).decode()
            ))

            _response = await connection['responses'].get()
            response = Response(
                status_code=_response['status'],
                headers=_response['headers'],
                content=b64decode(_response['body'].encode())
            )

        await response(self.scope, self.receive, self.send)


class Tunnel(WebSocketEndpoint):
    encoding = 'json'

    def __init__(self, scope: Scope, receive: Receive, send: Send):
        super().__init__(scope, receive, send)
        self.request_task = None
        self.config: Optional[Config] = None

    @property
    def requests(self) -> Queue[RequestData]:
        return connections[self.config['subdomain']]['requests']

    @property
    def responses(self) -> Queue[ResponseData]:
        return connections[self.config['subdomain']]['responses']

    async def handle_requests(self, websocket: WebSocket):
        while request := await self.requests.get():
            await websocket.send_json(request)

    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.config = await websocket.receive_json()

        if self.config['subdomain'] is None \
                or self.config['subdomain'] in connections:
            self.config['subdomain'] = uuid4().hex


        connections[self.config['subdomain']] = Connection(
            requests=Queue(),
            responses=Queue(),
        )

        hostname = os.environ.get("TUNNEL_DOMAIN")
        protocol = "https" if os.environ.get("SECURE", False) else "http"

        await websocket.send_json({
            'url': f'{protocol}://{self.config["subdomain"]}.{hostname}'
        })

        self.request_task = asyncio.create_task(self.handle_requests(websocket))

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        await self.responses.put(data)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        if self.config is not None and self.config['subdomain'] in connections:
            del connections[self.config['subdomain']]

        if self.request_task is not None:
            self.request_task.cancel()
