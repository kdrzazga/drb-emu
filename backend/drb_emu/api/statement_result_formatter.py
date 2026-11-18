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
                "data_array": [list(row) for row in zip(*column_values)],
            },
        }

    def _describe_column(self, position: int, field: pa.Field) -> dict:
        return {
            "name": field.name,
            "position": position,
            "type_name": self.spark_type_names.type_name(field.type),
            "type_text": self.spark_type_names.type_text(field.type),
        }
