from unittest import TestCase
from unittest.mock import MagicMock, Mock, mock_open, patch

# Util
from core.exceptions import VCSException

# Test Fixtures
from modules.manifest_modules import uris_local, uris_remote

# Under Test
from modules.manifest import Manifest

class TestManifest(TestCase):

    def _log(self, *objs, error=False, level=0):
        print(*objs)

    def setUp(self) -> None:
        logger = Mock()
        logger.log.side_effect = self._log

        self.mock_mod = Mock()
        self.mock_mod.log.return_value=logger

        self.mock_env = Mock()
        self.mock_env.VCS_MANIFEST_DEFAULT_PROJECT_SET = None
        self.mock_env.VCS_MANIFEST_ROOT = '/manifest/root'

        # Used in some context hooks tests
        self._uris_local_projects = set()
        self._uris_remote_projects = set()

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA'
    ])+b'\n')
    def test_resolve_basic(self, mock_manifest: MagicMock):
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'tags': {}
        })
        mock_manifest.assert_called_with('/manifest/root/manifest.txt', 'rb')

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA)'
    ])+b'\n')
    def test_resolve_single_tag_manifest(self, _):
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA'])
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)'
    ])+b'\n')
    def test_resolve_multi_tag_manifest(self, _):
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA', 'tagB'])
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)'
    ])+b'\n')
    def test_resolve_multi_projects_manifest(self, _):
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise/Configure/Start
        manifest = Manifest()
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.start(mod=self.mock_mod)

        # Test
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
        # Initialise
        manifest = Manifest()

        # Configure
        manifest.configure(mod=self.mock_mod, env=self.mock_env)

        mock_context_module = Mock()
        mock_context_module.context_type.return_value = 'some-context'
        mock_context_module_factory = Mock(return_value=mock_context_module)
        manifest.add_context_modules(mock_context_module_factory)

        # Start
        manifest.start(mod=self.mock_mod)

        # Test
        manifest.get_project('projectA')
        mock_context_module.on_enter_context.assert_called_once_with({
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
        # Initialise
        manifest = Manifest()

        # Configure
        manifest.configure(mod=self.mock_mod, env=self.mock_env)

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

        mock_context_module = Mock()
        mock_context_module.context_type.return_value = 'some-context'
        mock_context_module.on_enter_manifest.side_effect = verify_enter_manifest
        mock_context_module.on_enter_context.side_effect = verify_enter_context
        mock_context_module.on_declare_project.side_effect = verify_declare_project
        mock_context_module.on_declare_project_set.side_effect = verify_declare_project_set
        mock_context_module.on_exit_context.side_effect = verify_exit_context
        mock_context_module.on_exit_manifest.side_effect = verify_exit_manifest
        mock_context_module_factory = Mock(return_value=mock_context_module)
        manifest.add_context_modules(mock_context_module_factory)

        # Start
        manifest.start(mod=self.mock_mod)

        # Test
        manifest.get_project('projectA')
        mock_context_module.on_enter_manifest.assert_called_once()
        mock_context_module.on_enter_context.assert_called_once()
        mock_context_module.on_declare_project.assert_called_once()
        mock_context_module.on_declare_project_set.assert_called_once()
        mock_context_module.on_exit_context.assert_called_once()
        mock_context_module.on_exit_manifest.assert_called_once()

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'@uris (',
        b'  local = /home/username/test',
        b') {',
        b'  projectA (tagA, tagB)',
        b'  setA {tagA}',
        b'}',
    ])+b'\n')
    def test_resolve_context_complex(self, _):
        # Initialise
        manifest = Manifest()

        # Configure
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.add_context_modules(uris_local.UrisLocal)

        # Start
        manifest.start(mod=self.mock_mod)

        # Test
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
        b'  local = home/username/test',
        b') {',
        b'  projectA (tagA, tagB)',
        b'  setA {tagA}',
        b'}',
    ])+b'\n')
    def test_resolve_context_fails_if_hook_fails(self, _):
        # Initialise
        manifest = Manifest()

        # Configure
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.add_context_modules(uris_local.UrisLocal)

        # Test: Start
        with self.assertRaises(VCSException):
            manifest.start(mod=self.mock_mod)

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'@uris (',
        b'  remote = https://github.com/username',
        b'  local = /home/username/test',
        b') {',
        b'  projectA (tagA, tagB)',
        b'  setA {tagA}',
        b'}',
    ])+b'\n')
    def test_resolve_context_multi_hooks(self, _):
        # Initialise
        manifest = Manifest()

        # Configure
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.add_context_modules(uris_local.UrisLocal)
        manifest.add_context_modules(uris_remote.UrisRemote)

        # Start
        manifest.start(mod=self.mock_mod)

        # Test
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

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'@uris (',
        b'  local = /home/username/test',
        b') {',
        b'  projectA (tagA)',
        b'  @uris (local = /home/username/elsewhere) {',
        b'    projectB (tagA)',
        b'  }',
        b'  setA {tagA}',
        b'}',
    ])+b'\n')
    def test_resolve_context_nested(self, _):
        # Initialise
        manifest = Manifest()

        # Configure
        manifest.configure(mod=self.mock_mod, env=self.mock_env)
        manifest.add_context_modules(uris_local.UrisLocal)

        # Start
        manifest.start(mod=self.mock_mod)

        # Test
        self.assertEqual(manifest.get_project_set('setA'), {
            'projectA': {
                'ref': 'projectA',
                'path': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA'])
            },
            'projectB': {
                'ref': 'projectB',
                'path': '/home/username/elsewhere/projectB',
                'tags': dict.fromkeys(['tagA'])
            }
        })
