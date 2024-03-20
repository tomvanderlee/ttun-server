from asyncio import Queue
from enum import Enum
from typing import TypedDict, Optional


class HttpMessageType(Enum):
    request = 'request'
    response = 'response'


class Config(TypedDict):
    subdomain: str
    client_version: str


class HttpRequestData(TypedDict):
    method: str
    path: str
    headers: list[tuple[str, str]]
    body: Optional[str]


class HttpResponseData(TypedDict):
    status: int
    headers: list[tuple[str, str]]
    body: Optional[str]


class HttpMessage(TypedDict):
    type: HttpMessageType
    identifier: str
    payload: Config | HttpRequestData | HttpResponseData


class WebsocketMessageType(Enum):
    connect = 'connect'
    disconnect = 'disconnect'
    message = 'message'
    ack = 'ack'


class WebsocketConnectData(TypedDict):
    path: str
    headers: list[tuple[str, str]]


class WebsocketDisconnectData(TypedDict):
    close_code: int


class WebsocketMessageData(TypedDict):
    body: Optional[str]


class WebsocketMessage(TypedDict):
    type: WebsocketMessageType
    identifier: str
    payload: WebsocketConnectData | WebsocketDisconnectData | WebsocketMessageData


class MessageType(Enum):
    request = 'request'
    response = 'response'

    ws_connect = 'connect'
    ws_disconnect = 'disconnect'
    ws_message = 'message'
    ws_ack = 'ack'


Message = HttpMessage | WebsocketMessage


class MemoryConnection(TypedDict):
    requests: Queue[Message]
    responses: Queue[Message]
