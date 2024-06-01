from argparse import Namespace
from modules.manifest_modules import (
    # Generic
    tags,

    # Tools and Commands
    tool,
    query
)

class ToolManifestModule:

    # Lifecycle
    # --------------------

    def dependencies(self):
        return ['manifest']

    def configure(self, *, mod: Namespace, **_):
        mod.manifest.add_context_modules(
            tags.Tags,
            tool.Tool,
            query.Query
        )
