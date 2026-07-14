"""Contract tests for Mneme's zero-dependency converter adapter."""
from __future__ import annotations

import pytest

from mneme import cli, convert


def test_auto_pdf_reports_accurate_options_when_no_backend(monkeypatch, tmp_path, capsys):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"not a real PDF")
    output = tmp_path / "report.md"
    monkeypatch.setattr(convert.shutil, "which", lambda _: None)

    rc = cli.main(["convert", str(source), "--output", str(output)])

    assert rc == 1
    err = capsys.readouterr().err
    assert "markitdown report.pdf -o report.md" in err
    assert "pdftotext report.pdf report.txt" in err
    assert "OCR tool required" in err
    assert "pandoc" not in err
    assert not output.exists()


def test_convert_requires_explicit_nonexisting_output(tmp_path, capsys):
    source = tmp_path / "report.docx"
    source.write_bytes(b"source")
    output = tmp_path / "report.md"
    output.write_text("preserve me", encoding="utf-8")

    rc = cli.main(["convert", str(source), "--output", str(output)])

    assert rc == 1
    assert "refusing to overwrite" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "preserve me"


def test_pandoc_is_not_offered_for_pdf(tmp_path):
    source = tmp_path / "report.pdf"
    assert [backend.name for backend in convert.supported_backends(source)] == [
        "markitdown", "pdftotext"
    ]


def test_requested_backend_must_support_source(monkeypatch, tmp_path):
    source = tmp_path / "slides.pptx"
    source.write_bytes(b"source")
    monkeypatch.setattr(convert.shutil, "which", lambda _: "/usr/local/bin/pandoc")

    with pytest.raises(convert.ConvertError, match="does not support"):
        convert.select_backend(source, "pandoc")


def test_markitdown_uses_argument_list_and_reports_backend(monkeypatch, tmp_path, capsys):
    source = tmp_path / "a file.pdf"
    output = tmp_path / "derived.md"
    source.write_bytes(b"source")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        output.write_text("derived", encoding="utf-8")

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr(convert.shutil, "which", lambda _: "/usr/local/bin/markitdown")
    monkeypatch.setattr(convert.subprocess, "run", fake_run)

    rc = cli.main(["convert", str(source), "--output", str(output)])

    assert rc == 0
    assert calls == [
        (["markitdown", str(source), "-o", str(output)], {"capture_output": True, "text": True, "check": False})
    ]
    assert "converted via markitdown" in capsys.readouterr().out
