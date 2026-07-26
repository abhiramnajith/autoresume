# vhs script for the usage demo GIF.
# Regenerate from the repo root with:  vhs demo/autoresume.tape
# Requires the package installed in ./venv (pip install -e '.[dev]').

Output demo/autoresume.gif

Set Shell "bash"
Set FontSize 18
Set Width 1100
Set Height 640
Set Padding 24
Set Theme "Dracula"
Set TypingSpeed 55ms

# Hidden setup: activate the venv and put the demo `claude` stand-in on PATH.
Hide
Type "source venv/bin/activate && export PATH=$PWD/demo/bin:$PATH && clear"
Enter
Sleep 700ms
Show

# The demo: wrap `claude`, hit a (simulated) limit, wait, auto-resume.
# --reset-buffer 3 keeps the wait short enough to watch.
Type "autoresume --reset-buffer 3 -- claude"
Sleep 800ms
Enter
Sleep 12s
