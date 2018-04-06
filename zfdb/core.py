import os
import logging
import tempfile
import shutil
import warnings
import zipfile as _zip

import zfdb.exceptions as exc

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


class Database:
    """
    Class that represents database.
    Uses passed engine to perform operations with data.
    """

    def __init__(self, name, path, engine):
        """
        Initializes database instance.

        :param name: name of the database
        :param path: path to the database file
        :param engine: engine that used to perform operations with database
        """
        self.name = name
        self.path = path
        self.engine = engine

    def records(self):
        """
        Lists all existing records in database

        :return: list with records names
        """
        return self.engine.list_records(self)

    def find(self, records=None):
        """
        Performs search for passed record names.
        Record names can be sequences of string or string with one record name.

        :param records: sequence of names or string with record name to find
        :return: list of `Records` objects with found result or None
        """
        return self.engine.read_records(self, records)

    def insert(self, record_name, data):
        """
        Inserts new record into database.

        :param record_name: name for the record to store
        :param data: data to store inside the record (bytes or string)
        :return: True if success else can raise exception
        """
        return self.engine.write_record(self, record_name, data)

    def update(self, record_name, data, rebuild=False):
        """
        Updates record inside database.

        :param record_name: name of the record to update
        :param data: data to update record
        :param rebuild: indicates whether to rebuild database (see docs)
        :return: True if success else can raise exception
        """

        return self.engine.update_record(self, record_name, data, rebuild)

    def delete(self, record_name):
        """
        Deletes record inside database.

        :param record_name: name of the record to delete
        :return: True of success else can raise exception
        """
        return self.engine.remove_record(self, record_name)

    def drop(self):
        """
        Drops database and removed all related files and data.

        :return: True if success else can raise exception
        """
        return self.engine.drop_database(self)

    def count(self):
        """
        Return count of the records inside database.

        :return: number of record in the database
        """
        return len(self.engine.list_records(self))

    def close(self):
        """
        Closes connector to the database, avoiding further operations
        until opened again.
        """
        self.engine.drop_connectors(self)


class Record:
    """
    Class that wraps fetched data inti class to have ability store it as object
    with different representation of data.
    """

    def __init__(self, record_name, raw_data):
        """
        Initializes Record instance.

        :param record_name: name of the fetched record
        :param raw_data: raw representation of stored data
        """
        self.record_name = record_name
        self._raw_data = raw_data

    def raw(self):
        """
        Returns raw representation of data of the record.

        :return: raw data
        """
        return self._raw_data

    def to_text(self):
        """
        Returns text representation of data of the record if possible.
        Uses `utf-8` to decode data.

        :return: text representation of data of the record
        """
        return self._raw_data.decode('utf-8')


