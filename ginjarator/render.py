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
"""Template rendering."""

from collections.abc import Callable
import dataclasses
import json
from typing import override

import jinja2

from ginjarator import filesystem


@dataclasses.dataclass(frozen=True, kw_only=True)
class Api:
    """API for use by templates.

    Attributes:
        fs: Filesystem access.
    """

    fs: filesystem.Filesystem


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
        return (contents, str(self._fs.resolve(template)), lambda: False)


def render(
    api: Api,
    template_name: str,
    *,
    delete_created_files_on_error: bool,
) -> None:
    """Renders a template."""
    environment = jinja2.Environment(
        extensions=("jinja2.ext.do",),
        undefined=jinja2.StrictUndefined,
        loader=_Loader(api.fs),
    )
    environment.globals["ginjarator"] = api
    template = environment.get_template(template_name)
    template_state_path = filesystem.template_state_path(template_name)
    try:
        template.render()
        # Manually add the output so that api.fs.outputs has it before
        # write_text() is called.
        api.fs.add_output(template_state_path)
        api.fs.write_text(
            template_state_path,
            json.dumps(
                dict(
                    dependencies=sorted(map(str, api.fs.dependencies)),
                    outputs=sorted(map(str, api.fs.outputs)),
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
        )
    except Exception:
        if delete_created_files_on_error:
            api.fs.delete_created_files()
        raise
