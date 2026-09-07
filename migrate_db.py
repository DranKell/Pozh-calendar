# -*- coding: utf-8 -*-
import sqlite3

con = sqlite3.connect("data/app.db")
cols = [c[1] for c in con.execute("PRAGMA table_info(objects)").fetchall()]
print("Existing cols:", cols)

new_cols = [
    ("functional_hazard", "VARCHAR(50) DEFAULT 'Ф3.1'"),
    ("fire_hazard_category", "VARCHAR(50) DEFAULT 'В'"),
    ("construction_hazard", "VARCHAR(50) DEFAULT 'С0'"),
    ("total_area", "FLOAT DEFAULT 0.0"),
    ("floors", "INTEGER DEFAULT 1")
]

for col_name, col_type in new_cols:
    if col_name not in cols:
        con.execute(f"ALTER TABLE objects ADD COLUMN {col_name} {col_type}")
        print(f"Added {col_name}")

con.commit()
con.close()
print("Migration completed successfully")
