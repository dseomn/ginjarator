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
"""Path types, constants, and functions."""

import pathlib
import urllib.parse


class Filesystem(pathlib.PurePath):
    """Type of path that filesystem.Filesystem uses in its API.

    If it's relative, then it's relative to the Filesystem's root (and therefore
    build.ninja), not necessarily the current directory.
    """


CONFIG = Filesystem("ginjarator.toml")

INTERNAL = Filesystem(".ginjarator")


def internal(*components: str) -> Filesystem:
    """Returns a path for internal state.

    Args:
        *components: Path components. Each one is escaped to remove "/", so
            other paths can be used as single components. However, "." and ".."
            are not escaped.
    """
    return INTERNAL.joinpath(
        *(urllib.parse.quote(component, safe="") for component in components)
    )


NINJA_ENTRYPOINT = Filesystem("build.ninja")
NINJA_ENTRYPOINT_DEPFILE = internal("build.ninja.d")
NINJA_BUILDDIR = internal("ninja_builddir")
NINJA_MAIN = internal("main.ninja")
MINIMAL_CONFIG = internal("config", "minimal.json")
SCAN_DONE_STAMP = internal("scan-done.stamp")


def ninja_template_output(template_path: Filesystem | str) -> Filesystem:
    """Returns the output path for a ninja template."""
    return internal("ninja_templates", f"{template_path}.ninja")


def template_state(template_path: Filesystem | str) -> Filesystem:
    """Returns the path for template state."""
    return internal("templates", f"{template_path}.json")


def template_depfile(template_path: Filesystem | str) -> Filesystem:
    """Returns the path for a template's depfile."""
    return internal("templates", f"{template_path}.d")


def template_dyndep(template_path: Filesystem | str) -> Filesystem:
    """Returns the path for a template's dyndep file."""
    return internal("templates", f"{template_path}.dd")


def template_render_stamp(template_path: Filesystem | str) -> Filesystem:
    """Returns the path for a template's render stamp."""
    return internal("templates", f"{template_path}.render-stamp")


class Api:
    """API for use by templates.

    Attributes:
        current_template: The template currently being rendered.
    """

    def __init__(self, *, current_template: Filesystem) -> None:
        """Initializer."""
        self.current_template = current_template
