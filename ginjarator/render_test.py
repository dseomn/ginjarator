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
    return tmp_path


@pytest.fixture(name="fs")
def _fs(root_path: pathlib.Path) -> filesystem.Filesystem:
    return filesystem.Filesystem(
        root_path,
        read_allow=(pathlib.Path("."),),
        write_allow=(pathlib.Path("."),),
    )


@pytest.fixture(name="api")
def _api(fs: filesystem.Filesystem) -> render.Api:
    return render.Api(fs=fs)


def test_render_template_not_found(api: render.Api) -> None:
    with pytest.raises(jinja2.TemplateNotFound, match="kumquat"):
        render.render(api, "kumquat", delete_created_files_on_error=False)


@pytest.mark.parametrize("delete_created_files_on_error", (True, False))
def test_render_error(
    delete_created_files_on_error: bool,
    root_path: pathlib.Path,
    api: render.Api,
) -> None:
    (root_path / "template.jinja").write_text(
        """
        {% do ginjarator.fs.write_text("output", "some text") %}
        {{ this_variable_is_not_defined }}
        """
    )

    with pytest.raises(jinja2.UndefinedError):
        render.render(
            api,
            "template.jinja",
            delete_created_files_on_error=delete_created_files_on_error,
        )

    assert (root_path / "output").exists() == (
        not delete_created_files_on_error
    )


def test_render(root_path: pathlib.Path, api: render.Api) -> None:
    (root_path / "template.jinja").write_text(
        """
        {% call ginjarator.fs.write_text_macro("output") %}
            {{- 1 + 2 -}}
        {% endcall %}
        """
    )
    template_state_path = root_path / filesystem.template_state_path(
        "template.jinja"
    )

    render.render(api, "template.jinja", delete_created_files_on_error=False)

    assert (root_path / "output").read_text() == "3"
    assert json.loads(template_state_path.read_text()) == dict(
        dependencies=[str(root_path / "template.jinja")],
        outputs=sorted(
            (
                str(root_path / "output"),
                str(template_state_path),
            )
        ),
    )
