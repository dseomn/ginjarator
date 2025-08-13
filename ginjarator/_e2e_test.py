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

from collections.abc import Generator, Mapping, Sequence
import contextlib
import logging
import os
import pathlib
import subprocess
import textwrap
import time

import pytest

_NINJA_ARGS = ("ninja", "-d", "explain")

pytestmark = pytest.mark.e2e


def _sleep_for_mtime() -> None:
    """Prevents writes before/after calling this from having the same mtime."""
    time.sleep(0.01)


@pytest.fixture(autouse=True)
def _root_path(tmp_path: pathlib.Path) -> Generator[None, None, None]:
    logging.debug("root_path = %r", tmp_path)
    with contextlib.chdir(tmp_path):
        pathlib.Path("ginjarator.toml").write_text("")
        pathlib.Path("src").mkdir()
        pathlib.Path("build").mkdir()
        yield


def _run(
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        env=env,
    )
    returncode = result.returncode
    if expect_success:
        assert returncode == 0, result.stdout
    else:
        assert returncode != 0, result.stdout
    return result


def _run_init() -> None:
    _run(("ginjarator", "init"))


def _assert_ninja_noop() -> None:
    """Asserts that another ninja run does nothing."""
    # TODO: https://github.com/ninja-build/ninja/issues/905 - Remove this hack.
    message_when_building = "no-op expected, but ninja is doing: "
    result = _run(
        (*_NINJA_ARGS, "--verbose"),
        env={**os.environ, "NINJA_STATUS": message_when_building},
    )
    assert message_when_building not in result.stdout


def test_assert_ninja_noop() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            ninja_templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            rule write
                command = printf contents > $out
            build build/out: write
            """
        )
    )
    _run_init()

    with pytest.raises(AssertionError, match=r"no-op expected"):
        _assert_ninja_noop()


def _run_ninja() -> None:
    _run(_NINJA_ARGS)
    _assert_ninja_noop()
    _run((*_NINJA_ARGS, "-t", "cleandead"))
    _run((*_NINJA_ARGS, "-t", "missingdeps"))
    _assert_ninja_noop()


def _run_clean() -> None:
    _run((*_NINJA_ARGS, "-t", "clean"))


def test_empty_project() -> None:
    _run_init()
    _run_ninja()

    _run_clean()

    _run_ninja()


def test_ninja_template() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            ninja_templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    # Note that the rule name here is the same as one that ginjarator uses
    # internally, but they're in different scopes.
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            rule init
                command = printf contents > $out
            build build/out: init
            """
        )
    )

    _run_init()
    _run_ninja()

    assert pathlib.Path("build/out").read_text() == "contents"

    _run_clean()

    assert not pathlib.Path("build/out").exists()

    _run_ninja()

    assert pathlib.Path("build/out").read_text() == "contents"


def test_add_ninja_template() -> None:
    _run_init()
    _run_ninja()

    _sleep_for_mtime()
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            ninja_templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            rule write
                command = printf contents > $out
            build build/out: write
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/out").read_text() == "contents"


def test_remove_ninja_template() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            ninja_templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            rule write
                command = printf contents > $out
            build build/out: write
            """
        )
    )

    _run_init()
    _run_ninja()

    _sleep_for_mtime()
    pathlib.Path("ginjarator.toml").write_text("")
    pathlib.Path("src/foo.jinja").unlink()

    _run_ninja()

    assert not pathlib.Path("build/out").exists()


def test_update_ninja_template_dependency() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            ninja_templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/included.jinja").write_text("")
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            {% include "src/included.jinja" %}
            """
        )
    )

    _run_init()
    _run_ninja()

    _sleep_for_mtime()
    pathlib.Path("src/included.jinja").write_text(
        textwrap.dedent(
            """\
            rule write
                command = printf contents > $out
            build build/out: write
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/out").read_text() == "contents"


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

    _run_clean()

    assert not pathlib.Path("build/out-1").exists()
    assert not pathlib.Path("build/out-2").exists()

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

    _run_clean()

    assert not pathlib.Path("build/out-1").exists()
    assert not pathlib.Path("build/out-2").exists()

    _run_ninja()

    assert pathlib.Path("build/out-1").read_text() == "contents-1"
    assert pathlib.Path("build/out-2").read_text() == "contents-2"


def test_template_missing_dependency() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/template-2.jinja",
            ]
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
    _run(_NINJA_ARGS, expect_success=False)


@pytest.mark.xfail(
    condition=(
        subprocess.run(
            ("ninja", "--version"),
            stdout=subprocess.PIPE,
            check=True,
            text=True,
        ).stdout.strip()
        == "1.13.0"
    ),
    reason="https://github.com/ninja-build/ninja/issues/2621",
)
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
    _run(_NINJA_ARGS, expect_success=False)


def test_update_template() -> None:
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

    _sleep_for_mtime()
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out", "new-contents") %}
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/out").read_text() == "new-contents"


def test_update_template_dependency_scan_and_render() -> None:
    """Tests updating a dependency of both the scan and render passes."""
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/foo.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/foo-in").write_text("contents")
    pathlib.Path("src/foo.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text(
                "build/out",
                ginjarator.fs.read_text("src/foo-in"),
            ) %}
            """
        )
    )

    _run_init()
    _run_ninja()

    _sleep_for_mtime()
    pathlib.Path("src/foo-in").write_text("new-contents")

    _run_ninja()

    assert pathlib.Path("build/out").read_text() == "new-contents"


