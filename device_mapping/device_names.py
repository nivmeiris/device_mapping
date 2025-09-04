import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLineEdit, QPushButton, QTextEdit, QLabel,
    QCompleter
)
from PyQt6.QtCore import QStringListModel, Qt
from collections import defaultdict
import json
import csv
import os

# --- Data Loading and Processing ---
canonical_name_to_internal_models = defaultdict(set)
internal_model_to_canonical_names = defaultdict(set)
search_aliases = {}  # Maps normalized_query -> (type, original_string_key)

# Global variables to store results for copying (sets ensure uniqueness)
last_batch_models = set()
last_batch_names = set()


def load_data():
    """Loads and processes data from text files."""

    base_path = ""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    mapping_devices_path = os.path.join(base_path, 'mapping_devices.txt')
    device_names_path = os.path.join(base_path, 'device_names.txt')
    ios_device_mapping_path = os.path.join(base_path, 'mapping_ios_devices.txt')

    try:
        # Step 1: Process mapping_devices.txt (Android canonical names and models)
        with open(mapping_devices_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for entry in data:
            manufacturer = entry[0].strip()
            canonical_device_name = entry[1].strip()  # e.g., "Infinix SMART 8"

            # Add canonical name as a 'name' type alias
            search_aliases[canonical_device_name.lower()] = ("name", canonical_device_name)

            # Add combined manufacturer + canonical name as a 'name' type alias
            combined_name_by_manufacturer = f"{manufacturer} {canonical_device_name}".strip()
            if combined_name_by_manufacturer.lower() != canonical_device_name.lower():
                search_aliases[combined_name_by_manufacturer.lower()] = ("name", canonical_device_name)

            # Add alias from entry[2] as a 'name' type alias
            if len(entry) > 2 and entry[2]:
                alias_from_entry2 = entry[2].strip()
                if alias_from_entry2 and \
                        alias_from_entry2.lower() != canonical_device_name.lower() and \
                        search_aliases.get(alias_from_entry2.lower(), (None, None))[0] != "model" and \
                        alias_from_entry2.lower() != combined_name_by_manufacturer.lower():
                    search_aliases[alias_from_entry2.lower()] = ("name", canonical_device_name)

            specific_internal_models = []
            if len(entry) > 3:
                specific_internal_models.extend([m.strip() for m in entry[3:] if m.strip()])

            canonical_name_to_internal_models[canonical_device_name].update(specific_internal_models)

            # Crucial: Add internal models as 'model' type aliases. This should prioritize over 'name' if conflict.
            for model_code in specific_internal_models:  # e.g., "Infinix-X6525"
                internal_model_to_canonical_names[model_code].add(canonical_device_name)
                search_aliases[model_code.lower()] = ("model", model_code)

        # Step 2: Process device_names.txt (additional aliases for existing names, sometimes models listed as names)
        # This file's 'device_model' column (row[1]) contains device model strings but are really just names from other sources.
        # We need to be careful if a string here overlaps with a real internal model code.
        with open(device_names_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)  # Skip the header row
            for row in reader:
                if len(row) >= 2:
                    make_from_file = row[0].strip()
                    device_name_from_file = row[1].strip()  # This might be "Infinix X6525"

                    normalized_dn = device_name_from_file.lower()

                    # If this normalized string is already registered as a 'model' type, KEEP it as a 'model'.
                    # Otherwise, add/update it as a 'name' type.
                    if search_aliases.get(normalized_dn, (None, None))[0] != "model":
                        search_aliases[normalized_dn] = ("name", device_name_from_file)

                    combined_alias_from_file = f"{make_from_file} {device_name_from_file}".strip()
                    if search_aliases.get(combined_alias_from_file.lower(), (None, None))[0] != "model":
                        search_aliases[combined_alias_from_file.lower()] = ("name",
                                                                            combined_alias_from_file)  # Use combined_alias_from_file as the key for better lookup in search_aliases

        # Step 3: Process mapping_ios_devices.txt (iOS models and names)
        with open(ios_device_mapping_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line or line.startswith(
                        'device_model'):  # Skip header line 'device_model : device name'
                    continue

                parts = line.split(':', 1)
                ios_model = parts[0].strip()  # e.g., "iPhone1,1"
                ios_name = parts[1].strip()  # e.g., "iPhone"

                if not ios_model or not ios_name:
                    continue

                canonical_name_to_internal_models[ios_name].add(ios_model)
                internal_model_to_canonical_names[ios_model].add(ios_name)

                # Add iOS name as a 'name' type alias
                # Prioritize 'name' if already exists unless it's a 'model' already
                if search_aliases.get(ios_name.lower(), (None, None))[0] != "model":
                    search_aliases[ios_name.lower()] = ("name", ios_name)

                # Add iOS model as a 'model' type alias. This should overwrite 'name' if conflict.
                search_aliases[ios_model.lower()] = ("model", ios_model)

        print("Data loaded successfully!")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}. Please ensure data files are located correctly in the bundle.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from 'mapping_devices.txt': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during data loading: {e}")
        sys.exit(1)


# Load data when the script starts
load_data()


# --- PyQt6 Application ---
class DeviceLookupApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Device Model Lookup")
        self.setGeometry(100, 100, 750, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Single Lookup Section
        self.layout.addWidget(QLabel("--- Single Device Lookup ---"))
        self.input_label = QLabel("Enter device name or model:")
        self.layout.addWidget(self.input_label)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("e.g., iPhone 15 Pro Max or iPhone16,2")
        self.layout.addWidget(self.input_field)

        # Autocomplete Setup
        self.completer = QCompleter(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        all_suggestions = set()
        # Collect all original keys that are names from search_aliases
        for normalized_key, (key_type, original_key) in search_aliases.items():
            if key_type == "name":
                all_suggestions.add(original_key)
            elif key_type == "model":
                all_suggestions.add(original_key)  # Also add original model strings for autocompletion

        suggestions_list = sorted(list(all_suggestions))

        model = QStringListModel()
        model.setStringList(suggestions_list)
        self.completer.setModel(model)
        self.input_field.setCompleter(self.completer)

        # Single Lookup Buttons
        self.single_button_layout = QHBoxLayout()
        self.search_model_button = QPushButton("Search Model (Name -> Model)")
        self.search_model_button.clicked.connect(lambda: self.handle_single_lookup(search_type="model"))
        self.single_button_layout.addWidget(self.search_model_button)

        self.search_name_button = QPushButton("Search Name (Model -> Name)")
        self.search_name_button.clicked.connect(lambda: self.handle_single_lookup(search_type="name"))
        self.single_button_layout.addWidget(self.search_name_button)

        self.clear_single_button = QPushButton("Clear Single Search")
        self.clear_single_button.clicked.connect(self.clear_single_search)
        self.single_button_layout.addWidget(self.clear_single_button)

        self.layout.addLayout(self.single_button_layout)

        # Single Lookup Result Display
        self.result_label = QLabel("Single Search Results:")
        self.layout.addWidget(self.result_label)
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setFixedHeight(80)
        self.layout.addWidget(self.result_display)

        # --- Batch Lookup Section ---
        self.layout.addWidget(QLabel("\n--- Batch Device Lookup ---"))
        self.batch_input_label = QLabel("Enter device names or models (one per line):")
        self.layout.addWidget(self.batch_input_label)
        self.batch_input_field = QTextEdit()
        self.batch_input_field.setPlaceholderText("Paste list here, e.g.:\niPhone 14 Pro Max\nSM-S908U\niPhone16,2")
        self.batch_input_field.setFixedHeight(120)
        self.layout.addWidget(self.batch_input_field)

        # Batch Lookup Buttons
        self.batch_button_layout = QHBoxLayout()
        self.batch_lookup_button = QPushButton("Run Batch Lookup")
        self.batch_lookup_button.clicked.connect(self.batch_lookup)
        self.batch_button_layout.addWidget(self.batch_lookup_button)

        self.copy_models_button = QPushButton("Copy All Found Models")
        self.copy_models_button.clicked.connect(self.copy_models_to_clipboard)
        self.batch_button_layout.addWidget(self.copy_models_button)

        self.copy_names_button = QPushButton("Copy All Found Names")
        self.copy_names_button.clicked.connect(self.copy_names_to_clipboard)
        self.batch_button_layout.addWidget(self.copy_names_button)

        self.clear_batch_button = QPushButton("Clear Batch Search")
        self.clear_batch_button.clicked.connect(self.clear_batch_search)
        self.batch_button_layout.addWidget(self.clear_batch_button)

        self.layout.addLayout(self.batch_button_layout)

        # Batch Lookup Result Display
        self.batch_result_label = QLabel("Batch Search Results:")
        self.layout.addWidget(self.batch_result_label)
        self.batch_result_display = QTextEdit()
        self.batch_result_display.setReadOnly(True)
        self.layout.addWidget(self.batch_result_display)

        # Status Bar / Data Update Info
        self.statusBar().showMessage("Data loaded. Ready.")

    def _perform_single_lookup_logic(self, query_text, search_type):
        """
        Performs the core lookup logic for a single query.
        Returns a tuple: (result_type, list_of_found_items, message_for_user)
        """
        normalized_query = query_text.strip().lower()
        if not normalized_query:
            return "error", [], "Empty query."

        lookup_result = search_aliases.get(normalized_query)

        if lookup_result:
            lookup_alias_type, canonical_key_string = lookup_result  # Renamed 'key' to 'canonical_key_string' for clarity

            if search_type == "model":  # User wants models (Name -> Model)
                if lookup_alias_type == "name":
                    models = canonical_name_to_internal_models.get(canonical_key_string)
                    if models:
                        return "success", sorted(list(models)), f"Models for '{canonical_key_string}':"
                    else:
                        return "not_found", [], f"No internal models found for '{canonical_key_string}'."
                elif lookup_alias_type == "model":
                    return "info", [], f"'{query_text}' is an internal model. Use 'Search Name' to find its name(s)."

            elif search_type == "name":  # User wants names (Model -> Name)
                if lookup_alias_type == "model":
                    names = internal_model_to_canonical_names.get(canonical_key_string)
                    if names:
                        return "success", sorted(list(names)), f"Names for internal model '{canonical_key_string}':"
                    else:
                        return "not_found", [], f"No device names found for internal model '{canonical_key_string}'."
                elif lookup_alias_type == "name":
                    return "info", [], f"'{query_text}' is a device name. Use 'Search Model' to find its internal model(s)."

        return "not_found", [], f"No direct match found for '{query_text}'."

    def handle_single_lookup(self, search_type):
        """Handles single lookup requests from the UI."""
        query = self.input_field.text()

        status, items, message = self._perform_single_lookup_logic(query, search_type)

        if status == "success":
            self.result_display.setText(message + "\n" + "\n".join(items))
        elif status == "info":
            self.result_display.setText(message)
        else:  # "not_found" or "error"
            self.result_display.setText(message)

    def batch_lookup(self):
        """Performs batch lookup from the batch_input_field."""
        global last_batch_models, last_batch_names
        last_batch_models.clear()
        last_batch_names.clear()

        input_lines = self.batch_input_field.toPlainText().strip().split('\n')

        if not any(line.strip() for line in input_lines):
            self.batch_result_display.setText("Batch input is empty. Please enter device names or models.")
            self.statusBar().showMessage("Batch lookup failed: Empty input.")
            return

        results_output = []

        for line_num, line in enumerate(input_lines):
            original_query = line.strip()
            if not original_query:
                continue

            # First, try to identify it as a canonical name and get models
            status_model, models_found, msg_model = self._perform_single_lookup_logic(original_query, "model")

            # Second, if not found as a name, try to identify it as a model and get names
            status_name, names_found, msg_name = self._perform_single_lookup_logic(original_query, "name")

            if status_model == "success":
                results_output.append(f"Input: '{original_query}' -> Models: {','.join(models_found)}")
                last_batch_models.update(models_found)
                for model in models_found:
                    last_batch_names.update(internal_model_to_canonical_names.get(model, set()))
            elif status_name == "success":
                results_output.append(f"Input: '{original_query}' -> Names: {','.join(names_found)}")
                last_batch_names.update(names_found)
                last_batch_models.add(original_query)  # Add the original model string to the models set
            else:
                results_output.append(f"Input: '{original_query}' -> No direct match found. ({msg_model} / {msg_name})")

        self.batch_result_display.setText("\n".join(results_output))
        self.statusBar().showMessage(
            f"Batch lookup complete. Found {len(last_batch_models)} unique models and {len(last_batch_names)} unique names.")

    def copy_models_to_clipboard(self):
        """Copies all found internal models from the last batch lookup to the clipboard."""
        global last_batch_models
        if not last_batch_models:
            self.statusBar().showMessage("No models to copy. Run a batch lookup first.")
            return

        clipboard_text = ",".join(sorted(list(last_batch_models)))
        QApplication.clipboard().setText(clipboard_text)
        self.statusBar().showMessage(
            f"Copied {len(last_batch_models)} unique models to clipboard: {clipboard_text[:50]}...")

    def copy_names_to_clipboard(self):
        """Copies all found canonical names from the last batch lookup to the clipboard."""
        global last_batch_names
        if not last_batch_names:
            self.statusBar().showMessage("No names to copy. Run a batch lookup first.")
            return

        clipboard_text = ",".join(sorted(list(last_batch_names)))
        QApplication.clipboard().setText(clipboard_text)
        self.statusBar().showMessage(
            f"Copied {len(last_batch_names)} unique names to clipboard: {clipboard_text[:50]}...")

    def clear_single_search(self):
        """Clears the single search input and results."""
        self.input_field.clear()
        self.result_display.clear()
        self.statusBar().showMessage("Single search cleared. Ready.")

    def clear_batch_search(self):
        """Clears the batch search input and results."""
        global last_batch_models, last_batch_names
        self.batch_input_field.clear()
        self.batch_result_display.clear()
        last_batch_models.clear()
        last_batch_names.clear()
        self.statusBar().showMessage("Batch search cleared. Ready.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DeviceLookupApp()
    window.show()
    sys.exit(app.exec())
