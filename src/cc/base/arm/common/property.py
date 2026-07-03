import logging
from typing import Any, Type

log = logging.getLogger("CC")


class PropertyException(Exception):

    def __init__(self, message, *args):
        log.error(message)
        super().__init__(message, *args)


class PropertyTypeException(PropertyException): ...


class Property:
    _type: Type = False
    _unique: bool = False
    _required: bool = False
    _relation: str = False
    _one2many: str = False
    _inverse_name: str = False
    _many2many: str = False
    _value: Any = False
    _semantic: str = None  # optional hint: "datetime", "url", "path", "text", "csv"
    name: str

    SQL_PROPERTY_TYPE_MAPPING = {str: "TEXT", int: "INTEGER", bool: "BOOLEAN", float: "REAL"}

    def __init__(self, **kwargs) -> None:
        self._type = kwargs.get("type", self._type)
        self._unique = kwargs.get("unique", self._unique)
        self._required = kwargs.get("required", self._required)
        self._relation = kwargs.get("relation", self._relation)
        self._one2many = kwargs.get("one2many")
        self._inverse_name = kwargs.get("inverse_name")
        self._many2many = kwargs.get("many2many")
        self._value = kwargs.get("default", self._value)
        self._semantic = kwargs.get("semantic", None)

        defined_props = sum(1 for prop in [self._type, self._relation, self._one2many, self._many2many] if prop)

        if defined_props > 1:
            raise PropertyException("Property can only have one of 'type', 'relation', 'one2many', or 'many2many' defined.")
        if defined_props == 0:
            raise PropertyException("Property must have one of 'type', 'relation', 'one2many', or 'many2many' defined.")

        # A 'one2many' relationship must know which field on the other model points back to it.
        if self._one2many and not self._inverse_name:
            raise PropertyException("A 'one2many' property must also define an 'inverse_name'.")

    def __set_name__(self, owner, name):
        """
        Saves the attribute name on the descriptor instance.
        For example, when `id = Property(...)` is defined on BaseEntity,
        this method is called with owner=BaseEntity and name='id'.
        """
        self.name = name
        log.debug(f"Property descriptor '{name}' bound to owner '{owner.__name__}'")

    def __get__(self, instance, owner):
        if instance is None:
            return self

        cache_name = f"_{self.name}_cache"

        if self._many2many:
            cached_list = instance.__dict__.get(cache_name)
            if cached_list is not None:
                return cached_list

            instance_id = instance.__dict__.get("id")
            from cc.base.arm.common.base_entity import EntityList, _entity_registry
            from cc.base.db import get_db_connection

            RelatedModel = next((m for m in _entity_registry if m._name == self._many2many), None)
            if not RelatedModel:
                raise PropertyException(f"Could not find many2many model '{self._many2many}'.")

            junction = "_".join(sorted([owner._name, self._many2many])) + "_rel"
            self_col = f"{owner._name}_id"
            target_col = f"{self._many2many}_id"

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT {target_col} FROM {junction} WHERE {self_col} = ?", (instance_id,))
            related_ids = [row[0] for row in cursor.fetchall()]

            result = RelatedModel.search([("id", "in", related_ids)]) if related_ids else EntityList([])
            instance.__dict__[cache_name] = result
            return result

        if self._one2many:
            cached_list = instance.__dict__.get(cache_name)
            if cached_list is not None:
                return cached_list

            instance_id = instance.__dict__.get("id")
            log.debug(f"GET o2m '{self.name}': cache miss, fetching for instance {instance_id}")
            from cc.base.arm.common.base_entity import _entity_registry

            RelatedModel = next((m for m in _entity_registry if m._name == self._one2many), None)
            if not RelatedModel:
                raise PropertyException(f"Could not find related model '{self._one2many}' for one2many relation.")

            related_objects = RelatedModel.search([(self._inverse_name, "=", instance_id)])
            instance.__dict__[cache_name] = related_objects
            return related_objects

        elif self._relation:
            cached_obj = instance.__dict__.get(cache_name)
            if cached_obj:
                return cached_obj

            fk_id_name = f"{self.name}_id"
            fk_id = instance.__dict__.get(fk_id_name)
            if not fk_id:
                return None

            instance_id = instance.__dict__.get("id")
            log.debug(f"GET m2o '{self.name}': cache miss, fetching ID={fk_id} for instance {instance_id}")
            from cc.base.arm.common.base_entity import _entity_registry

            RelatedModel = next((m for m in _entity_registry if m._name == self._relation), None)
            if not RelatedModel:
                raise PropertyException(f"Could not find related model '{self._relation}'")

            related_obj = RelatedModel.find(fk_id)
            instance.__dict__[cache_name] = related_obj
            return related_obj

        # --- Handle Simple Properties ---
        return instance.__dict__.get(self.name, self._value)

    def __set__(self, instance, value):
        if self._one2many and instance:
            return

        if self._relation and instance:
            from cc.base.arm.common.base_entity import BaseEntity

            fk_id_name = f"{self.name}_id"
            cache_name = f"_{self.name}_cache"

            if isinstance(value, BaseEntity) and value._name == self._relation:
                # Set the foreign key ID and cache the full object
                instance.__dict__[fk_id_name] = value.id
                instance.__dict__[cache_name] = value
            elif isinstance(value, str) and value.isdigit():
                # Set the foreign key ID and clear any stale cached object
                instance.__dict__[fk_id_name] = int(value)
                if cache_name in instance.__dict__:
                    del instance.__dict__[cache_name]
            elif isinstance(value, int):
                # Set the foreign key ID and clear any stale cached object
                instance.__dict__[fk_id_name] = value
                if cache_name in instance.__dict__:
                    del instance.__dict__[cache_name]
            elif value is None:
                instance.__dict__[fk_id_name] = None
                if cache_name in instance.__dict__:
                    del instance.__dict__[cache_name]
            else:
                raise PropertyTypeException(
                    f"Cannot assign '{type(value).__name__}' to relation '{self.name}'. Expected '{self._relation}' model or an int.",
                )
            return

        if self._type is bool:
            value = bool(value)

        if value and not isinstance(value, self._type):
            raise PropertyTypeException(
                f"Cannot assign value of type '{type(value).__name__}' to property '{self.name}' of type '{self._type.__name__}'.",
            )

        instance.__dict__[self.name] = value
