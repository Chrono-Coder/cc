import logging
import sqlite3
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, overload

from cc.base.arm.common.property import Property, PropertyException
from cc.base.db import get_db_connection

log = logging.getLogger("CC")

_entity_registry: List = []

T = TypeVar("T", bound="BaseEntity")


# --- UPDATED EXCEPTION CLASS ---
class EntityException(Exception):
    """Custom exception for entity errors that logs itself on creation."""

    def __init__(self, message, *args):
        log.error(message)  # Log the error message automatically
        super().__init__(message, *args)


class BaseEntityMeta(type):
    def __new__(cls, name, bases, dct):
        if not dct.get("_name"):
            # This exception happens at import time, before logger might be fully set up,
            # so we log AND raise.
            log.critical(f"Class '{name}' must define a '_name' attribute for the table name.")
            raise EntityException(f"Class '{name}' must define a '_name' attribute for the table name.")

        # This part gathers all properties from base classes and the current class.
        properties = {}
        for base in reversed(bases):
            if hasattr(base, "_properties"):
                properties.update(base._properties)

        current_properties = {key: value for key, value in dct.items() if isinstance(value, Property)}
        properties.update(current_properties)
        dct["_properties"] = properties

        new_class = super().__new__(cls, name, bases, dct)
        if name != "BaseEntity" and new_class._name != "base":
            log.debug(f"Registering entity: {new_class._name}")
            _entity_registry.append(new_class)
        return new_class


class EntityList(list):
    def __repr__(self) -> str:
        if not self:
            return "[]"
        class_name = self[0].__class__._name
        if not class_name.endswith("s"):
            class_name += "s"
        count = len(self)
        id_preview = ", ".join(str(item.id) for item in self[:5])
        if count > 5:
            return f"{class_name} ({count}): [{id_preview}, ...]"
        return f"{class_name} ({count}): [{id_preview}]"

    def mapped(self, predicate: str | Callable[[Any], bool]) -> List[Any]:
        """
        Returns a list containing the values of a specific field from each record.
        """
        if isinstance(predicate, str):
            field_name = predicate
            return [getattr(record, field_name) for record in self]
        elif callable(predicate):
            return [predicate(record) for record in self]

        raise TypeError("Predicate must be a string (field name) or a callable function.")

    def filtered(self, predicate: str | Callable[[Any], bool]) -> "EntityList":
        """
        Returns a new EntityList containing only records that satisfy the predicate.
        """
        if isinstance(predicate, str):
            field_name = predicate
            return EntityList([record for record in self if getattr(record, field_name, None)])
        elif callable(predicate):
            return EntityList([record for record in self if predicate(record)])

        raise TypeError("Predicate must be a string (field name) or a callable function.")

    def __getattr__(self, item):
        if len(self) == 1:
            return getattr(self[0], item)
        if self:
            raise AttributeError(f"'EntityList' of size {len(self)} has no attribute '{item}'")

    def __call__(self, *args, **kwargs):
        if len(self) == 1 and callable(self[0]):
            return self[0](*args, **kwargs)
        raise TypeError("EntityList is not callable")


