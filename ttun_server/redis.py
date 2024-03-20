import asyncio
import os
from asyncio import get_running_loop

from redis.asyncio import ConnectionPool, Redis


class RedisConnectionPool:
    instance: 'RedisConnectionPool' = None

    def __init__(self):
       self.pool = ConnectionPool.from_url(os.environ.get('REDIS_URL'))

    @classmethod
    def get_connection(cls) -> Redis:
        if cls.instance is None:
            cls.instance = RedisConnectionPool()

        return Redis(connection_pool=cls.instance.pool)
