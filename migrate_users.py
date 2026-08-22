import sqlite3

def run_migration():
    conn = sqlite3.connect('data/db.sqlite3')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE")
        print("Added email column.")
    except Exception as e:
        print("Email column probably exists:", e)
        
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")
        print("Added password_hash column.")
    except Exception as e:
        print("Password hash column probably exists:", e)
        
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
