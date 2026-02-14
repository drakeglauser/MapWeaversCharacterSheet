# SheetTool.pyw — Double-click this file to launch without a terminal window.
# On Windows, .pyw files run with pythonw.exe which has no console.
import sys
import os

# Ensure stdout/stderr exist (pythonw sets them to None)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

from sheet_tool import dm_login_dialog, pick_character_file, CharacterApp

is_dm = dm_login_dialog()

path = pick_character_file()
if is_dm:
    initial_paths = [path] if path else []
    app = CharacterApp(initial_paths, is_dm=True)
else:
    if not path:
        sys.exit(0)
    app = CharacterApp([path], is_dm=False)
app.mainloop()
