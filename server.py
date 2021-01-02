import socket

HOST = "127.0.0.1"
PORT = 9000

with socket.socket() as server_socket:
    # tells the Kernel to reuse sockets in "TIME_WAIT" state
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((HOST, PORT))

    server_socket.listen(0)
    print(f"Listening on {HOST}:{PORT}")
