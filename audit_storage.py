import sqlite3
import os

DB_PATH = "data/metadata.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=== DATABASE AUDIT ===\n")

# Check uploads table schema
print("Uploads Table Schema:")
cursor.execute('PRAGMA table_info(uploads)')
for row in cursor.fetchall():
    print(f"  {row}")

# Check data
print("\nData Statistics:")
cursor.execute('SELECT COUNT(*) FROM uploads')
total = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(DISTINCT filename) FROM uploads')
unique = cursor.fetchone()[0]
print(f"  Total rows: {total}")
print(f"  Unique filenames: {unique}")

# List all files
print("\nStored Filenames:")
cursor.execute('SELECT filename, upload_time FROM uploads ORDER BY upload_time DESC')
for row in cursor.fetchall():
    print(f"  • {row[0]} (uploaded: {row[1]})")

conn.close()

# Check file system
print("\n=== FILE SYSTEM AUDIT ===")
temp_dir = "data/temp"
if os.path.exists(temp_dir):
    files = os.listdir(temp_dir)
    print(f"\nFiles in {temp_dir}:")
    for f in files:
        size = os.path.getsize(os.path.join(temp_dir, f))
        print(f"  • {f} ({size:,} bytes)")
    print(f"Total files: {len(files)}")
else:
    print(f"{temp_dir} does not exist!")

# Check FAISS
print("\n=== FAISS INDEX AUDIT ===")
faiss_path = "data/faiss_index"
if os.path.exists(faiss_path):
    print(f"FAISS index exists at {faiss_path}")
    if os.path.exists(os.path.join(faiss_path, "index.faiss")):
        print("  ✓ index.faiss found")
    if os.path.exists(os.path.join(faiss_path, "index.pkl")):
        print("  ✓ index.pkl found")
else:
    print("FAISS index does not exist!")
