import psycopg2

try:
    connection = psycopg2.connect(
        host="localhost",
        port=5432,
        database="urban_mobility",
        user="postgres",
        password=input("Enter PostgreSQL password: ")
    )

    print("POSTGRESQL CONNECTION SUCCESSFUL")

    connection.close()

except Exception as e:
    print("DATABASE CONNECTION FAILED")
    print(e)