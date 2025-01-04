from datetime import date
from enum import Enum

from core.exceptions import LIMARException

# Types
from modules.finance_utils.currency_amount import CurrencyAmount
from modules.manifest import Item, ItemSet

class TagType(Enum):
    none = 'none'
    string = 'string'
    integer = 'integer'
    currency = 'currency'
    date = 'date'
    ref = 'ref'

class FinancialTransaction:
    # Lifecycle
    # --------------------------------------------------

    @staticmethod
    def context_type():
        return 'transaction'

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('transaction')

        if 'from' not in item['tags']:
            item['tags'].add(**{'from': next(
                context['opts']['default-account']
                for context in reversed(contexts)
                if 'default-account' in context['opts']
            )})
        if 'to' not in item['tags']:
            item['tags'].add(to=next(
                context['opts']['default-account']
                for context in reversed(contexts)
                if 'default-account' in context['opts']
            ))

        if any(
            'unverified' in context['opts']
            for context in contexts
        ):
            item['tags'].add('unverified')

    def on_exit_manifest(self, items, item_sets, *_, **__):
        for item in items.values():
            if 'transaction' in item['tags']:
                self._parse_and_update(item, items)

    # Utils
    # --------------------------------------------------

    def _parse_and_update(self, item, items):
        # From and to accounts
        item['from'] = self._parse_tag(item, 'from', TagType.ref, items=items)
        item['to'] = self._parse_tag(item, 'to', TagType.ref, items=items)

        if item['from'] == item['to']:
            raise LIMARException(
                f"Cannot create transaction '{item['ref']}' from and to the"
                " same account"
            )

        # Paid and cleared dates
        item['paid'] = self._parse_tag(
            item, 'paid', type=TagType.date, default=None
        )
        item['cleared'] = self._parse_tag(
            item, 'cleared', type=TagType.date, default=None
        )

        if item['paid'] is None and item['cleared'] is None:
            raise LIMARException(
                f"Transaction '{item['ref']}' missing both a paid and cleared"
                " date (at least one is required)"
            )

        # Cover period start and end dates
        item['coverStart'] = self._parse_tag(
            item, 'coverStart', type=TagType.date, default=None
        )
        item['coverEnd'] = self._parse_tag(
            item, 'coverEnd', type=TagType.date, default=None
        )

        # Amount
        item['amount'] = self._parse_tag(item, 'amount', type=TagType.currency)

        # The good(s)/service(s) that were received/given in the transaction
        item['for'] = self._parse_tag(
            item, 'for', type=TagType.string, default=None
        )

    @staticmethod
    def _parse_tag(
            item: Item,
            name: str,
            type: TagType | None = None,
            items: ItemSet | None = None,
            **kwargs
    ):
        if items is None:
            items = {}

        # Optional tag
        if name not in item['tags']:
            if 'default' in kwargs:
                return kwargs['default']
            else:
                raise ValueError(
                    f"Missing required tag '{name}' in item '{item['ref']}'"
                )

        # Optional tag value
        tag_value = item['tags'].get(name)
        if tag_value is None:
            if type == TagType.none:
                return None
            else:
                raise ValueError(
                    f"Missing value of tag '{name}' in item '{item['ref']}'"
                )
        elif type == TagType.none:
            raise ValueError(
                f"Tag '{name}' has value '{tag_value}' in item"
                f" '{item['ref']}', but no tag value was expected"
            )

        # Type conversions
        if type == TagType.string:
            return tag_value

        elif type == TagType.integer:
            return int(tag_value)

        elif type == TagType.currency:
            tag_value_parsed = tag_value

            tag_currency = '£'
            if not tag_value_parsed[0].isdigit():
                tag_currency = tag_value_parsed[0]
                tag_value_parsed = tag_value_parsed[1:]

            # Store and process in the lowest unit of the currency to avoid
            # floating point errors. This forces a fractional part to be given.
            (whole_amount, fractional_amount) = tag_value_parsed.split('.')
            tag_amount = (
                int(whole_amount.replace('[,]', ''))
                * 10 ** len(fractional_amount)
                + int(fractional_amount)
            )

            return CurrencyAmount(tag_currency, tag_amount)

        elif type == TagType.date:
            try:
                tag_value_parsed = date(*[
                    int(component)
                    for component in tag_value.split('-')
                ])
            except ValueError as e:
                raise ValueError(f"Could not parse value '{tag_value}' of tag '{name}' in item '{item['ref']}'") from e
            if tag_value_parsed.strftime('%Y-%m-%d') != tag_value:
                raise ValueError(
                    f"Value of tag '{name}' in transaction '{item['ref']}'"
                    " is not an ISO-8601 date (ie. 'YYYY-MM-DD')"
                )

            return tag_value_parsed

        elif type == TagType.ref:
            return items[tag_value]

        # Type not recognised
        else:
            raise ValueError(
                f"Unknown type '{type}' found during validation of"
                f" tag '{name}' of transaction '{item['ref']}'. This is"
                " likely to be due to an error in the implementation of a"
                " module you are using."
            )
