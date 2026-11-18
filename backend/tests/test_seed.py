from pathlib import Path

import pytest

from drb_emu.errors import ResourceAlreadyExists
from drb_emu.seed.computer_store_dataset import ComputerStoreDataset
from drb_emu.seed.dataset_loader import DatasetLoader
from drb_emu.seed.people_dataset import PeopleDataset
from drb_emu.seed.trades_dataset import TradesDataset
from drb_emu.workspace import Workspace

DICTIONARY_TABLES = {"people.default.bank", "trades.default.currency", "trades.default.commodity", "trades.default.home_company"}


@pytest.fixture(scope="module")
def seeded_workspace(tmp_path_factory):
    root = tmp_path_factory.mktemp("seeded")
    workspace = Workspace(root / "lake", root / "metastore" / "metastore.db")
    loader = DatasetLoader(workspace.catalog_service)
    loaded = []
    for dataset in (PeopleDataset(), TradesDataset(), ComputerStoreDataset()):
        loaded.extend(loader.load(dataset.build(), replace=False))
    workspace.loaded_objects = loaded
    yield workspace
    workspace.close()


def scalar(workspace: Workspace, sql: str):
    return workspace.statement_executor.execute(sql).column(0)[0].as_py()


def test_every_table_has_a_visible_but_bounded_row_count(seeded_workspace: Workspace):
    tables = [loaded for loaded in seeded_workspace.loaded_objects if loaded.kind == "table"]

    assert len(tables) == 6 + 8 + 10
    for table in tables:
        assert table.row_count <= 2000, table.full_name
        if table.full_name not in DICTIONARY_TABLES:
            assert table.row_count >= 50, table.full_name


def test_every_view_returns_rows(seeded_workspace: Workspace):
    views = [loaded.full_name for loaded in seeded_workspace.loaded_objects if loaded.kind == "view"]

    assert len(views) == 7
    for view in views:
        assert scalar(seeded_workspace, f"SELECT COUNT(*) FROM {view}") > 0, view


@pytest.mark.parametrize(("child", "column", "parent"), [
    ("people.default.employment", "person_id", "people.default.person"),
    ("people.default.employment", "company_id", "people.default.company"),
    ("people.default.person_bank_account", "person_id", "people.default.person"),
    ("people.default.person_bank_account", "bank_id", "people.default.bank"),
    ("people.default.company_bank_account", "company_id", "people.default.company"),
    ("people.default.company_bank_account", "bank_id", "people.default.bank"),
    ("trades.default.trade", "customer_id", "trades.default.customer"),
    ("trades.default.trade", "home_company_id", "trades.default.home_company"),
    ("trades.default.trade", "commodity_id", "trades.default.commodity"),
    ("trades.default.trade", "trader_user_id", "trades.default.users"),
    ("trades.default.user_customer_access", "user_id", "trades.default.users"),
    ("trades.default.user_customer_access", "customer_id", "trades.default.customer"),
    ("trades.default.user_commodity_access", "commodity_id", "trades.default.commodity"),
    ("computer_store.default.orders", "customer_id", "computer_store.default.customer"),
    ("computer_store.default.orders", "employee_id", "computer_store.default.employee"),
    ("computer_store.default.order_item", "order_id", "computer_store.default.orders"),
    ("computer_store.default.order_item", "pc_id", "computer_store.default.pc"),
    ("computer_store.default.order_item", "laptop_id", "computer_store.default.laptop"),
    ("computer_store.default.order_item", "monitor_id", "computer_store.default.monitor"),
    ("computer_store.default.order_item", "retro_computer_id", "computer_store.default.retro_computer"),
    ("computer_store.default.order_item", "accessory_id", "computer_store.default.accessories"),
    ("computer_store.default.invoice", "order_id", "computer_store.default.orders"),
])
def test_foreign_keys_point_at_existing_rows(seeded_workspace: Workspace, child: str, column: str, parent: str):
    orphans = scalar(seeded_workspace, f"""
        SELECT COUNT(*) FROM {child} c LEFT JOIN {parent} p ON p.id = c.{column}
        WHERE c.{column} IS NOT NULL AND p.id IS NULL
    """)

    assert orphans == 0


def test_trade_currencies_exist(seeded_workspace: Workspace):
    assert scalar(seeded_workspace, """
        SELECT COUNT(*) FROM trades.default.trade t LEFT JOIN trades.default.currency c ON c.code = t.currency_code WHERE c.code IS NULL
    """) == 0


