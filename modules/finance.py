from math import ceil
from datetime import date, timedelta
import random
from dateutil.relativedelta import relativedelta, MO
from frozendict import frozendict

from core.exceptions import LIMARException
from core.modules.phase_utils.phase_system import PhaseSystem
from core.modules.phase_utils.phased_process import PhasedProcess

from modules.finance_utils.currency_amount import CurrencyAmount
from modules.manifest_modules import (
    # Generic
    tags,

    # Projects
    finance,
    financial_account,
    financial_transaction
)

# Types
from argparse import ArgumentParser, Namespace
from typing import Any, Callable, Hashable
from modules.manifest import Item, ItemSet

ItemGroup = ItemSet
ItemGroupSet = dict[frozendict[str, Hashable], ItemGroup]

FINANCE_LIFECYCLE = PhaseSystem(
    'finance.lifecycle',
    (
        'INITIALISE',
        'GET',
        'PREPARE',
        'WINDOW',
        'DISTRIBUTE',
        'FINALISE',
        'WRAP_IN_GROUP',
        'GROUP_BY_ACCOUNT',
        'GROUP_BY_TIME',
        'FILTER_GROUPS',
        'AGGREGATE',
        'TABULATE',
        'RENDER'
    ),
    {
        'WINDOW': ('FINALISE',),
        'FINALISE': (
            'GROUP_BY_ACCOUNT',
            'GROUP_BY_TIME',
            'FILTER_GROUPS',
            'AGGREGATE',
            'TABULATE'
        ),
        'WRAP_IN_GROUP': (
            'GROUP_BY_TIME',
            'FILTER_GROUPS',
            'AGGREGATE',
            'TABULATE'
        ),
        'GROUP_BY_ACCOUNT': ('FILTER_GROUPS', 'AGGREGATE', 'TABULATE'),
        'GROUP_BY_TIME': ('AGGREGATE', 'TABULATE'),
        'FILTER_GROUPS': ('TABULATE',)
    }
)

