import pyarrow as pa


class StatementResultFormatter:

    def __init__(self):
        self.default_row_limit = 10_000
        self.type_names = (
            (pa.types.is_int8, "BYTE"),
            (pa.types.is_int16, "SHORT"),
            (pa.types.is_int32, "INT"),
            (pa.types.is_int64, "LONG"),
            (pa.types.is_float32, "FLOAT"),
            (pa.types.is_float64, "DOUBLE"),
            (pa.types.is_decimal, "DECIMAL"),
            (pa.types.is_boolean, "BOOLEAN"),
            (pa.types.is_string, "STRING"),
            (pa.types.is_large_string, "STRING"),
            (pa.types.is_string_view, "STRING"),
            (pa.types.is_binary, "BINARY"),
            (pa.types.is_large_binary, "BINARY"),
            (pa.types.is_date, "DATE"),
            (pa.types.is_timestamp, "TIMESTAMP"),
            (pa.types.is_list, "ARRAY"),
            (pa.types.is_large_list, "ARRAY"),
            (pa.types.is_struct, "STRUCT"),
            (pa.types.is_map, "MAP"),
        )

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

    def type_name(self, arrow_type: pa.DataType) -> str:
        for matches_type, type_name in self.type_names:
            if matches_type(arrow_type):
                return type_name
        return str(arrow_type).upper()

    def _describe_column(self, position: int, field: pa.Field) -> dict:
        return {"name": field.name, "position": position, "type_name": self.type_name(field.type), "type_text": str(field.type)}
