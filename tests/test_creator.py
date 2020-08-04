from pathlib import Path

from tableauhyperapi import SqlType, NOT_NULLABLE, NULLABLE, TableDefinition, TableName
from tableauhyperapi import Name
from hyperleaup.creator import convert_struct_field, get_table_def, get_rows, insert_data_into_hyper_file, Creator
from pyspark.sql.types import *

from hyperleaup.spark_fixture import get_spark_session
from tableauhyperapi import HyperProcess, Connection, Telemetry, SchemaName


class TestUtils:

    @staticmethod
    def get_tables(schema: str, hyper_file_path: str):
        with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
            with Connection(endpoint=hp.endpoint, database=hyper_file_path) as connection:
                catalog = connection.catalog
                # Query the Catalog API for all tables under the given schema
                return catalog.get_table_names(SchemaName(schema))

    @staticmethod
    def get_row_count(schema: str, table: str, hyper_file_path: str):
        with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
            with Connection(endpoint=hp.endpoint, database=hyper_file_path) as connection:
                # Query the Hyper File for the number of rows in the table
                return connection.execute_scalar_query(f"SELECT COUNT(*) FROM {TableName(schema, table)}")


class TestCreator(object):

    def test_convert_struct_field(self):
        # ensure strings can be converted correctly
        first_name_col = StructField('first_name', StringType(), False)
        converted_col = convert_struct_field(first_name_col)
        assert(converted_col.name == Name('first_name'))
        assert(converted_col.nullability is NOT_NULLABLE)
        assert(converted_col.type == SqlType.text())

        # ensure dates can be converted correctly
        date_col = StructField('update_date', DateType(), True)
        converted_col = convert_struct_field(date_col)
        assert(converted_col.name == Name('update_date'))
        assert(converted_col.nullability is NULLABLE)
        assert(converted_col.type == SqlType.date())

        # ensure timestamps can be converted correctly
        timestamp_col = StructField('created_at', TimestampType(), False)
        converted_col = convert_struct_field(timestamp_col)
        assert(converted_col.name == Name('created_at'))
        assert(converted_col.nullability is NOT_NULLABLE)
        assert(converted_col.type == SqlType.timestamp())

    def test_get_table_def(self):
        data = [
            (1001, "Jane", "Doe", "2000-05-01", 29.0, False),
            (1002, "John", "Doe", "1988-05-03", 33.0, False),
            (2201, "Elonzo", "Smith", "1990-05-03", 21.0, True),
            (None, None, None, None, None, None) # Test Nulls
        ]
        df = get_spark_session().createDataFrame(data, ["id", "first_name", "last_name", "dob", "age", "is_temp"])
        table_def = get_table_def(df, "Extract", "Extract")

        # Ensure that the Table Name matches
        assert(table_def.table_name.name == Name("Extract"))

        # Ensure that the the TableDefinition column names match
        assert(table_def.get_column(0).name == Name("id"))
        assert(table_def.get_column(1).name == Name("first_name"))
        assert(table_def.get_column(2).name == Name("last_name"))
        assert(table_def.get_column(3).name == Name("dob"))
        assert(table_def.get_column(4).name == Name("age"))
        assert(table_def.get_column(5).name == Name("is_temp"))

        # Ensure that the column data types were converted correctly
        assert(table_def.get_column(0).type == SqlType.big_int())
        assert(table_def.get_column(1).type == SqlType.text())
        assert(table_def.get_column(2).type == SqlType.text())
        assert(table_def.get_column(3).type == SqlType.text())
        assert(table_def.get_column(4).type == SqlType.double())
        assert(table_def.get_column(5).type == SqlType.bool())

    def test_get_rows(self):
        data = [
            (1001, "Jane", "Doe", "2000-05-01", 29.0, False),
            (1002, "John", "Doe", "1988-05-03", 33.0, False),
            (2201, "Elonzo", "Smith", "1990-05-03", 21.0, True)
        ]
        df = get_spark_session().createDataFrame(data, ["id", "first_name", "last_name", "dob", "age", "is_temp"])
        rows = get_rows(df)
        expected_row = [1001, "Jane", "Doe", "2000-05-01", 29.0, False]
        assert(len(rows) == 3)
        assert(rows[0] == expected_row)

    def test_insert_data_into_hyper_file(self):
        data = [
            (1001, "Jane", "Doe"),
            (1002, "John", "Doe"),
            (2201, "Elonzo", "Smith")
        ]
        path = Path("/tmp/output.hyper")
        table_def = TableDefinition(
            table_name=TableName("Extract", "Extract"),
            columns=[
                TableDefinition.Column(name=Name("id"), type=SqlType.big_int(), nullability=NULLABLE),
                TableDefinition.Column(name=Name("first_name"), type=SqlType.text(), nullability=NULLABLE),
                TableDefinition.Column(name=Name("last_name"), type=SqlType.text(), nullability=NULLABLE)
            ]
        )
        insert_data_into_hyper_file(data, path, table_def)
        tables = TestUtils.get_tables("Extract", "/tmp/output.hyper")
        assert(len(tables) == 1)
        num_rows = TestUtils.get_row_count("Extract", "Extract", "/tmp/output.hyper")
        assert(num_rows == 3)

    def test_create(self):
        data = [
            (1001, "Jane", "Doe", "2000-05-01", 29.0, False),
            (1002, "John", "Doe", "1988-05-03", 33.0, False),
            (2201, "Elonzo", "Smith", "1990-05-03", 21.0, True),
            (2202, "James", "Towdry", "1980-05-03", 45.0, False),
            (2235, "Susan", "Sanders", "1980-05-03", 43.0, True)

        ]
        df = get_spark_session().createDataFrame(data, ["id", "first_name", "last_name", "dob", "age", "is_temp"])
        creator = Creator(df, Path("/tmp/output.hyper"), False)
        hyper_file_path = creator.create()
        assert(hyper_file_path == "/tmp/output.hyper")
        tables = TestUtils.get_tables("Extract", "/tmp/output.hyper")
        assert(len(tables) == 1)
        num_rows = TestUtils.get_row_count("Extract", "Extract", "/tmp/output.hyper")
        assert(num_rows == 5)