from __future__ import annotations

import sys
from pathlib import Path

# Ensure we can import as a package (api.*) even when executed as a script
APP_DIR = Path(__file__).resolve().parents[1]  # apps/api/src
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Prefer absolute import to work in both contexts
from api.app import create_app  # type: ignore

app = create_app()

if __name__ == "__main__":
    import uvicorn
    # When run directly: use the dotted path and point app-dir to APP_DIR
    uvicorn.run("api.main:app", host="0.0.0.0", port=8765, reload=True, app_dir=str(APP_DIR))
