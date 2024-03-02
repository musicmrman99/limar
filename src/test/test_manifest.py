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
        self.assertEqual(manifest.resolve_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'path': '/home/username/test/projectA',
            'tags': set()
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA)'
    ])+b'\n')
    def test_resolve_tag_is_parsed(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)
        self.assertEqual(manifest.resolve_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'path': '/home/username/test/projectA',
            'tags': {'tagA'}
        })

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/projectA (tagA)'
    ])+b'\n')
    def test_resolve_tag_is_parsed(self, _):
        manifest = Manifest(self.mock_cmd, self.mock_env)
        self.assertEqual(manifest.resolve_project('projectA'), {
            'ref': '/home/username/test/projectA',
            'path': '/home/username/test/projectA',
            'tags': {'tagA'}
        })
