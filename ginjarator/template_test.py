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
from ginjarator import template


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
def test_loader_template_not_found(
    template_name: str,
    error_regex: str,
    root_path: pathlib.Path,
) -> None:
    with pytest.raises(jinja2.TemplateNotFound, match=error_regex):
        template.scan(template_name, root_path=root_path)


def test_scan(root_path: pathlib.Path) -> None:
    template_state_path = root_path / filesystem.template_state_path(
        "src/template.jinja"
    )
    (root_path / "src/template.jinja").write_text(
        """
        {% call ginjarator.fs.write_text_macro("build/output") %}
            {{- 1 + 2 -}}
        {% endcall %}
        """
    )

    template.scan("src/template.jinja", root_path=root_path)

    assert not (root_path / "build/output").exists()
    assert json.loads(template_state_path.read_text()) == dict(
        dependencies=[str(root_path / "src/template.jinja")],
        outputs=[str(root_path / "build/output")],
    )
    assert (
        root_path / filesystem.template_depfile_path("src/template.jinja")
    ).exists()
    assert (
        root_path / filesystem.template_dyndep_path("src/template.jinja")
    ).exists()


def test_render(root_path: pathlib.Path) -> None:
    template_state_path = root_path / filesystem.template_state_path(
        "src/template.jinja"
    )
    template_state_path.parent.mkdir(parents=True, exist_ok=True)
    template_state_path.write_text(
        json.dumps(
            dict(
                dependencies=[str(root_path / "src/template.jinja")],
                outputs=[str(root_path / "build/output")],
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

    template.render("src/template.jinja", root_path=root_path)

    assert (root_path / "build/output").read_text() == "3"
    assert (
        root_path / filesystem.template_render_stamp_path("src/template.jinja")
    ).exists()
