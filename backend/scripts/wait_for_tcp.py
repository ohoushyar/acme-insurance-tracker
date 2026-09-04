"""Wait until a TCP host:port accepts connections."""

from __future__ import annotations

import argparse
import socket
import sys
import time


def wait_for_tcp(host: str, port: int, timeout_seconds: int) -> bool:
    if not host or port < 1 or port > 65535 or timeout_seconds < 1:
        return False
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("port", type=int)
    parser.add_argument("timeout", type=int, nargs="?", default=60)
    args = parser.parse_args()
    if not wait_for_tcp(args.host, args.port, args.timeout):
        sys.exit(1)


if __name__ == "__main__":
    main()
