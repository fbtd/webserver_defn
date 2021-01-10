import io, socket, typing, os, mimetypes
from datetime import datetime

from response import *
from request import Request

HOST = "127.0.0.1"
PORT = 9000
SERVER_ROOT = os.path.abspath('www')
FILE_RESPONSE_TEMPLATE = """\
HTTP/1.1 200 OK
Content-type: {content_type}
Content-length: {content_length}

""".replace("\n", "\r\n")

def log(msg: str) -> None:
     print(datetime.now().strftime("%x %X"), msg, sep=" - ")

def serve_file(sock: socket.socket, path:str) -> None:
    """Given a socket and the relative (to SERVER_ROOT) path to a file, send
    that file to the socet if it exists. If not, send a 404 Response
    """
    if path == "/":
        path = "/index.html"

    abspath = os.path.normpath(os.path.join(SERVER_ROOT, path.lstrip("/")))
    if not abspath.startswith(SERVER_ROOT):
        RESPONSE_404.send(sock)
        return

    try:
        with open(abspath, "rb") as f:
            content_type, encoding = mimetypes.guess_type(abspath)
            if content_type is None:
                content_type = "application/octet-stream"
            if encoding is not None:
                content_type += f"; charset={encoding}"

            response = Response(status="200 OK", body=f)
            response.headers.add("content-type", content_type)
            response.send(sock)

    except FileNotFoundError:
        RESPONSE_404.send(sock)
        return

class HTTPServer:
    def __init__(self, host="127.0.0.1", port=9000) -> None:
        self.host = host
        self.port = port

    def serve_forever(self) -> None:
        with socket.socket() as server_sock:
            # tells the Kernel to reuse sockets in "TIME_WAIT" state
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((HOST, PORT))

            server_sock.listen(0)
            log(f"Listening on {HOST}:{PORT}...")

            while True:
                client_sock, client_addr = server_sock.accept()
                self.handle_client(client_sock, client_addr)

    def handle_client(self, client_sock: socket.socket, client_addr: typing.Tuple[str, int]) -> None:
        log(f"New connection from {client_addr}")
        with client_sock:
            try:
                client_request = Request.from_socket(client_sock)
                log(f"Client request: {client_request}")

                try:
                    content_length = int(client_request.headers.get("content-length") or 0)
                except ValueError:
                    content_length = 0

                if client_request.method == "GET":
                    serve_file(client_sock, client_request.path)
                elif client_request.method == "POST":
                    if "100-continue" in client_request.headers.get("expect", ""):
                        log("sending \"100 Continue\" to client")
                        RESPONSE_100.send(client_sock)
                else:
                    RESPONSE_405.send(client_sock)

                if content_length:
                    body = client_request.body.read(content_length)
                    log(f"Request body: {body}")

            except Exception as e:
                log(f"faield to parse request: {e}")
                RESPONSE_400.send(client_sock)

if __name__ == "__main__":
    server = HTTPServer()
    server.serve_forever()
