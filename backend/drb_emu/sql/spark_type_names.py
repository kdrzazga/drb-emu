import pyarrow as pa


class SparkTypeNames:

    def __init__(self):
        self.simple_types = (
            (pa.types.is_int8, "BYTE", "tinyint"),
            (pa.types.is_int16, "SHORT", "smallint"),
            (pa.types.is_int32, "INT", "int"),
            (pa.types.is_int64, "LONG", "bigint"),
            (pa.types.is_uint8, "SHORT", "smallint"),
            (pa.types.is_uint16, "INT", "int"),
            (pa.types.is_uint32, "LONG", "bigint"),
            (pa.types.is_uint64, "DECIMAL", "decimal(20,0)"),
            (pa.types.is_float32, "FLOAT", "float"),
            (pa.types.is_float64, "DOUBLE", "double"),
            (pa.types.is_boolean, "BOOLEAN", "boolean"),
            (pa.types.is_string, "STRING", "string"),
            (pa.types.is_large_string, "STRING", "string"),
            (pa.types.is_string_view, "STRING", "string"),
            (pa.types.is_binary, "BINARY", "binary"),
            (pa.types.is_large_binary, "BINARY", "binary"),
            (pa.types.is_date, "DATE", "date"),
            (pa.types.is_null, "VOID", "void"),
        )

    def type_name(self, arrow_type: pa.DataType) -> str:
        if pa.types.is_decimal(arrow_type):
            return "DECIMAL"
        if pa.types.is_timestamp(arrow_type):
            return "TIMESTAMP" if arrow_type.tz else "TIMESTAMP_NTZ"
        if pa.types.is_list(arrow_type) or pa.types.is_large_list(arrow_type):
            return "ARRAY"
        if pa.types.is_struct(arrow_type):
            return "STRUCT"
        if pa.types.is_map(arrow_type):
            return "MAP"
        for matches_type, type_name, _ in self.simple_types:
            if matches_type(arrow_type):
                return type_name
        return str(arrow_type).upper()

    def type_text(self, arrow_type: pa.DataType) -> str:
        if pa.types.is_decimal(arrow_type):
            return f"decimal({arrow_type.precision},{arrow_type.scale})"
        if pa.types.is_timestamp(arrow_type):
            return "timestamp" if arrow_type.tz else "timestamp_ntz"
        if pa.types.is_list(arrow_type) or pa.types.is_large_list(arrow_type):
            return f"array<{self.type_text(arrow_type.value_type)}>"
        if pa.types.is_struct(arrow_type):
            fields = ",".join(f"{field.name}:{self.type_text(field.type)}" for field in arrow_type)
            return f"struct<{fields}>"
        if pa.types.is_map(arrow_type):
            return f"map<{self.type_text(arrow_type.key_type)},{self.type_text(arrow_type.item_type)}>"
        for matches_type, _, type_text in self.simple_types:
            if matches_type(arrow_type):
                return type_text
        return str(arrow_type)
