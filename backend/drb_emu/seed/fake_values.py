import random
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

from drb_emu.seed.reference_data import (
    CITIES,
    COMPANY_FIRST_WORDS,
    COMPANY_SECOND_WORDS,
    FIRST_NAMES,
    LAST_NAMES,
    LEGAL_FORMS,
    POLISH_CITY_WEIGHT,
    STREETS,
)


class FakeValues:

    def __init__(self, random_generator: random.Random):
        self.random = random_generator
        self.city_weights = [POLISH_CITY_WEIGHT if country == "PL" else 1 for _, country in CITIES]
        self.used_unique_values = set()

    def first_name(self) -> str:
        return self.random.choice(FIRST_NAMES)

    def last_name(self) -> str:
        return self.random.choice(LAST_NAMES)

    def city(self) -> tuple[str, str]:
        return self.random.choices(CITIES, weights=self.city_weights)[0]

    def street_address(self, country: str) -> str:
        street = self.random.choice(STREETS[country])
        building = self.random.randint(1, 180)
        if country == "PL" and self.random.random() < 0.6:
            return f"{street} {building}/{self.random.randint(1, 60)}"
        return f"{street} {building}"

    def postal_code(self, country: str) -> str:
        if country == "PL":
            return f"{self.random.randint(0, 99):02d}-{self.random.randint(0, 999):03d}"
        if country == "GB":
            return f"{self.random.choice(('EC', 'SW', 'M', 'N'))}{self.random.randint(1, 9)} {self.random.randint(1, 9)}{self.random.choice('ABDEFGH')}{self.random.choice('JLNPQRST')}"
        if country == "CZ":
            return f"{self.random.randint(100, 799)} {self.random.randint(0, 99):02d}"
        if country == "AT":
            return f"{self.random.randint(1000, 9999)}"
        return f"{self.random.randint(10000, 99999)}"

    def date_between(self, start: date, end: date) -> date:
        return start + timedelta(days=self.random.randint(0, (end - start).days))

    def money(self, low: float, high: float) -> Decimal:
        return Decimal(f"{self.random.uniform(low, high):.2f}")

    def email(self, first_name: str, last_name: str, number: int, domain: str) -> str:
        return f"{self._ascii(first_name)}.{self._ascii(last_name)}{number}@{domain}"

    def login(self, first_name: str, last_name: str) -> str:
        base_login = f"{self._ascii(first_name)[0]}{self._ascii(last_name)}"
        login = base_login
        suffix = 2
        while login in self.used_unique_values:
            login = f"{base_login}{suffix}"
            suffix += 1
        self.used_unique_values.add(login)
        return login

    def phone(self) -> str:
        return f"+48 {self.random.randint(500, 899)} {self.random.randint(100, 999)} {self.random.randint(100, 999)}"

    def personal_tax_id(self, birth_date: date) -> str:
        return self.unique(lambda: f"{birth_date:%y%m%d}{self.random.randint(10000, 99999)}")

    def company_tax_id(self, country: str) -> str:
        if country == "PL":
            return self.unique(lambda: "-".join((f"{self.random.randint(100, 999)}", f"{self.random.randint(100, 999)}",
                                                 f"{self.random.randint(10, 99)}", f"{self.random.randint(10, 99)}")))
        return self.unique(lambda: f"{country}{self.random.randint(100_000_000, 999_999_999)}")

    def iban(self, country: str, bank_code: str) -> str:
        return self.unique(lambda: f"{country}{self.random.randint(10, 99)}{bank_code}{self.random.randint(0, 10**16 - 1):016d}")

    def company_name(self, country: str) -> tuple[str, str]:
        second_word, industry = self.random.choice(COMPANY_SECOND_WORDS)
        name = self.unique(lambda: f"{self.random.choice(COMPANY_FIRST_WORDS)} {second_word} {self.random.choice(LEGAL_FORMS[country])}")
        return name, industry

    def unique(self, make_value) -> str:
        for _ in range(1000):
            value = make_value()
            if value not in self.used_unique_values:
                self.used_unique_values.add(value)
                return value
        raise RuntimeError("Could not generate a unique value")

    def _ascii(self, text: str) -> str:
        decomposed = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
        return "".join(character for character in decomposed if not unicodedata.combining(character)).lower()
