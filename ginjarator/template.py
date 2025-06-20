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
"""Template scanning and rendering."""

from collections.abc import Callable
import json
import pathlib
import textwrap
from typing import override

import jinja2

from ginjarator import build
from ginjarator import filesystem
from ginjarator import paths
from ginjarator import python


class Api:
    """API for use by templates.

    Attributes:
        fs: Filesystem access.
        py: API to use Python code.
        to_ninja: Converts a value to ninja syntax.
    """

    def __init__(
        self,
        *,
        fs: filesystem.Filesystem,
    ) -> None:
        """Initializer.

        Args:
            fs: Filesystem access.
        """
        self.fs = fs
        self.py = python.Api(fs=fs)
        self.to_ninja = build.to_ninja


class _Loader(jinja2.BaseLoader):
    """Jinja template loader."""

    def __init__(self, fs: filesystem.Filesystem) -> None:
        self._fs = fs

    @override
    def get_source(
        self,
        environment: jinja2.Environment,
        template: str,
    ) -> tuple[str, str | None, Callable[[], bool]]:
        del environment  # Unused.
        try:
            contents = self._fs.read_text(template)
        except FileNotFoundError as e:
            raise jinja2.TemplateNotFound(template) from e
        if contents is None:
            raise jinja2.TemplateNotFound(f"{template!r} is not built yet.")
        return (contents, str(self._fs.root / template), lambda: False)


def _render(api: Api, template_path: paths.Filesystem) -> str:
    environment = jinja2.Environment(
        keep_trailing_newline=True,
        extensions=("jinja2.ext.do",),
        undefined=jinja2.StrictUndefined,
        loader=_Loader(api.fs),
    )
    environment.globals["ginjarator"] = api
    template = environment.get_template(str(template_path))
    return template.render()


def ninja(
    template_path: paths.Filesystem,
    *,
    internal_fs: filesystem.Filesystem,
) -> str:
    """Returns custom ninja from the given template."""
    api = Api(
        fs=filesystem.Filesystem(internal_fs.root, mode=filesystem.NinjaMode()),
    )
    contents = _render(api, template_path)
    for dependency in api.fs.dependencies:
        internal_fs.add_dependency(dependency)
    # NinjaMode doesn't allow outputs, so no need to copy them.
    return contents


def scan(
    template_path: paths.Filesystem,
    *,
    root_path: pathlib.Path = pathlib.Path("."),
) -> None:
    """Scans a template for dependencies and outputs."""
    internal_fs = filesystem.Filesystem(root_path)
    api = Api(
        fs=filesystem.Filesystem(root_path, mode=filesystem.ScanMode()),
    )
    _render(api, template_path)
    scan_dependencies = api.fs.dependencies
    render_dependencies = api.fs.dependencies | api.fs.deferred_dependencies
    render_outputs = api.fs.outputs | api.fs.deferred_outputs
    state_path = paths.template_state(template_path)
    internal_fs.write_text(
        state_path,
        json.dumps(
            dict(
                dependencies=sorted(map(str, render_dependencies)),
                outputs=sorted(map(str, render_outputs)),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )
    internal_fs.write_text(
        paths.template_depfile(template_path),
        build.to_depfile(
            first_output=state_path,
            dependencies=scan_dependencies,
        ),
    )
    render_stamp_path = paths.template_render_stamp(template_path)
    internal_fs.write_text(
        paths.template_dyndep(template_path),
        textwrap.dedent(
            f"""\
            ninja_dyndep_version = 1
            build $
                    {build.to_ninja(render_stamp_path)} $
                    | $
                    {build.to_ninja(render_outputs)} $
                    : $
                    dyndep $
                    | $
                    {build.to_ninja(render_dependencies)}
            """
        ),
    )


def render(
    template_path: paths.Filesystem,
    *,
    root_path: pathlib.Path = pathlib.Path("."),
) -> None:
    """Renders a template."""
    internal_fs = filesystem.Filesystem(root_path)
    state = json.loads(
        internal_fs.read_text(
            paths.template_state(template_path),
            defer_ok=False,
        )
    )
    api = Api(
        fs=filesystem.Filesystem(
            root_path,
            mode=filesystem.RenderMode(
                dependencies=tuple(
                    map(paths.Filesystem, state["dependencies"])
                ),
                outputs=tuple(map(paths.Filesystem, state["outputs"])),
            ),
        ),
    )
    _render(api, template_path)
    internal_fs.write_text(paths.template_render_stamp(template_path), "")
