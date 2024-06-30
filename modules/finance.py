from argparse import ArgumentParser, Namespace
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta, MO

from core.exceptions import VCSException
from modules.manifest import ItemSet
from modules.manifest_modules import (
    # Generic
    tags,

    # Projects
    finance,
    financial_account,
    financial_transaction
)

ItemGroup = ItemSet
ItemGroupSet = dict[str, ItemGroup]

class FinanceModule:

    # Lifecycle
    # --------------------

    def dependencies(self):
        return ['manifest']

    def configure(self, *, mod: Namespace, **_):
        mod.manifest.add_context_modules(
            tags.Tags,
            finance.Finance,
            financial_account.FinancialAccount,
            financial_transaction.FinancialTransaction
        )

    def configure_args(self, *, parser: ArgumentParser, **_):
        # Filter, Group, and Distribute (inc. window param); graphically:
        #
        #   Transaction:
        #         clearned
        #       paid |  coverStart               coverEnd
        #          |-|--|---------------------------|
        # 2023-01-23 |  2023-01-28              2023-02-25
        #        2023-01-25
        #
        #   Window:
        #             :window_start               :window_end
        #                   |--------------------------|
        #               2023-02-01                 2023-02-28
        #
        #   Periods:
        #              2023-02-01    2023-02-15     2023-02-01   
        #                   |------|------|------|--|
        #                     2023-02-08    2023-02-08
        #
        # In general, the smaller the period unit given, the less temporal drift
        # there will be in the results, but the more inaccuracy there will be
        # due to rounding error. Because of this trade-off, the user is required
        # to select a period that is appropriate for their computation.

        parser.add_argument('-w', '--window', metavar='START_DATE:END_DATE',
            default=None,
            help="""
            If given, filter the results to only the given time period, given in
            the format 'yyyy-mm-dd:yyyy-mm-dd'. If `--distribute` is also given,
            then the distribution of cover periods that start before this window
            but overlap with this window will be aligned to the start of this
            window, not the start of the cover period.
            """)

        parser.add_argument('-d', '--distribute', metavar='PERIOD_LENGTH',
            default=None,
            help="""
            Distribute the amount of each transaction across its cover period in
            increments of the given period length, which is given in days.
            Transactions without a cover period are not distributed.
            """)

        parser.add_argument('-ga', '--group-by-account',
            action='store_true', default=False,
            help="""If given, group the data by account before aggregating.""")

        parser.add_argument('-gt', '--group-by-time', metavar='UNIT',
            default=None, choices=('day', 'week', 'month', 'year'),
            help="""
            If given, group the data into the given calendar unit (one of 'day',
            'week', 'month', or 'year') before aggregating.
            """)

        parser.add_argument('-a', '--aggregate', metavar='AGGREGATOR',
            default=None,
            help="""
            If given, aggregate the final data set by using the given aggregator
            against the amount field.
            The aggregator must be one of: sum, mean, median, min, max.
            """)

        # Subcommands / Resolve Item Set - Output Controls
        parser.add_argument('-L', '--lower-stage', default=None,
            help="""
            Specifies that all stages of processing up to the given stage should
            be performed, even if the result is being forwarded.
            """)
        parser.add_argument('-U', '--upper-stage', default=None,
            help="""
            Specifies that no stages of processing after the given stage should
            be performed, even if the result isn't being forwarded.
            """)
        parser.add_argument('---',
            action='store_true', default=False, dest='output_is_forward',
            help="""
            Specifies that the result of this module call should be forwarded to
            another module. This option terminates this module call.
            """)

    STAGES = [
        'get',
        'compute',
        'tabulate',
        'render'
    ]

    def __call__(self, *, mod: Namespace, args: Namespace, **_):
        # Check args
        # if (
        #     (
        #         args.aggregate is not None
        #         or args.group_by_account is True
        #         or args.group_by_time is not None
        #     ) and (
        #         args.aggregate is None or (
        #             args.group_by_account is False
        #             and args.group_by_time is None
        #         )
        #     )
        # ):
        #     raise VCSException(
        #         'Aggregation or grouping was requested, but not both. Similar'
        #         ' to SQL, to aggregate you must group, and if grouping you must'
        #         ' aggragate.'
        #     )

        # Fetch data
        output = mod.manifest.get_item_set('transaction')

        # Select the props we want from each item and set default cover period
        # where needed to the latest of the paid date or the cleared date.
        output = {
            ref: {
                'from': item['from'],
                'to': item['to'],
                'paid': item['paid'],
                'cleared': item['cleared'],
                'coverStart': (
                    item['coverStart']
                    if item['coverStart'] is not None
                    else max(
                        default
                        for default in (item['paid'], item['cleared'])
                        if default is not None
                    )
                ),
                'coverEnd': (
                    item['coverEnd']
                    if item['coverEnd'] is not None
                    else max(
                        default
                        for default in (item['paid'], item['cleared'])
                        if default is not None
                    )
                ),
                # For retaining precision while doing calculations
                'amount': item['amount'] | {
                    'amount': item['amount']['amount'] * 100
                },
                'for': item['for']
            }
            for ref, item in output.items()
        }

        # Filter out transactions not in the specified window and bound the
        # cover period of each transaction to the window.
        if args.window is not None:
            window_start, window_end = (
                date(*[
                    int(component)
                    for component in bound.split('-')
                ])
                for bound in args.window.split(':')
            )

            # Throw an error in case this was accidental. This would always
            # return zero results if we didn't catch it.
            if window_start > window_end:
                raise VCSException(
                    f"Given window start '{window_start}' is after window end"
                    f" '{window_end}'"
                )

            output = {
                ref: dict(
                    item,
                    coverStartWindowed=max(item['coverStart'], window_start),
                    coverEndWindowed=min(item['coverEnd'], window_end)
                )
                for ref, item in output.items()
                if (
                    item['coverEnd'] >= window_start
                    and item['coverStart'] <= window_end
                )
            }

        # Distribute transactions across their cover period
        if args.distribute is not None:
            period_length = timedelta(days=int(args.distribute))

            def distribute(ref, item):
                cover_size = (
                    item['coverEnd']
                    - item['coverStart']
                    + timedelta(days=1) # To make end date inclusive
                )
                windowed_cover_size = (
                    item['coverEndWindowed']
                    - item['coverStartWindowed']
                    + timedelta(days=1) # To make end date inclusive
                )

                full_periods, remaining_period = divmod(
                    windowed_cover_size,
                    period_length
                )

                item_set = {}
                for i in range(
                    0, full_periods + int(remaining_period > timedelta(days=0))
                ):
                    period_start = item['coverStartWindowed'] + i*period_length
                    period_end = min(
                        (
                            period_start + period_length
                            - timedelta(days=1) # Periods are non-overlaping
                        ),
                        item['coverEndWindowed']
                    )
                    period_size = period_end - period_start + timedelta(days=1)

                    item_set[f'{ref}[{i}]'] = item | {
                        'ref': f'{ref}[{i}]',
                        'periodStart': period_start,
                        'periodEnd': period_end,
                        'amount': item['amount'] | {
                            'amount': (
                                item['amount']['amount']
                                * period_size
                                // cover_size
                            )
                        }
                    }

                return item_set

            # Distribute and merge
            output = {
                ref: item
                for item_set in [
                    distribute(ref, item)
                    for ref, item in output.items()
                ]
                for ref, item in item_set.items()
            }

        # Undo the precision increase
        output = {
            ref: item | {
                'amount': item['amount'] | {
                    'amount': item['amount']['amount'] // 100
                }
            }
            for ref, item in output.items()
        }

        # Group
        # Create a single group
        groups: ItemGroupSet = {
            min(
                output.values(),
                key=lambda item: item['periodStart']
            )['coverStart']: output
        }

        if args.group_by_account is True:
            def group_by_account(
                    item_group_ref: str,
                    item_group: ItemGroup
            ) -> ItemGroupSet:
                by_account = {}
                for ref, item in item_group.items():
                    from_ref = f"{item_group_ref} / {item['from']['ref']}"
                    if from_ref not in by_account:
                        by_account[from_ref] = {}
                    by_account[from_ref][ref] = item

                    to_ref = f"{item_group_ref} / {item['to']['ref']}"
                    if to_ref not in by_account:
                        by_account[to_ref] = {}
                    by_account[to_ref][ref] = item

                return by_account

            # Group and merge
            groups = {
                new_item_group_ref: new_item_group
                for item_groups in [
                    group_by_account(item_group_ref, item_group)
                    for item_group_ref, item_group in groups.items()
                ]
                for new_item_group_ref, new_item_group in item_groups.items()
            }

        if args.group_by_time is not None:
            unit = args.group_by_time

            def group_by_time(
                    item_group_ref: str,
                    item_group: ItemGroup,
                    unit: str
            ) -> ItemGroupSet:
                by_time = {}
                for ref, item in item_group.items():
                    start: date = item['periodStart']

                    start_aligned = start
                    start_aligned_str = start_aligned.strftime('%Y-%m-%d')
                    if unit == 'week':
                        start_aligned = start + relativedelta(weekday=MO(-1))
                        start_aligned_str = start_aligned.strftime(
                            'wc. %Y-%m-%d'
                        )
                    elif unit == 'month':
                        start_aligned = start + relativedelta(day=1)
                        start_aligned_str = start_aligned.strftime('%Y-%m')
                    elif unit == 'year':
                        start_aligned = start + relativedelta(yearday=1)
                        start_aligned_str = start_aligned.strftime('%Y')

                    time_ref = f"{item_group_ref} / {start_aligned_str}"
                    if time_ref not in by_time:
                        by_time[time_ref] = {}
                    by_time[time_ref][ref] = item

                return by_time

            # Group and merge
            groups = {
                new_item_group_ref: new_item_group
                for item_groups in [
                    group_by_time(item_group_ref, item_group, unit)
                    for item_group_ref, item_group in groups.items()
                ]
                for new_item_group_ref, new_item_group in item_groups.items()
            }

        # Aggregate
        # if args.aggregate is not None:
        #     aggregator = args.aggregate

        #     aggregators = {
        #         'sum': sum,
        #         'mean': lambda data: (
        #             sum(data) / len(data)
        #             if len(data) > 0
        #             else None
        #         ),
        #         # Based on: https://stackoverflow.com/a/68719018/16967315
        #         'median': lambda data: (
        #             (lambda data_sorted:
        #                 (
        #                     data_sorted[ceil(len(data_sorted)/2) - 1]
        #                     + data_sorted[-ceil(len(data_sorted)/2)]
        #                 )
        #                 //2
        #             )(sorted(data))
        #             if len(data) > 0
        #             else None
        #         ),
        #         'min': min,
        #         'max': max
        #     }

        #     output = {
        #         ref: {
        #             aggregators[aggregator](item_group)
        #         }
        #         for ref, item_group in groups
        #     }

        # Format
        # if self._should_run_stage('tabulate',
        #     args.output_is_forward, args.lower_stage, args.upper_stage
        # ):
        #     output = mod.tr.tabulate(output, obj_mapping='all')

        # if self._should_run_stage('render',
        #     args.output_is_forward, args.lower_stage, args.upper_stage
        # ):
        #     output = mod.tr.render_table(output, has_headers=True)

        output = groups

        if self._should_run_stage('tabulate',
            args.output_is_forward, args.lower_stage, args.upper_stage
        ):
            output = {
                ref: mod.tr.tabulate(table_data, obj_mapping='all')
                for ref, table_data in output.items()
            }

        if self._should_run_stage('render',
            args.output_is_forward, args.lower_stage, args.upper_stage
        ):
            output = mod.tr.render_tree(
                [
                    mod.tr.render_table(
                        table, has_headers=True,
                        title=ref, title_justify='left'
                    )
                    for ref, table in output.items()
                ],
                label='Groups'
            )

        # Forward
        return output

    # Stage Management

    def _stage_is_at_or_before(self, target: str, upper: str | None):
        if upper is None:
            return True
        return self.STAGES.index(target) <= self.STAGES.index(upper)

    def _should_run_stage(self,
            stage: str,
            forwarded: bool,
            lower_stage: str | None = None,
            upper_stage: str | None = None
    ):
        include_if_not_reached_lower_stage = (
            lower_stage is not None and
            self._stage_is_at_or_before(stage, lower_stage)
        )
        include_if_not_reached_upper_stage = (
            self._stage_is_at_or_before(stage, upper_stage)
        )

        return (
            (
                not forwarded or
                include_if_not_reached_lower_stage
            ) and
            include_if_not_reached_upper_stage
        )
