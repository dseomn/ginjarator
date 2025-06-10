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

import jinja2
import pytest

from ginjarator import filesystem
from ginjarator import render


@pytest.fixture(name="root_path")
def _root_path(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "ginjarator.toml").write_text("")
    (tmp_path / "src").mkdir()
    return tmp_path


@pytest.mark.parametrize(
    "template_name,error_regex",
    (
        ("src/kumquat", r"kumquat"),
        ("build/kumquat", r"kumquat.* not built yet"),
    ),
)
def test_render_template_not_found(
    template_name: str,
    error_regex: str,
    root_path: pathlib.Path,
) -> None:
    api = render.Api(
        fs=filesystem.Filesystem(root_path, mode=filesystem.ScanMode()),
    )
    with pytest.raises(jinja2.TemplateNotFound, match=error_regex):
        render.render(api, template_name, scan=True)


def test_render_scan(root_path: pathlib.Path) -> None:
    template_state_path = root_path / filesystem.template_state_path(
        "src/template.jinja"
    )
    api = render.Api(
        fs=filesystem.Filesystem(root_path, mode=filesystem.ScanMode()),
    )
    (root_path / "src/template.jinja").write_text(
        """
        {% call ginjarator.fs.write_text_macro("build/output") %}
            {{- 1 + 2 -}}
        {% endcall %}
        """
    )

    render.render(api, "src/template.jinja", scan=True)

    assert not (root_path / "build/output").exists()
    assert json.loads(template_state_path.read_text()) == dict(
        dependencies=[str(root_path / "src/template.jinja")],
        outputs=sorted(
            (
                str(root_path / "build/output"),
                str(template_state_path),
            )
        ),
    )


def test_render_render(root_path: pathlib.Path) -> None:
    template_state_path = root_path / filesystem.template_state_path(
        "src/template.jinja"
    )
    api = render.Api(
        fs=filesystem.Filesystem(
            root_path,
            mode=filesystem.RenderMode(
                dependencies=(root_path / "src/template.jinja",),
                outputs=(
                    root_path / "build/output",
                    template_state_path,
                ),
            ),
        ),
    )
    (root_path / "src/template.jinja").write_text(
        """
        {% call ginjarator.fs.write_text_macro("build/output") %}
            {{- 1 + 2 -}}
        {% endcall %}
        """
    )

    render.render(api, "src/template.jinja", scan=False)

    assert (root_path / "build/output").read_text() == "3"
