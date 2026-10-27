"""The self-check passes on a working install, and spots a busy port."""
from __future__ import annotations

import socket

from app import doctor
from app.config import SETTINGS


def test_the_self_check_passes_here(capsys):
    result = doctor.run(verbose=True)
    out = capsys.readouterr().out
    assert result["ok"] is True, result["problems"]
    assert "analysis worker starts and answers" in out
    assert "Everything needed to run the app is in place." in out
    assert out.count("FAIL") == 0


def test_a_busy_port_is_reported():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((SETTINGS.host, 0))
        port = s.getsockname()[1]
        s.listen(1)
        assert doctor.port_free(SETTINGS.host, port) is False
    assert doctor.port_free(SETTINGS.host, port) is True
