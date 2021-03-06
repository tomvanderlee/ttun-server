from asyncio import Queue
from typing import TypedDict, Optional


class Config(TypedDict):
    subdomain: str

class RequestData(TypedDict):
    method: str
    path: str
    headers: list[tuple[str, str]]
    body: Optional[str]


class ResponseData(TypedDict):
    status: int
    headers: list[tuple[str, str]]
    body: Optional[str]


class MemoryConnection(TypedDict):
    requests: Queue[RequestData]
    responses: Queue[ResponseData]
