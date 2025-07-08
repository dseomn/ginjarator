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
"""Main entrypoint."""

import argparse

from ginjarator import _init
from ginjarator import _paths
from ginjarator import _template


def _init_command(args: argparse.Namespace) -> None:
    del args  # Unused.
    _init.init()


def _minimal_config(args: argparse.Namespace) -> None:
    del args  # Unused.
    _init.minimal_config()


def _scan(args: argparse.Namespace) -> None:
    _template.scan(args.template)


def _render(args: argparse.Namespace) -> None:
    _template.render(args.template)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.set_defaults(subcommand=lambda args: parser.print_help())
    subparsers = parser.add_subparsers()

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize ginjarator.",
    )
    init_parser.set_defaults(subcommand=_init_command)

    minimal_config_parser = subparsers.add_parser(
        "minimal-config",
        help=(
            "Generate minimal config. This generally shouldn't be called "
            "manually."
        ),
    )
    minimal_config_parser.set_defaults(subcommand=_minimal_config)

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a template. This generally shouldn't be called manually.",
    )
    scan_parser.set_defaults(subcommand=_scan)
    scan_parser.add_argument("template", type=_paths.Filesystem)

    render_parser = subparsers.add_parser(
        "render",
        help="Render a template. This generally shouldn't be called manually.",
    )
    render_parser.set_defaults(subcommand=_render)
    render_parser.add_argument("template", type=_paths.Filesystem)

    parsed_args = parser.parse_args()
    parsed_args.subcommand(parsed_args)
