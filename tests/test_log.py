"""Tests for the ring buffer logger (pyprobe.core.log)."""
import importlib.util
import sys
from pathlib import Path

import pytest

# ── Import helper ───────────────────────────────────────────────────────────

_LOG_PY = Path(__file__).resolve().parent.parent / "src" / "pyprobe" / "core" / "log.py"


def _import_log():
    """Import log.py without triggering pyprobe.core.__init__."""
    if "pyprobe.core.log" in sys.modules:
        return sys.modules["pyprobe.core.log"]
    spec = importlib.util.spec_from_file_location("pyprobe.core.log", str(_LOG_PY))
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pyprobe.core.log"] = mod
    spec.loader.exec_module(mod)  # type: ignore
    return mod


log = _import_log()
LogRing = log.LogRing
get_ring = log.get_ring


# ── Unit tests ──────────────────────────────────────────────────────────────


class TestLogRingWrite:
    def test_write_and_read_back(self):
        ring = LogRing(num_entries=4)
        ring.info(5, "hello world")
        entries = ring.peek()
        assert len(entries) == 1
        assert entries[0]["level"] == log.LEVEL_INFO
        assert entries[0]["module_id"] == 5
        assert entries[0]["message"] == "hello world"

    def test_write_stores_correct_timestamp(self):
        ring = LogRing(num_entries=4)
        import time
        before = time.monotonic()
        ring.info(0, "ts check")
        after = time.monotonic()
        entries = ring.peek()
        assert len(entries) == 1
        ts = entries[0]["timestamp"]
        assert before <= ts <= after

    def test_write_all_levels(self):
        ring = LogRing(num_entries=8)
        ring.debug(0, "d")
        ring.info(0, "i")
        ring.warn(0, "w")
        ring.error(0, "e")
        entries = ring.peek()
        assert len(entries) == 4
        levels = [e["level"] for e in entries]
        assert levels == [log.LEVEL_DEBUG, log.LEVEL_INFO, log.LEVEL_WARN, log.LEVEL_ERROR]


class TestLogRingOverflow:
    def test_overflow_overwrites_oldest(self):
        ring = LogRing(num_entries=4)
        ring.info(0, "a")
        ring.info(0, "b")
        ring.info(0, "c")
        ring.info(0, "d")
        ring.info(0, "e")  # overwrites slot 0
        entries = ring.peek()
        assert len(entries) == 4
        msgs = [e["message"] for e in entries]
        assert msgs == ["b", "c", "d", "e"]

    def test_overflow_multi_cycle(self):
        ring = LogRing(num_entries=2)
        for i in range(6):
            ring.info(0, f"m{i}")
        entries = ring.peek()
        assert len(entries) == 2
        assert entries[0]["message"] == "m4"
        assert entries[1]["message"] == "m5"


class TestLogRingPeek:
    def test_peek_empty_ring(self):
        ring = LogRing(num_entries=4)
        assert ring.peek() == []


class TestLogRingClear:
    def test_clear_resets_positions(self):
        ring = LogRing(num_entries=4)
        ring.info(0, "a")
        ring.info(0, "b")
        ring.clear()
        stats = ring.stats()
        assert stats["used"] == 0
        assert ring.peek() == []

    def test_clear_after_overflow(self):
        ring = LogRing(num_entries=3)
        ring.info(0, "a")
        ring.info(0, "b")
        ring.info(0, "c")
        ring.info(0, "d")  # overflow
        ring.clear()
        entries = ring.peek()
        assert entries == []


class TestLogRingStats:
    def test_stats_fields(self):
        ring = LogRing(num_entries=4)
        stats = ring.stats()
        for key in ("capacity", "used", "free", "total_writes", "total_flushes"):
            assert key in stats

    def test_stats_capacity(self):
        ring = LogRing(num_entries=512)
        assert ring.stats()["capacity"] == 512

    def test_stats_used(self):
        ring = LogRing(num_entries=4)
        ring.info(0, "a")
        ring.info(0, "b")
        stats = ring.stats()
        assert stats["used"] == 2
        assert stats["free"] == 2

    def test_stats_total_writes(self):
        ring = LogRing(num_entries=4)
        for _ in range(7):
            ring.info(0, "x")
        assert ring.stats()["total_writes"] == 7


class TestLogRingFlush:
    def test_flush_prints_output(self, capsys):
        ring = LogRing(num_entries=4)
        ring.info(2, "flush me")
        ring.flush()
        captured = capsys.readouterr()
        assert "flush me" in captured.out

    def test_flush_empty_ring_no_output(self, capsys):
        ring = LogRing(num_entries=4)
        ring.flush()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_flush_clears_buffer(self, capsys):
        ring = LogRing(num_entries=4)
        ring.info(2, "msg")
        ring.flush()
        ring.flush()  # second flush should be empty
        captured = capsys.readouterr()
        assert captured.out.count("msg") == 1

    def test_flush_contains_level(self, capsys):
        ring = LogRing(num_entries=4)
        ring.info(7, "mod test")
        ring.flush()
        captured = capsys.readouterr()
        assert "INFO" in captured.out
        assert "mod test" in captured.out

    def test_flush_returns_count(self):
        ring = LogRing(num_entries=4)
        ring.info(0, "a")
        ring.info(0, "b")
        count = ring.flush()
        assert count == 2

    def test_flush_clears_read_pos(self):
        ring = LogRing(num_entries=4)
        ring.info(0, "a")
        ring.flush()
        stats = ring.stats()
        assert stats["used"] == 0


class TestGetRingSingleton:
    def test_returns_same_instance(self):
        r1 = get_ring()
        r2 = get_ring()
        assert r1 is r2

    def test_is_logring_instance(self):
        r = get_ring()
        assert isinstance(r, LogRing)


class TestConvenienceFunctions:
    def test_debug_writes_to_ring(self):
        ring = get_ring()
        before = ring.stats()["total_writes"]
        ring.debug(0, "test debug")
        after = ring.stats()["total_writes"]
        assert after == before + 1

    def test_warn_writes_to_ring(self):
        ring = get_ring()
        before = ring.stats()["total_writes"]
        ring.warn(0, "warn msg")
        after = ring.stats()["total_writes"]
        assert after == before + 1

    def test_module_level_debug(self):
        before = log.get_ring().stats()["total_writes"]
        log.debug(0, "module debug")
        after = log.get_ring().stats()["total_writes"]
        assert after == before + 1

    def test_module_level_info(self):
        before = log.get_ring().stats()["total_writes"]
        log.info(0, "module info")
        after = log.get_ring().stats()["total_writes"]
        assert after == before + 1

    def test_module_level_warn(self):
        before = log.get_ring().stats()["total_writes"]
        log.warn(0, "module warn")
        after = log.get_ring().stats()["total_writes"]
        assert after == before + 1

    def test_module_level_error(self):
        before = log.get_ring().stats()["total_writes"]
        log.error(0, "module error")
        after = log.get_ring().stats()["total_writes"]
        assert after == before + 1

    def test_module_level_flush(self):
        log.get_ring().info(0, "flush via module")
        count = log.flush()
        assert count >= 1
