from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

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
                return 'whatever'
            return None
        self.mock_env.get.side_effect = envGet

    @patch("builtins.open", new_callable=mock_open, read_data=b'\n'.join([
        b'/home/username/test/project'
    ])+b'\n')
    def test_resolve_basic(self, mock_manifest):
        manifest = Manifest(self.mock_cmd, self.mock_env)
        assert manifest.resolve('test') == '/home/username/test/project'
