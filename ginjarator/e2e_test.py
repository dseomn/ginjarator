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
"""End-to-end tests on the installed program."""

from collections.abc import Generator, Sequence
import contextlib
import pathlib
import subprocess
import textwrap

import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _root_path(tmp_path: pathlib.Path) -> Generator[None, None, None]:
    with contextlib.chdir(tmp_path):
        pathlib.Path("ginjarator.toml").write_text("")
        pathlib.Path("src").mkdir()
        pathlib.Path("build").mkdir()
        yield


def _run(args: Sequence[str], *, expect_success: bool = True) -> None:
    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    returncode = result.returncode
    if expect_success:
        assert returncode == 0, result.stdout
    else:
        assert returncode != 0, result.stdout


def _run_init() -> None:
    _run(("ginjarator", "init"))


def _run_ninja() -> None:
    _run(("ninja",))
    _run(("ninja", "-t", "cleandead"))
    _run(("ninja", "-t", "missingdeps"))


def test_empty_project() -> None:
    _run_init()
    _run_ninja()


def test_empty_template() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/foo.jinja").write_text("")

    _run_init()
    _run_ninja()


def test_simple() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out-1", "contents-1") %}
            {% do ginjarator.fs.write_text("build/out-2", "contents-2") %}
            """
        )
    )

    _run_init()
    _run_ninja()

    assert pathlib.Path("build/out-1").read_text() == "contents-1"
    assert pathlib.Path("build/out-2").read_text() == "contents-2"


def test_template_dependencies() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/template-1.jinja",
                "src/template-2.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/template-1.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out-1", "contents-1") %}
            """
        )
    )
    pathlib.Path("src/template-2.jinja").write_text(
        textwrap.dedent(
            """\
            {% set out_1 = ginjarator.fs.read_text("build/out-1") %}
            {% if out_1 is none %}
                {% do ginjarator.fs.add_output("build/out-2") %}
            {% else %}
                {% do ginjarator.fs.write_text(
                    "build/out-2",
                    out_1.replace("1", "2"),
                ) %}
            {% endif %}
            """
        )
    )

    _run_init()
    _run_ninja()

    assert pathlib.Path("build/out-1").read_text() == "contents-1"
    assert pathlib.Path("build/out-2").read_text() == "contents-2"


def test_conflicting_writes() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/template-1.jinja",
                "src/template-2.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/template-1.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out", "contents-1") %}
            """
        )
    )
    pathlib.Path("src/template-2.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out", "contents-2") %}
            """
        )
    )

    _run_init()
    _run(("ninja",), expect_success=False)


def test_add_template() -> None:
    _run_init()
    _run_ninja()

    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out", "contents") %}
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/out").read_text() == "contents"


def test_add_template_dependency() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/template-1.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/template-1.jinja").write_text("")

    _run_init()
    _run_ninja()

    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/template-1.jinja",
                "src/template-2.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/template-1.jinja").write_text(
        textwrap.dedent(
            """\
            {% set out_2 = ginjarator.fs.read_text("build/out-2") %}
            {% if out_2 is none %}
                {% do ginjarator.fs.add_output("build/out-1") %}
            {% else %}
                {% do ginjarator.fs.write_text(
                    "build/out-1",
                    out_2.replace("2", "1"),
                ) %}
            {% endif %}
            """
        )
    )
    pathlib.Path("src/template-2.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out-2", "contents-2") %}
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/out-1").read_text() == "contents-1"
    assert pathlib.Path("build/out-2").read_text() == "contents-2"


def test_remove_template() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out", "contents") %}
            """
        )
    )

    _run_init()
    _run_ninja()

    pathlib.Path("ginjarator.toml").write_text("")
    pathlib.Path("src/foo.jinja").unlink()

    _run_ninja()

    assert not pathlib.Path("build/out").exists()


def test_remove_template_dependency() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/template-1.jinja",
                "src/template-2.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/template-1.jinja").write_text(
        textwrap.dedent(
            """\
            {% set out_2 = ginjarator.fs.read_text("build/out-2") %}
            {% if out_2 is none %}
                {% do ginjarator.fs.add_output("build/out-1") %}
            {% else %}
                {% do ginjarator.fs.write_text(
                    "build/out-1",
                    out_2.replace("2", "1"),
                ) %}
            {% endif %}
            """
        )
    )
    pathlib.Path("src/template-2.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out-2", "contents-2") %}
            """
        )
    )

    _run_init()
    _run_ninja()

    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/template-1.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/template-1.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out-1", "new-contents-1") %}
            """
        )
    )
    pathlib.Path("src/template-2.jinja").unlink()

    _run_ninja()

    assert pathlib.Path("build/out-1").read_text() == "new-contents-1"
    assert not pathlib.Path("build/out-2").exists()


def test_template_dependency_changes_creator() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/template-1.jinja",
                "src/template-2.jinja",
                "src/template-3.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/template-1.jinja").write_text(
        textwrap.dedent(
            """\
            {% set in_1 = ginjarator.fs.read_text("build/in-1") %}
            {% if in_1 is none %}
                {% do ginjarator.fs.add_output("build/out-1") %}
            {% else %}
                {% do ginjarator.fs.write_text(
                    "build/out-1",
                    in_1.replace("in", "out"),
                ) %}
            {% endif %}
            """
        )
    )
    pathlib.Path("src/template-2.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/in-1", "contents-2-in") %}
            """
        )
    )
    pathlib.Path("src/template-3.jinja").write_text("")

    _run_init()
    _run_ninja()

    pathlib.Path("src/template-2.jinja").write_text("")
    pathlib.Path("src/template-3.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/in-1", "contents-3-in") %}
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/in-1").read_text() == "contents-3-in"
    assert pathlib.Path("build/out-1").read_text() == "contents-3-out"
