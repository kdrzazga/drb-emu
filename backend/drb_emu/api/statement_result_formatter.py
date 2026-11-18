import math

import pyarrow as pa

from drb_emu.sql.spark_type_names import SparkTypeNames


class StatementResultFormatter:

    def __init__(self):
        self.default_row_limit = 10_000
        self.spark_type_names = SparkTypeNames()

    def format(self, result: pa.Table, row_limit: int | None) -> dict:
        effective_row_limit = row_limit or self.default_row_limit
        returned_rows = result.slice(0, effective_row_limit)
        column_values = [column.to_pylist() for column in returned_rows.columns]
        return {
            "manifest": {
                "schema": {
                    "column_count": result.num_columns,
                    "columns": [self._describe_column(position, field) for position, field in enumerate(result.schema)],
                },
                "total_row_count": result.num_rows,
                "truncated": result.num_rows > effective_row_limit,
            },
            "result": {
                "row_count": returned_rows.num_rows,
                "data_array": [[self._json_safe(value) for value in row] for row in zip(*column_values)],
            },
        }

    def _json_safe(self, value):
        if isinstance(value, float) and not math.isfinite(value):
            return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
        if isinstance(value, bytes):
            return value.hex()
        if isinstance(value, dict):
            return {key: self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        return value

    def _describe_column(self, position: int, field: pa.Field) -> dict:
        return {
            "name": field.name,
            "position": position,
            "type_name": self.spark_type_names.type_name(field.type),
            "type_text": self.spark_type_names.type_text(field.type),
        }
