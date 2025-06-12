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
"""Config file."""

from collections.abc import Collection
import dataclasses
import pathlib
from typing import Any, Self


@dataclasses.dataclass(frozen=True, kw_only=True)
class Config:
    """Config.

    All paths are relative to the config file.

    Attributes:
        source_paths: Source files/directories.
        build_paths: Build files/directories.
        ninja_templates: Templates to render to ninja code.
        templates: Normal templates to render.
    """

    source_paths: Collection[pathlib.Path]
    build_paths: Collection[pathlib.Path]
    ninja_templates: Collection[pathlib.Path]
    templates: Collection[pathlib.Path]

    @classmethod
    def parse(cls, raw: Any, /) -> Self:
        """Returns the parsed config from toml data."""
        if unexpected_keys := raw.keys() - {
            "source_paths",
            "build_paths",
            "ninja_templates",
            "templates",
        }:
            raise ValueError(f"Unexpected keys: {list(unexpected_keys)}")
        return cls(
            source_paths=tuple(
                map(pathlib.Path, raw.get("source_paths", ["src"]))
            ),
            build_paths=tuple(
                map(pathlib.Path, raw.get("build_paths", ["build"]))
            ),
            ninja_templates=tuple(
                map(pathlib.Path, raw.get("ninja_templates", []))
            ),
            templates=tuple(map(pathlib.Path, raw.get("templates", []))),
        )
