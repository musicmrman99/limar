from modules.manifest_modules import uris_local, uris_remote

# Types
from core.modulemanager import ModuleManager

class ManifestContextUris():

    # Lifecycle
    # --------------------

    def dependencies(self):
        return ['manifest']

    def configure(self, *, mod: ModuleManager, **_):
        mod.manifest().add_context_module(uris_local.UrisLocal)
        mod.manifest().add_context_module(uris_remote.UrisRemote)
