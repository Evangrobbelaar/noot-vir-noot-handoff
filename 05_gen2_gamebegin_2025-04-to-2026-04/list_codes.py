import sqlite3
import csv

def list_access_codes(db_path):
    """
    Retrieve and return a list of all access codes from the database.
    
    Args:
        db_path (str): Path to the SQLite database file.
    
    Returns:
        list: A list of access codes, or an empty list if there are no codes or an error occurs.
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Query all codes from the access_codes table
        c.execute("SELECT code FROM access_codes")
        
        # Fetch all rows and extract the codes
        codes = [row[0] for row in c.fetchall()]  # Removed trailing comma
        
        # Close the connection
        conn.close()
        
        return codes
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []

# Main execution
if __name__ == "__main__":
    # Assuming the script is run from the app directory
    db_path = "access_codes.db"
    codes = list_access_codes(db_path)
    
    # Check if there are any codes and write them to a CSV file
    if codes:
        with open('access_codes.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Access Code'])  # Write header
            writer.writerows([[code] for code in codes])  # Write each code as a row
        print("Access codes have been written to access_codes.csv")
    else:
        print("No access codes found or database error.")