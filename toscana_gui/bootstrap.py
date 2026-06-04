from __future__ import annotations

import panel as pn

from .app.shell import ToScaNAShell


def build_app() -> pn.template.FastListTemplate:
    shell = ToScaNAShell()
    template = shell.build()
    template._toscana_shell = shell
    return template
