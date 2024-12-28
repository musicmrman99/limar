from argparse import Namespace
from modules.manifest_modules import (
    # Generic
    tags,

    # Subjects
    subject,

    # Commands
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
        # Generic
        mod.manifest.add_context_modules(
            tags.Tags
        )

        # Subjects
        mod.manifest.add_context_modules(
            subject.Subject
        )

        # Commands
        mod.manifest.add_context_modules(
            tool.Tool,
            command.Command,
            query.Query,
            action.Action,
            cache.Cache,
            subjects.Subjects,
            primary_subject.PrimarySubject
        )
