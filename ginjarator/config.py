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
import itertools
import pathlib
from typing import Any, override, Self

from ginjarator import paths


@dataclasses.dataclass(frozen=True, kw_only=True)
class Minimal:
    """Minimal subset of config that's needed by (almost) everything.

    Almost all templates (indirectly) depend on these fields and would need to
    be rebuilt if they change. To avoid rebuilding all templates when other
    fields change, these fields are split out from the main Config class.

    Attributes:
        source_paths: Source files/directories.
        build_paths: Build files/directories.
    """

    source_paths: Collection[paths.Filesystem]
    build_paths: Collection[paths.Filesystem]

    def __post_init__(self) -> None:
        for source_path, build_path in itertools.product(
            self.source_paths, self.build_paths
        ):
            if source_path.is_relative_to(
                build_path
            ) or build_path.is_relative_to(source_path):
                raise ValueError(
                    "source_paths and build_paths must not overlap."
                )

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
                paths.Filesystem(pathlib.PurePath(path))
                for path in sorted(set(raw.get("source_paths", ["src"])))
            ),
            build_paths=tuple(
                paths.Filesystem(pathlib.PurePath(path))
                for path in sorted(set(raw.get("build_paths", ["build"])))
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

    Attributes:
        ninja_templates: Templates to render to ninja code.
        templates: Normal templates to render.
    """

    ninja_templates: Sequence[paths.Filesystem]
    templates: Sequence[paths.Filesystem]

    @classmethod
    @override
    def parse(cls, raw: Any, /, **kwargs: Any) -> Self:
        """Returns the parsed config from data."""
        raw_copy = dict(raw)
        return super().parse(
            raw_copy,
            ninja_templates=tuple(
                paths.Filesystem(pathlib.PurePath(path))
                for path in raw_copy.pop("ninja_templates", [])
            ),
            templates=tuple(
                paths.Filesystem(pathlib.PurePath(path))
                for path in raw_copy.pop("templates", [])
            ),
            **kwargs,
        )
