"""Snippy entrypoint - launches the PySide6 app (see the `snippy` package).

The original Tkinter implementation this file used to contain has been
fully ported to PySide6; it's preserved in git history (before the
"Rewrite UI from Tkinter to PySide6" commit) if you ever need to reference it.
"""

from snippy.app import main

if __name__ == "__main__":
    main()
