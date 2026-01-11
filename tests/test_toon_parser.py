"""
Unit tests for TOON parser.

Tests the services/toon_parser.py module which provides a custom parser
for TOON (Token-Optimized Object Notation) format used in Claude AI responses.
"""
from services.toon_parser import parse_toon


class TestToonParserBasicFields:
    """Test parsing of simple fields."""

    def test_simple_string_field(self):
        """Test parsing a simple string field."""
        toon = "extraction_status: complete"
        result = parse_toon(toon)
        assert result == {"extraction_status": "complete"}

    def test_simple_numeric_field(self):
        """Test parsing numeric fields."""
        toon = "amount: 42.50"
        result = parse_toon(toon)
        assert result == {"amount": 42.50}

    def test_simple_boolean_field(self):
        """Test parsing boolean fields."""
        toon = "is_valid: true"
        result = parse_toon(toon)
        assert result == {"is_valid": True}


class TestToonParserNestedObjects:
    """Test parsing of nested objects."""

    def test_simple_nested_object(self):
        """Test parsing a simple nested object."""
        toon = """merchant:
  name: REWE
  city: Dortmund"""
        result = parse_toon(toon)
        assert result == {
            "merchant": {
                "name": "REWE",
                "city": "Dortmund"
            }
        }

    def test_deeply_nested_object(self):
        """Test parsing deeply nested objects."""
        toon = """level1:
  level2:
    level3:
      value: deep"""
        result = parse_toon(toon)
        assert result == {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }

    def test_multiple_nested_objects(self):
        """Test parsing multiple nested objects at same level."""
        toon = """merchant:
  name: REWE
  city: Dortmund
transaction:
  date: 2025-10-11
  total: 21.74"""
        result = parse_toon(toon)
        assert result == {
            "merchant": {
                "name": "REWE",
                "city": "Dortmund"
            },
            "transaction": {
                "date": "2025-10-11",
                "total": 21.74
            }
        }


class TestToonParserArrays:
    """Test parsing of arrays."""

    def test_empty_array(self):
        """Test parsing empty arrays."""
        toon = "quality_issues[0]:"
        result = parse_toon(toon)
        assert result == {"quality_issues": []}

    def test_simple_array(self):
        """Test parsing simple arrays (list of strings)."""
        toon = "uncertain_fields[2]: merchant.address,transaction.time"
        result = parse_toon(toon)
        assert result == {
            "uncertain_fields": ["merchant.address", "transaction.time"]
        }

    def test_tabular_array_all_fields(self):
        """Test parsing tabular arrays with all fields present."""
        toon = """items[2]{name,total_price,category_id}:
  Milk,2.99,36
  Bread,1.49,36"""
        result = parse_toon(toon)
        assert result == {
            "items": [
                {"name": "Milk", "total_price": 2.99, "category_id": 36},
                {"name": "Bread", "total_price": 1.49, "category_id": 36}
            ]
        }

    def test_tabular_array_missing_trailing_fields(self):
        """Test parsing tabular arrays with missing trailing optional fields."""
        toon = """items[3]{name,total_price,category_id,quantity,unit_price,notes}:
  Milk,2.99,36
  Bread,1.49,36,2,0.75
  Eggs,3.19,36,,,organic"""
        result = parse_toon(toon)
        assert result == {
            "items": [
                {"name": "Milk", "total_price": 2.99, "category_id": 36},
                {
                    "name": "Bread",
                    "total_price": 1.49,
                    "category_id": 36,
                    "quantity": 2,
                    "unit_price": 0.75
                },
                {
                    "name": "Eggs",
                    "total_price": 3.19,
                    "category_id": 36,
                    "notes": "organic"
                }
            ]
        }

    def test_tabular_array_missing_middle_fields(self):
        """Test parsing tabular arrays with missing middle optional fields."""
        toon = """items[2]{name,total_price,category_id,quantity,unit_price,notes}:
  Milk,2.99,36
  Eggs,3.19,36,,,organic"""
        result = parse_toon(toon)
        # Middle fields (quantity and unit_price) should be omitted (not included as None)
        # Note: Three commas after 36 means two empty fields (quantity and unit_price)
        assert result == {
            "items": [
                {"name": "Milk", "total_price": 2.99, "category_id": 36},
                {
                    "name": "Eggs",
                    "total_price": 3.19,
                    "category_id": 36,
                    "notes": "organic"
                }
            ]
        }


