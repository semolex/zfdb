import json
import tempfile
from pathlib import Path

import pytest

from zfdb import Database, DatabaseConfig, DatabaseError, RecordError


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def db_config(temp_dir):
    return DatabaseConfig(
        name="test",
        path=Path(temp_dir) / "test.zip",
        password=None,
        compression_level=6,
    )


@pytest.fixture
def secure_db_config(temp_dir):
    return DatabaseConfig(
        name="test_secure",
        path=Path(temp_dir) / "test_secure.zip",
        password="secret123",
        compression_level=6,
    )


@pytest.fixture
def db(db_config):
    return Database(db_config)


@pytest.fixture
def secure_db(secure_db_config):
    return Database(secure_db_config)


def test_database_creation(db):
    """Test database initialization"""
    assert db.path.exists()
    assert db.path.suffix == ".zip"


def test_insert_and_get_json(db):
    """Test inserting and retrieving JSON data"""
    data = {"key": "value", "number": 42}
    db.insert("test1", json.dumps(data))

    record = db.get("test1")
    assert record is not None
    assert record.json == data
    assert record.validate()


def test_insert_and_get_text(db):
    """Test inserting and retrieving text data"""
    text = "Hello, World!"
    db.insert("test2", text)

    record = db.get("test2")
    assert record is not None
    assert record.text == text
    assert record.validate()


def test_insert_and_get_bytes(db):
    """Test inserting and retrieving binary data"""
    data = b"Binary Data"
    db.insert("test3", data)

    record = db.get("test3")
    assert record is not None
    assert record.raw == data
    assert record.validate()


def test_update_record(db):
    """Test updating existing record"""
    # Insert initial data
    initial_data = {"status": "old"}
    db.insert("update_test", json.dumps(initial_data))

    # Update data
    new_data = {"status": "new"}
    db.update("update_test", json.dumps(new_data))

    # Verify update
    record = db.get("update_test")
    assert record.json == new_data


def test_delete_record(db):
    """Test deleting a record"""
    # Insert and verify data exists
    db.insert("delete_test", "test data")
    assert db.get("delete_test") is not None

    # Delete and verify it's gone
    db.delete("delete_test")
    assert db.get("delete_test") is None


def test_list_and_search_records(db):
    """Test listing and searching records"""
    # Insert test records
    db.insert("test1", "data1")
    db.insert("test2", "data2")
    db.insert("other", "data3")

    # Test listing
    records = db.list_records()
    assert len(records) == 3
    assert "test1" in records
    assert "test2" in records
    assert "other" in records

    # Test searching
    test_records = db.search("test")
    assert len(test_records) == 2
    assert "test1" in test_records
    assert "test2" in test_records


def test_metadata(db):
    """Test record metadata"""
    metadata = {"type": "test", "tags": ["important"]}
    db.insert("metadata_test", "test data", metadata=metadata)

    record = db.get("metadata_test")
    assert record.metadata["type"] == "test"
    assert record.metadata["tags"] == ["important"]
    assert "created_at" in record.metadata
    assert "checksum" in record.metadata


def test_secure_database(secure_db):
    """Test encrypted database operations"""
    data = {"secret": "value"}
    secure_db.insert("secure_test", json.dumps(data))

    record = secure_db.get("secure_test")
    assert record.json == data
    assert record.validate()


def test_database_size_limit(db_config):
    """Test database size limit enforcement"""
    config = db_config
    config.max_size = 1000
    db = Database(config)

    data = "x" * 100
    inserted = 0

    try:
        for i in range(20):
            db.insert(f"test_{i}", data)
            inserted += 1
            db._validate_size()
    except DatabaseError as e:
        assert "exceeds size limit" in str(e)

    # Verify we inserted some records before hitting limit
    assert inserted > 0
    assert inserted < 20  # Should hit limit before 20 insertions


def test_database_size_validation(db_config):
    """Test size validation during database operations"""
    config = db_config
    config.max_size = 500  # Small limit
    db = Database(config)

    # Insert initial data
    initial_data = "x" * 200
    db.insert("test1", initial_data)

    # Try to update with larger data that would exceed limit
    update_data = "x" * 400

    with pytest.raises(DatabaseError) as exc_info:
        db.update("test1", update_data)
        db._validate_size()
    assert "exceeds size limit" in str(exc_info.value)


def test_database_size_tracking(db_config):
    """Test accurate size tracking of database"""
    config = db_config
    db = Database(config)

    # Get initial size
    initial_size = db.path.stat().st_size

    # Insert data and track size increase
    test_data = "x" * 1000
    db.insert("size_test", test_data)

    # Verify size increased
    new_size = db.path.stat().st_size
    assert new_size > initial_size

    # Delete data and verify size decrease after compaction
    db.delete("size_test")
    db.compact()
    final_size = db.path.stat().st_size
    assert final_size < new_size


def test_duplicate_record(db):
    """Test handling of duplicate records"""
    db.insert("duplicate", "original")

    with pytest.raises(RecordError):
        db.insert("duplicate", "new")


def test_update_nonexistent(db):
    """Test updating non-existent record"""
    with pytest.raises(RecordError):
        db.update("nonexistent", "data")


def test_backup_restore(db, temp_dir):
    """Test database backup functionality"""
    # Insert test data
    db.insert("backup_test", "test data")

    # Create backup
    backup_path = Path(temp_dir) / "backup.zip"
    db.backup(backup_path)

    # Create new database from backup
    backup_config = DatabaseConfig(name="backup", path=backup_path)
    backup_db = Database(backup_config)

    # Verify data
    record = backup_db.get("backup_test")
    assert record is not None
    assert record.text == "test data"


def test_compaction(db):
    """Test database compaction"""
    # Insert and delete some records
    db.insert("keep", "keep data")
    db.insert("delete1", "delete data")
    db.insert("delete2", "delete data")

    db.delete("delete1")
    db.delete("delete2")

    # Compact database
    db.compact()

    # Verify only kept record exists
    records = db.list_records()
    assert len(records) == 1
    assert "keep" in records


def test_record_validation(db):
    """Test record validation"""
    db.insert("validate", "test data")
    record = db.get("validate")

    # Valid record should pass validation
    assert record.validate()

    # Modify raw data to simulate corruption
    record._raw_data = b"corrupted"
    assert not record.validate()


def test_record_updates(db):
    """Test to verify record updates are working correctly"""

    # Insert initial record
    initial_data = {"key": "value1", "number": 1}
    db.insert("test1", json.dumps(initial_data))

    # Verify initial data
    record = db.get("test1")
    assert record.json == initial_data

    # Update record
    updated_data = {"key": "value1", "number": 2}
    db.update("test1", json.dumps(updated_data))

    # Verify update
    record = db.get("test1")
    assert record.json == updated_data

    # Insert records
    for i in range(10):
        data = {"key": f"value{i}", "number": i}
        db.insert(f"bulk{i}", json.dumps(data))

    # Update and verify each record
    for i in range(10):
        # Current state
        before_update = db.get(f"bulk{i}").json
        assert before_update["number"] == i
        # Update
        new_data = {"key": f"value{i}", "number": i + 100}
        db.update(f"bulk{i}", json.dumps(new_data))

        # Verify update
        after_update = db.get(f"bulk{i}").json
        assert after_update["number"] == i + 100

    all_records = db.list_records()
    assert len(all_records) == 11  # 1 initial + 10 bulk
    for i in range(10):
        record = db.get(f"bulk{i}")
        data = record.json
        print(f"Final state bulk{i}: {data}")
        assert data["number"] == i + 100
