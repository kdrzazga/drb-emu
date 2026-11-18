import random
from datetime import date
from decimal import Decimal

import pyarrow as pa

from drb_emu.seed.fake_values import FakeValues
from drb_emu.seed.reference_data import COMPANY_FIRST_WORDS
from drb_emu.seed.seed_dataset import SeedDataset, SeedTable, SeedView

MONEY = pa.decimal128(18, 2)
PRICE = pa.decimal128(16, 4)
QUANTITY = pa.decimal128(16, 3)
RATE = pa.decimal128(14, 6)


class TradesDataset:

    def __init__(self):
        self.random = random.Random(2002)
        self.fake = FakeValues(self.random)
        self.customer_count = 150
        self.trade_count = 2000
        self.first_trade_date = date(2024, 1, 2)
        self.last_trade_date = date(2026, 10, 30)
        self.currencies = (
            ("USD", "US dollar", "$", Decimal("1.000000")),
            ("EUR", "Euro", "€", Decimal("1.082000")),
            ("GBP", "Pound sterling", "£", Decimal("1.271000")),
            ("PLN", "Polish złoty", "zł", Decimal("0.251000")),
            ("CHF", "Swiss franc", "CHF", Decimal("1.128000")),
            ("JPY", "Japanese yen", "¥", Decimal("0.006700")),
            ("CNY", "Chinese yuan", "¥", Decimal("0.138000")),
            ("AUD", "Australian dollar", "A$", Decimal("0.661000")),
        )
        self.commodities = (
            ("Coal", "Energy", "tonne", 135.0, (500, 25000)),
            ("Crude oil", "Energy", "barrel", 78.0, (1000, 60000)),
            ("Copper ore", "Base metals", "tonne", 2600.0, (50, 4000)),
            ("Gold", "Precious metals", "troy ounce", 2350.0, (10, 2500)),
            ("Silver", "Precious metals", "troy ounce", 29.0, (200, 40000)),
        )
        self.home_companies = (
            ("Vistula Commodities S.A.", "PL", "Warszawa", "PLN", 2004),
            ("Baltic Resources GmbH", "DE", "Hamburg", "EUR", 1998),
            ("Thames Metals Ltd", "GB", "London", "GBP", 2011),
            ("Alpine Trading AG", "CH", "Zürich", "CHF", 2016),
        )
        self.customer_locations = (
            ("Santiago", "CL", "USD"), ("Johannesburg", "ZA", "USD"), ("Sydney", "AU", "AUD"), ("Shanghai", "CN", "CNY"),
            ("Toronto", "CA", "USD"), ("Rotterdam", "NL", "EUR"), ("Zürich", "CH", "CHF"), ("Tokyo", "JP", "JPY"),
            ("Katowice", "PL", "PLN"), ("Hamburg", "DE", "EUR"), ("London", "GB", "GBP"), ("Houston", "US", "USD"),
            ("Mumbai", "IN", "USD"), ("Antwerp", "BE", "EUR"),
        )
        self.customer_segments = (
            ("MINING", ("Mining", "Minerals", "Resources")), ("UTILITY", ("Power", "Energy", "Utilities")),
            ("REFINERY", ("Refining", "Petroleum", "Smelting")), ("JEWELLERY", ("Jewellers", "Bullion", "Goldsmiths")),
            ("MANUFACTURING", ("Industries", "Works", "Fabrication")), ("BROKER", ("Brokers", "Capital", "Markets")),
        )
        self.customer_legal_forms = ("Ltd", "Inc.", "S.A.", "GmbH", "B.V.", "Pty Ltd", "Co.")
        self.user_roles = (("ADMIN", 4), ("TRADER", 30), ("RISK_ANALYST", 12), ("AUDITOR", 6), ("VIEWER", 8))
        self.trade_statuses = (("SETTLED", 78), ("CONFIRMED", 12), ("PENDING", 6), ("CANCELLED", 4))

    def build(self) -> SeedDataset:
        currencies = self._currencies()
        commodities = self._commodities()
        home_companies = self._home_companies()
        customers = self._customers()
        users = self._users()
        customer_access = self._customer_access(users, customers)
        commodity_access = self._commodity_access(users, commodities)
        trades = self._trades(users, customer_access, commodity_access, home_companies, customers, commodities, currencies)
        return SeedDataset(
            catalog_name="trades",
            comment="Commodity trades between our home companies and customers, with user access rights",
            tables=(
                SeedTable("currency", "Trade currencies and their value in US dollars", (
                    ("code", pa.string()), ("name", pa.string()), ("symbol", pa.string()), ("rate_to_usd", RATE),
                ), currencies),
                SeedTable("commodity", "Traded commodities with a reference price in US dollars", (
                    ("id", pa.int64()), ("name", pa.string()), ("category", pa.string()), ("unit", pa.string()),
                    ("reference_price_usd", PRICE),
                ), [{key: value for key, value in commodity.items() if key != "quantity_range"} for commodity in commodities]),
                SeedTable("home_company", "Our own trading companies", (
                    ("id", pa.int64()), ("name", pa.string()), ("country", pa.string()), ("city", pa.string()),
                    ("tax_id", pa.string()), ("base_currency", pa.string()), ("founded_year", pa.int32()),
                ), home_companies),
                SeedTable("customer", "Counterparty companies we buy from and sell to", (
                    ("id", pa.int64()), ("name", pa.string()), ("segment", pa.string()), ("country", pa.string()),
                    ("city", pa.string()), ("tax_id", pa.string()), ("preferred_currency", pa.string()),
                    ("credit_limit", MONEY), ("customer_since", pa.date32()),
                ), customers),
                SeedTable("trade", "Trades: BUY means the home company buys from the customer, SELL means it sells to the customer", (
                    ("id", pa.int64()), ("trade_date", pa.date32()), ("direction", pa.string()), ("home_company_id", pa.int64()),
                    ("customer_id", pa.int64()), ("buyer_name", pa.string()), ("seller_name", pa.string()),
                    ("commodity_id", pa.int64()), ("amount", QUANTITY), ("unit", pa.string()), ("unit_price", PRICE),
                    ("currency_code", pa.string()), ("total_value", MONEY), ("status", pa.string()), ("trader_user_id", pa.int64()),
                ), trades),
                SeedTable("users", "Application users and their roles", (
                    ("id", pa.int64()), ("login", pa.string()), ("full_name", pa.string()), ("email", pa.string()),
                    ("role", pa.string()), ("is_active", pa.bool_()), ("created_on", pa.date32()),
                ), users),
                SeedTable("user_customer_access", "Which user may read or trade with which customer (ADMIN sees everything)", (
                    ("user_id", pa.int64()), ("customer_id", pa.int64()), ("access_level", pa.string()),
                ), customer_access),
                SeedTable("user_commodity_access", "Which user may view or trade which commodity", (
                    ("user_id", pa.int64()), ("commodity_id", pa.int64()), ("can_view", pa.bool_()), ("can_trade", pa.bool_()),
                ), commodity_access),
            ),
            views=(
                SeedView("trade_volume_by_commodity", "Trade count and value in USD per commodity and direction, excluding cancelled trades", """
                    SELECT c.name AS commodity, t.direction, COUNT(*) AS trades,
                           SUM(t.amount) AS total_amount, c.unit,
                           ROUND(SUM(t.total_value * cur.rate_to_usd), 2) AS value_usd
                    FROM trade t
                    JOIN commodity c ON c.id = t.commodity_id
                    JOIN currency cur ON cur.code = t.currency_code
                    WHERE t.status <> 'CANCELLED'
                    GROUP BY c.name, t.direction, c.unit
                """),
                SeedView("trader_activity", "Trades per trader with the number of customers they can trade with", """
                    SELECT u.login, u.full_name, COUNT(t.id) AS trades,
                           (SELECT COUNT(*) FROM user_customer_access a WHERE a.user_id = u.id AND a.access_level = 'TRADE') AS tradable_customers
                    FROM users u LEFT JOIN trade t ON t.trader_user_id = u.id
                    WHERE u.role = 'TRADER'
                    GROUP BY u.id, u.login, u.full_name
                """),
            ),
        )

    def _currencies(self) -> list[dict]:
        return [{"code": code, "name": name, "symbol": symbol, "rate_to_usd": rate} for code, name, symbol, rate in self.currencies]

    def _commodities(self) -> list[dict]:
        return [
            {"id": commodity_id, "name": name, "category": category, "unit": unit,
             "reference_price_usd": Decimal(f"{price:.4f}"), "quantity_range": quantity_range}
            for commodity_id, (name, category, unit, price, quantity_range) in enumerate(self.commodities, start=1)
        ]

    def _home_companies(self) -> list[dict]:
        return [
            {"id": company_id, "name": name, "country": country, "city": city, "tax_id": self.fake.company_tax_id(country),
             "base_currency": currency, "founded_year": founded_year}
            for company_id, (name, country, city, currency, founded_year) in enumerate(self.home_companies, start=1)
        ]

    def _customers(self) -> list[dict]:
        customers = []
        for customer_id in range(1, self.customer_count + 1):
            city, country, currency = self.random.choice(self.customer_locations)
            segment, name_words = self.random.choice(self.customer_segments)
            name = self.fake.unique(lambda: f"{self.random.choice(COMPANY_FIRST_WORDS)} {self.random.choice(name_words)} {self.random.choice(self.customer_legal_forms)}")
            customers.append({
                "id": customer_id,
                "name": name,
                "segment": segment,
                "country": country,
                "city": city,
                "tax_id": self.fake.company_tax_id(country),
                "preferred_currency": currency,
                "credit_limit": Decimal(self.random.choice((250_000, 500_000, 1_000_000, 2_500_000, 5_000_000, 10_000_000))),
                "customer_since": self.fake.date_between(date(2010, 1, 1), date(2025, 12, 31)),
            })
        return customers

    def _users(self) -> list[dict]:
        users = []
        for role, count in self.user_roles:
            for _ in range(count):
                first_name = self.fake.first_name()
                last_name = self.fake.last_name()
                user_id = len(users) + 1
                users.append({
                    "id": user_id,
                    "login": self.fake.login(first_name, last_name),
                    "full_name": f"{first_name} {last_name}",
                    "email": self.fake.email(first_name, last_name, user_id, "trades.example.com"),
                    "role": role,
                    "is_active": self.random.random() > 0.08,
                    "created_on": self.fake.date_between(date(2018, 1, 1), date(2025, 6, 30)),
                })
        return users

    def _customer_access(self, users: list[dict], customers: list[dict]) -> list[dict]:
        customers_per_role = {"TRADER": (12, 30), "RISK_ANALYST": (40, 80), "AUDITOR": (20, 40), "VIEWER": (5, 15)}
        access = []
        for user in users:
            if user["role"] not in customers_per_role:
                continue
            lowest, highest = customers_per_role[user["role"]]
            for customer in sorted(self.random.sample(customers, self.random.randint(lowest, highest)), key=lambda chosen: chosen["id"]):
                access_level = "TRADE" if user["role"] == "TRADER" and self.random.random() < 0.8 else "READ"
                access.append({"user_id": user["id"], "customer_id": customer["id"], "access_level": access_level})
            if user["role"] == "TRADER" and not any(row["user_id"] == user["id"] and row["access_level"] == "TRADE" for row in access):
                access[-1]["access_level"] = "TRADE"
        return access

    def _commodity_access(self, users: list[dict], commodities: list[dict]) -> list[dict]:
        access = []
        for user in users:
            if user["role"] == "ADMIN":
                continue
            chosen = commodities if user["role"] in ("RISK_ANALYST", "AUDITOR") else self.random.sample(commodities, self.random.randint(1, 3))
            for commodity in sorted(chosen, key=lambda item: item["id"]):
                access.append({
                    "user_id": user["id"],
                    "commodity_id": commodity["id"],
                    "can_view": True,
                    "can_trade": user["role"] == "TRADER",
                })
        return access

    def _trades(self, users: list[dict], customer_access: list[dict], commodity_access: list[dict], home_companies: list[dict],
                customers: list[dict], commodities: list[dict], currencies: list[dict]) -> list[dict]:
        customers_by_id = {customer["id"]: customer for customer in customers}
        commodities_by_id = {commodity["id"]: commodity for commodity in commodities}
        rate_by_currency = {currency["code"]: float(currency["rate_to_usd"]) for currency in currencies}
        traders = [user for user in users if user["role"] == "TRADER"]
        tradable_customers = {
            trader["id"]: [row["customer_id"] for row in customer_access if row["user_id"] == trader["id"] and row["access_level"] == "TRADE"]
            for trader in traders
        }
        tradable_commodities = {
            trader["id"]: [row["commodity_id"] for row in commodity_access if row["user_id"] == trader["id"] and row["can_trade"]]
            for trader in traders
        }
        trades = []
        for trade_id in range(1, self.trade_count + 1):
            trader = self.random.choice(traders)
            customer = customers_by_id[self.random.choice(tradable_customers[trader["id"]])]
            commodity = commodities_by_id[self.random.choice(tradable_commodities[trader["id"]])]
            home_company = self.random.choice(home_companies)
            direction = self.random.choice(("BUY", "SELL"))
            currency_code = self.random.choice((customer["preferred_currency"], home_company["base_currency"], "USD"))
            lowest_amount, highest_amount = commodity["quantity_range"]
            amount = Decimal(f"{self.random.uniform(lowest_amount, highest_amount):.3f}")
            unit_price_usd = float(commodity["reference_price_usd"]) * self.random.uniform(0.86, 1.14)
            unit_price = Decimal(f"{unit_price_usd / rate_by_currency[currency_code]:.4f}")
            buyer, seller = (home_company, customer) if direction == "BUY" else (customer, home_company)
            trades.append({
                "id": trade_id,
                "trade_date": self.fake.date_between(self.first_trade_date, self.last_trade_date),
                "direction": direction,
                "home_company_id": home_company["id"],
                "customer_id": customer["id"],
                "buyer_name": buyer["name"],
                "seller_name": seller["name"],
                "commodity_id": commodity["id"],
                "amount": amount,
                "unit": commodity["unit"],
                "unit_price": unit_price,
                "currency_code": currency_code,
                "total_value": (amount * unit_price).quantize(Decimal("0.01")),
                "status": self.random.choices([status for status, _ in self.trade_statuses], weights=[weight for _, weight in self.trade_statuses])[0],
                "trader_user_id": trader["id"],
            })
        trades.sort(key=lambda trade: (trade["trade_date"], trade["id"]))
        for trade_id, trade in enumerate(trades, start=1):
            trade["id"] = trade_id
        return trades
