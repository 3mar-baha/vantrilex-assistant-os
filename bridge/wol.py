"""Wake-on-LAN sender (sprint-3 3.4 AC11): exact 102-byte magic packet, ONE UDP
sendto (default broadcast:9). The daemon never binds — sendto only, socket in a
worker thread so the event loop never blocks."""

from __future__ import annotations

import asyncio
import socket


def magic_packet(mac: str) -> bytes:
    cleaned = mac.replace(":", "").replace("-", "").replace(".", "").strip()
    if len(cleaned) != 12:
        raise ValueError(f"MAC must have 6 octets: {mac!r}")
    try:
        addr = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"MAC is not hexadecimal: {mac!r}") from exc
    return b"\xff" * 6 + addr * 16


def _send_udp(packet: bytes, ip: str, port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return sock.sendto(packet, (ip, port))


async def send_wol(mac: str, ip: str = "255.255.255.255", port: int = 9) -> int:
    packet = magic_packet(mac)
    return await asyncio.to_thread(_send_udp, packet, ip, port)
