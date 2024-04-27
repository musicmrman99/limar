from unittest import TestCase
from unittest.mock import MagicMock, Mock, mock_open, patch

# Util
from core.exceptions import VCSException

# Test Fixtures
from modules.manifest_modules import uris_local, uris_remote

# Under Test
from modules.manifest import ManifestModule

class TestManifest(TestCase):

    def _log(self, *objs, error=False, level=0):
        print(*objs)

    def setUp(self) -> None:
        logger = Mock()
        logger.log.side_effect = self._log

        self.mock_mod = Mock()
        self.mock_mod.log.return_value=logger

        self.mock_env = Mock()
        self.mock_env.VCS_MANIFEST_DEFAULT_ITEM_SET = None
        self.mock_env.VCS_MANIFEST_ROOT = '/manifests'

    def test_item_basic(self):
        # Data
        manifest_store = Mock()
        manifest_store.get.side_effect = lambda key: {
            'test.manifest.txt': '\n'.join([
                'itemA'
            ])+'\n'
        }[key]

        # Initialise
        manifest = ManifestModule(manifest_store)

        # Configure
        manifest.configure(mod=self.mock_mod, env=self.mock_env)

        mock_context_module = Mock()
        mock_context_module_factory = Mock(return_value=mock_context_module)
        mock_context_module_factory.context_type.return_value = 'test'
        mock_context_module_factory.can_be_root.return_value = True
        manifest.add_context_modules(mock_context_module_factory)

        # Start
        manifest.start()

        # Test
        self.assertEqual(manifest.get_item('itemA'), {
            'ref': 'itemA',
            'tags': {}
        })
        mock_context_module.on_declare_item.assert_called_once_with(
            [{
                'type': 'test',
                'opts': {},
                'items': {
                    'itemA': {
                        'ref': 'itemA',
                        'tags': {}
                    }
                },
                'item_sets': {}
            }],
            {
                'ref': 'itemA',
                'tags': {}
            }
        )

    # TODO:

    # item with one tag (get its item set)
    # item with two tags (get their item sets)
    # two items with the same tag (get an item set)
    # two items with different tags (get all three item sets)

    # item set
    # item set & operator
    # item set | operator
    # item set precedence
    # item set precedence forcing with ()
    # item set operations on groups
    # item set group nesting

    # explicit context one item
    # explicit context item inside and out
    # explicit context item set
    # explicit context one parameter
    # explicit context two parameters
    # nested explicit contexts

    # exceptions from context modules
    # multiple context modules
    # multiple root context modules
