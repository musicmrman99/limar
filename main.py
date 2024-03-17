"""
Entry point for `vcs`.
"""

from core.modulemanager import ModuleManager

from core.modules.log import Log
from modules import manifest, manifest_context_uris, env

def main():
    with ModuleManager('vcs') as module_manager:
        module_manager.register(Log)
        # TODO: Implement a dependency system. For now, force Manifest to load
        #       first.
        module_manager.register(
            manifest.Manifest,
            manifest_context_uris.ManifestContextUris,
            env.Env
        )
        module_manager.run()

if __name__ == '__main__':
    main()
