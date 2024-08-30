import logging
import os

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Host, Router

from ttun_server.endpoints import Proxy, Health
from .websockets import WebsocketProxy, Tunnel

logging.basicConfig(level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO')))

base_router = Router(routes=[
    Route('/health/', Health),
    WebSocketRoute('/tunnel/', Tunnel)
])

server = Starlette(
    debug=True,
    routes=[
        Host(os.environ['TUNNEL_DOMAIN'], base_router, 'base'),
        Route('/{path:path}', Proxy),
        WebSocketRoute('/{path:path}', WebsocketProxy)
    ]
)

try:
    from ._version import version
    __version__ = version
except ImportError:
    __version__ = 'development'
