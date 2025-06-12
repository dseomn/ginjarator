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
"""Build system."""

import pathlib
import shlex
import textwrap
from typing import Any, Collection, Mapping

from ginjarator import filesystem

_NINJA_REQUIRED_VERSION = "1.10"


def to_ninja(value: Any, *, escape_shell: bool) -> str:
    """Returns a value in ninja's syntax."""
    # https://ninja-build.org/manual.html#ref_lexer
    match value:
        case str() if escape_shell:
            return to_ninja(shlex.quote(value), escape_shell=False)
        case str() if not set(value) & set("#\n"):
            return value.translate(
                str.maketrans(
                    dict[str, int | str | None](
                        {
                            " ": "$ ",
                            ":": "$:",
                            "$": "$$",
                        }
                    )
                )
            )
        case pathlib.Path():
            return to_ninja(str(value), escape_shell=escape_shell)
        case list() | tuple():
            return " ".join(
                to_ninja(item, escape_shell=escape_shell) for item in value
            )
        case set() | frozenset():
            return to_ninja(sorted(value), escape_shell=escape_shell)
        case _:
            raise NotImplementedError(
                f"Can't convert {value!r} to ninja syntax."
            )


def _depfile_escape(path: str | pathlib.Path) -> str:
    # The syntax does not seem to be well documented in any one place. The
    # Target Rules section of
    # https://pubs.opengroup.org/onlinepubs/9799919799/utilities/make.html
    # describes some of it, but not backslash handling.
    # https://github.com/ninja-build/ninja/blob/master/src/depfile_parser.in.cc
    # shows how ninja parses it, but from the comments it looks like that's not
    # the right syntax either and they might change it in the future. This code
    # just disallows potentially problematic characters as much as possible.
    if any(
        c.isspace() or not c.isprintable() or c in ':;#"\\' for c in str(path)
    ):
        raise NotImplementedError(
            f"Unsupported characters in path {str(path)!r}."
        )
    return str(path).replace("%", "\\%")


def to_depfile(
    dependency_map: Mapping[str | pathlib.Path, Collection[str | pathlib.Path]],
) -> str:
    """Returns depfile contents given a map from target to dependencies."""
    lines = []
    for target, dependencies in dependency_map.items():
        for dependency in dependencies:
            lines.append(
                f"{_depfile_escape(target)}: {_depfile_escape(dependency)}\n"
            )
    return "".join(lines)


def _template_ninja(
    template_name: pathlib.Path,
    *,
    fs: filesystem.Filesystem,
) -> str:
    path = fs.resolve(template_name)
    state_path = fs.resolve(filesystem.template_state_path(template_name))
    depfile_path = fs.resolve(filesystem.template_depfile_path(template_name))
    dyndep_path = fs.resolve(filesystem.template_dyndep_path(template_name))
    render_stamp_path = fs.resolve(
        filesystem.template_render_stamp_path(template_name)
    )
    scan_done_stamp_path = fs.resolve(
        filesystem.internal_path("scan-done.stamp")
    )
    return textwrap.dedent(
        f"""\
        build $
                {to_ninja(state_path, escape_shell=False)} $
                | $
                {to_ninja(depfile_path, escape_shell=False)} $
                {to_ninja(dyndep_path, escape_shell=False)} $
                : $
                scan $
                {to_ninja(path, escape_shell=False)} $
                || $
                {to_ninja(filesystem.BUILD_FILE, escape_shell=False)}
            depfile = {to_ninja(depfile_path, escape_shell=False)}
            template = {to_ninja(template_name, escape_shell=True)}

        build $
                {to_ninja(render_stamp_path, escape_shell=False)} $
                : $
                render $
                {to_ninja(path, escape_shell=False)} $
                | $
                {to_ninja(state_path, escape_shell=False)} $
                || $
                {to_ninja(dyndep_path, escape_shell=False)} $
                {to_ninja(scan_done_stamp_path, escape_shell=False)}
            dyndep = {to_ninja(dyndep_path, escape_shell=False)}
            template = {to_ninja(template_name, escape_shell=True)}
        """
    )


def init(
    *,
    root_path: pathlib.Path = pathlib.Path("."),
) -> None:
    fs = filesystem.Filesystem(root_path)
    main_ninja_path = fs.resolve(filesystem.internal_path("main.ninja"))
    subninjas_changed = []

    fs.write_text(
        filesystem.INTERNAL_DIR / ".gitignore",
        textwrap.dedent(
            """\
            # Automatically generated by ginjarator.
            *
            """
        ),
    )

    scan_done_stamp_path = fs.resolve(
        filesystem.internal_path("scan-done.stamp")
    )
    scan_done_dependencies = []

    parts = []
    parts.append(
        textwrap.dedent(
            f"""\
            ninja_required_version = {_NINJA_REQUIRED_VERSION}

            rule init
                command = ginjarator init
                description = INIT
                generator = true
                restat = true

            rule scan
                command = ginjarator scan $template
                description = SCAN $template
                restat = true

            rule render
                command = ginjarator render $template
                description = RENDER $template
                restat = true

            rule touch
                command = touch $out
            """
        )
    )

    for template_name in fs.read_config().templates:
        parts.append(_template_ninja(template_name, fs=fs))
        scan_done_dependencies.append(
            fs.resolve(filesystem.template_state_path(template_name))
        )

    # It seems that build.ninja needs to be a relative path for ninja to reload
    # it properly when it changes, so this hardcodes it rather than using
    # add_output() first.
    fs.add_output(main_ninja_path)
    parts.append(
        textwrap.dedent(
            f"""\
            build $
                    {to_ninja(filesystem.BUILD_FILE, escape_shell=False)} $
                    {to_ninja(sorted(fs.outputs), escape_shell=False)} $
                    : $
                    init $
                    {to_ninja(sorted(fs.dependencies), escape_shell=False)}

            build $
                    {to_ninja(scan_done_stamp_path, escape_shell=False)} $
                    : $
                    touch $
                    | $
                    {to_ninja(scan_done_dependencies, escape_shell=False)}
                description = STAMP done scanning
            """
        )
    )
    subninjas_changed.append(fs.write_text(main_ninja_path, "\n".join(parts)))

    fs.write_text(
        filesystem.BUILD_FILE,
        textwrap.dedent(
            f"""\
            ninja_required_version = {_NINJA_REQUIRED_VERSION}
            subninja {to_ninja(main_ninja_path, escape_shell=False)}
            """
        ),
        preserve_mtime=not any(subninjas_changed),
    )
