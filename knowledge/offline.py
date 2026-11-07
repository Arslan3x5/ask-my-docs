import ipaddress
import socket


class NetworkBlocked(OSError):
    """Raised when offline mode stops the app from reaching the network."""


def is_allowed(host, allowed=()):
    """Loopback and explicitly allowed hosts are fine. Everything else is blocked."""
    if host is None or host == "":
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    if host == "localhost" or host in allowed:
        return True
    try:
        ip = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return False
    return ip.is_loopback or ip.is_unspecified


_installed = False


def install(allowed=()):
    """Make every outgoing socket connection and DNS lookup to a non-local host fail."""
    global _installed
    if _installed:
        return
    _installed = True
    allowed = tuple(allowed)
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def check(host):
        if not is_allowed(host, allowed):
            raise NetworkBlocked(
                f"Offline mode blocked a network request to {host!r}. "
                "Set OFFLINE_ALLOW_HOSTS to allow a specific host."
            )

    def connect(self, address):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect(self, address)

    def connect_ex(self, address):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        check(host)
        return real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo