from modules.manifest_lang.build.ManifestListener import ManifestListener

# Types
from modules.manifest_lang.build.ManifestParser import ManifestParser
from core.modules.log import Log

class ManifestListenerImpl(ManifestListener):
    """
    An ANTLR4 Listener to parse the manifest file.

    You can give an indexed list (ie. a dictionary) of 'context modules' when
    initialising this class. Context modules are used to extend the manifest
    format (usually) by defining custom contexts. Contexts may be implicit
    (ie. global), or may be explicitly given in the manifest. If given, contexts
    are declared with `@context-type`, wrap one or more declarations, and may
    take one or more options.

    The declarations a context applies to can be given by placing them within a
    pair of braces after the context type. Each declaration must be on its own
    line, separate from the lines the braces are on. This is the declaration
    block.

    Context options are specified by placing key-value pairs, where the key and
    value are separated by an '=', within a pair of brackets between the context
    type and the declaration block. If more than one option is given, each
    option must be on its own line, separate from the lines the brackets are on.

    Spaces are mandatory between the type, option block, and declaration block.

    Examples of contexts:

        @context-type {
          dir/project-a
        }

        @context-type (someOption = /home/username/mystuff) {
          dir/project-b
        }

        @context-type (
            optionA = /home/username/directory
            optionB = https://somegithost.com/username
        ) {
          dir/project-c
        }

    Each context module must be a Python class that defines a `context_type()`
    method that returns the context type that module is for (as a string), and
    may define any of the following method-based hooks:

    - `on_enter_manifest()`
    - `on_enter_context(context)`
    - `on_declare_project(context, project)`
    - `on_declare_project_set(context, project_set)`
    - `on_exit_context(context, projects, project_sets)`
        - Note that projects and project_sets only contain those that were
        declared in this context.
    - `on_exit_manifest(projects, project_sets)`
    """

    def __init__(self,
            logger: Log,
            context_modules: 'dict[str, list]' = None
    ):
        """
        context_modules must be a dictionary of the following format:
            {'context-type-name': [context_module, ...], ...}
        """

        # Outputs
        self.projects = {}
        self.project_sets = {}

        # Internal operations
        self._logger = logger

        self._context_modules = context_modules
        if self._context_modules is None:
            self._context_modules = {}

        self._contexts = []
        self._tag_operand_stack = []

    def enterManifest(self, ctx: ManifestParser.ManifestContext):
        # Call 'on_enter_manifest' on all context modules
        self._run_context_lifecycle_point('on_enter_manifest', [])

    def exitManifest(self, ctx: ManifestParser.ManifestContext):
        # Call 'on_exit_manifest' on all context modules
        self._run_context_lifecycle_point('on_exit_manifest',
            [self.projects, self.project_sets]
        )

    def enterContext(self, ctx: ManifestParser.ContextContext):
        context_type = ctx.typeName.text
        if context_type not in self._context_modules.keys():
            self._logger.warning(
                f"Unsupported context type '{context_type}' found."
                " Ignoring context."
            )
            # Symbolises an unrecognised context (not an error for forwards
            # compatibility and to support dynamic modules)
            self._contexts.append(NotImplementedError)
            return

        context = {
            'type': context_type,
            'opts': {},
            'projects': {},
            'project_sets': {}
        }

        if ctx.contextOpts() is not None:
            for opt in ctx.contextOpts().contextOpt():
                context['opts'][opt.optName.text] = opt.optValue.getText()

        self._contexts.append(context)

        # Call 'on_enter_context' on all context modules registered for this
        # context
        self._run_context_lifecycle_point('on_enter_context',
            [context],
            context['type']
        )

    def exitContext(self, ctx: ManifestParser.ContextContext):
        old_context = self._contexts.pop()
        if old_context is NotImplementedError:
            return # Ignore unrecognised contexts

        # Call 'on_exit_context' on all context modules registered for this
        # context
        self._run_context_lifecycle_point('on_exit_context',
            [
                old_context,
                old_context['projects'],
                old_context['project_sets']
            ],
            old_context['type']
        )

    def enterProject(self, ctx: ManifestParser.ProjectContext):
        proj_ref = ctx.ref().getText()

        # Add to main project set
        self.projects[proj_ref] = {
            'ref': proj_ref,
            'tags': {}
        }
        if ctx.tagList() is not None:
            self.projects[proj_ref]['tags'] = {
                tag.getText(): None
                for tag in ctx.tagList().tag()
            }

        # Add to all relevant project sets
        for tag in self.projects[proj_ref]['tags']:
            if tag not in self.project_sets.keys():
                self.project_sets[tag] = {}
            self.project_sets[tag][proj_ref] = self.projects[proj_ref]

        # Add to all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context['projects'][proj_ref] = self.projects[proj_ref]

        # Call 'on_declare_project' on all context modules registered for all
        # active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            self._run_context_lifecycle_point('on_declare_project',
                [context, self.projects[proj_ref]],
                context['type']
            )

    def enterTagBase(self, ctx: ManifestParser.TagBaseContext):
        project_set_name = ctx.tag().getText()
        project_set = {} # In case the project set isn't defined
        if project_set_name in self.project_sets:
            project_set = self.project_sets[project_set_name]
        self._tag_operand_stack.append(project_set)

    def exitTagOp(self, ctx: ManifestParser.TagOpContext):
        right_proj_set = self._tag_operand_stack.pop()
        left_proj_set = self._tag_operand_stack.pop()
        if ctx.op.text == '&':
            result = {
                proj_set_name: left_proj_set[proj_set_name]
                for proj_set_name in left_proj_set.keys() & right_proj_set.keys()
            }
        elif ctx.op.text == '|':
            result = {
                proj_set_name: (
                    left_proj_set[proj_set_name]
                    if proj_set_name in left_proj_set
                    else right_proj_set[proj_set_name]
                )
                for proj_set_name in left_proj_set.keys() | right_proj_set.keys()
            }
        self._tag_operand_stack.append(result)

    def exitProjectSet(self, ctx: ManifestParser.ProjectSetContext):
        proj_set_ref = ctx.ref().getText()

        # Add to main project sets
        self.project_sets[proj_set_ref] = self._tag_operand_stack.pop()

        # Add to all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context['project_sets'][proj_set_ref] = (
                self.project_sets[proj_set_ref]
            )

        # Call 'on_declare_project_set' on all context modules registered for
        # all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            self._run_context_lifecycle_point('on_declare_project_set',
                [context, self.project_sets[proj_set_ref]],
                context['type']
            )

    def _run_context_lifecycle_point(self, name, args, context_type=None):
        """
        Run the named context lifecycle point for all context modules, passing
        args.

        If context_type is given, then only run the lifecycle point on context
        modules for that context type.
        """

        if context_type is not None:
            try:
                module_set = self._context_modules[context_type]
            except KeyError:
                module_set = []
        else:
            module_set = [
                mod
                for mod_set in self._context_modules.values()
                for mod in mod_set
            ]

        for module in module_set:
            if hasattr(module, name):
                getattr(module, name)(*args)
