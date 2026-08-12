import sqlite3
import os

# Database file path
DB_FILE = 'access_codes.db'

def initialize_database():
    """Initialize the database and create the access_codes table if it doesn't exist."""
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE access_codes
                     (code TEXT PRIMARY KEY)''')
        conn.commit()
        conn.close()
        print(f"Database '{DB_FILE}' created and initialized.")
    else:
        print(f"Database '{DB_FILE}' already exists.")

def add_access_code(code):
    """Add a new access code to the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO access_codes (code) VALUES (?)", (code,))
        conn.commit()
        print(f"Access code '{code}' added to the database.")
    except sqlite3.IntegrityError:
        print(f"Access code '{code}' already exists in the database.")
    finally:
        conn.close()

def use_access_code(code):
    """Validate an access code: check if it exists, remove it if it does, and return True/False."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT code FROM access_codes WHERE code = ?", (code,))
    result = c.fetchone()
    if result:
        c.execute("DELETE FROM access_codes WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        print(f"Access granted. Code '{code}' removed from the database.")
        return True
    else:
        conn.close()
        print("Invalid access code.")
        return False

# Initialize the database
initialize_database()

# Add initial access codes
initial_codes = ["abc123", "def456", "ghi789"]
for code in initial_codes:
    add_access_code(code)

# Test the access codes
print("\nTesting access codes:")
use_access_code("abc123")  # Should grant access and remove the code
use_access_code("abc123")  # Should deny access (code already used)
use_access_code("def456")  # Should grant access and remove the code
use_access_code("xyz000")  # Should deny access (code doesn't exist)