from sqlalchemy import create_engine, inspect

# Database connection URI
DATABASEURI = "postgresql://lw2999:341647@104.196.222.236/proj1part2"

# Create the database engine
engine = create_engine(DATABASEURI)

def get_table_columns(table_name):
    with engine.connect() as conn:
        try:
            # Use SQLAlchemy's inspector to get column names
            inspector = inspect(engine)
            columns = inspector.get_columns(table_name)
            print(f"Columns in '{table_name}':")
            for col in columns:
                print(f" - {col['name']} ({col['type']})")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Specify the table name you want to inspect
    get_table_columns("invoice_billed_to")
