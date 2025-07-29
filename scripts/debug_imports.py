import os
import sys

print("--- Python Executable ---")
print(sys.executable)
print("\\n--- sys.path ---")
# Print each path on a new line for clarity
for path in sys.path:
    print(path)

print("\\n--- PYTHONPATH Environment Variable ---")
print(os.environ.get("PYTHONPATH"))

print("\\n--- Current Working Directory ---")
print(os.getcwd())
print("\\n--- sys.version ---")
print(sys.version)
