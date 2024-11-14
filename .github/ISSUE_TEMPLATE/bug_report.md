---
name: Bug report
about: Create a report to help us improve this library
title: "[BUG]"
labels: bug
assignees: ''

---

## Bug Description
A clear and concise description of what the bug is.

## Environment
- Python version: [e.g., 3.9.00]
- Library version: [e.g., 1.2.0]
- OS: [e.g., Ubuntu 20.04, macOS 12.0]
- Dependencies versions (if relevant):
  ```
  black==24.10.0
  ```

## Steps To Reproduce
1. Initialize database '...'
2. Call method '...'
3. Pass parameters '...'
4. See error

## Expected Behavior
A clear and concise description of what you expected to happen.

## Actual Behavior
What actually happened, including error messages, stack traces, or unexpected responses.

```python
# Code sample that reproduces the issue
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
) # Error occurs here
```

```
# Error output or stack trace if applicable
Traceback (most recent call last):
  ...
Error: Description of the error
```

## Additional Context
- Have you reviewed the documentation?
- Are you using any special configuration?
- Any other context about the problem?

## Possible Solution
If you have any ideas about what might be causing the issue or how to fix it, please share them here.
