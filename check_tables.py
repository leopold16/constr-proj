from sqlalchemy import create_engine, inspect

DATABASEURI = "postgresql://lw2999:341647@104.196.222.236/proj1part2"
engine = create_engine(DATABASEURI)

# Connect and list tables
with engine.connect() as conn:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("Tables in the database:", tables)
