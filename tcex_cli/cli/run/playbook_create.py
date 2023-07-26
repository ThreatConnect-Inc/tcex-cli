"""Playbook Create"""
# standard library
import base64
import json
import logging
from pathlib import PosixPath

# third-party
from redis.client import Redis

# first-party
from tcex_cli.input.field_type.sensitive import Sensitive

# get tcex logger
logger = logging.getLogger('tcex')
TC_ENTITY_KEYS = ['type', 'value', 'id']
KEY_VALUE_KEYS = ['key', 'value']


class BaseStagger:
    """Base class for staging data in the kvstore."""

    def __init__(self, key: str, value: bytes | dict | str | list[bytes | dict | str]):
        """Initialize class properties."""
        self.key = key
        self.value = value

        self.validate()

    def validate(self):
        """Validate the provided data."""
        if self.key is None or self.value is None:
            raise RuntimeError(f'Invalid data provided, failed to stage {self.key}.')
        self.validate_value()

    @staticmethod
    def serialize(value):
        """Return a serialized value."""
        try:
            return json.dumps(value)
        except ValueError as e:  # pragma: no cover
            raise RuntimeError(f'Invalid data provided, failed to serialize value ({e}).') from e

    def validate_value(self):
        """Raise a RuntimeError if provided data is not valid."""
        return

    def transform(self):
        """Return the transformed value."""
        return self.value

    @staticmethod
    def _coerce_string_value(value) -> str:
        """Return a string value from an bool or int."""
        # coerce bool before int as python says a bool is an int
        if isinstance(value, bool):
            # coerce bool to str type
            return str(value).lower()

        # coerce int to str type
        if isinstance(value, (float, int, PosixPath)):
            return str(value)

        if isinstance(value, Sensitive):
            return str(value)

        if isinstance(value, str):
            return value

        raise RuntimeError(f'Invalid data provided, failed to coerce value ({value}).')

    def stage(self, kv_store, context):
        """Stage the provided value in the kvstore."""
        self.validate()
        if not self.value:
            return None
        value = self.transform()
        value = self.serialize(value)
        return kv_store.hset(context, self.key, value)


class TCEntityStagger(BaseStagger):
    """Stagger for TCEntity."""

    def validate_value(self):
        """Raise a RuntimeError if provided data is not a dict with the correct keys."""
        if not isinstance(self.value, dict):
            raise RuntimeError('Invalid data provided for TCEntity.')
        if not all(x in self.value for x in TC_ENTITY_KEYS):
            raise RuntimeError('Invalid data provided for TCEntity.')


class TCEntityArrayStagger(BaseStagger):
    """Stagger for TCEntity."""

    def validate_value(self):
        """Raise a RuntimeError if provided data is not a list of TCEntity."""
        if not isinstance(self.value, list):
            raise RuntimeError('Invalid data provided for TCEntityArray.')

        for value in self.value:
            if not isinstance(value, dict):
                raise RuntimeError('Invalid data provided for TCEntity.')
            if not all(x in value for x in TC_ENTITY_KEYS):
                raise RuntimeError('Invalid data provided for TCEntity.')


class BinaryStagger(BaseStagger):
    """Stagger for Binary."""

    def validate_value(self):
        """Raise a RuntimeError if provided data is not bytes."""
        if not isinstance(self.value, str):
            raise RuntimeError('Invalid data provided for Binary.')

        try:
            base64.b64decode(self.value)
        except Exception as e:
            raise RuntimeError(
                'Invalid data provided for Binary. Please ensure data is base64 encoded.'
            ) from e

    def transform(self) -> str:
        """Return a string value from bytes."""
        value = base64.b64decode(self.value)  # type: ignore
        return base64.b64encode(value).decode('utf-8')