class Engine:
    """
    Class that utilizes file operations with ZIP archives.
    """

    def __init__(self, storage):
        """
        Initializes engine.
        If no databases found in folded, new one can be created.
        Dict with available connectors is stored in `connections` attr.
        List of available databases is stored in `databases` attr.
        List of rebuild modes is stored in `rebuild_modes` attr.

        :param storage: path to the databases folder.
         """

        self.storage = storage
        self.connections = {}
        self.databases = self._list_databases()
        self.rebuild_modes = ['recreate', 'delete', 'update']

    @staticmethod
    def _recreate(tmp_db, tmp, existing):
        """
        Perform recreation database.
        Copy all extracted files in the temporary folder and recreates them in
        the database with same name as previous database.

        :param tmp_db: temporary database path
        :param tmp: path to the temporary folder
        :param existing: list of existing files in the database to rebuild.
        """
        with _zip.ZipFile(tmp_db, 'x') as z:
            z.close()
        with _zip.ZipFile(tmp_db, 'a') as z:
            fl = [os.path.join(tmp, rec) for rec in existing]
            for rec in fl:
                z.write(rec, arcname=rec.split('/')[-1])

    def _rebuild(self, database_name, rebuild_mode, record_name=None,
                 data=None):
        """
        Perform rebuild via passed mode and parameters.
        Existing database will be replaced after rebuild.

        :param database_name: name of the database to rebuild
        :param rebuild_mode: rebuild mode
        :param record_name: name of the record, required for some modes
        :param data: data for the record, required for some modes
        """
        path = self._get_path(database_name)
        if not rebuild_mode or rebuild_mode not in self.rebuild_modes:
            raise ValueError('Unknown rebuild mode. Available modes: {}'.format(
                self.rebuild_modes))
        tmp = tempfile.mkdtemp()
        with _zip.ZipFile(path, 'r') as z:
            existing = set(z.namelist())
            z.extractall(tmp)
        tmp_db = os.path.join(tmp, database_name + '.zip')
        if rebuild_mode == 'recreate':
            self._recreate(tmp_db, tmp, existing)

        elif rebuild_mode == 'update':
            if not record_name or not data:
                raise exc.RebuildFailedException(
                    '[{}] mode requires "record_name" and "data" parameters'.format(
                        rebuild_mode))
            if record_name not in existing:
                raise exc.RecordNotExists(
                    'Record [{}] not exists in database [{}]'.format(
                        record_name, database_name))
            if isinstance(data, bytes):
                mode = 'ba'
            else:
                mode = 'a'
            with open(os.path.join(tmp, record_name), mode) as _f:
                _f.write(data)
            self._recreate(tmp_db, tmp, existing)

        elif rebuild_mode == 'delete':
            if not record_name:
                raise exc.RebuildFailedException(
                    '[{}] mode requires "record_name" parameter'.format(
                        rebuild_mode))
            if record_name not in existing:
                raise exc.RecordNotExists(
                    'Record [{}] not exists in database [{}]'.format(
                        record_name, database_name))
            os.remove(os.path.join(tmp, record_name))
            existing = set(i for i in existing if i != record_name)
            self._recreate(tmp_db, tmp, existing)

        shutil.move(tmp_db, path)
        shutil.rmtree(tmp, ignore_errors=True)
        log.info(
            'Rebuild complete for [{}] database with [{}] mode'.format(
                database_name,
                rebuild_mode))

    def _get_path(self, database_name):
        """
        Creates path to the passed database name inside the storage path.

        :param database_name: name of the database to build path
        :return: path to the database
        """
        path = os.path.join(self.storage, '{}.zip'.format(database_name))
        return path

    def _validate_connection(self, database_obj):
        """
        Validates if connector to the database exists.
        If no connectors found, raises `ConnectorError` to avoid further
        operation with database until connected again.

        :param database_obj: database instance
        """

        if not id(database_obj) in self.connections:
            raise exc.ConnectorError('No open connectors found for database')

    def _list_databases(self):
        """
        List all available databases in the storage.

        :return: list of databases
        """

        databases = []
        db_list = [f for f in os.listdir(self.storage) if os.path.isfile(
            os.path.join(self.storage, f)) and f.endswith('.zip')]
        for n in db_list:
            databases.append(n.split('.zip')[0])
        return databases

    def create_db(self, database_name):
        """
        Creates new empty database with given name inside the storage path.
        If database with such name already exists, raises `DatabaseExists`
        exception.
        :param database_name: name of the database to create.
        """

        path = self._get_path(database_name)
        try:
            with _zip.ZipFile(path, 'x') as z:
                z.close()
            log.info('DB created: [{}]'.format(database_name))
        except FileExistsError:
            raise exc.DatabaseExists(
                'Database [{}] already exists'.format(database_name))

    def drop_database(self, database_obj):
        """
        Destroys database with all data and drops connector for it.

        :param database_obj: database instance which that must be deleted
        :return: True if success else can raise exception.
        """
        self._validate_connection(database_obj)
        log.info('Dropping database: [{}]'.format(database_obj.name))
        self.drop_connectors(database_obj)
        try:
            os.remove(database_obj.path)
        except FileNotFoundError:
            raise exc.NoSuchDatabaseError(
                'No such database: [{}]'.format(database_obj.name))
        del database_obj
        return True

    def get_db(self, database_name):
        """
        Creates instance of the database and connector for it.

        :param database_name: name of the database to connect.
        :return: `Database` instance
        """
        path = self._get_path(database_name)
        db = Database(database_name, path, self)
        self.connections[id(db)] = (id(db), database_name, path)
        log.info('Created connector for database [{}]'.format(database_name))
        return db

    def write_record(self, database_obj, record_name, data):
        """
        Writes new record with data inside given database.

        :param database_obj: database instance
        :param record_name: name of the record to store
        :param data: data for the record to store
        :return: True if success else can raise exception
        """

        mode = ''
        if isinstance(data, str):
            mode = 'w'
        elif isinstance(data, bytes):
            mode = 'bw'
        path = database_obj.path
        name = database_obj.name
        self._validate_connection(database_obj)
        tmp = tempfile.mkstemp()[1]
        with open(tmp, mode) as _tmp:
            _tmp.write(data)

        with _zip.ZipFile(path, 'a') as z:
            records = z.namelist()
            if record_name in records:
                raise exc.RecordExists(
                    'Record [{}] already exists in database [{}]'.format(
                        record_name, name))
            z.write(tmp, record_name)
            os.remove(tmp)
            log.info(
                'Record [{}] inserted into [{}] database'.format(record_name,
                                                                 name))
            return True

    def update_record(self, database_obj, record_name, data, rebuild=False):
        """
        Updates record with new data inside the given database.
        Supports two scenarions: via simple duplication of the record inside
        database ot via full recreation of the database with updated record.

        :param database_obj: database instance
        :param record_name: name of the record to update
        :param data: data for the record to update
        :param rebuild: indicates whether to rebuild database (see docs)
        :return: True if success else can raise exception
        """
        self._validate_connection(database_obj)
        path = database_obj.path
        name = database_obj.name
        if rebuild:
            self._rebuild(name, 'update', record_name, data)
        else:
            mode = ''
            if isinstance(data, str):
                mode = 'a'
            elif isinstance(data, bytes):
                mode = 'ba'

            self._validate_connection(database_obj)
            _, tmp = tempfile.mkstemp()

            with _zip.ZipFile(path, 'a') as z:
                records = z.namelist()
                if record_name not in records:
                    raise exc.RecordNotExists(
                        'Record [{}] not exists in database [{}]'.format(
                            record_name, name))
                existing_data = self.read_records(database_obj, record_name)[0]
                with open(tmp, mode) as _tmp:
                    _tmp.write(existing_data.raw())
                with open(tmp, mode) as _tmp:
                    _tmp.write(data)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    z.write(tmp, record_name)
                os.remove(tmp)
        log.info(
            'Record [{}] updated in [{}] database'.format(record_name,
                                                          name))
        return True

    def remove_record(self, database_obj, record_name):
        """
        Removes record from database and rebuild database.

        :param database_obj: database instance
        :param record_name: record name to delete
        :return: True if success else can raise exception
        """
        self._validate_connection(database_obj)
        self._rebuild(database_obj.name, 'delete', record_name)
        return True

    def list_connectors(self):
        """
        Lists all open connectors.

        :return: dict with available connectors
        """
        return self.connections

    def drop_connectors(self, database_obj):
        """
        Drop connectors for given database to avoid further operations with it.

        :param database_obj: database instance
        """
        name = database_obj.name
        del self.connections[id(database_obj)]
        log.info('Closed connector to database [{}]'.format(name))

    def list_records(self, database_obj):
        """
        Lists all records inside given database.

        :param database_obj: instance of the database
        :return: list of records inside database
        """

        path = database_obj.path
        self._validate_connection(database_obj)
        with _zip.ZipFile(path) as z:
            records = z.namelist()
            return records

    def read_records(self, database_obj, record_names=None):
        """
        Reads records inside given database by using passed names.
        Returns data from records wrapped with `Record` class.

        :param database_obj: database instance
        :param record_names: sequence of names or name (seq of string or string)
        :return: list of `Record` objects or empty list if record not found
        """
        self._validate_connection(database_obj)
        path = database_obj.path
        name = database_obj.name

        if not record_names:
            record_names = self.list_records(database_obj)
        if not hasattr(record_names, '__iter__') or isinstance(
                record_names, str):
            record_names = (record_names,)
        with _zip.ZipFile(path, 'r') as z:
            result = []
            for _file in record_names:
                try:
                    result.append(Record(record_name=record_names,
                                         raw_data=z.read(_file)))

                except KeyError:
                    pass
            log.info('Fetched [{}] records from [{}]'.format(len(result),
                                                             name))
            return result
