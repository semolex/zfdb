# ZFDB

A lightweight, pure Python library for file-based database operations with encryption support. ZFDB provides a secure and easy way to store and manage data in a local file system using ZIP archives.

## Features

- 🔒 Password-based encryption
- 📁 ZIP-based storage with compression
- 🔍 Record search capabilities
- 🏷️ Metadata support
- ✅ Data integrity validation
- 🔄 Automatic compaction
- 💾 Backup functionality
- 📝 JSON support
- 🐍 Pure Python (no external dependencies)

## Installation

Clone the repository or install the package using `pip`:
```bash
pip install zfdb
# or
git clone https://github.com/semolex/zfdb.git
cd zfdb
```

## Quick Start

```python
from pathlib import Path

from zfdb import Database, DatabaseConfig

# Create a database configuration
config = DatabaseConfig(
    name="mydb",
    path=Path("mydb.zip"),
    password="secret123",  # Optional
    compression_level=9
)

# Initialize database
db = Database(config)

# Insert records
db.insert(
    "user1",
    '{"name": "John Doe", "email": "john@example.com"}',
    metadata={"type": "user"}
)

# Read records
record = db.get("user1")
if record:
    user_data = record.json  # Parse as JSON
    print(f"User: {user_data['name']}")
    print(f"Record created: {record.metadata['created_at']}")

# Search records
results = db.search("user")
print(f"Found records: {results}")

# Create backup
db.backup("mydb_backup.zip")
```

## Detailed Usage

### Configuration

```python
from zfdb import DatabaseConfig
from pathlib import Path

config = DatabaseConfig(
    name="mydb",                      # Database name
    path=Path("mydb.zip"),            # Database file path
    password="secret123",             # Optional encryption password
    compression_level=6,              # ZIP compression level (0-9)
    max_size=1024 * 1024 * 100,       # Maximum database size (100MB)
    auto_compact=True,                # Enable automatic compaction
    version="1.0.0"                   # Database version
)
```

### Working with Records

#### Insert Records
```python
# Insert JSON data
db.insert(
    "config1",
    '{"setting": "value"}',
    metadata={"type": "configuration"}
)

# Insert text data
db.insert(
    "note1",
    "This is a text note",
    metadata={"type": "note"}
)

# Insert binary data
db.insert(
    "binary1",
    b"\x00\x01\x02\x03",
    metadata={"type": "binary"}
)
```

#### Read Records
```python
# Get record
record = db.get("config1")

# Access data in different formats
raw_data = record.raw      # bytes
text_data = record.text    # str
json_data = record.json    # parsed JSON

# Access metadata
created_at = record.metadata['created_at']
record_size = record.metadata['size']
```

#### Update Records
```python
db.update(
    "note1",
    "Updated content",
    metadata={"updated_at": datetime.utcnow().isoformat()}
)
```

#### Delete Records
```python
db.delete("note1")
```

### Database Management

#### List Records
```python
all_records = db.list_records()
```

#### Search Records
```python
# Search by name pattern
notes = db.search("note")
configs = db.search("config")
```

#### Database Maintenance
```python
# Compact database (remove deleted records)
db.compact()

# Create backup
db.backup("backup.zip")
```

## Data Security

ZFDB provides several security features:

1. **Password Protection**: Database contents are encrypted using a password-derived key
2. **Data Integrity**: Each record includes a SHA-256 checksum
3. **Size Limits**: Configurable database size limits
4. **Validation**: Automatic data integrity checking

## Best Practices

1. **Regular Backups**: Use the `backup()` method regularly
2. **Error Handling**: Always handle potential exceptions:
   ```python
   try:
       record = db.get("key")
   except DatabaseError as e:
       logger.error(f"Database error: {e}")
   ```
3. **Resource Management**: Close database when done:
   ```python
   try:
       # Use database
   finally:
       db.compact()  # Optional cleanup
   ```

## Limitations
- Not a real database
- Not suitable for concurrent access
- No built-in indexing
- Limited query capabilities
- Not recommended for very large datasets
- Simple encryption (not suitable for highly sensitive data)

## Testing and linting

```bash
poetry run black zfdb/
poetry run isort zfdb/
poetry run mypy zfdb/
poetry run pytest tests/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/yourfeature`)
3. Commit your changes (`git commit -m 'Add some yourfeature'`)
4. Push to the branch (`git push origin feature/yourfeature`)
5. Open a Pull Request
6. Use `isort`, `mypy` and `black` for code formatting and type checking

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Created to be used in local applications to persists data in case there is no other database available
- Inspired by simple key-value stores
- Built using Python standard library components
- Designed for simplicity and ease of use