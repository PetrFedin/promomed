"""Adversarial PostgreSQL migration parser tests (no external DB required)."""
import unittest

from app import db


class PostgreSQLSqlLexerTests(unittest.TestCase):
    def split(self, text):
        return db._split_postgres_script(text)

    def test_line_comment_semicolon_does_not_create_sql_fragment(self):
        query = """-- A migration document; all records are candidates.
        CREATE TABLE x(id INTEGER); -- between; statements; ignored
        INSERT INTO x(id) VALUES(1); -- trailing; comment"""
        self.assertEqual(
            self.split(query),
            ["CREATE TABLE x(id INTEGER)", "INSERT INTO x(id) VALUES(1)"]
        )

    def test_nested_block_comments_and_comment_only_input(self):
        query = "SELECT/* outer; /* inner; */ tail; */1; /* final; */"
        self.assertEqual(self.split(query), ["SELECT 1"])
        self.assertEqual(self.split("-- hi;\n/* outer /* nested; */ again; */"), [])

    def test_line_comment_preserves_sql_newline(self):
        query = "SELECT 1 -- inline; x;\n + 2; SELECT 3;"
        self.assertEqual(self.split(query), ["SELECT 1  \n + 2", "SELECT 3"])

    def test_literals_and_quoted_identifiers(self):
        text = """SELECT ';--/* hi; */', "semi;--"; SELECT 'it''s;ok';"""
        parts = self.split(text)
        self.assertEqual(len(parts), 2)
        self.assertIn("';--/* hi; */'", parts[0])
        self.assertIn('"semi;--"', parts[0])
        self.assertEqual(parts[1], "SELECT 'it''s;ok'")

    def test_escape_strings_do_not_split_at_escaped_quote(self):
        query = r"SELECT E'a\'b;c', E'd\\'; SELECT 2;"
        parts = self.split(query)
        self.assertEqual(parts, [r"SELECT E'a\'b;c', E'd\\'", "SELECT 2"])

    def test_tagged_dollar_quoted_function_containing_comments(self):
        query = """CREATE FUNCTION f() RETURNS text AS $body$
          BEGIN RETURN '--/*; still literal */';
          -- literal comment-like body; not a SQL statement;
          END;
        $body$ LANGUAGE plpgsql; SELECT 10;"""
        parts = self.split(query)
        self.assertEqual(len(parts), 2)
        self.assertIn("END;", parts[0])
        self.assertIn("-- literal comment-like body;", parts[0])
        self.assertEqual(parts[1], "SELECT 10")

    def test_untagged_dollar_quoted_function(self):
        query = "CREATE FUNCTION f() RETURNS text AS $$ BEGIN RETURN ';'; END; $$ LANGUAGE plpgsql; SELECT 1;"
        parts = self.split(query)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[1], "SELECT 1")

    def test_dollar_quoted_token_in_comment_is_not_opening_tag(self):
        query = "-- $body$ should be ignored; \nSELECT 1;"
        self.assertEqual(self.split(query), ["SELECT 1"])

    def test_unsupported_incomplete_inputs_fail_closed(self):
        for sql in (
            "SELECT 'x;",
            'SELECT "identifier;',
            "SELECT E'abc\\';",
            "CREATE FUNCTION f() RETURNS text AS $abc$ SELECT 1;",
            "/* nested /* still nested */ end",
            "SELECT 1; /* incomplete",
        ):
            with self.subTest(sql=sql):
                with self.assertRaisesRegex(RuntimeError, "Unterminated"):
                    self.split(sql)

    def test_no_semicolon_is_valid_one_statement(self):
        self.assertEqual(self.split(" -- heading;\n SELECT 1"), ["SELECT 1"])

    def test_migration_from_prior_incident_regression(self):
        snippet = """-- Candidate custody; all records have candidate status.
        CREATE TABLE IF NOT EXISTS financial_fixture(
          id TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'candidate'
        );
        CREATE OR REPLACE FUNCTION block_update()
        RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'immutability; no updates';
        END;
        $$ LANGUAGE plpgsql;"""
        parts = self.split(snippet)
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].startswith("CREATE TABLE"))
        self.assertTrue(parts[1].startswith("CREATE OR REPLACE FUNCTION"))
        self.assertIn("RAISE EXCEPTION 'immutability; no updates';", parts[1])

    def test_comments_do_not_merge_tokens(self):
        self.assertEqual(self.split("SELECT/**/1;"), ["SELECT 1"])
        self.assertEqual(self.split("SELECT--a;\n1;"), ["SELECT \n1"])


if __name__ == "__main__":
    unittest.main()
