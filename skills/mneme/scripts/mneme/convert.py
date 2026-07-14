"""Adapters for user-installed document-to-text tools.

Mneme deliberately owns no document parser. This module selects and invokes
an existing local executable; it never installs software or uses a shell.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class Backend:
    name: str
    executable: str
    extensions: frozenset[str]


BACKENDS = (
    Backend("markitdown", "markitdown", frozenset({".pdf", ".docx", ".pptx"})),
    Backend("pdftotext", "pdftotext", frozenset({".pdf"})),
    Backend("pandoc", "pandoc", frozenset({".docx"})),
)


class ConvertError(RuntimeError):
    """A conversion failure suitable for concise CLI presentation."""


def supported_backends(source: Path) -> tuple[Backend, ...]:
    """Return backends that are technically applicable to ``source``."""
    suffix = source.suffix.lower()
    return tuple(backend for backend in BACKENDS if suffix in backend.extensions)


def available_backends(source: Path) -> tuple[Backend, ...]:
    """Return applicable backends whose executable is on ``PATH``."""
    return tuple(
        backend for backend in supported_backends(source)
        if shutil.which(backend.executable)
    )


def select_backend(source: Path, requested: str) -> Backend:
    """Pick an installed backend, or validate an explicitly requested one."""
    candidates = supported_backends(source)
    if not candidates:
        raise ConvertError(
            f"unsupported source type: {source.suffix or '(no extension)'}; "
            "supported types are .pdf, .docx, and .pptx"
        )
    if requested != "auto":
        backend = next((item for item in candidates if item.name == requested), None)
        if backend is None:
            supported = ", ".join(item.name for item in candidates)
            raise ConvertError(
                f"backend {requested!r} does not support {source.suffix}; "
                f"supported backends: {supported}"
            )
        if not shutil.which(backend.executable):
            raise ConvertError(f"backend {backend.name!r} is not installed")
        return backend

    available = available_backends(source)
    if available:
        return available[0]
    raise ConvertError(missing_backend_message(source))


def missing_backend_message(source: Path) -> str:
    """Describe real local alternatives without telling Mneme to install one."""
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return (
            f"cannot extract text from {source.name}: no supported converter was found.\n"
            "Available options (Mneme will not install converters automatically):\n"
            "  markitdown report.pdf -o report.md  # text-based PDF\n"
            "  pdftotext report.pdf report.txt     # text-based PDF\n"
            "  OCR tool required                    # scanned/image-only PDF"
        )
    if suffix == ".docx":
        return (
            f"cannot extract text from {source.name}: no supported converter was found.\n"
            "Available options (Mneme will not install converters automatically):\n"
            "  markitdown report.docx -o report.md\n"
            "  pandoc report.docx -t gfm -o report.md"
        )
    return (
        f"cannot extract text from {source.name}: no supported converter was found.\n"
        "Available option (Mneme will not install converters automatically):\n"
        "  markitdown slides.pptx -o slides.md"
    )


def convert(source: Path, output: Path, backend_name: str = "auto") -> Backend:
    """Convert ``source`` to ``output`` with an installed executable."""
    backend = select_backend(source, backend_name)
    if backend.name == "markitdown":
        command = [backend.executable, str(source), "-o", str(output)]
    elif backend.name == "pdftotext":
        command = [backend.executable, str(source), str(output)]
    else:  # Pandoc is deliberately limited to DOCX input by ``BACKENDS``.
        command = [backend.executable, str(source), "-t", "gfm", "-o", str(output)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ConvertError(f"could not start {backend.name}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic"
        raise ConvertError(f"{backend.name} failed: {detail}")
    if not output.is_file():
        raise ConvertError(f"{backend.name} reported success but did not create {output}")
    return backend
