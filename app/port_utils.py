import socket
from contextlib import closing


def find_free_port(start_port: int, max_tries: int = 50) -> int:
    """
    Find an available port, starting from start_port and scanning upward.
    """
    for port in range(start_port, start_port + max_tries):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex(("0.0.0.0", port)) != 0:
                return port
    raise RuntimeError("No free port found in range.")

