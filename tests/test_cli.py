import pytest

import autoresume
from autoresume.cli import build_parser


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0
    assert autoresume.__version__ in capsys.readouterr().out


def test_version_matches_packaging_metadata():
    """__version__ and pyproject must not drift apart."""
    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = re.search(r'^version = "(.+)"$', pyproject.read_text(), re.M).group(1)
    assert declared == autoresume.__version__
