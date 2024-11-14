import base64
import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class DatabaseError(Exception):
    """Base exception for database operations"""

    pass


class SecurityError(DatabaseError):
    """Security related exceptions"""

    pass


class RecordError(DatabaseError):
    """Record related exceptions"""

    pass


@dataclass
class DatabaseConfig:
    """Configuration for database instance"""

    name: str
    path: Path
    password: Optional[str] = None
    compression_level: int = 6
    max_size: int = 1024 * 1024  # 1 MB
    auto_compact: bool = True
    version: str = "1.0.0"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "DatabaseConfig":
        """
        Create a DatabaseConfig instance from a dictionary.

        :param data: Dictionary with configuration data
        :return: DatabaseConfig instance
        """
        return DatabaseConfig(
            name=data["name"],
            path=Path(data["path"]),
            password=data.get("password"),
            compression_level=data.get("compression_level", 6),
            max_size=data.get("max_size", 1024 * 1024),
            auto_compact=data.get("auto_compact", True),
            version=data.get("version", "1.0.0"),
        )


class SimpleEncryption:
    """Simple encryption using XOR with a key derived from password"""

    def __init__(self, password: Optional[str] = None):
        self.key: Optional[bytes] = None
        if password:
            # Create a repeatable key from password using SHA-256
            key_hash = hashlib.sha256(password.encode()).digest()
            self.key = key_hash
        else:
            self.key = None

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using XOR with key"""
        if not self.key:
            return data

        key_bytes = self.key * (len(data) // len(self.key) + 1)
        key_bytes = key_bytes[: len(data)]

        encrypted = bytes(a ^ b for a, b in zip(data, key_bytes))
        return base64.b64encode(encrypted)

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data using XOR with key"""
        if not self.key:
            return data

        data = base64.b64decode(data)
        key_bytes = self.key * (len(data) // len(self.key) + 1)
        key_bytes = key_bytes[: len(data)]

        return bytes(a ^ b for a, b in zip(data, key_bytes))


class Record:
    """Enhanced record class with metadata and encryption support"""

    def __init__(
        self,
        name: str,
        data: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None,
        encryption: Optional[SimpleEncryption] = None,
    ):
        self.name = name
        self._raw_data = data if isinstance(data, bytes) else data.encode("utf-8")
        self.metadata = metadata or {}
        self.metadata.update(
            {
                "created_at": datetime.utcnow().isoformat(),
                "size": len(self._raw_data),
                "checksum": self._calculate_checksum(),
            }
        )
        self._encryption = encryption

    def _calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum of the data"""
        return hashlib.sha256(self._raw_data).hexdigest()

    @property
    def raw(self) -> bytes:
        """Get raw bytes data"""
        if self._encryption:
            return self._encryption.decrypt(self._raw_data)
        return self._raw_data

    @property
    def text(self) -> str:
        """Get text representation of data"""
        return self.raw.decode("utf-8")

    @property
    def json(self) -> Any:
        """Get JSON parsed data if possible"""
        return json.loads(self.text)

    def validate(self) -> bool:
        """Validate record integrity"""
        return self._calculate_checksum() == self.metadata.get("checksum")


class Database:
    """Enhanced database class with security and advanced features"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.path = Path(config.path)
        self._encryption = (
            SimpleEncryption(config.password) if config.password else None
        )
        self._validate_or_create()

    def _validate_or_create(self):
        """Validate database file or create new one"""
        if not self.path.exists():
            self._create_new_database()
        elif not zipfile.is_zipfile(self.path):
            raise DatabaseError(f"Invalid database file: {self.path}")
        self._validate_size()

    def _create_new_database(self):
        """Create new database with metadata"""
        with zipfile.ZipFile(
            self.path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=self.config.compression_level,
        ) as zf:
            metadata = {
                "created_at": datetime.utcnow().isoformat(),
                "version": self.config.version,
                "encryption": bool(self._encryption),
            }
            zf.writestr("__metadata__.json", json.dumps(metadata))

    def _validate_size(self):
        """Check if database size exceeds limit"""
        if self.path.stat().st_size > self.config.max_size:
            raise DatabaseError(
                f"Database exceeds size limit of {self.config.max_size} bytes"
            )

    def insert(
        self, name: str, data: Union[bytes, str], metadata: Optional[Dict] = None
    ) -> Record:
        """Insert new record with optional metadata"""
        record = Record(name, data, metadata, self._encryption)

        with zipfile.ZipFile(self.path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
            if f"data/{name}" in zf.namelist():
                raise RecordError(f"Record {name} already exists")

            # Store data and metadata
            encrypted_data = record._raw_data
            if self._encryption:
                encrypted_data = self._encryption.encrypt(encrypted_data)

            zf.writestr(f"data/{name}", encrypted_data)
            zf.writestr(f"metadata/{name}.json", json.dumps(record.metadata))

        return record

    def get(self, name: str) -> Optional[Record]:
        """Retrieve a record by name"""
        with zipfile.ZipFile(self.path, "r") as zf:
            try:
                data_path = f"data/{name}"
                metadata_path = f"metadata/{name}.json"

                # Read data and metadata
                data = zf.read(data_path)
                metadata = json.loads(zf.read(metadata_path))

                # Create and return record
                record = Record(name, data, metadata, self._encryption)
                return record
            except KeyError:
                return None
            except Exception as e:
                raise DatabaseError(f"Failed to read record {name}: {str(e)}")

    def update(
        self, name: str, data: Union[bytes, str], metadata: Optional[Dict] = None
    ) -> Record:
        """Update an existing record with proper preservation of all records"""
        # First, verify record exists
        existing_record = self.get(name)
        if not existing_record:
            raise RecordError(f"Record {name} does not exist")

        # Create new metadata or update existing
        new_metadata = existing_record.metadata.copy() if metadata is None else metadata
        new_metadata.update(
            {
                "updated_at": datetime.utcnow().isoformat(),
                "previous_checksum": existing_record.metadata.get("checksum"),
                "size": len(data if isinstance(data, bytes) else data.encode("utf-8")),
            }
        )

        # Create new record
        new_record = Record(name, data, new_metadata, self._encryption)

        # Prepare data for storage
        encrypted_data = new_record._raw_data
        if self._encryption:
            encrypted_data = self._encryption.encrypt(encrypted_data)

        temp_path = Path(tempfile.mktemp())

        try:
            # Create new zip file with all existing content plus updated record
            with zipfile.ZipFile(self.path, "r") as src_zip:
                # Get list of all files excluding the ones we're updating
                files_to_copy = [
                    f
                    for f in src_zip.namelist()
                    if not (f == f"data/{name}" or f == f"metadata/{name}.json")
                ]

                with zipfile.ZipFile(
                    temp_path,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                    compresslevel=self.config.compression_level,
                ) as dst_zip:
                    # Copy existing files
                    for item in files_to_copy:
                        dst_zip.writestr(item, src_zip.read(item))

                    # Write updated record and metadata
                    dst_zip.writestr(f"data/{name}", encrypted_data)
                    dst_zip.writestr(
                        f"metadata/{name}.json", json.dumps(new_record.metadata)
                    )

            # Verify the temp file
            with zipfile.ZipFile(temp_path, "r") as check_zip:
                all_files = check_zip.namelist()
                data_files = [f for f in all_files if f.startswith("data/")]
                assert len(data_files) == len(
                    set(data_files)
                ), "Duplicate data files found"

            # Replace original file with updated version
            shutil.move(str(temp_path), str(self.path))
            return new_record

        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise DatabaseError(f"Update failed: {str(e)}")

    def delete(self, name: str) -> bool:
        """Delete a record"""
        temp_path = Path(tempfile.mktemp())

        with zipfile.ZipFile(self.path, "r") as src_zip:
            with zipfile.ZipFile(
                temp_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=self.config.compression_level,
            ) as dst_zip:
                for item in src_zip.namelist():
                    if not (
                        item.startswith(f"data/{name}")
                        or item.startswith(f"metadata/{name}")
                    ):
                        dst_zip.writestr(item, src_zip.read(item))

        shutil.move(temp_path, self.path)
        return True

    def list_records(self) -> List[str]:
        """List all record names"""
        with zipfile.ZipFile(self.path, "r") as zf:
            return [
                name.split("/")[-1]
                for name in zf.namelist()
                if name.startswith("data/")
            ]

    def search(self, pattern: str) -> List[str]:
        """Search records by name pattern"""
        all_records = self.list_records()
        return [name for name in all_records if pattern in name]

    def compact(self):
        """Compact database by removing deleted records and optimizing storage"""
        temp_path = Path(tempfile.mktemp())

        with zipfile.ZipFile(self.path, "r") as src_zip:
            with zipfile.ZipFile(
                temp_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=self.config.compression_level,
            ) as dst_zip:
                for item in src_zip.namelist():
                    dst_zip.writestr(item, src_zip.read(item))

        shutil.move(temp_path, self.path)

    def backup(self, backup_path: Union[str, Path]):
        """Create a backup of the database"""
        backup_path = Path(backup_path)
        shutil.copy2(self.path, backup_path)