class FinanceModule:
    """
    MM module for managing financial accounts and transactions.
    """

    # Lifecycle
    # --------------------------------------------------

    def dependencies(self):
        return ['manifest']

    def configure_args(self, *, mod: Namespace, parser: ArgumentParser, **_):
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

        parser.add_argument('-fg', '--filter-groups', metavar='FUNCTION',
            default=None,
            help="""
            If given, filter the grouped data using the given filter function
            before aggregating.
            """)

        parser.add_argument('-a', '--aggregate', metavar='AGGREGATOR',
            default=None,
            help="""
            If given, aggregate the final data set by using the given aggregator
            against the amount field.
            The aggregator must be one of: sum, mean, median, min, max.
            """)

        # Output Controls
        mod.phase.configure_phase_control_args(parser)
        parser.add_argument('---',
            action='store_true', default=False, dest='output_is_forward',
            help="""
            Specifies that the result of this module call should be forwarded to
            another module. This option terminates this module call.
            """)

    def configure(self, *, mod: Namespace, **_):
        mod.phase.register_system(FINANCE_LIFECYCLE)
        mod.manifest.add_context_modules(
            tags.Tags,
            finance.Finance,
            financial_account.FinancialAccount,
            financial_transaction.FinancialTransaction
        )

    def __call__(self, *,
            mod: Namespace,
            args: Namespace,
            forwarded_data: Any,
            **_
    ):
        # Set up phase process and a common transition function
        invokation_process_name = (
            'finance.lifecycle_instance.' +
            ''.join(random.choices('0123456789abcdef', k=6))
        )

        mod.phase.register_process(PhasedProcess(
            invokation_process_name,
            FINANCE_LIFECYCLE,
            FINANCE_LIFECYCLE.PHASES.INITIALISE
        ))

        # WARNING: THIS MUTATES STATE, even though it's used in `if` statements
        transition_to_phase = lambda phase, default=True: (
            mod.phase.transition_to_phase(
                invokation_process_name, phase, args, default
            )
        )

        # Start from where the forwarding chain left off
        output = forwarded_data

        # Fetch data
        if transition_to_phase(FINANCE_LIFECYCLE.PHASES.GET):
            output = mod.manifest.get_item_set('transaction')

        # Select the props we want from each item and set default cover
        # period where needed to the latest of the paid date or the cleared
        # date.
        if transition_to_phase(FINANCE_LIFECYCLE.PHASES.PREPARE):
            output = self._extract_and_prepare(output)

        # Filter out transactions not in the specified window and bound the
        # cover period of each transaction to the window.
        if transition_to_phase(FINANCE_LIFECYCLE.PHASES.WINDOW):
            if args.window is not None:
                window_start, window_end = (
                    date(*[
                        int(component)
                        for component in bound.split('-')
                    ])
                    for bound in args.window.split(':')
                )

                output = self._window(output, window_start, window_end)
            else:
                output = self._infinite_window(output)

        # Distribute transactions across their cover period
        if (
            args.distribute is not None and
            transition_to_phase(FINANCE_LIFECYCLE.PHASES.DISTRIBUTE)
        ):
            period_length = timedelta(days=int(args.distribute))
            output = self._distribute(output, period_length)

        # Undo the precision increase (aka. un-prepare)
        if transition_to_phase(FINANCE_LIFECYCLE.PHASES.FINALISE):
            output = self._finalise(output)

        # Create a single group initially
        if transition_to_phase(FINANCE_LIFECYCLE.PHASES.WRAP_IN_GROUP):
            output = {frozendict(): output}

        # Group by account
        if (
            args.group_by_account is True and
            transition_to_phase(FINANCE_LIFECYCLE.PHASES.GROUP_BY_ACCOUNT)
        ):
            output = self._group_by_account(output)

        # Group by time
        if (
            args.group_by_time is not None and
            transition_to_phase(FINANCE_LIFECYCLE.PHASES.GROUP_BY_TIME)
        ):
            unit = args.group_by_time
            output = self._group_by_time(output, unit)

        # Filter groups
        if (
            args.filter_groups is not None and
            transition_to_phase(FINANCE_LIFECYCLE.PHASES.FILTER_GROUPS)
        ):
            output = self._filter_groups(output, args.filter_groups)

        # Aggregate the amounts in each group
        if (
            args.aggregate is not None and
            transition_to_phase(FINANCE_LIFECYCLE.PHASES.AGGREGATE)
        ):
            output = self._aggregate(output, args.aggregate)

        # Format
        if args.group_by_account is True or args.group_by_time is not None:
            if args.aggregate is not None:
                # Format - window/distribute + group + aggregate
                if transition_to_phase(
                    FINANCE_LIFECYCLE.PHASES.TABULATE,
                    not args.output_is_forward
                ):
                    output = mod.tr.tabulate(output, obj_mapping='all')

                if transition_to_phase(
                    FINANCE_LIFECYCLE.PHASES.RENDER, not args.output_is_forward
                ):
                    output = mod.tr.render_table(output, has_headers=True)

            else:
                # Format - window/distribute + group
                if transition_to_phase(
                    FINANCE_LIFECYCLE.PHASES.TABULATE,
                    not args.output_is_forward
                ):
                    output = {
                        ref: mod.tr.tabulate(table_data, obj_mapping='all')
                        for ref, table_data in output.items()
                    }

                if transition_to_phase(
                    FINANCE_LIFECYCLE.PHASES.RENDER, not args.output_is_forward
                ):
                    output = mod.tr.render_tree(
                        [
                            mod.tr.render_table(
                                table, has_headers=True,
                                title=f"[red]{ref}", title_justify='left'
                            )
                            for ref, table in output.items()
                        ],
                        label='Groups'
                    )

        else:
            # Format - window/distribute
            if transition_to_phase(
                FINANCE_LIFECYCLE.PHASES.TABULATE, not args.output_is_forward
            ):
                output = mod.tr.tabulate(output.values(), obj_mapping='all')

            if transition_to_phase(
                FINANCE_LIFECYCLE.PHASES.RENDER, not args.output_is_forward
            ):
                output = mod.tr.render_table(output, has_headers=True)

        # Forward
        return output

    # Main Process
    # --------------------------------------------------

    def _extract_and_prepare(self, item_set):
        return {
            ref: {
                'ref': item['ref'],
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
                'amount': CurrencyAmount(
                    item['amount'].currency,
                    item['amount'].amount * 100
                ),
                'for': item['for']
            }
            for ref, item in item_set.items()
        }

    def _window(self, item_set, window_start, window_end):
        # Throw an error in case this was accidental. This would always
        # return zero results if we didn't catch it.
        if window_start > window_end:
            raise LIMARException(
                f"Given window start '{window_start}' is after window end"
                f" '{window_end}'"
            )

        return {
            ref: dict(
                item,
                coverStartWindowed=max(item['coverStart'], window_start),
                coverEndWindowed=min(item['coverEnd'], window_end)
            )
            for ref, item in item_set.items()
            if (
                item['coverEnd'] >= window_start
                and item['coverStart'] <= window_end
            )
        }

    def _infinite_window(self, item_set):
        return {
            ref: item | {
                'coverStartWindowed': item['coverStart'],
                'coverEndWindowed': item['coverEnd']
            }
            for ref, item in item_set.items()
        }

    def _distribute_item(self, ref: str, item: Item, period_length: timedelta):
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
                'amount': CurrencyAmount(
                    item['amount'].currency,
                    # WARNING: THIS MAY MAKE MONEY DISAPPEAR
                    # But will be APPROXIMATELY accurate.
                    int(
                        item['amount'].amount
                        * (period_size / cover_size)
                    )
                )
            }

        return item_set

    def _distribute(self, item_set: ItemSet, period_length: timedelta):
            return {
                ref: item
                for item_set in [
                    self._distribute_item(ref, item, period_length)
                    for ref, item in item_set.items()
                ]
                for ref, item in item_set.items()
            }

    def _finalise(self, item_set):
        return {
            ref: item | {
                'amount': CurrencyAmount(
                    item['amount'].currency,
                    item['amount'].amount // 100
                )
            }
            for ref, item in item_set.items()
        }

    def _group_group_by_account(self,
            item_group_ref: frozendict[str, Hashable],
            item_group: ItemGroup
    ) -> ItemGroupSet:
        """
        Group the given group by account, returning the resulting set of groups.
        """

        by_account = {}
        for item_ref, item in item_group.items():
            from_account_ref = frozendict(**item_group_ref, account=item['from']['ref'])
            if from_account_ref not in by_account:
                by_account[from_account_ref] = {}
            by_account[from_account_ref][item_ref] = item | {
                'account': item['from'],
                'amount': CurrencyAmount(
                    item['amount'].currency,
                    -item['amount'].amount
                )
            }
            del by_account[from_account_ref][item_ref]['from']
            del by_account[from_account_ref][item_ref]['to']

            to_account_ref = frozendict(**item_group_ref, account=item['to']['ref'])
            if to_account_ref not in by_account:
                by_account[to_account_ref] = {}
            by_account[to_account_ref][item_ref] = item | {
                'account': item['to']
            }
            del by_account[to_account_ref][item_ref]['from']
            del by_account[to_account_ref][item_ref]['to']

        return by_account

    def _group_by_account(self, groups: ItemGroupSet) -> ItemGroupSet:
        return {
            new_item_group_ref: new_item_group
            for item_groups in [
                self._group_group_by_account(item_group_ref, item_group)
                for item_group_ref, item_group in groups.items()
            ]
            for new_item_group_ref, new_item_group in item_groups.items()
        }

    def _group_group_by_time(self,
            item_group_ref: frozendict[str, Hashable],
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

            time_ref = frozendict(**item_group_ref, date=start_aligned_str)
            if time_ref not in by_time:
                by_time[time_ref] = {}
            by_time[time_ref][ref] = item

        return by_time

    def _group_by_time(self, groups: ItemGroupSet, unit: str) -> ItemGroupSet:
        # Group and merge
        return {
            new_item_group_ref: new_item_group
            for item_groups in [
                self._group_group_by_time(item_group_ref, item_group, unit)
                for item_group_ref, item_group in groups.items()
            ]
            for new_item_group_ref, new_item_group in item_groups.items()
        }

    def _filter_account_type(self,
            ref: frozendict[str, Hashable],
            group: ItemGroup,
            value: Any
    ) -> bool:
        return next(iter(group.values()))['account']['tags']['type'] == value

    def _filter_groups(self, groups: ItemGroupSet, filter: str) -> ItemGroupSet:
        _filters: dict[
            str,
            Callable[[frozendict[str, Hashable], ItemGroup, Any], bool]
        ] = {
            'account-type': self._filter_account_type
        }

        filter_name, filter_value = filter.split('=')

        return {
            item_group_ref: item_group
            for item_group_ref, item_group in groups.items()
            if _filters[filter_name](item_group_ref, item_group, filter_value)
        }

    def _aggregate_sum(self,
            iterable,
            key: Callable[[Any], int] | None = None
    ):
        return sum([
            (
                key(item)
                if key is not None
                else iterable
            )
            for item in iterable
        ])
    def _aggregate_mean(self,
            iterable,
            key: Callable[[Any], int] | None = None
    ):
        return (
            self._aggregate_sum(iterable, key) / len(iterable)
            if len(iterable) > 0
            else None
        )
    def _aggregate_median(self,
            iterable,
            key: Callable[[Any], int] | None = None
    ):
        # Based on: https://stackoverflow.com/a/68719018/16967315
        sorted_iterable = sorted(iterable, key=key)
        return (
            # These might be structures that aren't averagable (ie. `(a+b)//2``),
            # so take both.
            (
                sorted_iterable[ceil(len(sorted_iterable)/2) - 1],
                sorted_iterable[-ceil(len(sorted_iterable)/2)]
            )
            if len(iterable) > 0
            else None
        )

    def _aggregate(self, groups: ItemGroupSet, aggregator: str):
        _aggregators = {
            'sum': self._aggregate_sum,
            'mean': self._aggregate_mean,
            'median': self._aggregate_median,
            'min': min,
            'max': max
        }

        aggregator_fn = _aggregators[aggregator]

        aggregation = {}
        for item_group_ref, item_group in groups.items():
            currency_discovery: str | None = None
            for item in item_group.values():
                if currency_discovery is None:
                    currency_discovery = item['amount'].currency

                if currency_discovery != item['amount'].currency:
                    raise LIMARException(
                        f"Found different currencies '{currency_discovery}' and"
                        f" '{item['amount'].currency}' when aggregating item"
                        f" group '{item_group_ref}': Cannot aggregate amounts"
                        " in different currencies"
                    )

            if currency_discovery is None:
                # Shouldn't be possible, but it keeps the type checker happy
                raise LIMARException(
                    "No currency found when aggregating item group"
                    f" '{item_group_ref}'"
                )
            currency = currency_discovery

            aggregate_ref = ' / '.join([
                str(val)
                for val in item_group_ref.values()
            ])
            aggregation[aggregate_ref] = {
                'ref': aggregate_ref,
                **item_group_ref,
                'amount': CurrencyAmount(
                    currency,
                    aggregator_fn(
                        item_group.values(),
                        key=lambda item: item['amount'].amount
                    )
                )
            }

        return aggregation
