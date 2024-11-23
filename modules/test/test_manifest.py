from unittest import TestCase
from unittest.mock import MagicMock, Mock, call, mock_open, patch

# Util
from core.exceptions import LIMARException

# Test Fixtures
from modules.manifest_modules import uris_local, uris_remote

# Under Test
from modules.manifest import ManifestModule, ManifestItemTags

class TestManifest(TestCase):
    # NOTE: Side-effects are often used in these tests because
    #       assert_has_calls() doesn't account for mutation between calls.

    def _log(self, *objs, error=False, level=0):
        print(*objs)

    def _warning(self, *objs):
        self._log(*objs, level=1)

    def _get_cache(self, name):
        raise KeyError()

    def setUp(self):
        log_module = Mock()
        log_module.log.side_effect = self._log
        log_module.warning.side_effect = self._warning

        cache_module = Mock()
        cache_module.get.side_effect = self._get_cache
        cache_module.set.side_effect = lambda name, data: None
        cache_module.flush.side_effect = lambda: None

        self.mock_mod = Mock()
        self.mock_mod.log.return_value=log_module
        self.mock_mod.cache.return_value=cache_module

        self.mock_env = Mock()
        self.mock_env.LIMAR_MANIFEST_DEFAULT_ITEM_SET = None
        self.mock_env.LIMAR_MANIFEST_ROOT = '/manifests'
        self.mock_env.LIMAR_CACHE_ROOT = '/cache'

    def test_item_basic(self):
        # Input
        manifest_store = Mock()
        manifest_store.get.side_effect = lambda key: {
            'test.manifest.txt': '\n'.join([
                'itemA'
            ])+'\n'
        }[key]

        # Expected Output
        expected_items = {
            'itemA': {
                'ref': 'itemA',
                'tags': self._manifest_item_tags()
            }
        }
        expected_declare_item_calls = [
            call(
                [{
                'type': 'test',
                    'opts': {},
                    'items': expected_items,
                    'item_sets': {}
                }],
                expected_items['itemA']
            )
        ]

        # Run / Verify
        manifest, context_mod = self._basic_manifest_setup(manifest_store)
        context_mod.on_declare_item.side_effect = self._assert_has_calls(
            expected_declare_item_calls
        )
        manifest.start(mod=self.mock_mod) # Verifier runs here

        self.assertEqual(
            manifest.get_item('itemA'),
            self._item_with_finalised_tags(expected_items['itemA'])
        )
        context_mod.on_declare_item.assert_called()

    def test_item_tag(self):
        # Data
        manifest_store = Mock()
        manifest_store.get.side_effect = lambda key: {
            'test.manifest.txt': '\n'.join([
                'itemA (tagA)'
            ])+'\n'
        }[key]

        # Expected Output
        expected_items = {
            'itemA': {
                'ref': 'itemA',
                'tags': self._manifest_item_tags('tagA')
            }
        }
        expected_declare_item_calls = [
            call(
                [{
                'type': 'test',
                    'opts': {},
                    'items': expected_items,
                    'item_sets': {}
                }],
                expected_items['itemA']
            )
        ]

        # Run / Verify
        manifest, context_mod = self._basic_manifest_setup(manifest_store)
        context_mod.on_declare_item.side_effect = self._assert_has_calls(
            expected_declare_item_calls
        )
        manifest.start(mod=self.mock_mod) # Verifier runs here

        self.assertEqual(
            manifest.get_item('itemA'),
            self._item_with_finalised_tags(expected_items['itemA'])
        )
        self.assertEqual(
            manifest.get_item_set('tagA'),
            self._items_with_finalised_tags(expected_items)
        )
        context_mod.on_declare_item.assert_called()

    def test_item_tags(self):
        # Input
        manifest_store = Mock()
        manifest_store.get.side_effect = lambda key: {
            'test.manifest.txt': '\n'.join([
                'itemA (tagA, tagB)'
            ])+'\n'
        }[key]

        # Expected Output
        expected_items = {
            'itemA': {
                'ref': 'itemA',
                'tags': self._manifest_item_tags('tagA', 'tagB')
            }
        }
        expected_declare_item_calls = [
            call(
                [{
                'type': 'test',
                    'opts': {},
                    'items': expected_items,
                    'item_sets': {}
                }],
                expected_items['itemA']
            )
        ]

        # Run / Verify
        manifest, context_mod = self._basic_manifest_setup(manifest_store)
        context_mod.on_declare_item.side_effect = self._assert_has_calls(
            expected_declare_item_calls
        )
        manifest.start(mod=self.mock_mod) # Verifier runs here

        self.assertEqual(
            manifest.get_item('itemA'),
            self._item_with_finalised_tags(expected_items['itemA'])
        )
        self.assertEqual(
            manifest.get_item_set('tagA'),
            self._items_with_finalised_tags(expected_items)
        )
        context_mod.on_declare_item.assert_called()

    def test_items(self):
        # Input
        manifest_store = Mock()
        manifest_store.get.side_effect = lambda key: {
            'test.manifest.txt': '\n'.join([
                'itemA (tagA)',
                'itemB (tagA)'
            ])+'\n'
        }[key]

        # Expected Output
        expected_items = {
            'itemA': {
                'ref': 'itemA',
                'tags': self._manifest_item_tags('tagA')
            },
            'itemB': {
                'ref': 'itemB',
                'tags': self._manifest_item_tags('tagA')
            }
        }
        expected_declare_item_calls = [
            call(
                [{
                    'type': 'test',
                    'opts': {},
                    'items': {
                        'itemA': expected_items['itemA']
                    },
                    'item_sets': {}
                }],
                expected_items['itemA']
            ),
            call(
                [{
                    'type': 'test',
                    'opts': {},
                    'items': expected_items,
                    'item_sets': {}
                }],
                expected_items['itemB']
            )
        ]

        # Run / Verify
        manifest, context_mod = self._basic_manifest_setup(manifest_store)
        context_mod.on_declare_item.side_effect = self._assert_has_calls(
            expected_declare_item_calls
        )
        manifest.start(mod=self.mock_mod) # Verifier runs here

        self.assertEqual(
            manifest.get_item('itemA'),
            self._item_with_finalised_tags(expected_items['itemA'])
        )
        self.assertEqual(
            manifest.get_item_set('tagA'),
            self._items_with_finalised_tags(expected_items)
        )
        context_mod.on_declare_item.assert_called()

    def test_items_tags(self):
        # Input
        manifest_store = Mock()
        manifest_store.get.side_effect = lambda key: {
            'test.manifest.txt': '\n'.join([
                'itemA (tagA, tagB)',
                'itemB (tagA, tagC)'
            ])+'\n'
        }[key]

        # Expected Output
        expected_items = {
            'itemA': {
                'ref': 'itemA',
                'tags': self._manifest_item_tags('tagA', 'tagB')
            },
            'itemB': {
                'ref': 'itemB',
                'tags': self._manifest_item_tags('tagA', 'tagC')
            }
        }
        expected_declare_item_calls = [
            call(
                [{
                    'type': 'test',
                    'opts': {},
                    'items': {
                        'itemA': expected_items['itemA']
                    },
                    'item_sets': {}
                }],
                expected_items['itemA']
            ),
            call(
                [{
                    'type': 'test',
                    'opts': {},
                    'items': expected_items,
                    'item_sets': {}
                }],
                expected_items['itemB']
            )
        ]

        # Run / Verify
        manifest, context_mod = self._basic_manifest_setup(manifest_store)
        context_mod.on_declare_item.side_effect = self._assert_has_calls(
            expected_declare_item_calls
        )
        manifest.start(mod=self.mock_mod) # Verifier runs here

        self.assertEqual(
            manifest.get_item('itemA'),
            self._item_with_finalised_tags(expected_items['itemA'])
        )
        self.assertEqual(
            manifest.get_item_set('tagA'),
            self._items_with_finalised_tags(expected_items)
        )
        self.assertEqual(
            manifest.get_item_set('tagB'),
            self._items_with_finalised_tags({
                k: expected_items[k] for k in ['itemA']
            })
        )
        self.assertEqual(
            manifest.get_item_set('tagC'),
            self._items_with_finalised_tags({
                k: expected_items[k] for k in ['itemB']
            })
        )
        context_mod.on_declare_item.assert_called()

    # TODO:

    # ./ an item

    # ./ item with one tag (get its item set)
    # ./ item with two tags (get their item sets)
    # ./ two items with the same tag (get an item set)
    # ./ two items with different tags (get all three item sets)

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

    def _basic_manifest_setup(self, manifest_store):
        # Initialise
        manifest = ManifestModule(manifest_store)

        # Configure
        manifest.configure(mod=self.mock_mod, env=self.mock_env)

        mock_context_module = Mock()
        mock_context_module_factory = Mock(return_value=mock_context_module)
        mock_context_module_factory.context_type.return_value = 'test'
        mock_context_module_factory.can_be_root.return_value = True
        manifest.add_context_modules(mock_context_module_factory)

        return (manifest, mock_context_module)

    def _manifest_item_tags(self, *names, **tags):
        tags_obj = ManifestItemTags()
        tags_obj.add(*names, **tags)
        return tags_obj

    def _item_with_finalised_tags(self, item):
        return {
            **item,
            'tags': item['tags'].raw()
        }

    def _items_with_finalised_tags(self, items):
        return {
            ref: self._item_with_finalised_tags(item)
            for ref, item in items.items()
        }

    def _assert_has_calls(self, expected_calls):
        call_num = 0
        def _verifier(*args, **kwargs):
            nonlocal call_num
            # print('got:', call(*args, **kwargs))
            # print('expected:', expected_calls[call_num])
            self.assertEqual(call(*args, **kwargs), expected_calls[call_num])
            call_num += 1
            self.assertLessEqual(call_num, len(expected_calls))
        return _verifier
