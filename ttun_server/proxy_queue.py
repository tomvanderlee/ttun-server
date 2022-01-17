import asyncio
import json
import logging
import os
from typing import Awaitable, Callable

from ttun_server.redis import RedisConnectionPool
from ttun_server.types import RequestData, ResponseData, MemoryConnection

logger = logging.getLogger(__name__)

class BaseProxyQueue:
    def __init__(self, identifier: str):
        self.identifier = identifier

    @classmethod
    async def create_for_identifier(cls, identifier: str) -> 'BaseProxyQueue':
        raise NotImplementedError(f'Please implement create_for_identifier')

    @classmethod
    async def get_for_identifier(cls, identifier: str) -> 'BaseProxyQueue':
        assert await cls.has_connection(identifier)
        return cls(identifier)

    @classmethod
    async def has_connection(cls, identifier) -> bool:
        raise NotImplementedError(f'Please implement has_connection')

    async def send_request(self, request_data: RequestData):
        raise NotImplementedError(f'Please implement send_request')

    async def handle_request(self) -> RequestData:
        raise NotImplementedError(f'Please implement handle_requests')

    async def send_response(self, response_data: ResponseData):
        raise NotImplementedError(f'Please implement send_request')

    async def handle_response(self) -> ResponseData:
        raise NotImplementedError(f'Please implement handle_response')

    async def delete(self):
        raise NotImplementedError(f'Please implement delete')

class MemoryProxyQueue(BaseProxyQueue):
    connections: dict[str, MemoryConnection] = {}

    @classmethod
    async def has_connection(cls, identifier) -> bool:
        return identifier in cls.connections

    @classmethod
    async def create_for_identifier(cls, identifier: str) -> 'MemoryProxyQueue':
        instance = cls(identifier)

        cls.connections[identifier] = {
            'requests': asyncio.Queue(),
            'responses': asyncio.Queue(),
        }

        return instance

    @property
    def requests(self) -> asyncio.Queue[RequestData]:
        return self.__class__.connections[self.identifier]['requests']

    @property
    def responses(self) -> asyncio.Queue[ResponseData]:
        return self.__class__.connections[self.identifier]['responses']

    async def send_request(self, request_data: RequestData):
        await self.requests.put(request_data)

    async def handle_request(self) -> RequestData:
        return await self.requests.get()

    async def send_response(self, response_data: ResponseData):
        return await self.responses.put(response_data)

    async def handle_response(self) -> ResponseData:
        return await self.responses.get()

    async def delete(self):
        del self.__class__.connections[self.identifier]


class RedisProxyQueue(BaseProxyQueue):
    def __init__(self, identifier):
        super().__init__(identifier)

        self.pubsub = RedisConnectionPool()\
            .get_connection()\
            .pubsub()

        self.subscription_queue = asyncio.Queue()

    @classmethod
    async def create_for_identifier(cls, identifier: str) -> 'BaseProxyQueue':
        instance = cls(identifier)

        await instance.pubsub.subscribe(f'request_{identifier}')
        return instance

    @classmethod
    async def get_for_identifier(cls, identifier: str) -> 'RedisProxyQueue':
        instance: 'RedisProxyQueue' = await super().get_for_identifier(identifier)

        await instance.pubsub.subscribe(f'response_{identifier}')

        return instance

    @classmethod
    async def has_connection(cls, identifier) -> bool:
        logger.debug(await RedisConnectionPool.get_connection().pubsub_channels())
        return f'request_{identifier}' in {
            channel.decode()
            for channel
            in await RedisConnectionPool \
                .get_connection() \
                .pubsub_channels()
        }

    async def wait_for_message(self):
        async for message in self.pubsub.listen():
            match message['type']:
                case 'subscribe':
                    continue
                case _:
                    return message['data']

    async def send_request(self, request_data: RequestData):
        await RedisConnectionPool \
            .get_connection() \
            .publish(f'request_{self.identifier}', json.dumps(request_data))

    async def handle_request(self) -> RequestData:
        message = await self.wait_for_message()
        return json.loads(message)

    async def send_response(self, response_data: ResponseData):
        await RedisConnectionPool \
            .get_connection() \
            .publish(f'response_{self.identifier}', json.dumps(response_data))

    async def handle_response(self) -> ResponseData:
        message = await self.wait_for_message()
        return json.loads(message)

    async def delete(self):
        await self.pubsub.unsubscribe(f'request_{self.identifier}')

        await RedisConnectionPool.get_connection()\
            .srem('connections', self.identifier)


class ProxyQueueMeta(type):
    def __new__(cls, name, superclasses, attributes):
        return RedisProxyQueue \
            if 'REDIS_URL' in os.environ \
            else MemoryProxyQueue


class ProxyQueue(BaseProxyQueue, metaclass=ProxyQueueMeta):
    pass
