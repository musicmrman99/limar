from yaql import yaqlization

@yaqlization.yaqlize
class CurrencyAmount:
    def __init__(self, currency: str, amount: int):
        self.currency = currency
        self.amount = amount

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.currency}', {self.amount})"

    def __str__(self):
        quotient, remainder = divmod(self.amount, 10**2)
        sign = '-' if quotient < 0 else ' '
        return f"{sign}{self.currency} {abs(quotient)}.{remainder:02}"
