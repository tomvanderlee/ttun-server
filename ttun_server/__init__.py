import logging
import os

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from ttun_server.endpoints import Proxy, Tunnel

logging.basicConfig(level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO')))

server = Starlette(
    debug=True,
    routes=[
        Route('/{path:path}', Proxy),
        WebSocketRoute('/tunnel/', Tunnel)
    ]
)
