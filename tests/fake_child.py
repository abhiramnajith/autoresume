import sys
import time

# Print a limit banner whose reset is "now", then wait for the injected resume.
sys.stdout.write("Claude usage limit reached. resets in 0 minutes\n")
sys.stdout.flush()

line = sys.stdin.readline()
if "continue" in line:
    sys.stdout.write("GOTRESUME\n")
    sys.stdout.flush()

time.sleep(0.1)
