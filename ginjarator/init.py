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
"""Initializing a ginjarator project and generating its build file."""

import json
import pathlib
import textwrap

from ginjarator import build
from ginjarator import config
from ginjarator import filesystem
from ginjarator import template

_NINJA_REQUIRED_VERSION = "1.10"


def _main_ninja_for_template(
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
                {build.to_ninja(state_path)} $
                | $
                {build.to_ninja(depfile_path)} $
                {build.to_ninja(dyndep_path)} $
                : $
                scan $
                {build.to_ninja(path)} $
                || $
                {build.to_ninja(filesystem.BUILD_PATH)}
            depfile = {build.to_ninja(depfile_path)}
            template = {build.to_ninja(template_name, escape_shell=True)}

        build $
                {build.to_ninja(render_stamp_path)} $
                : $
                render $
                {build.to_ninja(path)} $
                | $
                {build.to_ninja(state_path)} $
                || $
                {build.to_ninja(dyndep_path)} $
                {build.to_ninja(scan_done_stamp_path)}
            dyndep = {build.to_ninja(dyndep_path)}
            template = {build.to_ninja(template_name, escape_shell=True)}
        """
    )


def _main_ninja(
    *,
    fs: filesystem.Filesystem,
    config_: config.Config,
) -> str:
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

    for template_name in config_.templates:
        parts.append(_main_ninja_for_template(template_name, fs=fs))
        scan_done_dependencies.append(
            fs.resolve(filesystem.template_state_path(template_name))
        )

    depfile_path = fs.resolve(
        filesystem.internal_path(f"{filesystem.BUILD_PATH}.d")
    )
    fs.write_text(
        depfile_path,
        build.to_depfile({filesystem.BUILD_PATH: fs.dependencies}),
    )

    # It seems that build.ninja needs to be a relative path for ninja to reload
    # it properly when it changes, so this hardcodes it rather than using
    # add_output() first.
    parts.append(
        textwrap.dedent(
            f"""\
            build $
                    {build.to_ninja(filesystem.BUILD_PATH)} $
                    {build.to_ninja(sorted(fs.outputs))} $
                    : $
                    init
                depfile = {build.to_ninja(depfile_path)}

            build $
                    {build.to_ninja(scan_done_stamp_path)} $
                    : $
                    touch $
                    | $
                    {build.to_ninja(scan_done_dependencies)}
                description = STAMP done scanning
            """
        )
    )

    return "\n".join(parts)


def init(
    *,
    root_path: pathlib.Path = pathlib.Path("."),
) -> None:
    """Initializes a ginjarator project and generates its build files."""
    fs = filesystem.Filesystem(root_path)
    config_ = fs.read_config()
    subninjas = []
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

    fs.write_text(
        filesystem.MINIMAL_CONFIG_PATH,
        json.dumps(
            config_.serialize_minimal(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )

    for template_name in config_.ninja_templates:
        template_ninja_path = fs.resolve(
            filesystem.internal_path(
                "ninja_templates",
                f"{template_name}.ninja",
            )
        )
        subninjas.append(template_ninja_path)
        subninjas_changed.append(
            fs.write_text(
                template_ninja_path,
                template.ninja(str(template_name), internal_fs=fs),
            )
        )

    # This has to be the last subninja, so that it can include the dependencies
    # and outputs added by previous subninjas.
    main_ninja_path = fs.resolve(filesystem.internal_path("main.ninja"))
    fs.add_output(main_ninja_path)
    subninjas.append(main_ninja_path)
    subninjas_changed.append(
        fs.write_text(main_ninja_path, _main_ninja(fs=fs, config_=config_))
    )

    fs.write_text(
        filesystem.BUILD_PATH,
        "".join(
            (
                f"ninja_required_version = {_NINJA_REQUIRED_VERSION}\n",
                *(
                    f"subninja {build.to_ninja(subninja)}\n"
                    for subninja in subninjas
                ),
            )
        ),
        preserve_mtime=not any(subninjas_changed),
    )
