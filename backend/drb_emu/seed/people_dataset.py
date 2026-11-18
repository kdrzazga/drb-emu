import random
from datetime import date

import pyarrow as pa

from drb_emu.seed.fake_values import FakeValues
from drb_emu.seed.seed_dataset import SeedDataset, SeedTable, SeedView

MONEY = pa.decimal128(14, 2)


class PeopleDataset:

    def __init__(self):
        self.random = random.Random(1001)
        self.fake = FakeValues(self.random)
        self.person_count = 1000
        self.company_count = 120
        self.employment_rate = 0.8
        self.second_job_rate = 0.12
        self.today = date(2026, 11, 1)
        self.currencies = {"PL": "PLN", "DE": "EUR", "AT": "EUR", "GB": "GBP", "CZ": "CZK"}
        self.positions = (
            ("Junior Specialist", 5200, 7500), ("Specialist", 7000, 11000), ("Senior Specialist", 10000, 16000),
            ("Team Leader", 13000, 19000), ("Manager", 16000, 26000), ("Director", 24000, 42000),
            ("Accountant", 7500, 12500), ("Engineer", 9000, 18000), ("Sales Representative", 6500, 13000),
        )
        self.banks = (
            ("First Vistula Bank", "FVBKPLPW", "PL"), ("Amber Savings Bank", "AMSBPLPK", "PL"),
            ("Silesia Cooperative Bank", "SCBAPLPW", "PL"), ("Mazovia Credit Bank", "MZCBPLPW", "PL"),
            ("Baltic Commerce Bank", "BCOMPLPG", "PL"), ("Carpathian Digital Bank", "CRDBPLPW", "PL"),
            ("Rhine Volksbank", "RHVBDEFF", "DE"), ("Hanse Sparkasse", "HNSPDEHH", "DE"),
            ("Thames Mutual Bank", "THMBGB2L", "GB"), ("Pennine Building Society", "PNBSGB2M", "GB"),
            ("Vltava Banka", "VLTBCZPP", "CZ"), ("Danube Privatbank", "DNPBATWW", "AT"),
        )

    def build(self) -> SeedDataset:
        people = self._people()
        companies = self._companies()
        banks = self._bank_rows()
        employment = self._employment(people, companies)
        person_accounts = self._person_accounts(people, banks)
        company_accounts = self._company_accounts(companies, banks)
        return SeedDataset(
            catalog_name="people",
            comment="People, the companies they work for and the banks they keep accounts in",
            tables=(
                SeedTable("person", "Natural persons with home address and tax identifier", (
                    ("id", pa.int64()), ("name", pa.string()), ("last_name", pa.string()), ("address", pa.string()),
                    ("postal_code", pa.string()), ("city", pa.string()), ("country", pa.string()), ("tax_id", pa.string()),
                    ("birth_date", pa.date32()), ("email", pa.string()), ("phone", pa.string()),
                ), people),
                SeedTable("company", "Companies that employ people and hold company bank accounts", (
                    ("id", pa.int64()), ("name", pa.string()), ("tax_id", pa.string()), ("industry", pa.string()),
                    ("address", pa.string()), ("postal_code", pa.string()), ("city", pa.string()), ("country", pa.string()),
                    ("founded_year", pa.int32()),
                ), companies),
                SeedTable("employment", "Which person works in which company", (
                    ("id", pa.int64()), ("person_id", pa.int64()), ("company_id", pa.int64()), ("position", pa.string()),
                    ("start_date", pa.date32()), ("monthly_salary", MONEY), ("currency", pa.string()),
                ), employment),
                SeedTable("bank", "Banks (fictional names)", (
                    ("id", pa.int64()), ("name", pa.string()), ("swift_code", pa.string()), ("country", pa.string()),
                ), [{key: value for key, value in bank.items() if key != "bank_code"} for bank in banks]),
                SeedTable("person_bank_account", "Personal accounts: which person has an account in which bank", (
                    ("id", pa.int64()), ("person_id", pa.int64()), ("bank_id", pa.int64()), ("iban", pa.string()),
                    ("account_type", pa.string()), ("currency", pa.string()), ("balance", MONEY), ("opened_on", pa.date32()),
                ), person_accounts),
                SeedTable("company_bank_account", "Company accounts: which company has an account in which bank", (
                    ("id", pa.int64()), ("company_id", pa.int64()), ("bank_id", pa.int64()), ("iban", pa.string()),
                    ("currency", pa.string()), ("balance", MONEY), ("opened_on", pa.date32()),
                ), company_accounts),
            ),
            views=(
                SeedView("employees_by_company", "Head count and average salary per company", """
                    SELECT c.id AS company_id, c.name AS company, c.industry, COUNT(e.id) AS employees,
                           ROUND(AVG(e.monthly_salary), 2) AS average_salary
                    FROM company c LEFT JOIN employment e ON e.company_id = c.id
                    GROUP BY c.id, c.name, c.industry
                """),
                SeedView("bank_clients", "Number of personal and company clients per bank", """
                    SELECT b.name AS bank, b.country,
                           COUNT(DISTINCT pa.person_id) AS personal_clients,
                           COUNT(DISTINCT ca.company_id) AS company_clients
                    FROM bank b
                    LEFT JOIN person_bank_account pa ON pa.bank_id = b.id
                    LEFT JOIN company_bank_account ca ON ca.bank_id = b.id
                    GROUP BY b.name, b.country
                """),
            ),
        )

    def _people(self) -> list[dict]:
        people = []
        for person_id in range(1, self.person_count + 1):
            name = self.fake.first_name()
            last_name = self.fake.last_name()
            city, country = self.fake.city()
            birth_date = self.fake.date_between(date(1950, 1, 1), date(2005, 12, 31))
            people.append({
                "id": person_id,
                "name": name,
                "last_name": last_name,
                "address": self.fake.street_address(country),
                "postal_code": self.fake.postal_code(country),
                "city": city,
                "country": country,
                "tax_id": self.fake.personal_tax_id(birth_date),
                "birth_date": birth_date,
                "email": self.fake.email(name, last_name, person_id, "example.com"),
                "phone": self.fake.phone(),
            })
        return people

    def _companies(self) -> list[dict]:
        companies = []
        for company_id in range(1, self.company_count + 1):
            city, country = self.fake.city()
            name, industry = self.fake.company_name(country)
            companies.append({
                "id": company_id,
                "name": name,
                "tax_id": self.fake.company_tax_id(country),
                "industry": industry,
                "address": self.fake.street_address(country),
                "postal_code": self.fake.postal_code(country),
                "city": city,
                "country": country,
                "founded_year": self.random.randint(1990, 2023),
            })
        return companies

    def _bank_rows(self) -> list[dict]:
        return [
            {"id": bank_id, "name": name, "swift_code": swift_code, "country": country, "bank_code": f"{bank_id * 1010:08d}"}
            for bank_id, (name, swift_code, country) in enumerate(self.banks, start=1)
        ]

    def _employment(self, people: list[dict], companies: list[dict]) -> list[dict]:
        employment = []
        for person in people:
            if self.random.random() > self.employment_rate or person["birth_date"].year > 2004:
                continue
            job_count = 2 if self.random.random() < self.second_job_rate else 1
            for company in self.random.sample(companies, job_count):
                position, lowest_salary, highest_salary = self.random.choice(self.positions)
                earliest_start = date(max(person["birth_date"].year + 19, company["founded_year"]), 1, 1)
                employment.append({
                    "id": len(employment) + 1,
                    "person_id": person["id"],
                    "company_id": company["id"],
                    "position": position,
                    "start_date": self.fake.date_between(min(earliest_start, self.today), self.today),
                    "monthly_salary": self.fake.money(lowest_salary, highest_salary),
                    "currency": self.currencies[company["country"]],
                })
        return employment

    def _person_accounts(self, people: list[dict], banks: list[dict]) -> list[dict]:
        accounts = []
        for person in people:
            account_count = self.random.choices((0, 1, 2, 3), weights=(10, 55, 28, 7))[0]
            for _ in range(account_count):
                bank = self._bank_for(person["country"], banks)
                accounts.append({
                    "id": len(accounts) + 1,
                    "person_id": person["id"],
                    "bank_id": bank["id"],
                    "iban": self.fake.iban(bank["country"], bank["bank_code"]),
                    "account_type": self.random.choices(("CHECKING", "SAVINGS"), weights=(3, 1))[0],
                    "currency": self.currencies[bank["country"]],
                    "balance": self.fake.money(0, 85000),
                    "opened_on": self.fake.date_between(date(max(person["birth_date"].year + 18, 1995), 1, 1), self.today),
                })
        return accounts

    def _company_accounts(self, companies: list[dict], banks: list[dict]) -> list[dict]:
        accounts = []
        for company in companies:
            for _ in range(self.random.randint(1, 3)):
                bank = self._bank_for(company["country"], banks)
                accounts.append({
                    "id": len(accounts) + 1,
                    "company_id": company["id"],
                    "bank_id": bank["id"],
                    "iban": self.fake.iban(bank["country"], bank["bank_code"]),
                    "currency": self.currencies[bank["country"]],
                    "balance": self.fake.money(5000, 4_500_000),
                    "opened_on": self.fake.date_between(date(company["founded_year"], 1, 1), self.today),
                })
        return accounts

    def _bank_for(self, country: str, banks: list[dict]) -> dict:
        return self.random.choices(banks, weights=[6 if bank["country"] == country else 1 for bank in banks])[0]
