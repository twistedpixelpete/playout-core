"""Validation for externally configured Show Controller connections."""

from copy import deepcopy
import json
from pathlib import Path
import re


class ConnectionConfigError(ValueError):
    pass


RECEIVE_PURPOSES = {'contestantSnapshot', 'executorTrigger'}
SEND_PURPOSES = {'logicState', 'manual'}


def _string(value, field, allow_empty=False):
    if not isinstance(value, str):
        raise ConnectionConfigError('{} must be a string'.format(field))
    value = value.strip()
    if not value and not allow_empty:
        raise ConnectionConfigError(
            '{} must be a non-empty string'.format(field)
        )
    return value


def _port(value, field):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > 65535
    ):
        raise ConnectionConfigError(
            '{} must be an integer from 1 to 65535'.format(field)
        )
    return value


class ConnectionConfig:
    def __init__(self, data):
        if not isinstance(data, dict):
            raise ConnectionConfigError('connection config must be an object')
        try:
            json.dumps(data, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ConnectionConfigError(
                'connection config must contain strict JSON values'
            ) from exc
        if data.get('version') != 1:
            raise ConnectionConfigError('connection config version must be 1')
        unknown = set(data).difference({'version', 'connections'})
        if unknown:
            raise ConnectionConfigError(
                'Unknown connection config field(s): {}'.format(
                    ', '.join(sorted(unknown))
                )
            )
        connections = data.get('connections')
        if not isinstance(connections, list):
            raise ConnectionConfigError('connections must be a list')

        result = []
        identifiers = set()
        receive_ports = set()
        for index, connection in enumerate(connections):
            field = 'connections[{}]'.format(index)
            if not isinstance(connection, dict):
                raise ConnectionConfigError(
                    '{} must be an object'.format(field)
                )
            direction = _string(
                connection.get('direction'), field + '.direction'
            )
            if direction not in ('receive', 'send'):
                raise ConnectionConfigError(
                    '{}.direction must be receive or send'.format(field)
                )
            allowed = {
                'id', 'label', 'direction', 'protocol', 'enabled',
                'port', 'purpose',
                'localAddress' if direction == 'receive' else 'address',
            }
            unknown = set(connection).difference(allowed)
            missing = allowed.difference(connection)
            if unknown:
                raise ConnectionConfigError(
                    '{} has unknown field(s): {}'.format(
                        field, ', '.join(sorted(unknown))
                    )
                )
            if missing:
                raise ConnectionConfigError(
                    '{} missing field(s): {}'.format(
                        field, ', '.join(sorted(missing))
                    )
                )
            identifier = _string(connection['id'], field + '.id')
            if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', identifier) is None:
                raise ConnectionConfigError(
                    '{}.id must be a valid TouchDesigner operator name'.format(
                        field
                    )
                )
            if identifier in identifiers:
                raise ConnectionConfigError(
                    'Duplicate connection id: {}'.format(identifier)
                )
            identifiers.add(identifier)
            protocol = _string(
                connection['protocol'], field + '.protocol'
            )
            if protocol != 'udp':
                raise ConnectionConfigError(
                    '{}.protocol currently supports only udp'.format(field)
                )
            enabled = connection['enabled']
            if not isinstance(enabled, bool):
                raise ConnectionConfigError(
                    '{}.enabled must be boolean'.format(field)
                )
            port = _port(connection['port'], field + '.port')
            if direction == 'receive':
                bind_key = (
                    _string(
                        connection['localAddress'],
                        field + '.localAddress',
                        allow_empty=True,
                    ),
                    port,
                )
                if enabled and bind_key in receive_ports:
                    raise ConnectionConfigError(
                        'Enabled UDP receivers cannot share {}:{}'.format(
                            bind_key[0] or '*', port
                        )
                    )
                receive_ports.add(bind_key)
                address = bind_key[0]
                purposes = RECEIVE_PURPOSES
            else:
                address = _string(
                    connection['address'], field + '.address'
                )
                purposes = SEND_PURPOSES
            purpose = _string(
                connection['purpose'], field + '.purpose'
            )
            if purpose not in purposes:
                raise ConnectionConfigError(
                    '{}.purpose is invalid for {}'.format(field, direction)
                )
            result.append({
                'id': identifier,
                'label': _string(
                    connection['label'], field + '.label'
                ),
                'direction': direction,
                'protocol': protocol,
                'enabled': enabled,
                'address': address,
                'port': port,
                'purpose': purpose,
            })
        self._connections = tuple(result)
        self._by_id = {
            connection['id']: connection
            for connection in self._connections
        }

    @classmethod
    def from_path(cls, path):
        path = Path(path)
        return cls(json.loads(path.read_text(encoding='utf-8')))

    @property
    def connections(self):
        return tuple(deepcopy(item) for item in self._connections)

    def connection(self, identifier):
        try:
            return deepcopy(self._by_id[identifier])
        except KeyError as exc:
            raise ConnectionConfigError(
                'Unknown connection: {}'.format(identifier)
            ) from exc