class BaseEntity(metaclass=BaseEntityMeta):
    _name: str = "base"
    _properties: Dict[str, Property]

    # Default ORDER BY for search()/find_by() when the caller passes no orderby.
    # "id" keeps results deterministic (insertion order) for every model;
    # display models (Project, Environment, …) override to "name ASC" so their
    # lists/pickers read alphabetically. Explicit orderby= still wins.
    _order: str = "id"

    id = Property(type=int, unique=True, required=True)

    # === Dunder Methods === #
    def __init__(self, **kwargs):
        """
        Initializes the model instance. Attributes are set from kwargs or Property defaults.
        """
        if type(self) is BaseEntity:
            raise EntityException("Base Entity cannot be initialized directly!")

        for prop_name, prop_obj in self.__class__._properties.items():
            # Use kwargs for explicit values, else use the Property's default value
            value = kwargs.get(prop_name, prop_obj._value)
            setattr(self, prop_name, value)

    def __bool__(self) -> bool:
        return bool(self.id)

    def __repr__(self) -> str:
        instance_id = self.id if hasattr(self, "id") and self.id is not None else "Unsaved"
        return f"{self.__class__._name}(id={instance_id})"

    # === Properties === #
    @property
    def conn(self) -> sqlite3.Connection:
        """
        Returns a database connection for the current entity instance.
        """
        return get_db_connection()

    @classmethod
    def _get_class_conn(cls) -> sqlite3.Connection:
        """
        Returns a database connection for the class.
        """
        return get_db_connection()

    # === CRUD === #
    @classmethod
    def _convert_to_instance(cls, row: sqlite3.Row):
        """
        Converts a database row to an instance of the model.
        """
        new_rec = cls()
        for key, value in dict(row).items():
            setattr(new_rec, key, value)

        return new_rec

    def save(self) -> T:
        """Saves the record to the database (INSERT or UPDATE)."""
        log.debug(f"save() called for {self!r}")
        for prop_name, prop_obj in self.__class__._properties.items():
            if prop_obj._required and getattr(self, prop_name) is None:
                raise EntityException(
                    f"Required property '{prop_name}' is missing for {self.__class__.__name__} before save."
                )

        if self.id:
            log.debug("Record has ID, performing update.")
            self._update()
        else:
            log.debug("Record has no ID, performing create.")
            db_values = self._get_db_values()
            new_instance = self.__class__.create(db_values)
            # Copy new data (like ID) back to this instance
            for prop_name in self.__class__._properties.keys():
                setattr(self, prop_name, getattr(new_instance, prop_name))
        return self

    @classmethod
    def create(cls, vals: Union[Dict, List[Dict]]) -> Union[T, EntityList[T]]:
        """
        Creates one or more records in the database.
        """
        conn = cls._get_class_conn()
        cursor = conn.cursor()

        is_single = isinstance(vals, dict)
        if is_single:
            vals = [vals]

        if not vals:
            return EntityList([]) if not is_single else cls()

        log.debug(f"Creating {len(vals)} record(s) for model '{cls._name}'")

        result_instances = []
        processed_data = []
        complex_data = []
        for v in vals:
            val, complex_vals = cls._prepare_vals_for_creation(v)
            if not val:
                raise EntityException("Cannot create an entity with empty values.")
            processed_data.append(val)
            if complex_vals:
                complex_data.append(complex_vals)

        columns = list(processed_data[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        # No RETURNING: it needs SQLite >= 3.35 and Python links the system
        # libsqlite3, which is older on still-supported LTS distros. lastrowid
        # + SELECT works everywhere and costs one PK lookup.
        sql = f"INSERT INTO {cls._name} ({', '.join(columns)}) VALUES ({placeholders})"

        for row_data in processed_data:
            values = [row_data.get(col) for col in columns]
            log.debug(f"Executing SQL: {sql} with values {values}")
            cursor.execute(sql, values)
            new_row = cursor.execute(
                f"SELECT * FROM {cls._name} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            result_instances.append(cls._convert_to_instance(new_row))

        if complex_data:
            log.debug("Handling complex o2m relationships post-creation.")
            cls._handle_complex_one2many_relationships(complex_data, result_instances)

        if is_single:
            return result_instances[0] if result_instances else cls()
        return EntityList(result_instances)

    @classmethod
    def _apply_default_field_values(cls, vals):
        for prop_name, prop_obj in cls._properties.items():
            if prop_name not in vals and not prop_obj._one2many and not prop_obj._many2many:
                vals[prop_name] = None if prop_obj._relation else (prop_obj._value if prop_obj._value else None)
        return vals

    def _update(self) -> bool:
        """Writes to the database based on how the local instance of an object has been changed"""
        db_values = self._get_db_values()
        if not db_values:  # No values to update (e.g., trying to update only ID or no changes)
            log.warning(f"No updatable properties found or set for {self.__class__.__name__} ID {self.id}.")
            return None

        set_clause = ", ".join([f"{col} = ?" for col in db_values.keys()])
        sql = f"UPDATE {self._name} SET {set_clause} WHERE id = ?"
        cursor = self.conn.cursor()

        log.debug(f"Executing SQL: {sql} with values {(*db_values.values(), self.id)}")
        cursor.execute(sql, (*db_values.values(), self.id))
        return True

    def update(self, vals: Dict[str, Any]) -> T:
        """
        Updates the instance's attributes with new values from a dictionary
        and then calls save() to persist changes to the database.
        """
        if not self.id:
            raise EntityException("Cannot update an entity that has not been saved to the database (it has no ID).")

        log.debug(f"Updating record {self!r} with fields: {list(vals.keys())}")
        properties = self.__class__._properties
        has_local_changes = False
        for key, value in vals.items():
            if key == "id":
                log.warning("Attempted to update 'id' field. Skipping.")
                continue
            if not hasattr(self, key) or key not in properties:
                raise PropertyException(f"E: Property '{key}' not defined on {self.__class__.__name__}.")
            prop = properties[key]

            if prop._many2many:
                log.debug(f"Processing m2m commands for field '{key}'")
                self._process_many2many_commands(key, value)

            elif prop._one2many:
                log.debug(f"Processing o2m commands for field '{key}'")
                self._process_one2many_commands(key, value)

            else:
                setattr(self, key, value)
                has_local_changes = True

        if has_local_changes:
            log.debug("Local changes detected, calling save()")
            return self.save()
        else:
            log.debug("No local changes, skipping save().")
            return self

    def delete(self) -> bool:
        """
        Deletes the current instance's record from the database.
        This method will also recursively delete all one2many children.
        """
        if not self.id:
            log.warning("Cannot delete an object that has not been saved to the database.")
            return False

        log.debug(f"Starting delete for {self!r}. Checking for o2m children.")
        for prop_name, prop in self.__class__._properties.items():
            if prop._one2many:
                # Get all children associated with this record
                children_to_delete = getattr(self, prop_name)
                if children_to_delete:
                    log.debug(f"Deleting {len(children_to_delete)} children from field '{prop_name}'")
                    for child in children_to_delete:
                        # This will recursively call delete if the child has its own children
                        child.delete()

        # 2. Delete the record itself
        log.debug(f"Deleting record {self!r} itself.")
        return self._delete()

    def _delete(self) -> bool:
        """Deletes the current instance's record from the database."""
        cursor = self.conn.cursor()
        # Clean up any many2many junction rows for this record
        for prop_name, prop_obj in self.__class__._properties.items():
            if prop_obj._many2many:
                junction = "_".join(sorted([self._name, prop_obj._many2many])) + "_rel"
                self_col = f"{self._name}_id"
                cursor.execute(f"DELETE FROM {junction} WHERE {self_col} = ?", (self.id,))
        sql = f"DELETE FROM {self._name} WHERE id = ?"
        log.debug(f"Executing SQL: {sql} with ID {self.id}")
        cursor.execute(sql, (self.id,))
        self = self.__class__()  # Reset instance state (though it will be garbage collected)
        return True

    @classmethod
    def delete_all(cls) -> bool:
        log.warning(f"Deleting ALL records from table '{cls._name}'")
        sql = f"DELETE FROM {cls._name}"
        cursor = cls._get_class_conn().cursor()
        cursor.execute(sql)
        return True

    @classmethod
    def upsert(cls, vals_list: List[Dict], on: str) -> List[T]:
        log.debug(f"Upserting {len(vals_list)} records on model '{cls._name}' using key '{on}'")
        domain = [(on, "in", [val[on] for val in vals_list])]
        existing_entities = cls.search(domain)
        existing_entities_key = [getattr(entity, on) for entity in existing_entities]

        log.debug(f"Found {len(existing_entities)} existing records.")
        for entity in existing_entities:
            for val in vals_list:
                if val[on] == getattr(entity, on):
                    log.debug(f"Updating existing record: {entity!r}")
                    entity.update(val)

        filtered_vals = [val for val in vals_list if val[on] not in existing_entities_key]
        log.debug(f"Creating {len(filtered_vals)} new records.")
        return cls.create(filtered_vals)

    @overload
    @classmethod
    def search(
        cls: Type[T], domain: List[tuple], *, limit: int = 1, orderby: Optional[str] = None, operation: str = "AND"
    ) -> T: ...

    @classmethod
    def search(
        cls: Type[T],
        domain: List[tuple],
        limit: Optional[int] = None,
        orderby: Optional[str] = None,
        operation: str = "AND",
    ) -> EntityList[T]:
        """
        Searches for records based on a domain of search criteria.
        Returns:
          - EntityList if multiple or singular or zero records
        """
        where_clauses = []
        params = []

        if not domain:
            log.debug(f"search() called on '{cls._name}' with empty domain. Calling find_by() instead.")
            return cls.find_by(limit=limit, orderby=orderby)

        for field, op, value in domain:
            prop = cls._properties.get(field)
            if not prop:
                raise EntityException(f"Field '{field}' not found on model '{cls._name}'.")

            # Handle operators
            if op.lower() in ("in", "not in"):
                if not isinstance(value, (list, tuple)):
                    raise TypeError(f"Value for '{op}' operator must be a list or tuple.")
                if not value:
                    where_clauses.append("0 = 1")
                    continue
                placeholders = ", ".join(["?"] * len(value))
                where_clauses.append(f"{field} {op.upper()} ({placeholders})")
                params.extend(value)
            else:
                where_clauses.append(f"{field} {op} ?")
                params.append(value)

        operation = " " + operation.strip() + " "
        sql = f"SELECT * FROM {cls._name} WHERE {operation.join(where_clauses)}"
        # Default to the model's _order so results are deterministic. Without it
        # SQLite returns rowid order, which can drift across vacuums/rebuilds and
        # makes pickers/lists shuffle between runs.
        sql += f" ORDER BY {orderby or cls._order}"
        if limit is not None:
            sql += f" LIMIT {limit}"

        cursor = cls._get_class_conn().cursor()
        log.debug(f"Executing SQL: {sql} with params {tuple(params)}")
        cursor.execute(sql, tuple(params))
        results = [cls._convert_to_instance(row) for row in cursor.fetchall()]
        return EntityList(results)

    @overload
    @classmethod
    def find_by(cls: Type[T], limit: int = 1, orderby: Optional[str] = None, **kwargs) -> T: ...

    @classmethod
    def find_by(cls: Type[T], limit: Optional[int] = None, orderby: Optional[str] = None, **kwargs) -> EntityList[T]:
        """Finds records by one or more column values."""
        if not kwargs:
            where_clauses = ["1 = 1"]
        else:
            where_clauses = [f"{key} = ?" for key in kwargs.keys()]

        sql = f"SELECT * FROM {cls._name} WHERE {' AND '.join(where_clauses)}"
        # See search(): default to the model's _order so lists don't shuffle.
        sql += f" ORDER BY {orderby or cls._order}"
        if limit is not None:
            sql += f" LIMIT {limit}"

        cursor = cls._get_class_conn().cursor()
        log.debug(f"Executing SQL: {sql} with params {tuple(kwargs.values())}")
        cursor.execute(sql, tuple(kwargs.values()))
        results = [cls._convert_to_instance(row) for row in cursor.fetchall()]
        return EntityList(results)

    @classmethod
    def find(cls, entity_id: int) -> T:
        """
        Returns an object given an id.
        """
        sql = f"SELECT * FROM {cls._name} WHERE id = ?"
        cursor = cls._get_class_conn().cursor()
        log.debug(f"Executing SQL: {sql} with ID {entity_id}")
        cursor.execute(sql, (entity_id,))
        row = cursor.fetchone()
        return cls._convert_to_instance(row) if row else cls()

    # === Helper Methods === #
    def _get_db_values(self) -> Dict[str, Any]:
        """
        Helper to get a dict of column names and their current values
        for use in INSERT/UPDATE queries. Excludes 'id'.
        """
        db_values = {}
        for prop_name, prop_obj in self.__class__._properties.items():
            if prop_name == "id":
                continue
            if prop_obj._one2many or prop_obj._many2many:
                continue
            value = getattr(self, prop_name, None)
            # Include None so a column can be cleared to NULL on update (else clearing a m2one is a silent no-op).
            if prop_obj._relation:
                db_values[prop_name] = value.id if value is not None else None
            else:
                db_values[prop_name] = value
        return db_values

    def _process_one2many_commands(self, key: str, value: list):
        """
        Helper method to process command lists for one2many fields.
        """
        prop = self.__class__._properties[key]

        if not prop._one2many:
            return None  # Should not happen if called correctly

        if not isinstance(value, list):
            raise PropertyException(f"Value for one2many field '{key}' must be a list of commands.")

        from cc.base.arm.common.base_entity import _entity_registry

        RelatedModel = next((m for m in _entity_registry if m._name == prop._one2many), None)
        if not RelatedModel:
            raise PropertyException(f"Could not find related model '{prop._one2many}'")

        log.debug(f"Processing {len(value)} o2m commands for field '{key}'")
        for command in value:
            if not isinstance(command, (list, tuple)) or len(command) != 3:
                raise PropertyException(f"Invalid command format for one2many field '{key}': {command}")

            cmd_type, cmd_id, cmd_vals = command
            log.debug(f"o2m command: type={cmd_type}, id={cmd_id}, vals={cmd_vals}")

            if cmd_type == 0:  # (0, 0, {vals}) - CREATE
                create_vals = cmd_vals.copy()
                create_vals[prop._inverse_name] = self.id
                RelatedModel.create(create_vals)

            elif cmd_type == 4:  # (4, id, 0) - LINK a single existing record by id
                child_to_link = RelatedModel.find(cmd_id)
                if child_to_link:
                    child_to_link.update({prop._inverse_name: self.id})
                else:
                    log.warning(
                        f"Cannot find related record with ID {cmd_id} for one2many field '{key}'. Skipping link."
                    )

            elif cmd_type == 5:  # (5, 0, 0) - CLEAR all existing related records
                current_children = getattr(self, key)
                log.debug(f"Clearing {len(current_children)} children from '{key}'")
                for record_to_clear in current_children:
                    record_to_clear.delete()

            elif cmd_type == 6:  # (6, 0, [ids]) - REPLACE the list of related records
                new_ids = set(cmd_vals)  # Use a set for efficient lookups
                current_children = getattr(self, key)
                for child in current_children:
                    if child.id not in new_ids:
                        child.delete()

                # Next, find which of the new_ids are not already children
                current_child_ids = {child.id for child in current_children}
                ids_to_add = new_ids - current_child_ids
                if ids_to_add:
                    log.debug(f"Replacing children: Linking {len(ids_to_add)} new records.")
                    for new_id in ids_to_add:
                        child_to_link = RelatedModel.find(new_id)
                        if child_to_link:
                            child_to_link.update({prop._inverse_name: self.id})
                        else:
                            log.warning(
                                f"Cannot find related record with ID {new_id} for one2many field '{key}'. Skipping link."
                            )
            else:
                raise PropertyException(f"Unsupported command type '{cmd_type}' for one2many field '{key}'.")
        return True

    def _process_many2many_commands(self, key: str, value: list):
        """
        Process command lists for many2many fields via the junction table.

        Supported commands (same syntax as o2m):
          (3, id, 0)       — unlink (remove junction row)
          (4, id, 0)       — link (add junction row)
          (5, 0, 0)        — clear (remove all junction rows for this record)
          (6, 0, [ids])    — replace (clear then link given ids)
        """
        prop = self.__class__._properties[key]
        if not prop._many2many:
            return None
        if not isinstance(value, list):
            raise PropertyException(f"Value for many2many field '{key}' must be a list of commands.")

        junction = "_".join(sorted([self._name, prop._many2many])) + "_rel"
        self_col = f"{self._name}_id"
        target_col = f"{prop._many2many}_id"
        cursor = self.conn.cursor()

        # Invalidate the read cache
        cache_name = f"_{key}_cache"
        if cache_name in self.__dict__:
            del self.__dict__[cache_name]

        for command in value:
            if not isinstance(command, (list, tuple)) or len(command) != 3:
                raise PropertyException(f"Invalid command format for many2many field '{key}': {command}")
            cmd_type, cmd_id, cmd_vals = command

            if cmd_type == 4:  # link
                cursor.execute(
                    f"INSERT OR IGNORE INTO {junction} ({self_col}, {target_col}) VALUES (?, ?)",
                    (self.id, cmd_id),
                )
            elif cmd_type == 3:  # unlink
                cursor.execute(
                    f"DELETE FROM {junction} WHERE {self_col} = ? AND {target_col} = ?",
                    (self.id, cmd_id),
                )
            elif cmd_type == 5:  # clear
                cursor.execute(f"DELETE FROM {junction} WHERE {self_col} = ?", (self.id,))
            elif cmd_type == 6:  # replace
                cursor.execute(f"DELETE FROM {junction} WHERE {self_col} = ?", (self.id,))
                for new_id in (cmd_vals or []):
                    cursor.execute(
                        f"INSERT OR IGNORE INTO {junction} ({self_col}, {target_col}) VALUES (?, ?)",
                        (self.id, new_id),
                    )
            else:
                raise PropertyException(f"Unsupported command type '{cmd_type}' for many2many field '{key}'.")
        return True

    @classmethod
    def _prepare_vals_for_creation(cls, vals: Dict) -> Dict:
        """Helper method to process a dictionary of values for creation."""
        final_vals = {}
        complex_vals = {}
        # Handle relations first
        for column_name, value in vals.items():
            prop = cls._properties.get(column_name)
            if prop and prop._many2many:
                pass  # M2M cannot be set during create; use update() after creation
            elif prop and prop._one2many:
                complex_vals[(prop._inverse_name, prop._one2many)] = value
            elif prop and prop._relation:
                if isinstance(value, BaseEntity):
                    final_vals[column_name] = value.id
                elif isinstance(value, int):
                    final_vals[column_name] = value
                elif value is None or value is False:
                    final_vals[column_name] = None
                else:
                    raise TypeError(
                        f"For relation '{column_name}', value must be a model instance, an int ID, or None."
                    )
            else:
                final_vals[column_name] = value

        cls._apply_default_field_values(final_vals)

        if "id" in final_vals:
            del final_vals["id"]

        if not final_vals:
            raise EntityException("Cannot create an entity with empty values.")
        return final_vals, complex_vals

    @classmethod
    def _get_schema_definition(cls) -> (List[str], Dict[str, str]):
        """Helper to generate column definitions from the model's properties."""
        column_definitions = []
        column_map = {}

        for prop_name, prop_obj in cls._properties.items():
            if prop_obj._many2many:
                continue  # junction table, no column in this table
            if prop_name == "id":
                column_definitions.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
                column_map["id"] = "id"
                continue

            column_name = f"{prop_name}" if prop_obj._relation else prop_name
            column_map[prop_name] = column_name

            sql_type = (
                "INTEGER" if prop_obj._relation else Property.SQL_PROPERTY_TYPE_MAPPING.get(prop_obj._type, "TEXT")
            )

            definition = f"{column_name} {sql_type}"
            if prop_obj._unique:
                definition += " UNIQUE"
            if prop_obj._required:
                definition += " NOT NULL"
            column_definitions.append(definition)

        return column_definitions, column_map

    @classmethod
    def _get_properties(cls) -> List[str]:
        """
        This method is not currently used by the ORM logic, but kept for potential future introspection.
        """
        props = [p for p in dir(cls) if isinstance(getattr(cls, p), Property)]
        return props

    @classmethod
    def _handle_complex_one2many_relationships(cls, complex_data: List[Dict], result_instances: EntityList[T]):
        """
        Handles the creation of one2many relationships after the main record has been created.
        """
        from cc.base.arm.common.base_entity import _entity_registry

        for i, vals in enumerate(complex_data):
            instance = result_instances[i]
            for (inverse_rel, one2many_rel), vals_list in vals.items():
                related_model = next((m for m in _entity_registry if m._name == one2many_rel), None)
                if not related_model:
                    log.warning(f"Could not find related model '{one2many_rel}' — skipping o2m commands.")
                    continue

                for command in vals_list:
                    cmd_type, cmd_id, cmd_vals = command

                    if cmd_type == 0:  # (0, 0, {vals}) — CREATE
                        val = cmd_vals.copy()
                        val[inverse_rel] = instance.id
                        related_model.create(val)

                    elif cmd_type == 4:  # (4, id, 0) — LINK existing record
                        child = related_model.find(cmd_id)
                        if child:
                            child.update({inverse_rel: instance.id})
                        else:
                            log.warning(f"Cannot find related record id={cmd_id} for o2m link — skipping.")

                    elif cmd_type == 6:  # (6, 0, [ids]) — REPLACE: link listed ids
                        for new_id in (cmd_vals or []):
                            child = related_model.find(new_id)
                            if child:
                                child.update({inverse_rel: instance.id})
                            else:
                                log.warning(f"Cannot find related record id={new_id} for o2m replace — skipping.")

                    # cmd_type 5 (clear) is a no-op on create — record has no children yet

    @classmethod
    def sync_schema(cls):
        """
        Ensures the database table schema matches the model definition.
        """
        conn = cls._get_class_conn()
        cursor = conn.cursor()

        column_definitions, desired_columns_map = cls._get_schema_definition()
        desired_columns = set(desired_columns_map.values())

        create_sql = f"CREATE TABLE IF NOT EXISTS {cls._name} ({', '.join(column_definitions)})"
        log.debug(f"Syncing Schema for '{cls._name}': {create_sql}")
        cursor.execute(create_sql)

        cursor.execute(f"PRAGMA table_info({cls._name});")
        existing_columns = {row[1] for row in cursor.fetchall()}

        columns_to_add = desired_columns - existing_columns
        for col_name in columns_to_add:
            # Find the full definition for the new column
            col_def = next((d for d in column_definitions if d.strip().startswith(col_name)), None)
            if col_def:
                log.info(f"Schema Sync: Adding column '{col_name}' to table '{cls._name}'...")
                alter_sql = f"ALTER TABLE {cls._name} ADD COLUMN {col_def}"
                cursor.execute(alter_sql)

        columns_to_remove = existing_columns - desired_columns
        if columns_to_remove:
            log.warning(f"Schema Sync: Removing columns {columns_to_remove} from table '{cls._name}'...")

            temp_table_name = f"{cls._name}_temp_rebuild"
            rebuild_create_sql = f"CREATE TABLE {temp_table_name} ({', '.join(column_definitions)})"
            cursor.execute(rebuild_create_sql)

            columns_to_keep = ", ".join(sorted(existing_columns.intersection(desired_columns)))
            copy_sql = f"INSERT INTO {temp_table_name} ({columns_to_keep}) SELECT {columns_to_keep} FROM {cls._name};"
            cursor.execute(copy_sql)
            drop_sql = f"DROP TABLE {cls._name};"
            cursor.execute(drop_sql)

            rename_sql = f"ALTER TABLE {temp_table_name} RENAME TO {cls._name};"
            cursor.execute(rename_sql)

        # Constraints declared via _constraints = [UniqueConstraint(...), ...]
        for constraint in getattr(cls, "_constraints", []):
            cursor.execute(constraint.to_sql(cls._name))

        # Junction tables for many2many properties
        for prop_name, prop_obj in cls._properties.items():
            if not prop_obj._many2many:
                continue
            junction = "_".join(sorted([cls._name, prop_obj._many2many])) + "_rel"
            self_col = f"{cls._name}_id"
            target_col = f"{prop_obj._many2many}_id"
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {junction} (
                    {self_col} INTEGER NOT NULL,
                    {target_col} INTEGER NOT NULL,
                    PRIMARY KEY ({self_col}, {target_col})
                )
            """)
