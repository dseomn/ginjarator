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

from collections.abc import Collection, Sequence
import dataclasses
import pathlib
from typing import Any, override, Self


@dataclasses.dataclass(frozen=True, kw_only=True)
class Minimal:
    """Minimal subset of config that's needed by (almost) everything.

    Almost all templates (indirectly) depend on these fields and would need to
    be rebuilt if they change. To avoid rebuilding all templates when other
    fields change, these fields are split out from the main Config class.

    All paths are relative to the config file.

    Attributes:
        source_paths: Source files/directories.
        build_paths: Build files/directories.
    """

    source_paths: Collection[pathlib.Path]
    build_paths: Collection[pathlib.Path]

    @classmethod
    def parse(cls, raw: Any, /, **kwargs: Any) -> Self:
        """Returns the parsed config from data.

        To avoid triggering rebuilds when they're not needed, this should
        normalize the data as much as possible. E.g., the order of source_paths
        has no effect, so that's sorted.
        """
        if unexpected_keys := raw.keys() - {
            "source_paths",
            "build_paths",
        }:
            raise ValueError(f"Unexpected keys: {list(unexpected_keys)}")
        return cls(
            source_paths=tuple(
                map(pathlib.Path, sorted(set(raw.get("source_paths", ["src"]))))
            ),
            build_paths=tuple(
                map(
                    pathlib.Path, sorted(set(raw.get("build_paths", ["build"])))
                )
            ),
            **kwargs,
        )

    def serialize_minimal(self) -> Any:
        """Returns the Minimal config suitable for dumping as JSON."""
        return dict(
            source_paths=list(map(str, self.source_paths)),
            build_paths=list(map(str, self.build_paths)),
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class Config(Minimal):
    """Config.

    All paths are relative to the config file.

    Attributes:
        ninja_templates: Templates to render to ninja code.
        templates: Normal templates to render.
    """

    ninja_templates: Sequence[pathlib.Path]
    templates: Sequence[pathlib.Path]

    @classmethod
    @override
    def parse(cls, raw: Any, /, **kwargs: Any) -> Self:
        """Returns the parsed config from data."""
        raw_copy = dict(raw)
        return super().parse(
            raw_copy,
            ninja_templates=tuple(
                map(pathlib.Path, raw_copy.pop("ninja_templates", []))
            ),
            templates=tuple(map(pathlib.Path, raw_copy.pop("templates", []))),
            **kwargs,
        )
