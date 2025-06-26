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

import json
import pathlib
import textwrap

import jinja2
import pytest

from ginjarator import _filesystem
from ginjarator import _paths
from ginjarator import _template


@pytest.fixture(name="root_path")
def _root_path(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            source_paths = ["src"]
            build_paths = ["build"]
            python_paths = ["src/py"]
            """
        )
    )
    (tmp_path / ".ginjarator").mkdir()
    (tmp_path / ".ginjarator/config").mkdir()
    (tmp_path / ".ginjarator/config/minimal.json").write_text(
        json.dumps(
            dict(
                source_paths=["src"],
                build_paths=["build"],
                python_paths=["src/py"],
            )
        )
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src/py").mkdir()
    return tmp_path


def test_api(root_path: pathlib.Path) -> None:
    api = _template.Api(
        current_template=_paths.Filesystem("foo"),
        fs=_filesystem.Filesystem(root_path),
    )

    with _template.set_api(api):
        assert _template.api() is api


def test_api_error() -> None:
    with pytest.raises(LookupError):
        _template.api()


def test_api_available_to_project_python(root_path: pathlib.Path) -> None:
    template_state_path = root_path / _paths.template_state(
        "src/template.jinja"
    )
    (
        root_path
        / "src/py"
        / "ginjarator__template_test__test_api_available_to_project_python.py"
    ).write_text(
        textwrap.dedent(
            """
            import ginjarator

            def write():
                ginjarator.api().fs.write_text("build/output", "kumquat")
            """
        )
    )
    (root_path / "src/template.jinja").write_text(
        """
        {% set module = ginjarator.py.import_(
            "ginjarator__template_test__test_api_available_to_project_python"
        ) %}
        {% do module.write() %}
        """
    )

    _template.scan(_paths.Filesystem("src/template.jinja"), root_path=root_path)

    assert json.loads(template_state_path.read_text())["outputs"] == [
        "build/output"
    ]


@pytest.mark.parametrize(
    "template_path,error_regex",
    (
        ("src/kumquat", r"kumquat"),
        ("build/kumquat", r"kumquat.* not built yet"),
    ),
)
def test_loader_template_not_found(
    template_path: str,
    error_regex: str,
    root_path: pathlib.Path,
) -> None:
    with pytest.raises(jinja2.TemplateNotFound, match=error_regex):
        _template.scan(_paths.Filesystem(template_path), root_path=root_path)


def test_ninja(root_path: pathlib.Path) -> None:
    (root_path / "src/template.jinja").write_text("contents")
    internal_fs = _filesystem.Filesystem(root_path)

    rendered = _template.ninja(
        _paths.Filesystem("src/template.jinja"),
        internal_fs=internal_fs,
    )

    assert rendered == "contents"
    assert set(internal_fs.dependencies) >= {
        _paths.Filesystem("src/template.jinja"),
    }


def test_scan(root_path: pathlib.Path) -> None:
    template_state_path = root_path / _paths.template_state(
        "src/template.jinja"
    )
    (root_path / "src/template.jinja").write_text(
        """
        {% call ginjarator.fs.write_text_macro("build/output") %}
            {{- 1 + 2 -}}
        {% endcall %}
        """
    )

    _template.scan(_paths.Filesystem("src/template.jinja"), root_path=root_path)

    assert not (root_path / "build/output").exists()
    assert json.loads(template_state_path.read_text()) == dict(
        dependencies=[
            ".ginjarator/config/minimal.json",
            "src/template.jinja",
        ],
        outputs=["build/output"],
    )
    assert (root_path / _paths.template_depfile("src/template.jinja")).exists()
    assert (root_path / _paths.template_dyndep("src/template.jinja")).exists()


def test_render(root_path: pathlib.Path) -> None:
    template_state_path = root_path / _paths.template_state(
        "src/template.jinja"
    )
    template_state_path.parent.mkdir(parents=True, exist_ok=True)
    template_state_path.write_text(
        json.dumps(
            dict(
                dependencies=[
                    ".ginjarator/config/minimal.json",
                    "src/template.jinja",
                ],
                outputs=["build/output"],
            )
        )
    )
    (root_path / "src/template.jinja").write_text(
        """
        {% call ginjarator.fs.write_text_macro("build/output") %}
            {{- 1 + 2 -}}
        {% endcall %}
        """
    )

    _template.render(
        _paths.Filesystem("src/template.jinja"),
        root_path=root_path,
    )

    assert (root_path / "build/output").read_text() == "3"
    assert (
        root_path / _paths.template_render_stamp("src/template.jinja")
    ).exists()
