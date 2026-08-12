import sqlite3
import random
import string

# Database file path
DB_FILE = 'access_codes.db'

def generate_code(length=8):
    """Generate a random access code of the specified length."""
    charset = string.ascii_uppercase + string.digits  # A-Z, 0-9
    return ''.join(random.choice(charset) for _ in range(length))

# Connect to the database
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

# Create the table if it doesn't exist
c.execute('''CREATE TABLE IF NOT EXISTS access_codes
             (code TEXT PRIMARY KEY)''')

# Insert 250 unique access codes
inserted = 0
while inserted < 250:
    code = generate_code()
    try:
        c.execute("INSERT INTO access_codes (code) VALUES (?)", (code,))
        conn.commit()
        inserted += 1
    except sqlite3.IntegrityError:
        # Code already exists, try again
        pass

# Close the database connection
conn.close()

print("250 access codes have been added to the database.")