# zfdb
Simple interface to the ZIP files to use them as DB

*zfdb* stands for "ZIP file as database".
It is very simple idea that utilizes ability to use some generic ZIP file as data storage.
Main idea of package is to have ability to store some data from application into simple file that can be used via 
DB-styled interface. It might be usefull if there is need to save some intermediate data from other applications - some logs, file lists, configs etc.
Any record inside ZIP file (files are called databases) is just a text\binary file.
You can initialize record with text data, however it is recommended to use your data as bytes for better compatibility.

### Rebuild database
While there is no support of direct editing and deleting files inside ZIP archive (Python built-in package lacks such feature), in some cases you must perform rebuild.
Update can be done by creating duplicate inside the archive. In this case, you can fetch data by using record name from latest file. 
However, you might find useful to use rebuild to defragment database and avoid duplicates.
Rebuild is default operation when deleting record, cause there is no other way to do it.
Rebuild means that current archive (database) will be extracted into temporary folder, some operations can be done upon files (records) and then new archive with same name will be created and old one will be replaced.

### Installation

To install package, use *pip*:
`pip install git+https://github.com/semolex/zfdb`


### Simple usage example

```python 
>>> from zfdb.core import Engine
>>> eng = Engine('./')   # Creates engine that tracks passes storage folder
>>> eng.databases  # List existing databases in the storage
[]
>>> db = eng.get_db('my_db')  # Creates new database or connects to existing
INFO: DB created: [my_db]
INFO: Created connector for database [my_db]
>>> eng.databases  # New database is present now.
['my_db']
>>> db.records() # List all records inside database.
[]
>>> db.insert('new_record', '1')  # Iitializes new record inside database.
INFO: Record [new_record] inserted into [my_db] database
True
>>> db.records()  # New record in now present at database.
['new_record']
>>> rec = db.find('new_record')  # Fetched data from passed record. Also list of record names can be used.
INFO: Fetched [1] records from [my_db]
>>> rec
[<zfdb.core.Record object at 0x1027a7eb8>]  # Result is the list of "Record" objects. Those objects are wrappers around raw data and additional ifo about record.
>>> rec[0].raw() # Show raw data
b'1'
>>> rec[0].to_text()  # Attempt to convert data into text
'1'
>>> db.update('new_record', b' 2')  # Update record with new data
INFO: Fetched [1] records from [my_db]
INFO: Record [new_record] updated in [my_db] database
True
>>> db.records()  # While there is lack of editing file directly, new one is created as duplicate, updated with new data.
['new_record', 'new_record']
>>> rec = db.find('new_record')  # Fetch updated data from database
INFO: Fetched [1] records from [my_db]
>>> rec[0].raw()
b'1 2'
>>> db.update('new_record', b' 3', rebuild=True)  # Update record with rebuild, so no duplicates are created.
INFO: Rebuild complete for [my_db] database with [update] mode
INFO: Record [new_record] updated in [my_db] database
True
>>> rec = db.find('new_record')[0].raw()
INFO: Fetched [1] records from [my_db]
>>> rec
b'1 2 3'
>>> db.records()
['new_record']
>>> db.delete('new_record')  # Delete record from database
INFO: Rebuild complete for [my_db] database with [delete] mode
True
>>> db.records()  
[]
>>> db.drop()  # Drop database
INFO: Dropping database: [my_db]
INFO: Closed connector to database [my_db]
True
>>> db.records()
Traceback (most recent call last):
...
zfdb.exceptions.ConnectorError: No open connectors found for database
>>> eng.databases
[]
```

### Future release plans
* Add bulk operations for insert, delete, update
* Optimize file operations
* Different updates that might be usefull
