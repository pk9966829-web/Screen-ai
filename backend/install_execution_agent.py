"""Safely install the separately supplied VOSI agent archive into this backend.

Place vosi_agent_ready.zip beside this script, then run:
    python install_execution_agent.py
"""
from __future__ import annotations

import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "vosi_agent_ready.zip"
REQUIRED = {"agent.py", "vosi_agent/router.py", "vosi_agent/config.py"}


def main() -> int:
    if not ARCHIVE.is_file():
        print(f"Missing archive: {ARCHIVE}")
        print("Copy vosi_agent_ready.zip into the backend folder and run this installer again.")
        return 2

    with zipfile.ZipFile(ARCHIVE) as archive:
        names = {name.replace("\\", "/").lstrip("./") for name in archive.namelist()}
        missing = REQUIRED - names
        if missing:
            print("Archive is not the expected VOSI execution-agent package:", ", ".join(sorted(missing)))
            return 3

        root = HERE.resolve()
        for member in archive.infolist():
            name = member.filename.replace("\\", "/")
            target = (HERE / name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"Unsafe archive path rejected: {member.filename}")
        archive.extractall(HERE)

    # The supplied archive's top-level agent.py has a stray closing parenthesis
    # after its module docstring. Normalize that exact typo before it is imported.
    entrypoint = HERE / "agent.py"
    source = entrypoint.read_text(encoding="utf-8")
    source = source.replace('\\n""")\\n\\nfrom vosi_agent.router import router', '\\n"""\\n\\nfrom vosi_agent.router import router', 1)
    entrypoint.write_text(source, encoding="utf-8")

    import py_compile
    py_compile.compile(str(entrypoint), doraise=True)
    print("VOSI execution agent files extracted and entrypoint syntax-checked.")
    print("Restart the Cherry AI backend and check GET /execution-agent/status.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