class BinaryArrayStagger(BaseStagger):
    """Stagger for Binary."""

    def validate_value(self):
        """Raise a RuntimeError if provided data is not a list of bytes."""
        if not isinstance(self.value, list):
            raise RuntimeError('Invalid data provided for BinaryArray.')

        for value in self.value:
            if not isinstance(value, str):
                raise RuntimeError('Invalid data provided for BinaryArray.')
            try:
                base64.b64decode(value)
            except Exception as e:
                raise RuntimeError(
                    'Invalid data provided for BinaryArray. Please ensure data is base64 encoded.'
                ) from e

    def transform(self) -> list[str]:
        """Return a list of string values from a list bytes."""
        values = []
        for v in self.value:
            v = base64.b64decode(v)  # type: ignore
            values.append(base64.b64encode(v).decode('utf-8'))

        return values


class KeyValueStagger(BaseStagger):
    """Stagger for KeyValue."""

    def validate_value(self):
        """Raise a RuntimeError if provided data is not a dict with key and value."""
        if not isinstance(self.value, dict):
            raise RuntimeError('Invalid data provided for KeyValue.')
        if not all(x in self.value for x in KEY_VALUE_KEYS):
            raise RuntimeError('Invalid data provided for KeyValue.')


class KeyValueArrayStagger(BaseStagger):
    """Stagger for KeyValue."""

    def validate_value(self):
        """Raise a RuntimeError if provided data is not a list of KeyValues."""
        if not isinstance(self.value, list):
            raise RuntimeError('Invalid data provided for KeyValueArray.')

        for value in self.value:
            if not isinstance(value, dict):
                raise RuntimeError('Invalid data provided for KeyValue.')
            if not all(x in value for x in KEY_VALUE_KEYS):
                raise RuntimeError('Invalid data provided for KeyValue.')


class StringStagger(BaseStagger):
    """Stagger for String."""

    def transform(self):
        """Return a string value from an bool or int."""
        return self._coerce_string_value(self.value)

    def validate_value(self):
        """Raise a RuntimeError if provided data is not a string."""
        if not isinstance(self.value, (str, bool, float, int, PosixPath, Sensitive)):
            raise RuntimeError('Invalid data provided for String.')


class StringArrayStagger(BaseStagger):
    """Stagger for StringArray."""

    def validate_value(self):
        """Raise a RuntimeError if provided data is not a list of strings."""
        if not isinstance(self.value, list):
            raise RuntimeError('Invalid data provided for StringArray.')

        for value in self.value:
            if not isinstance(value, (str, bool, float, int, PosixPath, Sensitive)):
                raise RuntimeError('Invalid data provided for String.')

    def transform(self) -> list[str]:
        """Return a list of string values from a list of bool or int."""
        return [self._coerce_string_value(v) for v in self.value]


class TCBatchStagger(BaseStagger):
    """Stagger for TCBatch."""

    def validate_value(self):
        """Return True if provided data has proper structure for TC Batch."""
        if (
            not isinstance(self.value, dict)
            or not isinstance(self.value.get('indicator', []), list)
            or not isinstance(self.value.get('group', []), list)
        ):
            raise RuntimeError('Invalid data provided for TCBatch.')


class PlaybookCreate:
    """Playbook Write ABC"""

    def __init__(self, key_value_store: Redis, context: str):
        """Initialize the class properties."""
        self.context = context
        self.key_value_store = key_value_store

        # properties
        self.log = logger

    @staticmethod
    def get_data_type(key: str) -> str:
        """Return the data type for the provided key."""
        if not key or not isinstance(key, str) or key.count('!') != 1:
            raise RuntimeError(f'Invalid key: {key} provided.')

        return key.split('!')[1].lower()

    def any(self, key: str, value: str | dict | list[str | dict]):
        """Write the value to the keystore for all types."""

        variable_type_map = {
            'binary': BinaryStagger,
            'binaryarray': BinaryArrayStagger,
            'keyvalue': KeyValueStagger,
            'keyvaluearray': KeyValueArrayStagger,
            'string': StringStagger,
            'stringarray': StringArrayStagger,
            'tcentity': TCEntityStagger,
            'tcentityarray': TCEntityArrayStagger,
            'tcbatch': TCBatchStagger,
        }
        data_type = self.get_data_type(key).lower()
        stagger = variable_type_map[data_type](key, value)
        return stagger.stage(self.key_value_store, self.context)
