class Constraint:
    """Base class for declarative model constraints."""
    pass


class UniqueConstraint(Constraint):
    """Declares a unique index across one or more columns."""

    def __init__(self, *columns: str, name: str = None):
        if not columns:
            raise ValueError("UniqueConstraint requires at least one column")
        self.columns = columns
        self._name = name

    def index_name(self, table_name: str) -> str:
        if self._name:
            return self._name
        return f"uq_{table_name}_{'_'.join(self.columns)}"

    def to_sql(self, table_name: str) -> str:
        cols = ", ".join(self.columns)
        return (
            f"CREATE UNIQUE INDEX IF NOT EXISTS {self.index_name(table_name)}"
            f" ON {table_name} ({cols})"
        )
