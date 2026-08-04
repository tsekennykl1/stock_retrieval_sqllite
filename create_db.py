import sqlite3



# Create and connect to SQLite DB

conn = sqlite3.connect("mystocks.db")

cursor = conn.cursor()



# Create a sample table

cursor.execute("""

    CREATE TABLE IF NOT EXISTS users (

        id INTEGER PRIMARY KEY,

        name TEXT NOT NULL,

        email TEXT NOT NULL

    )

""")



# Insert sample data

cursor.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")

conn.commit()

conn.close()



print("SQLite database created successfully!")
