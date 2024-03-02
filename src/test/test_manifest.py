from unittest import TestCase
from unittest.mock import MagicMock, Mock, mock_open, patch

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
        manifest = Manifest(self.mock_cmd, self.mock_env)
        mock_manifest.assert_called_with('/manifest/root/manifest.txt', 'rb')
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'path': '/home/username/test/projectA',
            'tags': {}
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA)'
    ])+b'\n')
    def test_resolve_single_tag_manifest(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'path': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA'])
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)'
    ])+b'\n')
    def test_resolve_multi_tag_manifest(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)
        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'path': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA', 'tagB'])
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)'
    ])+b'\n')
    def test_resolve_multi_projects_manifest(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)

        self.assertEqual(manifest.get_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'path': '/home/username/test/projectA',
            'tags': dict.fromkeys(['tagA', 'tagB'])
        })

        self.assertEqual(manifest.get_project('projectB'), {
            'ref': '/home/username/test/projectB',
            'path': '/home/username/test/projectB',
            'tags': dict.fromkeys(['tagA', 'tagC'])
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
    ])+b'\n')
    def test_resolve_tag_project_set(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)

        self.assertEqual(manifest.get_project_set('tagA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'path': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectB': {
                'ref': '/home/username/test/projectB',
                'path': '/home/username/test/projectB',
                'tags': dict.fromkeys(['tagA', 'tagC'])
            }
        })

        self.assertEqual(manifest.get_project_set('tagB'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'path': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            }
        })

        self.assertEqual(manifest.get_project_set('tagC'), {
            '/home/username/test/projectB': {
                'ref': '/home/username/test/projectB',
                'path': '/home/username/test/projectB',
                'tags': dict.fromkeys(['tagA', 'tagC'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'setA {tagA}'
    ])+b'\n')
    def test_resolve_explicit_project_set_one_tag(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'path': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectB': {
                'ref': '/home/username/test/projectB',
                'path': '/home/username/test/projectB',
                'tags': dict.fromkeys(['tagA', 'tagC'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'setA {tagA & tagB}'
    ])+b'\n')
    def test_resolve_explicit_project_set_two_tags_and(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'path': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            }
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA, tagB)',
        b'/home/username/test/projectB (tagA, tagC)',
        b'setA {tagB | tagC}'
    ])+b'\n')
    def test_resolve_explicit_project_set_two_tags_or(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)

        self.assertEqual(manifest.get_project_set('setA'), {
            '/home/username/test/projectA': {
                'ref': '/home/username/test/projectA',
                'path': '/home/username/test/projectA',
                'tags': dict.fromkeys(['tagA', 'tagB'])
            },
            '/home/username/test/projectB': {
                'ref': '/home/username/test/projectB',
                'path': '/home/username/test/projectB',
                'tags': dict.fromkeys(['tagA', 'tagC'])
            }
        })
