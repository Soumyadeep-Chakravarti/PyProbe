"""
PyProbe Ring Buffer Logger
=========================
Lock-free SPSC circular ring buffer for high-performance logging.

Performance target: 20-50ns per log call (pure Python/ctypes, no C extension).

Entry format (256 bytes):
    +0   timestamp  (float64, 8B)  — monotonic_ns * 1e-9
    +8   level      (uint8, 1B)    — 0=DEBUG, 1=INFO, 2=WARN, 3=ERROR
    +9   module_id  (uint8, 1B)
    +10  msg_len    (uint16, 2B)
    +12  message    (244B, padded with nulls)

Header (16 bytes):
    +0   write_pos  (uint32)  — entry index, wraps at capacity
    +4   read_pos   (uint32)
    +8   capacity   (uint32)
    +12  flags      (uint32)  — bit 0: buffer-full
"""

import ctypes
import os
import struct
import time
from typing import Optional


# ── Constants ───────────────────────────────────────────────────────────────

ENTRY_SIZE = 256
HEADER_SIZE = 16
MAX_MSG_LEN = ENTRY_SIZE - 12  # 244 bytes

LEVEL_DEBUG = 0
LEVEL_INFO = 1
LEVEL_WARN = 2
LEVEL_ERROR = 3

_LEVEL_NAMES = {0: "DEBUG", 1: "INFO", 2: "WARN", 3: "ERROR"}


# ── ANSI Colors ─────────────────────────────────────────────────────────────

def _should_color() -> bool:
    """Determine if ANSI colors should be used."""
    mode = os.environ.get("PYPROBE_COLOR", "auto").lower()
    if mode == "always":
        return True
    if mode == "never":
        return False
    # auto: check NO_COLOR, then TTY
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(os, "isatty") and os.isatty(1)


def _is_colorblind() -> bool:
    return os.environ.get("PYPROBE_COLOR_MODE", "normal").lower() == "colorblind"


_COLORS = {
    "normal": {
        LEVEL_DEBUG: "\033[36m",   # cyan
        LEVEL_INFO: "\033[32m",    # green
        LEVEL_WARN: "\033[33m",    # yellow
        LEVEL_ERROR: "\033[31m",   # red
    },
    "colorblind": {
        LEVEL_DEBUG: "\033[36m",   # cyan
        LEVEL_INFO: "\033[37m",    # white
        LEVEL_WARN: "\033[33m",    # yellow
        LEVEL_ERROR: "\033[31m",   # red
    },
}
_RESET = "\033[0m"


# ── LogRing ─────────────────────────────────────────────────────────────────

