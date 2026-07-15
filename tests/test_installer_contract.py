from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / "install.sh"
PYPROJECT = ROOT / "pyproject.toml"


def test_installer_freezes_external_inputs_and_fails_closed_before_release() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert 'UV_VERSION="0.11.28"' in source
    assert 'MODEL_REPO="kroffske/shellcue-lfm2.5-230m-alpha"' in source
    assert 'MODEL_REVISION="ae5b48546645926a6839df554a46596a8a19498e"' in source
    assert (
        'MODEL_WEIGHTS_SHA256="c4f7973c48eb04fa2e8013f0d03171fcfb4ee27c157dea31e96020b12b84fb53"'
        in source
    )
    assert (
        'MODEL_CHECKSUMS_SHA256="d781bffab68c5c667eb28f9a1591a7bb2347c16a63f39893f45d118eae5f4025"'
        in source
    )
    assert "model_is_accepted" in source
    assert "shasum -a 256 -c checksums.sha256" in source
    assert 'shellcue @ file://${package_file}' in source
    assert "shellcue[neural]" not in source
    assert 'shellcue 0.1.0a3' in source
    assert "SHELLCUE_PACKAGE_URL" in source
    assert "SHELLCUE_PACKAGE_SHA256" in source
    assert "public alpha package is not finalized" in source
    assert "wait_for_service_ready" in source
    assert "shellcue daemon status" in source
    assert "stop_current_shellcue" in source
    assert "shellcue service stop" in source


def test_neural_runtime_dependencies_are_mandatory() -> None:
    source = PYPROJECT.read_text(encoding="utf-8")
    mandatory = source.split("[project.optional-dependencies]", 1)[0]

    assert '"safetensors>=0.4"' in mandatory
    assert '"tokenizers>=0.20"' in mandatory
    assert '"torch>=2.2"' in mandatory
    assert '"transformers>=5.0.0"' in mandatory
    assert "\nneural = [" not in source


def test_installer_never_signals_or_invokes_legacy_pid_fallback() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert "os.kill" not in source
    assert "smart-bash daemon" not in source
    assert "no PID signal attempted" in source
    assert "client.connect(str(path))" in source
    assert "socket does not match the legacy daemon protocol" in source
    assert "legacy daemon shutdown requested over confirmed live socket" in source


def test_installer_has_valid_bash_syntax() -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is unavailable")

    result = subprocess.run(
        [bash, "-n", str(INSTALLER)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
