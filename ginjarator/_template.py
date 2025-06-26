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

from collections.abc import Callable, Generator
import contextlib
import contextvars
import json
import pathlib
import textwrap
from typing import override

import jinja2

from ginjarator import _build
from ginjarator import _filesystem
from ginjarator import _paths
from ginjarator import _python


class Api:
    """API for use by templates.

    Attributes:
        current_template: The template currently being rendered.
        fs: Filesystem access.
        py: API to use Python code.
        to_ninja: Converts a value to ninja syntax.
    """

    def __init__(
        self,
        *,
        current_template: _paths.Filesystem,
        fs: _filesystem.Filesystem,
    ) -> None:
        """Initializer."""
        self.current_template = current_template
        self.fs = fs
        self.py = _python.Api(fs=fs)
        self.to_ninja = _build.to_ninja


_api: contextvars.ContextVar[Api] = contextvars.ContextVar("_api")


def api() -> Api:
    """Returns the current Api.

    This should only be used by project code called from templates. Ginjarator
    itself should pass around Api objects as needed.
    """
    return _api.get()


@contextlib.contextmanager
def set_api(api_: Api) -> Generator[None, None, None]:
    """Returns a context manager that sets the current Api."""
    token = _api.set(api_)
    try:
        yield
    finally:
        _api.reset(token)


class _Loader(jinja2.BaseLoader):
    """Jinja template loader."""

    def __init__(self, fs: _filesystem.Filesystem) -> None:
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


def _render(api_: Api, template_path: _paths.Filesystem) -> str:
    environment = jinja2.Environment(
        keep_trailing_newline=True,
        extensions=("jinja2.ext.do",),
        undefined=jinja2.StrictUndefined,
        loader=_Loader(api_.fs),
    )
    environment.globals["ginjarator"] = api_
    template = environment.get_template(str(template_path))
    with set_api(api_):
        return template.render()


def ninja(
    template_path: _paths.Filesystem,
    *,
    internal_fs: _filesystem.Filesystem,
) -> str:
    """Returns custom ninja from the given template."""
    api_ = Api(
        current_template=template_path,
        fs=_filesystem.Filesystem(
            internal_fs.root, mode=_filesystem.NinjaMode()
        ),
    )
    contents = _render(api_, template_path)
    for dependency in api_.fs.dependencies:
        internal_fs.add_dependency(dependency)
    # NinjaMode doesn't allow outputs, so no need to copy them.
    return contents


def scan(
    template_path: _paths.Filesystem,
    *,
    root_path: pathlib.Path = pathlib.Path("."),
) -> None:
    """Scans a template for dependencies and outputs."""
    internal_fs = _filesystem.Filesystem(root_path)
    api_ = Api(
        current_template=template_path,
        fs=_filesystem.Filesystem(root_path, mode=_filesystem.ScanMode()),
    )
    _render(api_, template_path)
    scan_dependencies = api_.fs.dependencies
    render_dependencies = api_.fs.dependencies | api_.fs.deferred_dependencies
    render_outputs = api_.fs.outputs | api_.fs.deferred_outputs
    state_path = _paths.template_state(template_path)
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
        _paths.template_depfile(template_path),
        _build.to_depfile(
            first_output=state_path,
            dependencies=scan_dependencies,
        ),
    )
    render_stamp_path = _paths.template_render_stamp(template_path)
    internal_fs.write_text(
        _paths.template_dyndep(template_path),
        textwrap.dedent(
            f"""\
            ninja_dyndep_version = 1
            build $
                    {_build.to_ninja(render_stamp_path)} $
                    | $
                    {_build.to_ninja(render_outputs)} $
                    : $
                    dyndep $
                    | $
                    {_build.to_ninja(render_dependencies)}
            """
        ),
    )


def render(
    template_path: _paths.Filesystem,
    *,
    root_path: pathlib.Path = pathlib.Path("."),
) -> None:
    """Renders a template."""
    internal_fs = _filesystem.Filesystem(root_path)
    state = json.loads(
        internal_fs.read_text(
            _paths.template_state(template_path),
            defer_ok=False,
        )
    )
    api_ = Api(
        current_template=template_path,
        fs=_filesystem.Filesystem(
            root_path,
            mode=_filesystem.RenderMode(
                dependencies=tuple(
                    map(_paths.Filesystem, state["dependencies"])
                ),
                outputs=tuple(map(_paths.Filesystem, state["outputs"])),
            ),
        ),
    )
    _render(api_, template_path)
    internal_fs.write_text(_paths.template_render_stamp(template_path), "")