class LogRing:
    """Lock-free SPSC circular ring buffer logger.

    Write path (~20-50ns): monotonic_ns + struct.pack_into + memmove.
    Read path (flush): format timestamp, level name, colorize, print.
    """

    __slots__ = (
        "_num_entries", "_entry_size", "_buf_size",
        "_buf", "_write_pos", "_read_pos",
        "_fmt", "_ts_offset", "_level_offset", "_mod_offset",
        "_len_offset", "_msg_offset",
        "_use_color", "_color_mode",
        "_total_flushes",
    )

    def __init__(self, num_entries: int = 1024) -> None:
        self._num_entries = num_entries
        self._entry_size = ENTRY_SIZE
        self._buf_size = HEADER_SIZE + (num_entries * ENTRY_SIZE)
        self._buf = ctypes.create_string_buffer(self._buf_size)

        self._write_pos = 0
        self._read_pos = 0

        # Pre-computed struct offsets (avoid recomputing per call)
        self._fmt = "<dBBH"  # double, ubyte, ubyte, uint16
        self._ts_offset = 0
        self._level_offset = 8
        self._mod_offset = 9
        self._len_offset = 10
        self._msg_offset = 12

        # Color settings (cached at init, not per call)
        self._use_color = _should_color()
        self._color_mode = "colorblind" if _is_colorblind() else "normal"

        self._total_flushes = 0

        # Initialize header
        hdr = struct.pack("<III", num_entries, 0, 0)
        ctypes.memmove(self._buf, hdr, 12)

    # ── Write Path (hot) ────────────────────────────────────────────────

    def log(self, module_id: int, level: int, message: str | bytes) -> None:
        """Write one entry to the ring buffer. ~20-50ns target."""
        # 1. Timestamp (monotonic_ns is faster than time.time())
        ts = float(time.monotonic_ns()) * 1e-9

        # 2. Compute entry address
        entry_idx = self._write_pos % self._num_entries
        addr = HEADER_SIZE + (entry_idx * self._entry_size)

        # 3. Encode message
        if isinstance(message, str):
            msg_bytes = message.encode("utf-8", errors="replace")
        else:
            msg_bytes = message
        msg_len = len(msg_bytes)
        if msg_len > MAX_MSG_LEN:
            msg_len = MAX_MSG_LEN

        # 4. Batch write all fixed fields at once (single ctypes call)
        struct.pack_into(
            self._fmt, self._buf, addr,
            ts, level & 0xFF, module_id & 0xFF, msg_len & 0xFFFF,
        )

        # 5. Write message body
        if msg_len > 0:
            buf_addr = ctypes.addressof(self._buf)
            ctypes.memmove(buf_addr + addr + self._msg_offset, msg_bytes, msg_len)

        # 6. Advance write_pos
        self._write_pos += 1

    def debug(self, module_id: int, message: str) -> None:
        self.log(module_id, LEVEL_DEBUG, message)

    def info(self, module_id: int, message: str) -> None:
        self.log(module_id, LEVEL_INFO, message)

    def warn(self, module_id: int, message: str) -> None:
        self.log(module_id, LEVEL_WARN, message)

    def error(self, module_id: int, message: str) -> None:
        self.log(module_id, LEVEL_ERROR, message)

    # ── Read Path (not hot) ─────────────────────────────────────────────

    def flush(self) -> int:
        """Read all unread entries, format, print. Returns entry count flushed."""
        count = 0
        while self._read_pos < self._write_pos:
            entry_idx = self._read_pos % self._num_entries
            addr = HEADER_SIZE + (entry_idx * self._entry_size)

            # Unpack fields
            ts, level, module_id, msg_len = struct.unpack_from(
                self._fmt, self._buf, addr,
            )

            # Read message
            if msg_len > 0:
                src_addr = ctypes.addressof(self._buf) + addr + self._msg_offset
                arr = (ctypes.c_ubyte * msg_len).from_address(src_addr)
                message = bytes(arr).decode("utf-8", errors="replace")
            else:
                message = ""

            # Format timestamp (HH:MM:SS.mmm)
            seconds = int(ts)
            millis = int((ts - seconds) * 1000)
            minutes, secs = divmod(seconds, 60)
            hours, mins = divmod(minutes, 60)
            ts_str = f"{hours:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

            # Level name
            level_name = _LEVEL_NAMES.get(level, f"?{level}")

            # Colorize
            if self._use_color:
                palette = _COLORS[self._color_mode]
                color = palette.get(level, "")
                line = (
                    f"{color}[{ts_str}] [{level_name:>5}]{_RESET} "
                    f"{message}"
                )
            else:
                line = f"[{ts_str}] [{level_name:>5}] {message}"

            print(line, flush=True)

            self._read_pos += 1
            count += 1

        self._total_flushes += 1
        return count

    def peek(self, limit: int = 0) -> list[dict]:
        """Read entries without advancing read_pos.

        Args:
            limit: Max entries to return. 0 = all unread (capped at capacity).
        """
        entries = []
        # If write_pos has wrapped past capacity, start from the most recent entries
        total = self._write_pos - self._read_pos
        if total > self._num_entries:
            start = self._write_pos - self._num_entries
        else:
            start = self._read_pos
        if limit > 0:
            start = max(start, self._write_pos - limit)
        pos = start
        while pos < self._write_pos:
            entry_idx = pos % self._num_entries
            addr = HEADER_SIZE + (entry_idx * self._entry_size)

            ts, level, module_id, msg_len = struct.unpack_from(
                self._fmt, self._buf, addr,
            )

            if msg_len > 0:
                src_addr = ctypes.addressof(self._buf) + addr + self._msg_offset
                arr = (ctypes.c_ubyte * msg_len).from_address(src_addr)
                message = bytes(arr).decode("utf-8", errors="replace")
            else:
                message = ""

            entries.append({
                "timestamp": ts,
                "level": level,
                "level_name": _LEVEL_NAMES.get(level, f"?{level}"),
                "module_id": module_id,
                "message": message,
            })
            pos += 1

        return entries

    def clear(self) -> None:
        """Discard all unread entries."""
        self._read_pos = self._write_pos

    def stats(self) -> dict:
        """Return buffer statistics."""
        used = self._write_pos - self._read_pos
        return {
            "capacity": self._num_entries,
            "used": used,
            "free": self._num_entries - used,
            "total_writes": self._write_pos,
            "total_flushes": self._total_flushes,
        }


# ── Module-level singleton ──────────────────────────────────────────────────

_default_ring: Optional[LogRing] = None


def get_ring() -> LogRing:
    """Get or create the default LogRing singleton."""
    global _default_ring
    if _default_ring is None:
        _default_ring = LogRing(num_entries=1024)
    return _default_ring


# ── Convenience functions (import these in other modules) ────────────────────

def log(module_id: int, level: int, message: str) -> None:
    """Write one entry to the default ring buffer."""
    get_ring().log(module_id, level, message)


def debug(module_id: int, message: str) -> None:
    get_ring().debug(module_id, message)


def info(module_id: int, message: str) -> None:
    get_ring().info(module_id, message)


def warn(module_id: int, message: str) -> None:
    get_ring().warn(module_id, message)


def error(module_id: int, message: str) -> None:
    get_ring().error(module_id, message)


def flush() -> int:
    """Flush all pending entries from the default ring."""
    return get_ring().flush()


def clear() -> None:
    """Discard all unread entries from the default ring."""
    get_ring().clear()
