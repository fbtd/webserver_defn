import socket, typing, os, mimetypes
from datetime import datetime

from request import Request

HOST = "127.0.0.1"
PORT = 9000
SERVER_ROOT = os.path.abspath('www')
FILE_RESPONSE_TEMPLATE = """\
HTTP/1.1 200 OK
Content-type: {content_type}
Content-length: {content_length}

""".replace("\n", "\r\n")

def response(body:str, code:str="200 OK", content_type:str="text/html") -> bytes:
    body_b = body.encode()
    content_length = len(body_b)
    return b"HTTP/1.1 " + bytes(code, "ascii") + b"\r\n" + \
           b"Content-type: "  + bytes(content_type, "ascii") + b"\r\n" + \
           b"Content-length: " + bytes(str(content_length), "ascii") + \
           b"\r\n\r\n" + body_b
RESPONSE_200 = response("Hello web!")
RESPONSE_400 = response("Bad request", code="400 Bad Request")
RESPONSE_404 = response("Not found", code="404 Not found")
RESPONSE_405 = response("Method Not Allowed", code="405 Method Not Allowed")

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
        sock.sendall(RESPONSE_404)
        return

    try:
        with open(abspath, "rb") as f:
            stat = os.fstat(f.fileno())
            content_type, encoding = mimetypes.guess_type(abspath)
            if content_type is None:
                content_type = "application/octet-stream"
            if encoding is not None:
                content_type += f"; charset={encoding}"

            response_header = FILE_RESPONSE_TEMPLATE.format(
                content_type=content_type,
                content_length=stat.st_size,
            ).encode("ascii")

            sock.sendall(response_header)
            sock.sendfile(f)
    except FileNotFoundError:
        sock.sendall(RESPONSE_404)
        return

if __name__ == "__main__":
    with socket.socket() as server_sock:
        # tells the Kernel to reuse sockets in "TIME_WAIT" state
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server_sock.bind((HOST, PORT))

        server_sock.listen(0)
        log(f"Listening on {HOST}:{PORT}...")

        while True:
            client_sock, client_addr = server_sock.accept()
            log(f"New connection from {client_addr}")
            with client_sock:
                try:
                    client_request = Request.from_socket(client_sock)
                    log(f"Client request: {client_request}")
                    if client_request.method != "GET":
                        client_sock.sendall(RESPONSE_405)
                        break
                    serve_file(client_sock, client_request.path)
                except Exception as e:
                    log(f"faield to parse request: {e}")
                    client_sock.sendall(RESPONSE_400)
