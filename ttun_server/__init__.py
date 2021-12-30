from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from ttun_server.endpoints import Proxy, Tunnel

server = Starlette(
    debug=True,
    routes=[
        Route('/{path:path}', Proxy),
        WebSocketRoute('/tunnel/', Tunnel)
    ]
)
