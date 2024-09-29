from unittest import TestCase

from modules.manifest_modules.query import Query

class TestQuery(TestCase):
    def test_group_fragments_params_blank(self):
        q = Query()
        self.assertEqual(
            q._group_fragments_params([''], [], ','),
            [([''], [])]
        )

    def test_group_fragments_params_constant(self):
        q = Query()
        self.assertEqual(
            q._group_fragments_params(['x'], [], ','),
            [(['x'], [])]
        )

    def test_group_fragments_params_interpolate_basic(self):
        q = Query()
        self.assertEqual(
            q._group_fragments_params(
                ['x is ', ' but not yet ', ' I think'],
                [('a','m',(),None,'$'), ('a','m2',(),None,'$')],
                ','
            ),
            [
                (
                    ['x is ', ' but not yet ', ' I think'],
                    [('a', 'm', (), None, '$'), ('a', 'm2', (), None, '$')]
                )
            ]
        )

    def test_group_fragments_params_interpolate_two_args(self):
        q = Query()
        self.assertEqual(
            q._group_fragments_params(
                ['x is ', ', but not yet ', ' I think'],
                [('a','m',(),None,'$'), ('a','m2',(),None,'$')],
                ','
            ),
            [
                (
                    ['x is ', ''],
                    [('a', 'm', (), None, '$')]
                ),
                (
                    [' but not yet ', ' I think'],
                    [('a', 'm2', (), None, '$')]
                )
            ]
        )

    def test_group_fragments_params_interpolate_multiple_params_per_fragment(self):
        q = Query()
        self.assertEqual(
            q._group_fragments_params(
                [
                    'feature/',
                    '{',
                    '}, feature/',
                    ', feature/',
                    ''
                ],
                [
                    ('mod','name',(),None,'$'),
                    ('mod','back',(),None,'$'),
                    ('mod','name',('upstream',),None,'$'),
                    ('mod','name',('full',),None,'$')
                ],
                ', '
            ),
            [
                (
                    ['feature/', '{', '}'],
                    [
                        ('mod', 'name', (), None, '$'),
                        ('mod', 'back', (), None, '$')
                    ]
                ), (
                    ['feature/', ''],
                    [('mod', 'name', ('upstream',), None, '$')]
                ), (
                    ['feature/', ''],
                    [('mod', 'name', ('full',), None, '$')]
                )
            ]
        )

    def test_group_fragments_params_interpolate_multiple_groups_per_fragment(self):
        q = Query()
        self.assertEqual(
            q._group_fragments_params(
                [
                    'interpolate, once, per ',
                    ' fragment, but this, can(',
                    '), be done'
                ],
                [
                    ('mod','test1',(),None,'$'),
                    ('mod','test2',(),None,'$'),
                ],
                ', '
            ),
            [
                (['interpolate'], []),
                (['once'], []),
                (['per ', ' fragment'], [('mod','test1',(),None,'$')]),
                (['but this'], []),
                (['can(', ')'], [('mod','test2',(),None,'$')]),
                (['be done'], [])
            ]
        )

    def test_group_fragments_params_chaining(self):
        q = Query()
        self.assertEqual(
            [
                q._chain_fragments_params(fragments, parameters)
                for fragments, parameters in q._group_fragments_params(
                    [
                        'feature/',
                        '{',
                        '}, feature/',
                        ', feature/',
                        ''
                    ],
                    [
                        ('mod','name',(),None,'$'),
                        ('mod','back',(),None,'$'),
                        ('mod','name',('upstream',),None,'$'),
                        ('mod','name',('full',),None,'$')
                    ],
                    ', '
                )
            ],
            [
                ['feature/', ('mod', 'name', (), None, '$'), '{', ('mod', 'back', (), None, '$'), '}'],
                ['feature/', ('mod', 'name', ('upstream',), None, '$')],
                ['feature/', ('mod', 'name', ('full',), None, '$')]
            ]
        )
