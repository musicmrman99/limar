from argparse import Namespace
from modules.manifest_modules import (
    # Generic
    tags,

    # Tools and Commands
    tool,
    command,
    query,
    action,
    cache,
    subjects,
    primary_subject
)

class CommandManifestModule:

    # Lifecycle
    # --------------------

    def dependencies(self):
        return ['manifest']

    def configure(self, *, mod: Namespace, **_):
        mod.manifest.add_context_modules(
            tags.Tags,

            tool.Tool,
            command.Command,
            query.Query,
            action.Action,
            cache.Cache,
            subjects.Subjects,
            primary_subject.PrimarySubject
        )
