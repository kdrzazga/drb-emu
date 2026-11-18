import random
from datetime import date, timedelta
from decimal import Decimal

import pyarrow as pa

from drb_emu.seed.fake_values import FakeValues
from drb_emu.seed.seed_dataset import SeedDataset, SeedTable, SeedView

MONEY = pa.decimal128(12, 2)


class ComputerStoreDataset:

    def __init__(self):
        self.random = random.Random(3003)
        self.fake = FakeValues(self.random)
        self.pc_count = 120
        self.laptop_count = 150
        self.monitor_count = 80
        self.accessory_count = 200
        self.retro_computer_count = 60
        self.customer_count = 600
        self.order_count = 800
        self.first_order_date = date(2023, 1, 2)
        self.today = date(2026, 11, 1)
        self.vat_rate = Decimal("0.23")
        self.store_cities = ("Warszawa", "Kraków", "Wrocław", "Gdańsk")
        self.pc_lines = (
            ("Dell", "OptiPlex"), ("Dell", "XPS Desktop"), ("HP", "ProDesk"), ("HP", "Omen"), ("Lenovo", "ThinkCentre"),
            ("Lenovo", "Legion Tower"), ("Acer", "Aspire TC"), ("ASUS", "ROG Strix G"), ("MSI", "MEG Trident"), ("drb", "Custom Build"),
        )
        self.desktop_cpus = (
            ("Intel Core i3-12100", 420), ("Intel Core i5-13400", 780), ("Intel Core i7-14700", 1450), ("Intel Core i9-14900K", 2400),
            ("AMD Ryzen 5 7600", 820), ("AMD Ryzen 7 7800X3D", 1700), ("AMD Ryzen 9 7950X", 2500),
        )
        self.gpus = (
            ("Integrated", 0), ("NVIDIA GeForce RTX 4060", 1350), ("NVIDIA GeForce RTX 4070 Super", 2700),
            ("NVIDIA GeForce RTX 4080 Super", 4800), ("AMD Radeon RX 7700 XT", 1900), ("AMD Radeon RX 7900 XTX", 4300),
        )
        self.laptop_lines = (
            ("Dell", "XPS 13"), ("Dell", "Latitude 5440"), ("HP", "EliteBook 840"), ("HP", "Pavilion 15"), ("Lenovo", "ThinkPad T14"),
            ("Lenovo", "Yoga Slim 7"), ("Apple", "MacBook Air 13"), ("Apple", "MacBook Pro 14"), ("ASUS", "Zenbook 14"),
            ("ASUS", "ROG Zephyrus G14"), ("Acer", "Swift Go 14"), ("MSI", "Katana 15"),
        )
        self.laptop_cpus = (
            ("Intel Core i5-1335U", 600), ("Intel Core Ultra 5 125H", 900), ("Intel Core Ultra 7 155H", 1400),
            ("AMD Ryzen 7 8840HS", 1200), ("AMD Ryzen 9 8945HS", 1800),
        )
        self.apple_cpus = (("Apple M3", 1500), ("Apple M3 Pro", 2800), ("Apple M4", 2000))
        self.monitor_brands = (("Dell", "U"), ("LG", "GP"), ("Samsung", "Odyssey G"), ("BenQ", "PD"), ("ASUS", "ProArt PA"),
                               ("AOC", "Q"), ("Eizo", "FlexScan EV"), ("Philips", "B"))
        self.monitor_sizes = ((24, ("1920x1080", "2560x1440")), (27, ("2560x1440", "3840x2160")), (32, ("3840x2160",)), (34, ("3440x1440",)))
        self.monitor_panels = (("IPS", 1.0), ("VA", 0.9), ("OLED", 1.9), ("TN", 0.75))
        self.retro_models = (
            ("Commodore 64", "Commodore", 1982, "MOS 6510", 64, 450), ("Commodore 64C", "Commodore", 1986, "MOS 8500", 64, 420),
            ("Commodore 128", "Commodore", 1985, "MOS 8502 + Z80", 128, 550), ("Commodore VIC-20", "Commodore", 1980, "MOS 6502", 5, 260),
            ("Amiga 500", "Commodore", 1987, "Motorola 68000", 512, 750), ("Amiga 1200", "Commodore", 1992, "Motorola 68EC020", 2048, 1150),
            ("ZX Spectrum 48K", "Sinclair", 1982, "Zilog Z80A", 48, 420), ("ZX Spectrum +2", "Amstrad", 1986, "Zilog Z80A", 128, 380),
            ("Atari 800XL", "Atari", 1983, "MOS 6502C", 64, 430), ("Atari 65XE", "Atari", 1985, "MOS 6502C", 64, 320),
            ("Atari 1040 STF", "Atari", 1986, "Motorola 68000", 1024, 620), ("Apple IIe", "Apple", 1983, "MOS 6502", 64, 950),
            ("Amstrad CPC 464", "Amstrad", 1984, "Zilog Z80A", 64, 360), ("BBC Micro Model B", "Acorn", 1981, "MOS 6502", 32, 520),
            ("Timex Computer 2048", "Timex", 1984, "Zilog Z80A", 48, 330),
        )
        self.retro_conditions = (("MINT", 1.7), ("VERY GOOD", 1.25), ("GOOD", 1.0), ("WORN", 0.7), ("FOR PARTS", 0.35))
        self.accessory_categories = (
            ("Keyboard", ("Mechanical Keyboard", "Wireless Keyboard", "Compact 75% Keyboard"), (89, 749),
             ("Logitech", "Razer", "Corsair", "SteelSeries", "Keychron"), ("Black", "White", "Grey")),
            ("Mouse", ("Gaming Mouse", "Wireless Mouse", "Vertical Mouse"), (49, 449),
             ("Logitech", "Razer", "SteelSeries", "Glorious"), ("Black", "White")),
            ("Headset", ("Gaming Headset", "Wireless Headset", "Studio Headphones"), (129, 1199),
             ("HyperX", "SteelSeries", "Sony", "Logitech"), ("Black", "White")),
            ("Webcam", ("Full HD Webcam", "4K Webcam"), (149, 899), ("Logitech", "Razer", "Elgato"), ("Standard",)),
            ("Cable", ("HDMI 2.1 Cable", "DisplayPort 1.4 Cable", "USB-C Cable", "Ethernet Cat6 Cable"), (19, 129),
             ("Ugreen", "Anker", "Belkin"), ("1 m", "2 m", "3 m")),
            ("Storage", ("External SSD", "USB Flash Drive", "microSD Card"), (39, 1099),
             ("Samsung", "Kingston", "SanDisk", "Crucial"), ("128 GB", "256 GB", "1 TB", "2 TB")),
            ("Docking", ("USB-C Dock", "USB Hub"), (79, 1199), ("Anker", "Dell", "CalDigit", "Ugreen"), ("4-port", "7-port", "Thunderbolt")),
            ("Retro", ("Competition Pro Joystick", "Quickshot II Joystick", "Datasette 1530", "SD2IEC Drive", "Floppy Disk Pack",
                       "1541 Ultimate II+", "Amiga Tank Mouse"), (39, 899), ("Retro Games Ltd", "Speedlink", "drb Retro"), ("Standard", "Refurbished")),
        )
        self.employee_positions = (
            ("Store Manager", 4, (12000, 16000)), ("Sales Specialist", 20, (5500, 8500)), ("Service Technician", 8, (6500, 9500)),
            ("Retro Hardware Specialist", 4, (6500, 9000)), ("Warehouse Clerk", 8, (4800, 6500)), ("Cashier", 6, (4600, 5800)),
        )
        self.selling_positions = ("Store Manager", "Sales Specialist", "Retro Hardware Specialist", "Cashier")
        self.order_statuses = (("DELIVERED", 60), ("SHIPPED", 10), ("PAID", 10), ("NEW", 12), ("CANCELLED", 8))
        self.invoiced_statuses = ("DELIVERED", "SHIPPED", "PAID")
        self.product_type_weights = (("accessories", 40), ("laptop", 20), ("pc", 15), ("monitor", 15), ("retro_computer", 10))
        self.product_foreign_keys = {
            "pc": "pc_id", "laptop": "laptop_id", "monitor": "monitor_id", "retro_computer": "retro_computer_id", "accessories": "accessory_id",
        }

    def build(self) -> SeedDataset:
        products = {
            "pc": self._pcs(),
            "laptop": self._laptops(),
            "monitor": self._monitors(),
            "retro_computer": self._retro_computers(),
            "accessories": self._accessories(),
        }
        employees = self._employees()
        customers = self._customers()
        orders = self._orders(customers, employees)
        order_items = self._order_items(orders, products)
        invoices = self._invoices(orders, order_items)
        stock_columns = (("price", MONEY), ("stock", pa.int32()))
        return SeedDataset(
            catalog_name="computer_store",
            comment="A computer store: products, staff, customers, orders and invoices",
            tables=(
                SeedTable("pc", "Desktop computers", (
                    ("id", pa.int64()), ("model", pa.string()), ("brand", pa.string()), ("form_factor", pa.string()), ("cpu", pa.string()),
                    ("ram_gb", pa.int32()), ("storage_gb", pa.int32()), ("gpu", pa.string()), *stock_columns,
                ), products["pc"]),
                SeedTable("laptop", "Laptops", (
                    ("id", pa.int64()), ("model", pa.string()), ("brand", pa.string()), ("cpu", pa.string()), ("ram_gb", pa.int32()),
                    ("storage_gb", pa.int32()), ("screen_inches", pa.float64()), ("weight_kg", pa.float64()), *stock_columns,
                ), products["laptop"]),
                SeedTable("monitor", "Monitors", (
                    ("id", pa.int64()), ("model", pa.string()), ("brand", pa.string()), ("size_inches", pa.int32()), ("resolution", pa.string()),
                    ("panel", pa.string()), ("refresh_hz", pa.int32()), *stock_columns,
                ), products["monitor"]),
                SeedTable("retro_computer", "Second-hand 8-bit and 16-bit home computers", (
                    ("id", pa.int64()), ("model", pa.string()), ("manufacturer", pa.string()), ("release_year", pa.int32()), ("cpu", pa.string()),
                    ("ram_kb", pa.int32()), ("condition", pa.string()), ("boxed", pa.bool_()), *stock_columns,
                ), products["retro_computer"]),
                SeedTable("accessories", "Keyboards, mice, cables, storage and retro accessories", (
                    ("id", pa.int64()), ("name", pa.string()), ("category", pa.string()), ("brand", pa.string()), *stock_columns,
                ), products["accessories"]),
                SeedTable("employee", "Store staff", (
                    ("id", pa.int64()), ("first_name", pa.string()), ("last_name", pa.string()), ("position", pa.string()),
                    ("store_city", pa.string()), ("email", pa.string()), ("hired_on", pa.date32()), ("monthly_salary", MONEY),
                ), employees),
                SeedTable("customer", "Store customers", (
                    ("id", pa.int64()), ("first_name", pa.string()), ("last_name", pa.string()), ("email", pa.string()), ("phone", pa.string()),
                    ("address", pa.string()), ("postal_code", pa.string()), ("city", pa.string()), ("company_name", pa.string()),
                    ("registered_on", pa.date32()),
                ), customers),
                SeedTable("orders", "Customer orders, each handled by one employee", (
                    ("id", pa.int64()), ("order_number", pa.string()), ("customer_id", pa.int64()), ("employee_id", pa.int64()),
                    ("order_date", pa.date32()), ("status", pa.string()), ("channel", pa.string()), ("payment_method", pa.string()),
                ), orders),
                SeedTable("order_item", "Order lines; exactly one of the product id columns is set, matching product_type", (
                    ("id", pa.int64()), ("order_id", pa.int64()), ("line_number", pa.int32()), ("product_type", pa.string()),
                    ("pc_id", pa.int64()), ("laptop_id", pa.int64()), ("monitor_id", pa.int64()), ("retro_computer_id", pa.int64()),
                    ("accessory_id", pa.int64()), ("product_name", pa.string()), ("quantity", pa.int32()), ("unit_price", MONEY),
                    ("line_total", MONEY),
                ), order_items),
                SeedTable("invoice", "Invoices for paid, shipped and delivered orders (VAT 23%)", (
                    ("id", pa.int64()), ("invoice_number", pa.string()), ("order_id", pa.int64()), ("issued_on", pa.date32()),
                    ("due_on", pa.date32()), ("net_amount", MONEY), ("vat_amount", MONEY), ("gross_amount", MONEY), ("currency", pa.string()),
                    ("is_paid", pa.bool_()), ("paid_on", pa.date32()),
                ), invoices),
            ),
            views=(
                SeedView("order_lines_detailed", "Every order line joined to its product, whichever product table it comes from", """
                    SELECT i.order_id, o.order_number, o.order_date, i.line_number, i.product_type,
                           COALESCE(pc.model, l.model, m.model, r.model, a.name) AS product,
                           COALESCE(pc.brand, l.brand, m.brand, r.manufacturer, a.brand) AS brand,
                           i.quantity, i.unit_price, i.line_total
                    FROM order_item i
                    JOIN orders o ON o.id = i.order_id
                    LEFT JOIN pc ON pc.id = i.pc_id
                    LEFT JOIN laptop l ON l.id = i.laptop_id
                    LEFT JOIN monitor m ON m.id = i.monitor_id
                    LEFT JOIN retro_computer r ON r.id = i.retro_computer_id
                    LEFT JOIN accessories a ON a.id = i.accessory_id
                """),
                SeedView("order_summary", "One row per order with customer, salesperson, item count and totals", """
                    SELECT o.id AS order_id, o.order_number, o.order_date, o.status,
                           c.first_name || ' ' || c.last_name AS customer,
                           e.first_name || ' ' || e.last_name AS sold_by,
                           COUNT(i.id) AS items, SUM(i.line_total) AS net_total, inv.invoice_number
                    FROM orders o
                    JOIN customer c ON c.id = o.customer_id
                    JOIN employee e ON e.id = o.employee_id
                    JOIN order_item i ON i.order_id = o.id
                    LEFT JOIN invoice inv ON inv.order_id = o.id
                    GROUP BY o.id, o.order_number, o.order_date, o.status, c.first_name, c.last_name, e.first_name, e.last_name, inv.invoice_number
                """),
                SeedView("sales_by_product_type", "Units sold and net revenue per product type, excluding cancelled orders", """
                    SELECT i.product_type, SUM(i.quantity) AS units, SUM(i.line_total) AS net_revenue
                    FROM order_item i JOIN orders o ON o.id = i.order_id
                    WHERE o.status <> 'CANCELLED'
                    GROUP BY i.product_type
                """),
            ),
        )

    def _retail_price(self, value: float) -> Decimal:
        return Decimal(f"{max(round(value / 10) * 10, 10) - 0.01:.2f}")

    def _pcs(self) -> list[dict]:
        pcs = []
        for pc_id in range(1, self.pc_count + 1):
            brand, line = self.random.choice(self.pc_lines)
            cpu, cpu_price = self.random.choice(self.desktop_cpus)
            gpu, gpu_price = self.random.choice(self.gpus)
            ram_gb = self.random.choice((8, 16, 32, 64))
            storage_gb = self.random.choice((256, 512, 1024, 2048))
            pcs.append({
                "id": pc_id,
                "model": self.fake.unique(lambda: f"{brand} {line} {self.random.randint(3, 9)}{self.random.randint(0, 99):02d}"),
                "brand": brand,
                "form_factor": self.random.choice(("Tower", "Tower", "Mini", "All-in-One")),
                "cpu": cpu,
                "ram_gb": ram_gb,
                "storage_gb": storage_gb,
                "gpu": gpu,
                "price": self._retail_price((900 + cpu_price + gpu_price + ram_gb * 30 + storage_gb * 0.4) * self.random.uniform(1.0, 1.15)),
                "stock": self.random.randint(0, 25),
            })
        return pcs

    def _laptops(self) -> list[dict]:
        laptops = []
        for laptop_id in range(1, self.laptop_count + 1):
            brand, line = self.random.choice(self.laptop_lines)
            cpu, cpu_price = self.random.choice(self.apple_cpus if brand == "Apple" else self.laptop_cpus)
            ram_gb = self.random.choice((8, 16, 16, 32))
            storage_gb = self.random.choice((256, 512, 1024))
            laptops.append({
                "id": laptop_id,
                "model": self.fake.unique(lambda: f"{brand} {line} ({cpu}, {ram_gb} GB, {storage_gb} GB) #{self.random.randint(100, 999)}"),
                "brand": brand,
                "cpu": cpu,
                "ram_gb": ram_gb,
                "storage_gb": storage_gb,
                "screen_inches": self.random.choice((13.3, 14.0, 15.6, 16.0)),
                "weight_kg": round(self.random.uniform(1.1, 2.4), 2),
                "price": self._retail_price((2200 + cpu_price + ram_gb * 45 + storage_gb * 0.6) * self.random.uniform(1.0, 1.2)),
                "stock": self.random.randint(0, 30),
            })
        return laptops

    def _monitors(self) -> list[dict]:
        monitors = []
        for monitor_id in range(1, self.monitor_count + 1):
            brand, model_prefix = self.random.choice(self.monitor_brands)
            size_inches, resolutions = self.random.choice(self.monitor_sizes)
            resolution = self.random.choice(resolutions)
            panel, panel_factor = self.random.choice(self.monitor_panels)
            refresh_hz = self.random.choice((60, 75, 144, 165, 240))
            pixel_factor = {"1920x1080": 1.0, "2560x1440": 1.5, "3440x1440": 2.0, "3840x2160": 2.4}[resolution]
            monitors.append({
                "id": monitor_id,
                "model": self.fake.unique(lambda: f"{brand} {model_prefix}{size_inches}{self.random.randint(10, 99)}{self.random.choice(('', 'Q', 'U', 'K'))}"),
                "brand": brand,
                "size_inches": size_inches,
                "resolution": resolution,
                "panel": panel,
                "refresh_hz": refresh_hz,
                "price": self._retail_price((350 + size_inches * 18) * pixel_factor * panel_factor * (1 + refresh_hz / 400)),
                "stock": self.random.randint(0, 40),
            })
        return monitors

    def _retro_computers(self) -> list[dict]:
        retro_computers = []
        for retro_id in range(1, self.retro_computer_count + 1):
            model, manufacturer, release_year, cpu, ram_kb, base_price = self.random.choice(self.retro_models)
            condition, condition_factor = self.random.choice(self.retro_conditions)
            boxed = self.random.random() < 0.3
            retro_computers.append({
                "id": retro_id,
                "model": model,
                "manufacturer": manufacturer,
                "release_year": release_year,
                "cpu": cpu,
                "ram_kb": ram_kb,
                "condition": condition,
                "boxed": boxed,
                "price": self._retail_price(base_price * condition_factor * (1.35 if boxed else 1.0)),
                "stock": self.random.randint(1, 3),
            })
        return retro_computers

    def _accessories(self) -> list[dict]:
        combinations = [
            (category, brand, item_name, variant, price_range)
            for category, item_names, price_range, brands, variants in self.accessory_categories
            for brand in brands
            for item_name in item_names
            for variant in variants
        ]
        accessories = []
        for accessory_id, (category, brand, item_name, variant, (lowest_price, highest_price)) in enumerate(
                self.random.sample(combinations, self.accessory_count), start=1):
            accessories.append({
                "id": accessory_id,
                "name": f"{brand} {item_name}" if variant == "Standard" else f"{brand} {item_name} {variant}",
                "category": category,
                "brand": brand,
                "price": self._retail_price(self.random.uniform(lowest_price, highest_price)),
                "stock": self.random.randint(0, 120),
            })
        accessories.sort(key=lambda accessory: (accessory["category"], accessory["name"]))
        for accessory_id, accessory in enumerate(accessories, start=1):
            accessory["id"] = accessory_id
        return accessories

    def _employees(self) -> list[dict]:
        employees = []
        for position, count, (lowest_salary, highest_salary) in self.employee_positions:
            for _ in range(count):
                first_name = self.fake.first_name()
                last_name = self.fake.last_name()
                employee_id = len(employees) + 1
                employees.append({
                    "id": employee_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "position": position,
                    "store_city": self.random.choice(self.store_cities),
                    "email": self.fake.email(first_name, last_name, employee_id, "store.example.com"),
                    "hired_on": self.fake.date_between(date(2019, 3, 1), date(2026, 6, 30)),
                    "monthly_salary": self.fake.money(lowest_salary, highest_salary),
                })
        return employees

    def _customers(self) -> list[dict]:
        customers = []
        for customer_id in range(1, self.customer_count + 1):
            first_name = self.fake.first_name()
            last_name = self.fake.last_name()
            city, country = self.fake.city()
            company_name = self.fake.company_name(country)[0] if self.random.random() < 0.12 else None
            customers.append({
                "id": customer_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": self.fake.email(first_name, last_name, customer_id, "mail.example.com"),
                "phone": self.fake.phone(),
                "address": self.fake.street_address(country),
                "postal_code": self.fake.postal_code(country),
                "city": city,
                "company_name": company_name,
                "registered_on": self.fake.date_between(date(2019, 3, 1), date(2026, 9, 30)),
            })
        return customers

    def _orders(self, customers: list[dict], employees: list[dict]) -> list[dict]:
        sellers = [employee for employee in employees if employee["position"] in self.selling_positions]
        orders = []
        for _ in range(self.order_count):
            customer = self.random.choice(customers)
            orders.append({
                "customer_id": customer["id"],
                "employee_id": self.random.choice(sellers)["id"],
                "order_date": self.fake.date_between(max(customer["registered_on"], self.first_order_date), self.today),
                "status": self.random.choices([status for status, _ in self.order_statuses], weights=[weight for _, weight in self.order_statuses])[0],
                "channel": self.random.choice(("STORE", "ONLINE", "ONLINE")),
                "payment_method": self.random.choice(("CARD", "TRANSFER", "BLIK", "CASH")),
            })
        orders.sort(key=lambda order: order["order_date"])
        for order_id, order in enumerate(orders, start=1):
            order["id"] = order_id
            order["order_number"] = f"ORD-{order['order_date'].year}-{order_id:05d}"
        return orders

    def _order_items(self, orders: list[dict], products: dict[str, list[dict]]) -> list[dict]:
        product_types = [product_type for product_type, _ in self.product_type_weights]
        type_weights = [weight for _, weight in self.product_type_weights]
        order_items = []
        for order in orders:
            line_count = self.random.choices((1, 2, 3, 4), weights=(35, 30, 20, 15))[0]
            for line_number in range(1, line_count + 1):
                product_type = self.random.choices(product_types, weights=type_weights)[0]
                product = self.random.choice(products[product_type])
                quantity = self.random.randint(1, 3) if product_type == "accessories" else 1
                discount = Decimal("0.90") if self.random.random() < 0.1 else Decimal("1.00")
                unit_price = (product["price"] * discount).quantize(Decimal("0.01"))
                order_item = {key: None for key in self.product_foreign_keys.values()}
                order_item.update({
                    "id": len(order_items) + 1,
                    "order_id": order["id"],
                    "line_number": line_number,
                    "product_type": product_type,
                    self.product_foreign_keys[product_type]: product["id"],
                    "product_name": self._product_name(product_type, product),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": unit_price * quantity,
                })
                order_items.append(order_item)
        return order_items

    def _product_name(self, product_type: str, product: dict) -> str:
        if product_type == "accessories":
            return product["name"]
        if product_type == "retro_computer":
            return f"{product['model']} ({product['condition'].lower()}{', boxed' if product['boxed'] else ''})"
        return product["model"]

    def _invoices(self, orders: list[dict], order_items: list[dict]) -> list[dict]:
        net_by_order = {}
        for order_item in order_items:
            net_by_order[order_item["order_id"]] = net_by_order.get(order_item["order_id"], Decimal("0")) + order_item["line_total"]
        invoices = []
        invoice_sequence_by_year = {}
        for order in orders:
            if order["status"] not in self.invoiced_statuses:
                continue
            issued_on = min(order["order_date"] + timedelta(days=self.random.randint(0, 2)), self.today)
            sequence = invoice_sequence_by_year.get(issued_on.year, 0) + 1
            invoice_sequence_by_year[issued_on.year] = sequence
            net_amount = net_by_order[order["id"]]
            vat_amount = (net_amount * self.vat_rate).quantize(Decimal("0.01"))
            is_paid = order["payment_method"] != "TRANSFER" or self.random.random() < 0.85
            invoices.append({
                "id": len(invoices) + 1,
                "invoice_number": f"FV/{issued_on.year}/{sequence:05d}",
                "order_id": order["id"],
                "issued_on": issued_on,
                "due_on": issued_on + timedelta(days=14),
                "net_amount": net_amount,
                "vat_amount": vat_amount,
                "gross_amount": net_amount + vat_amount,
                "currency": "PLN",
                "is_paid": is_paid,
                "paid_on": min(issued_on + timedelta(days=self.random.randint(0, 13)), self.today) if is_paid else None,
            })
        return invoices
