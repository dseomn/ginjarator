# Copyright 2025 David Mandelberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=missing-module-docstring

from typing import Any

import pytest

from ginjarator import _config
from ginjarator import _paths


@pytest.mark.parametrize(
    "kwargs,error_regex",
    (
        (
            dict(
                source_paths=(_paths.Filesystem("foo"),),
                build_paths=(_paths.Filesystem("foo"),),
                python_paths=(),
            ),
            r"must not overlap",
        ),
        (
            dict(
                source_paths=(_paths.Filesystem("foo/bar"),),
                build_paths=(_paths.Filesystem("foo"),),
                python_paths=(),
            ),
            r"must not overlap",
        ),
        (
            dict(
                source_paths=(_paths.Filesystem("foo"),),
                build_paths=(_paths.Filesystem("foo/bar"),),
                python_paths=(),
            ),
            r"must not overlap",
        ),
        (
            dict(
                source_paths=(_paths.Filesystem("foo/bar"),),
                build_paths=(),
                python_paths=(_paths.Filesystem("foo"),),
            ),
            r"python_paths must all be within source_paths",
        ),
    ),
)
def test_minimal_error(kwargs: dict[str, Any], error_regex: str) -> None:
    with pytest.raises(ValueError, match=error_regex):
        _config.Minimal(**kwargs)


def test_minimal_parse_error() -> None:
    with pytest.raises(ValueError, match="templates"):
        _config.Minimal.parse(dict(templates=[]))


def test_config_parse_error() -> None:
    with pytest.raises(ValueError, match="kumquat"):
        _config.Config.parse(dict(kumquat="foo"))


@pytest.mark.parametrize(
    "config_raw,expected_config,expected_minimal_raw,expected_minimal",
    (
        (
            {},
            _config.Config(
                source_paths=(_paths.Filesystem("src"),),
                build_paths=(_paths.Filesystem("build"),),
                python_paths=(),
                ninja_templates=(),
                templates=(),
            ),
            dict(
                source_paths=["src"],
                build_paths=["build"],
                python_paths=[],
            ),
            _config.Minimal(
                source_paths=(_paths.Filesystem("src"),),
                build_paths=(_paths.Filesystem("build"),),
                python_paths=(),
            ),
        ),
        (
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
                python_paths=["src1/py", "src2/py"],
                ninja_templates=["n1.jinja", "n2.jinja"],
                templates=["t1.jinja", "t2.jinja"],
            ),
            _config.Config(
                source_paths=(
                    _paths.Filesystem("src1"),
                    _paths.Filesystem("src2"),
                ),
                build_paths=(
                    _paths.Filesystem("build1"),
                    _paths.Filesystem("build2"),
                ),
                python_paths=(
                    _paths.Filesystem("src1/py"),
                    _paths.Filesystem("src2/py"),
                ),
                ninja_templates=(
                    _paths.Filesystem("n1.jinja"),
                    _paths.Filesystem("n2.jinja"),
                ),
                templates=(
                    _paths.Filesystem("t1.jinja"),
                    _paths.Filesystem("t2.jinja"),
                ),
            ),
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
                python_paths=["src1/py", "src2/py"],
            ),
            _config.Minimal(
                source_paths=(
                    _paths.Filesystem("src1"),
                    _paths.Filesystem("src2"),
                ),
                build_paths=(
                    _paths.Filesystem("build1"),
                    _paths.Filesystem("build2"),
                ),
                python_paths=(
                    _paths.Filesystem("src1/py"),
                    _paths.Filesystem("src2/py"),
                ),
            ),
        ),
        (
            # Minimal's fields are normalized.
            dict(
                source_paths=["src2", "src2", "src1"],
                build_paths=["build2", "build2", "build1"],
                python_paths=[],
            ),
            _config.Config(
                source_paths=(
                    _paths.Filesystem("src1"),
                    _paths.Filesystem("src2"),
                ),
                build_paths=(
                    _paths.Filesystem("build1"),
                    _paths.Filesystem("build2"),
                ),
                python_paths=(),
                ninja_templates=(),
                templates=(),
            ),
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
                python_paths=[],
            ),
            _config.Minimal(
                source_paths=(
                    _paths.Filesystem("src1"),
                    _paths.Filesystem("src2"),
                ),
                build_paths=(
                    _paths.Filesystem("build1"),
                    _paths.Filesystem("build2"),
                ),
                python_paths=(),
            ),
        ),
    ),
)
def test_config(
    config_raw: Any,
    expected_config: _config.Config,
    expected_minimal_raw: Any,
    expected_minimal: _config.Minimal,
) -> None:
    actual_config = _config.Config.parse(config_raw)
    actual_minimal_raw = actual_config.serialize_minimal()
    actual_minimal = _config.Minimal.parse(actual_minimal_raw)

    assert actual_config == expected_config
    assert actual_minimal_raw == expected_minimal_raw
    assert actual_minimal == expected_minimal
