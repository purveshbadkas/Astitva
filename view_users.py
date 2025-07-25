import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Show tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("📦 Tables in your database:")
for table in tables:
    print(" -", table[0])

# Show user records
print("\n👤 User Records:")
cursor.execute("SELECT * FROM users")
rows = cursor.fetchall()

if rows:
    for row in rows:
        print(f"ID: {row[0]} | Name: {row[1]} {row[2]} | Email: {row[3]} | Mobile: {row[4]} | Password: {row[5]}")
else:
    print("No user data found.")
    conn.close()
    exit()

# Ask if user wants to delete a record
user_id = input("\n🗑️ Enter the ID of the user you want to delete (or press Enter to skip): ")

if user_id.strip():
    try:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

        if user:
            confirm = input(f"⚠️ Are you sure you want to delete user '{user[1]} {user[2]}' (ID: {user_id})? [y/N]: ").lower()
            if confirm == 'y':
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                print(f"✅ User with ID {user_id} deleted.")
            else:
                print("❎ Deletion cancelled.")
        else:
            print("🚫 No user found with that ID.")
    except Exception as e:
        print("❌ Error while deleting user:", e)

conn.close()

