import logging
from base64 import b64decode, b64encode
from uuid import uuid4

from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ttun_server.proxy_queue import ProxyQueue
from ttun_server.types import HttpRequestData, Message, HttpMessageType, HttpMessage

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

            logger.debug('PROXY %s%s ', subdomain, request.url)
            await request_queue.enqueue(
                HttpMessage(
                    type=HttpMessageType.request.value,
                    identifier=identifier,
                    payload=
                    HttpRequestData(
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