def test_identifiers_are_unique(seeded_workspace: Workspace):
    for table, column in (("people.default.person", "tax_id"), ("people.default.person_bank_account", "iban"),
                          ("people.default.company", "tax_id"), ("trades.default.users", "login"),
                          ("computer_store.default.invoice", "invoice_number")):
        assert scalar(seeded_workspace, f"SELECT COUNT(*) - COUNT(DISTINCT {column}) FROM {table}") == 0, f"{table}.{column}"


def test_each_order_line_references_exactly_its_product_type(seeded_workspace: Workspace):
    assert scalar(seeded_workspace, """
        SELECT COUNT(*) FROM computer_store.default.order_item
        WHERE (CASE WHEN pc_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN laptop_id IS NULL THEN 0 ELSE 1 END)
            + (CASE WHEN monitor_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN retro_computer_id IS NULL THEN 0 ELSE 1 END)
            + (CASE WHEN accessory_id IS NULL THEN 0 ELSE 1 END) <> 1
           OR (product_type = 'pc' AND pc_id IS NULL)
           OR (product_type = 'laptop' AND laptop_id IS NULL)
           OR (product_type = 'monitor' AND monitor_id IS NULL)
           OR (product_type = 'retro_computer' AND retro_computer_id IS NULL)
           OR (product_type = 'accessories' AND accessory_id IS NULL)
    """) == 0


def test_invoices_match_their_order_lines(seeded_workspace: Workspace):
    assert scalar(seeded_workspace, """
        SELECT COUNT(*) FROM computer_store.default.invoice inv
        JOIN (SELECT order_id, SUM(line_total) AS net FROM computer_store.default.order_item GROUP BY order_id) lines
          ON lines.order_id = inv.order_id
        WHERE inv.net_amount <> lines.net OR inv.gross_amount <> inv.net_amount + inv.vat_amount
    """) == 0
    assert scalar(seeded_workspace, """
        SELECT COUNT(*) FROM computer_store.default.invoice inv JOIN computer_store.default.orders o ON o.id = inv.order_id
        WHERE o.status IN ('NEW', 'CANCELLED')
    """) == 0


def test_every_trade_was_made_by_a_trader_allowed_to_make_it(seeded_workspace: Workspace):
    assert scalar(seeded_workspace, """
        SELECT COUNT(*) FROM trades.default.trade t
        LEFT JOIN trades.default.user_customer_access ca
          ON ca.user_id = t.trader_user_id AND ca.customer_id = t.customer_id AND ca.access_level = 'TRADE'
        LEFT JOIN trades.default.user_commodity_access co
          ON co.user_id = t.trader_user_id AND co.commodity_id = t.commodity_id AND co.can_trade
        WHERE ca.user_id IS NULL OR co.user_id IS NULL
    """) == 0


def test_trade_buyer_and_seller_follow_direction(seeded_workspace: Workspace):
    assert scalar(seeded_workspace, """
        SELECT COUNT(*) FROM trades.default.trade t
        JOIN trades.default.home_company h ON h.id = t.home_company_id
        JOIN trades.default.customer c ON c.id = t.customer_id
        WHERE NOT ((t.direction = 'BUY' AND t.buyer_name = h.name AND t.seller_name = c.name)
                OR (t.direction = 'SELL' AND t.buyer_name = c.name AND t.seller_name = h.name))
    """) == 0


def test_all_five_commodities_exist(seeded_workspace: Workspace):
    names = [row["name"] for row in seeded_workspace.statement_executor.execute("SELECT name FROM trades.default.commodity ORDER BY id").to_pylist()]

    assert names == ["Coal", "Crude oil", "Copper ore", "Gold", "Silver"]


def test_generation_is_deterministic():
    first_build = PeopleDataset().build()
    second_build = PeopleDataset().build()

    assert first_build.tables[0].rows[:20] == second_build.tables[0].rows[:20]
    assert len(ComputerStoreDataset().build().tables[8].rows) == len(ComputerStoreDataset().build().tables[8].rows)


def test_existing_catalog_needs_replace(tmp_path: Path):
    workspace = Workspace(tmp_path / "lake", tmp_path / "metastore" / "metastore.db")
    try:
        loader = DatasetLoader(workspace.catalog_service)
        loader.load(TradesDataset().build(), replace=False)

        with pytest.raises(ResourceAlreadyExists):
            loader.load(TradesDataset().build(), replace=False)

        reloaded = loader.load(TradesDataset().build(), replace=True)
        trade_rows = next(loaded.row_count for loaded in reloaded if loaded.full_name == "trades.default.trade")

        assert scalar(workspace, "SELECT COUNT(*) FROM trades.default.trade") == trade_rows
    finally:
        workspace.close()
