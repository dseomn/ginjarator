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

CONFIG_PATH = pathlib.Path("ginjarator.toml")

INTERNAL_DIR = pathlib.Path(".ginjarator")


def internal_path(*components: str) -> pathlib.Path:
    """Returns a path for internal state.

    Args:
        *components: Path components. Each one is escaped to remove "/", so
            other paths can be used as single components. However, "." and ".."
            are not escaped.
    """
    return INTERNAL_DIR.joinpath(
        *(urllib.parse.quote(component, safe="") for component in components)
    )


BUILD_PATH = pathlib.Path("build.ninja")
MINIMAL_CONFIG_PATH = internal_path("config", "minimal.json")


def template_state_path(template_name: pathlib.Path | str) -> pathlib.Path:
    """Returns the path for template state."""
    return internal_path("templates", f"{template_name}.json")


def template_depfile_path(template_name: pathlib.Path | str) -> pathlib.Path:
    """Returns the path for a template's depfile."""
    return internal_path("templates", f"{template_name}.d")


def template_dyndep_path(template_name: pathlib.Path | str) -> pathlib.Path:
    """Returns the path for a template's dyndep file."""
    return internal_path("templates", f"{template_name}.dd")


def template_render_stamp_path(
    template_name: pathlib.Path | str,
) -> pathlib.Path:
    """Returns the path for a template's render stamp."""
    return internal_path("templates", f"{template_name}.render-stamp")
