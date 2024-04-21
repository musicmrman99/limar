from modules.manifest_modules import projects, uris_local, uris_remote

# Types
from core.modulemanager import ModuleManager

class ProjectManifest():

    # Lifecycle
    # --------------------

    def dependencies(self):
        return ['manifest']

    def configure(self, *, mod: ModuleManager, **_):
        mod.manifest().add_context_modules(
            projects.Projects,
            uris_local.UrisLocal,
            uris_remote.UrisRemote
        )
        mod.manifest().add_context_modules()