class TestToonParserReceiptStructures:
    """Test parsing of complete receipt-like structures."""

    def test_minimal_receipt(self):
        """Test parsing a minimal receipt structure."""
        toon = """extraction_status: complete

merchant:
  name: REWE
  city: Dortmund

transaction:
  date: 2025-10-11
  total: 4.48

items[2]{name,total_price,category_id}:
  Milk,2.99,36
  Bread,1.49,36"""
        result = parse_toon(toon)

        assert result["extraction_status"] == "complete"
        assert result["merchant"]["name"] == "REWE"
        assert result["merchant"]["city"] == "Dortmund"
        assert result["transaction"]["date"] == "2025-10-11"
        assert result["transaction"]["total"] == 4.48
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "Milk"
        assert result["items"][1]["name"] == "Bread"

    def test_full_receipt_with_optional_fields(self):
        """Test parsing a complete receipt with all optional fields."""
        toon = """extraction_status: complete

merchant:
  name: REWE
  address: Hauptstraße 123
  city: Dortmund
  country: Germany

transaction:
  date: 2025-10-11
  time: "14:30:00"
  currency: EUR
  net_amount: 19.99
  vat_amount: 1.75
  brutto_amount: 21.74
  payment_method: card
  card_number: "1234"

items[3]{name,total_price,category_id,quantity,unit_price,notes}:
  Milk,2.99,36
  Bread,1.49,36,2,0.75
  Coffee,5.99,35,,,imported beans

processing_notes:
  multiline_items_merged: 2
  quality_issues[1]: shadow in lower third

uncertain_fields[1]: merchant.address

need_clarification[1]{name,reason}:
  item_name,unclear text"""
        result = parse_toon(toon)

        # Verify all sections present
        assert "extraction_status" in result
        assert "merchant" in result
        assert "transaction" in result
        assert "items" in result
        assert "processing_notes" in result
        assert "uncertain_fields" in result
        assert "need_clarification" in result

        # Verify merchant details
        assert result["merchant"]["name"] == "REWE"
        assert result["merchant"]["address"] == "Hauptstraße 123"
        assert result["merchant"]["city"] == "Dortmund"
        assert result["merchant"]["country"] == "Germany"

        # Verify transaction details
        assert result["transaction"]["date"] == "2025-10-11"
        assert result["transaction"]["time"] == "14:30:00"
        assert result["transaction"]["currency"] == "EUR"
        assert result["transaction"]["net_amount"] == 19.99
        assert result["transaction"]["vat_amount"] == 1.75
        assert result["transaction"]["brutto_amount"] == 21.74
        assert result["transaction"]["payment_method"] == "card"
        assert result["transaction"]["card_number"] == "1234"

        # Verify items
        assert len(result["items"]) == 3
        assert result["items"][0] == {
            "name": "Milk",
            "total_price": 2.99,
            "category_id": 36
        }
        assert result["items"][1] == {
            "name": "Bread",
            "total_price": 1.49,
            "category_id": 36,
            "quantity": 2,
            "unit_price": 0.75
        }
        assert result["items"][2] == {
            "name": "Coffee",
            "total_price": 5.99,
            "category_id": 35,
            "notes": "imported beans"
        }

        # Verify processing notes
        assert result["processing_notes"]["multiline_items_merged"] == 2
        assert result["processing_notes"]["quality_issues"] == ["shadow in lower third"]

        # Verify uncertain fields
        assert result["uncertain_fields"] == ["merchant.address"]

        # Verify need_clarification
        assert len(result["need_clarification"]) == 1
        assert result["need_clarification"][0] == {
            "name": "item_name",
            "reason": "unclear text"
        }


