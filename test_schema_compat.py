import json
from pathlib import Path
import unittest


class SchemaCompatibilityTests(unittest.TestCase):
    def test_object_fields_have_items_and_rule_overrides_is_free_form_dict(self):
        schema = json.loads(
            (Path(__file__).parent / "_conf_schema.json").read_text(encoding="utf-8")
        )

        def visit(fields):
            for name, field in fields.items():
                if field["type"] == "object":
                    self.assertIn("items", field, name)
                    visit(field["items"])

        visit(schema)
        self.assertEqual(schema["growth"]["items"]["rules_overrides"]["type"], "dict")


if __name__ == "__main__":
    unittest.main()
