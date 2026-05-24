"""Locate LibreOffice and convert a .pptx to PDF (headless).

The render step's first stage. LibreOffice is the engine that understands
PowerPoint layout/fonts; we hand off its PDF output to the rasterizer next.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Default install location of soffice.exe on Windows (winget/installer puts it here
# and does not add it to PATH).
_WINDOWS_DEFAULT = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
_CONVERT_TIMEOUT = 180  # seconds


class LibreOfficeNotFound(RuntimeError):
    """LibreOffice could not be located."""


class RenderError(RuntimeError):
    """LibreOffice ran but did not produce the expected PDF."""


def find_soffice() -> str:
    """Locate the LibreOffice binary, in order: `LIBREOFFICE_PATH`, then `soffice`
    / `libreoffice` on PATH, then the Windows default install location.

    Raises `LibreOfficeNotFound` with an install hint if none are present.
    """
    env = os.environ.get("LIBREOFFICE_PATH")
    if env:
        if Path(env).is_file():
            return env
        raise LibreOfficeNotFound(f"LIBREOFFICE_PATH is set but is not a file: {env}")

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found

    if sys.platform.startswith("win") and _WINDOWS_DEFAULT.is_file():
        return str(_WINDOWS_DEFAULT)

    raise LibreOfficeNotFound(
        "LibreOffice not found. Install it "
        "(winget install TheDocumentFoundation.LibreOffice) or set LIBREOFFICE_PATH "
        "to the soffice(.exe) binary."
    )


def pptx_to_pdf(
    pptx: str | Path,
    out_dir: str | Path,
    soffice: str | None = None,
    timeout: int = _CONVERT_TIMEOUT,
) -> Path:
    """Convert `pptx` to a PDF inside `out_dir`, returning the PDF path.

    Uses a throwaway user-profile dir so the conversion still works when another
    LibreOffice instance is already running (otherwise it can silently no-op).
    """
    pptx = Path(pptx)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = soffice or find_soffice()

    with tempfile.TemporaryDirectory(prefix="lo_profile_") as profile:
        profile_uri = Path(profile).resolve().as_uri()
        cmd = [
            exe,
            "--headless",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(pptx),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise RenderError(
                f"LibreOffice timed out after {timeout}s converting {pptx.name}."
            ) from exc

    if proc.returncode != 0:
        raise RenderError(
            f"LibreOffice failed ({proc.returncode}) converting {pptx.name}: "
            f"{proc.stderr.strip()}"
        )

    pdf = out_dir / f"{pptx.stem}.pdf"
    if not pdf.is_file():
        raise RenderError(
            f"LibreOffice produced no PDF for {pptx.name}. stderr: {proc.stderr.strip()}"
        )
    return pdf
