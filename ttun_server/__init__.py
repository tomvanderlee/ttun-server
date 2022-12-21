import logging
import os

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Host, Router

from ttun_server.endpoints import Proxy, Tunnel, Health

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
    ]
)
