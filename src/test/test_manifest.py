from unittest import TestCase
from unittest.mock import MagicMock, Mock, mock_open, patch

# Util
import os.path
import re
from src.exceptions import VCSException

# Under Test
from commands.manifest import Manifest

class TestManifest(TestCase):

    def setUp(self) -> None:
        logger = Mock()
        logger.log.side_effect = lambda self, *objs, error=False, level=0: print(*objs)

        self.mock_cmd = Mock()
        self.mock_cmd.log.return_value=logger

        self.mock_env = Mock()
        def envGet(value):
            if value == 'manifest.default_project_set':
                return None
            if value == 'manifest.root':
                return '/manifest/root'
            return None
        self.mock_env.get.side_effect = envGet

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA'
    ])+b'\n')
    def test_resolve_basic(self, mock_manifest: MagicMock):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'tags': {}
        })
        mock_manifest.assert_called_with('/manifest/root/manifest.txt', 'rb')

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA)'
    ])+b'\n')
    def test_resolve_single_tag_manifest(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA'])
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)'
    ])+b'\n')
    def test_resolve_multi_tag_manifest(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA', 'tagB'])
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)'
    ])+b'\n')
    def test_resolve_multi_projects_manifest(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA', 'tagB'])
        })

        self.assertEqual(manifest.get_project('projectB'), {
            'ref': '/home/username/test/projectB',
            'tags': dict.fromkeys(['tagA', 'tagC'])
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
    ])+b'\n')
    def test_resolve_tag_project_set(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project_set('tagA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectB': {
                'ref': '/home/username/test/projectB',
                'tags': dict.fromkeys(['tagA', 'tagC'])
            }
        })

        self.assertEqual(manifest.get_project_set('tagB'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            }
        })

        self.assertEqual(manifest.get_project_set('tagC'), {
            '/home/username/test/projectB': {
                'ref': '/home/username/test/projectB',
                'tags': dict.fromkeys(['tagA', 'tagC'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'setA {tagA}'
    ])+b'\n')
    def test_resolve_explicit_project_set_one_tag(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectB': {
                'ref': '/home/username/test/projectB',
                'tags': dict.fromkeys(['tagA', 'tagC'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'setA {tagA & tagB}'
    ])+b'\n')
    def test_resolve_explicit_project_set_two_tags_and(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'setA {tagB | tagC}'
    ])+b'\n')
    def test_resolve_explicit_project_set_two_tags_or(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectB': {
                'ref': '/home/username/test/projectB',
                'tags': dict.fromkeys(['tagA', 'tagC'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'/home/username/test/projectC (tagD)',
        b'setA {tagA & tagB | tagD}'
    ])+b'\n')
    def test_resolve_explicit_project_set_grouping_default(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectC': {
                'ref': '/home/username/test/projectC',
                'tags': dict.fromkeys(['tagD'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'/home/username/test/projectC (tagD)',
        b'setA {(tagA & tagB) | tagD}',
        b'setB {tagA & (tagB | tagD)}'
    ])+b'\n')
    def test_resolve_explicit_project_set_grouping_explicit(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectC': {
                'ref': '/home/username/test/projectC',
                'tags': dict.fromkeys(['tagD'])
            }
        })

        self.assertEqual(manifest.get_project_set('setB'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'/home/username/test/projectC (tagD)',
        b'/home/username/test/projectD (tagD, tagE)',
        b'/home/username/test/projectE (tagD, tagB, tagF)',
        b'setA { (tagA & tagB) | (tagD & tagE) }'
    ])+b'\n')
    def test_resolve_explicit_project_set_grouping_of_groups(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectD': {
                'ref': '/home/username/test/projectD',
                'tags': dict.fromkeys(['tagD', 'tagE'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'/home/username/test/projectC (tagD)',
        b'/home/username/test/projectD (tagD, tagE)',
        b'/home/username/test/projectE (tagD, tagB, tagF)',
        b'setA { (tagA & tagB) | (tagD & (tagE | tagF)) }'
    ])+b'\n')
    def test_resolve_explicit_project_set_grouping_nesting(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectD': {
                'ref': '/home/username/test/projectD',
                'tags': dict.fromkeys(['tagD', 'tagE'])
            },
            '/home/username/test/projectE': {
                'ref': '/home/username/test/projectE',
                'tags': dict.fromkeys(['tagD', 'tagB', 'tagF'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'@some-context {',
        b'  projectA',
        b'}',
    ])+b'\n')
    def test_resolve_context_basic(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        on_enter_context = Mock()
        manifest.register_context_hooks('some-context',
            on_enter_context=on_enter_context
        )

        manifest.get_project('projectA')
        on_enter_context.assert_called_once_with({
            'type': 'some-context',
            'opts': {},
            'projects': {
                'projectA': {
                    'ref': 'projectA',
                    'tags': {}
                }
            },
            'project_sets': {}
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'projectA',
        b'setA {tagA}',
        b'@some-context {',
        b'  projectB',
        b'  setB {tagB}',
        b'}',
    ])+b'\n')
    def test_resolve_context_inside_and_outside(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)

        # Note: Can't used self.assert_called_once_with() because arguments are
        #       mutated as the parse progresses.

        def verify_enter_manifest():
            pass # Called with correct arguments, or would throw TypeError

        def verify_enter_context(context):
            self.assertEqual(context, {
                'type': 'some-context',
                'opts': {},
                # Chronological order, so doesn't have the project or project
                # set yet
                'projects': {},
                'project_sets': {}
            })

        def verify_declare_project(context, project):
            self.assertEqual(context, {
                'type': 'some-context',
                'opts': {},
                'projects': {
                    'projectB': {
                        'ref': 'projectB',
                        'tags': {}
                    }
                },
                # Chronological order, so doesn't have the project set yet
                'project_sets': {}
            })
            self.assertEqual(project, {
                'ref': 'projectB',
                'tags': {}
            })

        def verify_declare_project_set(context, project_set):
            self.assertEqual(context, {
                'type': 'some-context',
                'opts': {},
                'projects': {
                    'projectB': {
                        'ref': 'projectB',
                        'tags': {}
                    }
                },
                'project_sets': {
                    'setB': {}
                }
            })
            self.assertEqual(project_set, {})

        def verify_exit_context(context, projects, project_sets):
            self.assertEqual(context, {
                'type': 'some-context',
                'opts': {},
                # Only includes the project and project set in the context
                'projects': {
                    'projectB': {
                        'ref': 'projectB',
                        'tags': {}
                    }
                },
                'project_sets': {
                    'setB': {}
                }
            })
            self.assertEqual(projects, {
                'projectB': {
                    'ref': 'projectB',
                    'tags': {}
                }
            })
            self.assertEqual(project_sets, {
                'setB': {}
            })

        def verify_exit_manifest(projects, project_sets):
            self.assertEqual(projects, {
                'projectA': {
                    'ref': 'projectA',
                    'tags': {}
                },
                'projectB': {
                    'ref': 'projectB',
                    'tags': {}
                }
            })
            self.assertEqual(project_sets, {
                'setA': {},
                'setB': {}
            })

        on_enter_manifest = Mock(side_effect=verify_enter_manifest)
        on_enter_context = Mock(side_effect=verify_enter_context)
        on_declare_project = Mock(side_effect=verify_declare_project)
        on_declare_project_set = Mock(side_effect=verify_declare_project_set)
        on_exit_context = Mock(side_effect=verify_exit_context)
        on_exit_manifest = Mock(side_effect=verify_exit_manifest)

        manifest.register_context_hooks('some-context',
            on_enter_manifest=on_enter_manifest,
            on_enter_context=on_enter_context,
            on_declare_project=on_declare_project,
            on_declare_project_set=on_declare_project_set,
            on_exit_context=on_exit_context,
            on_exit_manifest=on_exit_manifest
        )
        manifest.get_project('projectA')

        on_enter_manifest.assert_called_once()
        on_enter_context.assert_called_once()
        on_declare_project.assert_called_once()
        on_declare_project_set.assert_called_once()
        on_exit_context.assert_called_once()
        on_exit_manifest.assert_called_once()

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'@uris (',
        b'  local = /home/username/test',
        b') {',
        b'  projectA (tagA, tagB)',
        b'  setA {tagA}',
        b'}',
    ])+b'\n')
    def test_resolve_context_complex(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)
        manifest.register_context_hooks('uris',
            on_declare_project=self.set_project_local_path_hook,
            on_exit_context=self.verify_project_local_paths_hook
        )

        self.assertEqual(manifest.get_project('projectA'), {
            'ref': 'projectA',
            'path': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA', 'tagB'])
        })

        self.assertEqual(manifest.get_project_set('setA'), {
            'projectA': {
                'ref': 'projectA',
                'path': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'@uris (',
        b'  remote = https://github.com/username',
        b'  local = /home/username/test',
        b') {',
        b'  projectA (tagA, tagB)',
        b'  setA {tagA}',
        b'}',
    ])+b'\n')
    def test_resolve_context_complex_multi_hooks(self, _):
        manifest = Manifest(cmd=self.mock_cmd, env=self.mock_env)
        manifest.register_context_hooks('uris',
            on_declare_project=self.set_project_local_path_hook,
            on_exit_context=self.verify_project_local_paths_hook
        )
        manifest.register_context_hooks('uris',
            on_declare_project=self.set_project_remote_path_hook,
            on_exit_context=self.verify_project_remote_paths_hook
        )

        self.assertEqual(manifest.get_project('projectA'), {
            'ref': 'projectA',
            'path': '/home/username/test/projectA',
            'remote': 'https://github.com/username/projectA',
            'tags': dict.fromkeys(['tagA', 'tagB'])
        })

        self.assertEqual(manifest.get_project_set('setA'), {
            'projectA': {
                'ref': 'projectA',
                'path': '/home/username/test/projectA',
                'remote': 'https://github.com/username/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            }
        })

    # Utils
    # --------------------------------------------------

    def set_project_local_path_hook(self, context, project):
        proj_path = project['ref']
        try:
            context_local_path = context['opts']['local']
            if not context_local_path.startswith('/'):
                raise ValueError('local mapped URI not absolute')

            proj_path = os.path.join(context_local_path, proj_path)

        except (KeyError, ValueError):
            pass # For now, until all nested contexts have been tried

        project['path'] = proj_path

    def verify_project_local_paths_hook(self, context, projects, project_sets):
        for project in projects.values():
            try:
                if not project['path'].startswith('/'):
                    raise ValueError('project path is not absolute')
            except KeyError:
                raise VCSException(
                    f"Path of project '{project['ref']}' not defined"
                    " (required by @uris context)"
                )
            except ValueError:
                raise VCSException(
                    f"Path of project '{project['ref']}' not absolute"
                    " (required by @uris context)"
                )

    def set_project_remote_path_hook(self, context, project):
        proj_url = project['ref']
        try:
            context_remote_url = context['opts']['remote']
            if not re.match('^https?://', context_remote_url):
                raise ValueError('remote mapped URI is not a HTTP(S) URL')

            proj_url = os.path.join(context_remote_url, proj_url)

        except (KeyError, ValueError):
            pass # For now, until all nested contexts have been tried

        project['remote'] = proj_url

    def verify_project_remote_paths_hook(self, context, projects, project_sets):
        for project in projects.values():
            try:
                if not re.match('^https?://', project['remote']):
                    raise ValueError('project path is not a HTTP(S) URL')
            except KeyError:
                raise VCSException(
                    f"Remote of project '{project['ref']}' not defined"
                    " (required by @uris context)"
                )
            except ValueError:
                raise VCSException(
                    f"Remote of project '{project['ref']}' not a valid HTTP(S)"
                    " URL (required by @uris context)"
                )
