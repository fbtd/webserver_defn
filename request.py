import socket, typing
from collections import defaultdict

def iter_lines(sock: socket.socket, bufsize: int = 16_384) -> typing.Generator[bytes, None, bytes]:
    """Given a socket, read all the individual CRLF-separated lines and yield
    each one until an empty line is found. Returns the remainder after the empty
    line"""
    buff = b""
    while True:
        data = sock.recv(bufsize)
        if not data:
            return b""
        buff += data
        while True:
            try:
                i = buff.index(b"\r\n")
                line, buff = buff[:i], buff[i+2:]
                if not line:
                    return buff
                yield line
            except IndexError:
                break

class Headers:
    def __init__(self) -> None:
        self._headers = defaultdict(list)

    def add(self, name:str, value:str) -> None:
        self._headers[name.lower()].append(value)

    def get_all(self, name:str) -> typing.List[str]:
        return self._headers[name.lower()]

    def get(self, name:str, default: typing.Optional[str] = None) -> typing.Optional[str]:
        try:
            return self.get_all(name)[-1]
        except IndexError:
            return default

class Request(typing.NamedTuple):
    method: str
    path: str
    headers: typing.Mapping[str, str]
    
    @classmethod
    def from_socket(cls, sock: socket.socket) -> "Request":
        """Read and parse the request from a socket opject

        Raises:
          ValueError: When the request cannot be parsed
        """
        lines = iter_lines(sock)
        try:
            request_line = next(lines).decode("ascii")
        except StopIteration:
            raise ValueError("Request line missing")

        try:
            method, path, _ = request_line.split(" ")
        except ValueError:
            raise ValueError("Malformed request line: {request_line!r}")

        headers = dict()
        for line in lines:
            try:
                name, _, value = line.decode("ascii").partition(":")
                headers[name.lower()] = value.lstrip()
            except ValueError:
                raise ValueError("Malformed header line: {line!r}")

        return cls(method=method.upper(), path=path, headers=headers)