def test_update_template_dependency_render_only() -> None:
    """Tests updating a dependency of only the render pass."""
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

    _sleep_for_mtime()
    pathlib.Path("src/template-2.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text("build/out-2", "new-contents-2") %}
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/out-1").read_text() == "new-contents-1"
    assert pathlib.Path("build/out-2").read_text() == "new-contents-2"


def test_add_template() -> None:
    _run_init()
    _run_ninja()

    _sleep_for_mtime()
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

    _sleep_for_mtime()
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

    _sleep_for_mtime()
    pathlib.Path("ginjarator.toml").write_text("")
    pathlib.Path("src/foo.jinja").unlink()

    _run_ninja()

    assert not pathlib.Path("build/out").exists()


@pytest.mark.xfail(reason="https://github.com/ninja-build/ninja/issues/2617")
def test_remove_template_that_created_directory() -> None:
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
            {% do ginjarator.fs.write_text("build/dir/out", "contents") %}
            """
        )
    )

    _run_init()
    _run_ninja()

    _sleep_for_mtime()
    pathlib.Path("ginjarator.toml").write_text("")
    pathlib.Path("src/foo.jinja").unlink()

    _run_ninja()

    assert not pathlib.Path("build/dir/out").exists()
    assert not pathlib.Path("build/dir").exists()


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

    _sleep_for_mtime()
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


def test_remove_template_output() -> None:
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

    _sleep_for_mtime()
    pathlib.Path("src/foo.jinja").write_text("")

    _run_ninja()

    assert not pathlib.Path("build/out").exists()


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

    _sleep_for_mtime()
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


@pytest.mark.xfail(reason="https://github.com/ninja-build/ninja/issues/2610")
@pytest.mark.parametrize(
    "change_path,change_contents",
    (
        ("src/template-1.jinja", ""),
        ("ginjarator.toml", "templates = ['src/template-2.jinja']"),
    ),
)
def test_template_depends_on_removed_output(
    change_path: str,
    change_contents: str,
) -> None:
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

    pathlib.Path(change_path).write_text(change_contents)

    _run(_NINJA_ARGS, expect_success=False)


def test_template_depends_on_custom_ninja() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            ninja_templates = [
                "src/ninja.jinja",
            ]
            templates = [
                "src/template.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/ninja.jinja").write_text(
        textwrap.dedent(
            """\
            rule write
                command = printf before-normal-template > $out
            build build/ninja-out: write
            """
        )
    )
    pathlib.Path("src/template.jinja").write_text(
        textwrap.dedent(
            """\
            {% set ninja_out = ginjarator.fs.read_text("build/ninja-out") %}
            {% if ninja_out is none %}
                {% do ginjarator.fs.add_output("build/template-out") %}
            {% else %}
                {% do ginjarator.fs.write_text(
                    "build/template-out",
                    ninja_out.replace("before", "after"),
                ) %}
            {% endif %}
            """
        )
    )

    _run_init()
    _run_ninja()

    assert (
        pathlib.Path("build/ninja-out").read_text() == "before-normal-template"
    )
    assert (
        pathlib.Path("build/template-out").read_text()
        == "after-normal-template"
    )

    pathlib.Path("src/ninja.jinja").write_text(
        textwrap.dedent(
            """\
            rule write
                command = printf before-normal-template-2 > $out
            build build/ninja-out: write
            """
        )
    )

    _run_ninja()

    assert (
        pathlib.Path("build/ninja-out").read_text()
        == "before-normal-template-2"
    )
    assert (
        pathlib.Path("build/template-out").read_text()
        == "after-normal-template-2"
    )


def test_custom_ninja_depends_on_template_implicitly() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            ninja_templates = [
                "src/ninja.jinja",
            ]
            templates = [
                "src/template.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/ninja.jinja").write_text(
        textwrap.dedent(
            """\
            rule dyndep
                command = printf $
                    'ninja_dyndep_version = 1\\n%s\\n' $
                    'build build/ninja-out: dyndep | build/template-out' $
                    > $out
            rule transform
                command = sed 's/before/after/' < $fake_in > $out
                dyndep = $out.dd
            build build/ninja-out.dd: dyndep
            build $
                    build/ninja-out $
                    : $
                    transform $
                    || $
                    build/ninja-out.dd $
                    {{ ginjarator.to_ninja(ginjarator.paths.scan_done_stamp) }}
                fake_in = build/template-out
            """
        )
    )
    pathlib.Path("src/template.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text(
                "build/template-out",
                "before-ninja",
            ) %}
            """
        )
    )

    _run_init()
    _run_ninja()

    assert pathlib.Path("build/template-out").read_text() == "before-ninja"
    assert pathlib.Path("build/ninja-out").read_text() == "after-ninja"

    pathlib.Path("src/template.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text(
                "build/template-out",
                "before-ninja-2",
            ) %}
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/template-out").read_text() == "before-ninja-2"
    assert pathlib.Path("build/ninja-out").read_text() == "after-ninja-2"


