from argparse import Namespace
from modules.manifest_modules import (
    # Generic
    tags,

    # Projects
    project,
    uris_local,
    uris_remote
)

class ProjectManifestModule:

    # Lifecycle
    # --------------------

    def dependencies(self):
        return ['manifest']

    def configure(self, *, mod: Namespace, **_):
        mod.manifest.add_context_modules(
            tags.Tags,
            project.Project,
            uris_local.UrisLocal,
            uris_remote.UrisRemote
        )
