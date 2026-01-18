import json
import logging
import tempfile
import unittest
from pathlib import Path

from taskman.config import (
    get_data_store_dir,
    get_log_level,
    load_config,
    set_data_store_dir,
    set_log_level,
)


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.orig_dir = get_data_store_dir()
        self.orig_level = get_log_level()

    def tearDown(self):
        set_data_store_dir(self.orig_dir)
        set_log_level(self.orig_level)

    def test_load_config_missing_path_uses_default(self):
        # Should resolve and create the default directory
        default_dir = load_config(None)
        self.assertTrue(default_dir.exists())
        self.assertEqual(default_dir, get_data_store_dir())

    def test_load_config_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_config("/no/such/config.json")

    def test_load_config_invalid_json(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write("{not json")
            tmp_path = tmp.name
        try:
            with self.assertRaises(ValueError):
                load_config(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_config_missing_data_store_path(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            json.dump({"foo": "bar"}, tmp)
            tmp_path = tmp.name
        try:
            with self.assertRaises(ValueError):
                load_config(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_config_sets_log_level_string(self):
        with tempfile.TemporaryDirectory() as data_dir:
            with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
                json.dump({"DATA_STORE_PATH": data_dir, "LOG_LEVEL": "DEBUG"}, tmp)
                tmp_path = tmp.name
            try:
                load_config(tmp_path)
                self.assertEqual(logging.DEBUG, get_log_level())
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    def test_load_config_sets_log_level_numeric_string(self):
        with tempfile.TemporaryDirectory() as data_dir:
            with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
                json.dump({"DATA_STORE_PATH": data_dir, "LOG_LEVEL": "15"}, tmp)
                tmp_path = tmp.name
            try:
                load_config(tmp_path)
                self.assertEqual(15, get_log_level())
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    def test_load_config_invalid_log_level_defaults(self):
        with tempfile.TemporaryDirectory() as data_dir:
            with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
                json.dump({"DATA_STORE_PATH": data_dir, "LOG_LEVEL": "VERBOSE"}, tmp)
                tmp_path = tmp.name
            try:
                load_config(tmp_path)
                self.assertEqual(logging.INFO, get_log_level())
            finally:
                Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