def test_custom_ninja_depends_on_template_explicitly() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            ninja_templates = [
                "src/ninja.jinja",
            ]
            templates = [
                "src/template.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/ninja.jinja").write_text(
        textwrap.dedent(
            """\
            rule transform
                command = $
                    sed 's/before/after/' < $fake_in > $out && $
                    printf '%s: %s\\n' $out $fake_in > $out.d
                depfile = $out.d
            build $
                    build/ninja-out $
                    : $
                    transform $
                    || $
                    {{ ginjarator.to_ninja(
                        ginjarator.paths.template_render_stamp(
                            "src/template.jinja"
                        )
                    ) }}
                fake_in = build/template-out
            """
        )
    )
    pathlib.Path("src/template.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text(
                "build/template-out",
                "before-ninja",
            ) %}
            """
        )
    )

    _run_init()
    _run_ninja()

    assert pathlib.Path("build/template-out").read_text() == "before-ninja"
    assert pathlib.Path("build/ninja-out").read_text() == "after-ninja"

    pathlib.Path("src/template.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text(
                "build/template-out",
                "before-ninja-2",
            ) %}
            """
        )
    )

    _run_ninja()

    assert pathlib.Path("build/template-out").read_text() == "before-ninja-2"
    assert pathlib.Path("build/ninja-out").read_text() == "after-ninja-2"


def test_non_minimal_config_change_does_not_rebuild_all() -> None:
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = [
                "src/kumquat.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/kumquat.jinja").write_text("")

    _run_init()
    _run_ninja()

    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            # This new comment does not change the minimal config file.
            templates = [
                "src/kumquat.jinja",
            ]
            """
        )
    )

    ninja_result = _run((*_NINJA_ARGS, "--verbose"))

    assert "src/kumquat.jinja" not in ninja_result.stdout


def test_error_when_path_removed_from_config() -> None:
    pathlib.Path("other_src").mkdir()
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            source_paths = [
                "src",
                "other_src",
            ]
            templates = [
                "src/template.jinja",
            ]
            """
        )
    )
    pathlib.Path("src/template.jinja").write_text(
        textwrap.dedent(
            """\
            {% do ginjarator.fs.write_text(
                "build/out",
                ginjarator.fs.read_text("other_src/in").replace("in", "out"),
            ) %}
            """
        )
    )
    pathlib.Path("other_src/in").write_text("contents-in")

    _run_init()
    _run_ninja()

    _sleep_for_mtime()
    pathlib.Path("ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            source_paths = [
                "src",
            ]
            templates = [
                "src/template.jinja",
            ]
            """
        )
    )

    _run(_NINJA_ARGS, expect_success=False)