class TestToonParserEdgeCases:
    """Test edge cases and special values."""

    def test_quoted_values_with_commas(self):
        """Test parsing quoted values that contain commas."""
        toon = 'address: "Hauptstraße 123, 2nd Floor"'
        result = parse_toon(toon)
        assert result == {"address": "Hauptstraße 123, 2nd Floor"}

    def test_quoted_numeric_strings(self):
        """Test parsing quoted numeric strings."""
        toon = 'card_number: "1234"'
        result = parse_toon(toon)
        assert result == {"card_number": "1234"}

    def test_zero_values(self):
        """Test parsing zero values."""
        toon = """vat_amount: 0
discount: 0.00"""
        result = parse_toon(toon)
        assert result == {"vat_amount": 0, "discount": 0.00}

    def test_empty_string_values(self):
        """Test parsing empty string values."""
        toon = 'notes: ""'
        result = parse_toon(toon)
        assert result == {"notes": ""}

    def test_special_characters(self):
        """Test parsing values with special characters."""
        toon = """merchant:
  name: Café & Bar
  address: Hauptstraße 123"""
        result = parse_toon(toon)
        assert result["merchant"]["name"] == "Café & Bar"
        assert result["merchant"]["address"] == "Hauptstraße 123"

    def test_apostrophes_in_item_names(self):
        """Test parsing item names with apostrophes (not quote delimiters)."""
        toon = """items[3]{name,total_price,category_id}:
  M und M's,5.78,35
  Joe's Pizza,12.99,36
  O'Brien Potatoes,3.50,36"""
        result = parse_toon(toon)

        # Verify all items parsed correctly
        assert len(result["items"]) == 3

        # Check first item (M und M's)
        assert result["items"][0]["name"] == "M und M's"
        assert result["items"][0]["total_price"] == 5.78
        assert result["items"][0]["category_id"] == 35

        # Check second item (Joe's Pizza)
        assert result["items"][1]["name"] == "Joe's Pizza"
        assert result["items"][1]["total_price"] == 12.99
        assert result["items"][1]["category_id"] == 36

        # Check third item (O'Brien Potatoes)
        assert result["items"][2]["name"] == "O'Brien Potatoes"
        assert result["items"][2]["total_price"] == 3.5
        assert result["items"][2]["category_id"] == 36

    def test_quoted_commas_in_tabular_arrays(self):
        """Test parsing tabular arrays with quoted item names containing commas."""
        toon = """items[3]{name,total_price,category_id,quantity,unit_price,notes}:
  "VOLVIC NATURELLE 1,5L",7.14,36,6,1.19
  "Water 1,5L",1.49,36,6,0.25
  Regular Milk,2.99,36"""
        result = parse_toon(toon)

        # Verify all items parsed correctly
        assert len(result["items"]) == 3

        # Check first item (VOLVIC with comma in name)
        assert result["items"][0]["name"] == "VOLVIC NATURELLE 1,5L"
        assert result["items"][0]["total_price"] == 7.14
        assert result["items"][0]["category_id"] == 36
        assert result["items"][0]["quantity"] == 6
        assert result["items"][0]["unit_price"] == 1.19

        # Check second item (Water with comma in name)
        assert result["items"][1]["name"] == "Water 1,5L"
        assert result["items"][1]["total_price"] == 1.49
        assert result["items"][1]["category_id"] == 36
        assert result["items"][1]["quantity"] == 6
        assert result["items"][1]["unit_price"] == 0.25

        # Check third item (no comma, no quotes)
        assert result["items"][2]["name"] == "Regular Milk"
        assert result["items"][2]["total_price"] == 2.99
        assert result["items"][2]["category_id"] == 36

    def test_unquoted_comma_detection(self):
        """Test that unquoted commas in item names are detected and raise helpful error."""
        import pytest

        # This should fail because the comma is not quoted
        toon = """items[1]{name,total_price,category_id,quantity,unit_price}:
  VOLVIC NATURELLE 1,5L,7.14,36,6,1.19"""

        with pytest.raises(ValueError) as exc_info:
            parse_toon(toon)

        # Verify error message is helpful
        error_msg = str(exc_info.value)
        assert "Field misalignment detected" in error_msg
        assert "category_id is 7.14 (float)" in error_msg
        assert "unquoted comma" in error_msg
        assert "VOLVIC NATURELLE 1,5L,7.14,36,6,1.19" in error_msg


class TestToonParserErrorHandling:
    """Test error handling for malformed TOON."""

    def test_empty_string_returns_empty_dict(self):
        """Test that empty string returns empty dict."""
        result = parse_toon("")
        assert result == {}

    def test_malformed_syntax_is_tolerated(self):
        """Test that malformed TOON is handled gracefully."""
        # Parser is lenient - skips lines it can't parse
        toon = """valid_key: valid_value
this is not valid TOON { syntax
another_key: another_value"""
        result = parse_toon(toon)
        # Should parse valid lines and skip invalid ones
        assert result.get("valid_key") == "valid_value"
        assert result.get("another_key") == "another_value"
