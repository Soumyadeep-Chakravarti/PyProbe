import collections
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FaultSnapshot:
    """The live data structure preserved in RAM for introspection."""
    timestamp: float
    error_class: str
    address: int
    target_type: str
    message: str
    version: str = f"{sys.version_info.major}.{sys.version_info.minor}"


class PyProbeDiagnostics:
    """
    The centralized logging and telemetry system for PyProbe.
    Implemented as a singleton subsystem to ensure unified state tracking.
    """
    _instance: Optional['PyProbeDiagnostics'] = None

    def __new__(cls, log_file: str = "pyprobe_faults.log", max_buffer_size: int = 1000, write_to_disk: bool = True) -> 'PyProbeDiagnostics':
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_file: str = "pyprobe_faults.log", max_buffer_size: int = 1000, write_to_disk: bool = True):
        # Prevent re-initialization of the singleton
        if self._initialized:
            return
        
        self.log_file = log_file
        self.max_buffer_size = max_buffer_size
        self.write_to_disk = write_to_disk
        
        # Volatile runtime ring buffer (Always ON for testing)
        self.buffer: collections.deque[FaultSnapshot] = collections.deque(maxlen=self.max_buffer_size)
        # Initialize internal standard logger
        self.logger = logging.getLogger("PyProbe.Internal")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        # Only attach the physical file writer if the toggle is True
        if self.write_to_disk:
            file_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s", 
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        else:
            # Attach a NullHandler so Python doesn't complain about missing handlers
            self.logger.addHandler(logging.NullHandler())
            
        self._initialized = True

    def record_success(self, address: int, target_obj: Any, steps_string: str) -> None:
        """Outputs the ultra-clean, one-line pipeline success message."""
        obj_type = type(target_obj).__name__ if target_obj is not None else "RawPointer"
        
        # 1. Format the terminal output exactly as requested
        pipeline_line = f"[INFO] PROCESS | Type: {obj_type} | Addr: {hex(address)} | Steps: {steps_string} | Status: MUTATION_COMPLETE"
        
        # 2. Print directly to console
        print(pipeline_line)
        print("===================================")
        
        # 3. Log quietly to the physical file if enabled
        if self.write_to_disk:
            self.logger.info(pipeline_line)

    def record_fault(self, error: Exception, address: int, target_obj: Any, critical: bool = False, steps_string: str = "") -> None:
        """Ingests a fault event, saves the RAM snapshot, and triggers visual alerts if critical."""
        obj_type = type(target_obj).__name__ if target_obj is not None else "RawPointer"
        err_class = type(error).__name__
        
        # 1. Append to the memory ring buffer
        snapshot = FaultSnapshot(
            timestamp=time.time(),
            error_class=err_class,
            address=address,
            target_type=obj_type,
            message=str(error)
        )
        self.buffer.append(snapshot)
            
        # 2. Write to physical log file
        log_payload = f"CLASS: {err_class} | ADDR: {hex(address)} | TYPE: {obj_type} | MSG: {str(error)}"
        if critical:
            self.logger.error(log_payload) 
        else:
            self.logger.debug(log_payload)
        
        # 3. Intercept and print critical full-card alerts to console instantly
        if critical:
            self._broadcast_critical(snapshot, steps_string)

    def _broadcast_critical(self, snapshot: FaultSnapshot, steps_string: str) -> None:
        """Immediate, comprehensive console alert layout for critical failures."""
        print("\n=======================================================", file=sys.stderr)
        print("[CRITICAL MEMORY FAULT] Diagnostic Capture in PyProbe!", file=sys.stderr)
        print("=======================================================", file=sys.stderr)
        print(f"Exception Class    : {snapshot.error_class}", file=sys.stderr)
        print(f"Memory Address     : {hex(snapshot.address)}", file=sys.stderr)
        print(f"Target Object Type : {snapshot.target_type}", file=sys.stderr)
        print(f"Reason for Failure : {snapshot.message}", file=sys.stderr)
        print(f"Diagnostic Log File: {os.path.abspath(self.log_file)}", file=sys.stderr)
        
        # Inject the pipeline history if it exists
        if steps_string:
            print("-------------------------------------------------------", file=sys.stderr)
            print("EXECUTION PIPELINE TELEMETRY:", file=sys.stderr)
            print(f"[WARN] PROCESS | Type: {snapshot.target_type} | Addr: {hex(snapshot.address)} | Steps: {steps_string} | Status: ROLLBACK_EXEC_SAFE", file=sys.stderr)
            
        print("=======================================================\n", file=sys.stderr)

    # ── System Query API ────────────────────────────────────────────────────
    
    def get_failures_by_type(self, error_class_name: str) -> list[FaultSnapshot]:
        """Query system state programmatically for matching error footprints."""
        return [snap for snap in self.buffer if snap.error_class == error_class_name]

    def clear_runtime_buffer(self) -> None:
        """Flushes the active memory buffer."""
        self.buffer.clear()