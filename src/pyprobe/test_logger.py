from pyprobe.utils.Log_engine import PyProbeDiagnostics

# Boot up the engine
diag = PyProbeDiagnostics()

print("=============================")
print("🧪 TESTING SUCCESS PIPELINE")
print("=============================")
# Pretend we just successfully mutated a list
dummy_list = [1, 2, 3]
diag.record_success(
    address=id(dummy_list), 
    target_obj=dummy_list, 
    steps_string="[1/3: BACKUP_OK] -> [2/3: WRITE_OK] -> [3/3: VERIFY_OK]"
)

print("\n=============================")
print("🔥 TESTING CRITICAL FAULT")
print("=============================")
try:
    # Force a deliberate Python crash (ZeroDivisionError)
    math_crash = 1 / 0
except Exception as e:
    # Throw it to the logger!
    diag.record_fault(
        error=e, 
        address=0xDEADBEEF, 
        target_obj=None, 
        critical=True, 
        steps_string="[1/3: BACKUP_OK] -> [2/3: MATH_CRASH]"
    )

print("\n=============================")
print("🧠 TESTING RAM BUFFER")
print("=============================")
print(f"Total faults captured in active RAM: {len(diag.buffer)}")
print(f"Name of the last error caught: {diag.buffer[-1].error_class}")
print(f"Timestamp: {diag.buffer[-1].timestamp}")