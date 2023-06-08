from asyncio import Queue
from enum import Enum
from typing import TypedDict, Optional


class MessageType(Enum):
    request = 'request'
    response = 'response'


class Config(TypedDict):
    subdomain: str
    client_version: str


class RequestData(TypedDict):
    method: str
    path: str
    headers: list[tuple[str, str]]
    body: Optional[str]


class ResponseData(TypedDict):
    status: int
    headers: list[tuple[str, str]]
    body: Optional[str]


class Message(TypedDict):
    type: MessageType
    identifier: str
    payload: Config | RequestData | ResponseData


class MemoryConnection(TypedDict):
    requests: Queue[Message]
    responses: Queue[Message]
