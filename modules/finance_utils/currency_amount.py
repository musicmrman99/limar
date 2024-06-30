class CurrencyAmount:
    def __init__(self, currency: str, amount: int):
        self.currency = currency
        self.amount = amount

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.currency}', {self.amount})"

    def __str__(self):
        amount_str = '.'.join(map(str, divmod(self.amount, 10**2)))
        return f"{self.currency} {amount_str}"
