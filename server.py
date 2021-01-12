import io, socket, typing, os, mimetypes
from datetime import datetime
import threading, queue

from request import Request
from response import *

HandlerT = typing.Callable[[Request], Response]

SERVER_ROOT = os.path.abspath('www')

def log(msg: str) -> None:
     print(datetime.now().strftime("%x %X"), msg, sep=" - ")

def serve_static(server_root: str = SERVER_ROOT) -> HandlerT:
    """Generate a request handler that serve a file
    """
    def handler(request: Request) -> Response:
        path = request.path
        if path == "/":
            path = "/index.html"

        abspath = os.path.normpath(os.path.join(server_root, path.lstrip("/")))
        if not abspath.startswith(server_root):
            response = Response(status = "404 Not found", content = "Not found")
            return
        try:
            content_type, encoding = mimetypes.guess_type(abspath)
            if content_type is None:
                content_type = "application/octet-stream"
            if encoding is not None:
                content_type += f"; charset={encoding}"
            body_file = open(abspath, "rb")
            response = Response(status="200 OK", body=body_file)
            response.headers.add("content-type", content_type)
            log(f"file found {path}")
            return response
        except FileNotFoundError:
            return Response(status = "404 Not found", content = "Not found")
    return handler

class HTTPWorker(threading.Thread):
    def __init__(self, connection_queue: queue.Queue,
                 handlers: typing.List[typing.Tuple[str, HandlerT]]) -> None:
        super().__init__(daemon=True)
        self.connection_queue = connection_queue
        self.handlers = handlers
        self.running = False

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        self.running = True
        while self.running:
            try:
                client_sock, client_addr = self.connection_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                self.handle_client(client_sock, client_addr)
            except Exception as e:
                log(f"Unhandeld error: {e}")
            finally:
                self.connection_queue.task_done()

    def handle_client(self, client_sock: socket.socket, client_addr: typing.Tuple[str, int]) -> None:
        log(f"New connection from {client_addr}")
        with client_sock:
            try:
                request = Request.from_socket(client_sock)
                log(f"Client request: {request}")
            except Exception as e:
                log(f"faield to parse request: {e}")
                Response(status = "400 Bad request", content = "Bad request").send(client_sock)
                return

            # force the client to send the full body, so that the handler does
            # not have to deal with this
            if "100-continue" in request.headers.get("expect", ""):
                log("sending \"100 Continue\" to client")
                Response(status = "100 Continue").send(client_sock)

            for path_prefix, handler in self.handlers:
                if request.path.startswith(path_prefix):
                    try:
                        request = request._replace(path=request.path[len(path_prefix):])
                        response = handler(request)
                        response.send(client_sock)
                    except Exception as e:
                        log(f"unexpected error from handler {handler}: {e}")
                        Response(status = "500 Internal Server Error", content = "Internal Server Error").send(client_sock)
                    finally:
                        break
            else:
                Response(status = "500 Internal Server Error", content = "Internal Server Error").send(client_sock)

def app(request: Request) -> Response:
    return Response(status="200 OK", content="hello web!")

def wrap_auth(handler: HandlerT, token: str) -> HandlerT:
    def auth_handler(request: Request) -> Response:
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer ") and \
           authorization[len("Bearer "):] == token:
            return handler(request)
        return Response(status="403 Forbidden", content="get out!")
    return auth_handler

class HTTPServer:
    def __init__(self, host="127.0.0.1", port=9000, worker_count=16) -> None:
        self.handlers = list()
        self.host = host
        self.port = port
        self.worker_count = worker_count
        self.worker_backlog = worker_count * 8
        self.connection_queue = queue.Queue(self.worker_backlog)

    def mount(self, path_prefix:str, handler: HandlerT) -> None:
        """Mount a request handler at a particular path. Handler prefixes are
        tested in the order that they are added
        """
        self.handlers.append((path_prefix, handler))

    def serve_forever(self) -> None:
        workers = list()
        for _ in range(self.worker_count):
            worker = HTTPWorker(self.connection_queue, self.handlers)
            worker.start()
            workers.append(worker)

        with socket.socket() as server_sock:
            # tells the Kernel to reuse sockets in "TIME_WAIT" state
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((self.host, self.port))
            server_sock.listen(self.worker_backlog)
            log(f"Listening on {self.host}:{self.port}...")

            while True:
                try:
                    self.connection_queue.put(server_sock.accept())
                except KeyboardInterrupt:
                    break

            for worker in workers:
                worker.stop()

            for worker in workers:
                worker.join(timeout=30)

if __name__ == "__main__":
    server = HTTPServer()
    server.mount("/static", serve_static())
    server.mount("/secure", wrap_auth(serve_static(), token="t0kEn"))
    server.mount("", app)
    server.serve_forever()
