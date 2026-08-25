import sqlite3
conn = sqlite3.connect('spendwise.db')
cols = [r[1] for r in conn.execute("PRAGMA table_info('user')")]
print(cols)
conn.close()
