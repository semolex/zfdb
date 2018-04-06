class DatabaseExists(Exception):
    pass


class ConnectorError(Exception):
    pass


class RecordExists(Exception):
    pass


class RecordNotExists(Exception):
    pass


class DataTypeError(Exception):
    pass


class RebuildFailedException(Exception):
    pass


class NoSuchDatabaseError(Exception):
    pass
