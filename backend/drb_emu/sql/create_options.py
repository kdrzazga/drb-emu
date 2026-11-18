from dataclasses import dataclass

from sqlglot import exp


@dataclass(frozen=True)
class CreateOptions:
    comment: str | None
    location: str | None
    partition_by: tuple[str, ...]
    is_temporary: bool
    replace: bool
    if_not_exists: bool

    @classmethod
    def of(cls, create: exp.Create) -> "CreateOptions":
        properties = create.args.get("properties")
        property_list = properties.expressions if properties else []
        comment = None
        location = None
        partition_by = ()
        is_temporary = False
        for create_property in property_list:
            if isinstance(create_property, exp.SchemaCommentProperty):
                comment = create_property.this.name
            elif isinstance(create_property, exp.LocationProperty):
                location = create_property.this.name
            elif isinstance(create_property, exp.PartitionedByProperty):
                partition_by = tuple(column.name for column in create_property.this.expressions)
            elif isinstance(create_property, exp.TemporaryProperty):
                is_temporary = True
        return cls(comment, location, partition_by, is_temporary, bool(create.args.get("replace")), bool(create.args.get("exists")))
