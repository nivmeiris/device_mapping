# app.py (גרסה מתוקנת ושלמה)
import sys
import json
import csv
import os
from collections import defaultdict
from flask import Flask, request, jsonify, render_template

# --- הגדרת משתנים גלובליים ---
canonical_name_to_internal_models = defaultdict(set)
internal_model_to_canonical_names = defaultdict(set)
search_aliases = {}
all_suggestions = set()


# === קוד מתוקן ושלם לפונקציית טעינת הנתונים ===
def load_data():
    """Loads and processes data from text files."""
    global all_suggestions

    base_path = os.path.dirname(os.path.abspath(__file__))
    mapping_devices_path = os.path.join(base_path, 'mapping_devices.txt')
    device_names_path = os.path.join(base_path, 'device_names.txt')
    ios_device_mapping_path = os.path.join(base_path, 'mapping_ios_devices.txt')

    try:
        # Step 1: Process mapping_devices.txt (Android)
        with open(mapping_devices_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for entry in data:
            manufacturer = entry[0].strip()
            canonical_device_name = entry[1].strip()
            search_aliases[canonical_device_name.lower()] = ("name", canonical_device_name)
            combined_name_by_manufacturer = f"{manufacturer} {canonical_device_name}".strip()
            if combined_name_by_manufacturer.lower() != canonical_device_name.lower():
                search_aliases[combined_name_by_manufacturer.lower()] = ("name", canonical_device_name)
            if len(entry) > 2 and entry[2]:
                alias_from_entry2 = entry[2].strip()
                if alias_from_entry2 and alias_from_entry2.lower() != canonical_device_name.lower() and \
                        search_aliases.get(alias_from_entry2.lower(), (None, None))[
                            0] != "model" and alias_from_entry2.lower() != combined_name_by_manufacturer.lower():
                    search_aliases[alias_from_entry2.lower()] = ("name", canonical_device_name)
            specific_internal_models = [m.strip() for m in entry[3:] if m.strip()] if len(entry) > 3 else []
            canonical_name_to_internal_models[canonical_device_name].update(specific_internal_models)
            for model_code in specific_internal_models:
                internal_model_to_canonical_names[model_code].add(canonical_device_name)
                search_aliases[model_code.lower()] = ("model", model_code)

        # Step 2: Process device_names.txt
        with open(device_names_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)
            for row in reader:
                if len(row) >= 2:
                    make_from_file = row[0].strip()
                    device_name_from_file = row[1].strip()
                    if search_aliases.get(device_name_from_file.lower(), (None, None))[0] != "model":
                        search_aliases[device_name_from_file.lower()] = ("name", device_name_from_file)
                    combined_alias = f"{make_from_file} {device_name_from_file}".strip()
                    if search_aliases.get(combined_alias.lower(), (None, None))[0] != "model":
                        search_aliases[combined_alias.lower()] = ("name", combined_alias)

        # Step 3: Process mapping_ios_devices.txt
        with open(ios_device_mapping_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line or line.startswith('device_model'):
                    continue
                parts = line.split(':', 1)
                ios_model, ios_name = parts[0].strip(), parts[1].strip()
                if not ios_model or not ios_name:
                    continue
                canonical_name_to_internal_models[ios_name].add(ios_model)
                internal_model_to_canonical_names[ios_model].add(ios_name)
                if search_aliases.get(ios_name.lower(), (None, None))[0] != "model":
                    search_aliases[ios_name.lower()] = ("name", ios_name)
                search_aliases[ios_model.lower()] = ("model", ios_model)

        # Step 4: Populate suggestions for autocomplete
        for key_type, original_key in search_aliases.values():
            all_suggestions.add(original_key)

        print(f"Data loaded successfully! Found {len(all_suggestions)} suggestions.")
    except FileNotFoundError as e:
        print(f"FATAL ERROR: Data file not found: {e}. Make sure all .txt files are in the same directory as app.py.")
        sys.exit(1)
    except Exception as e:
        print(f"Error during data loading: {e}")
        sys.exit(1)


def _perform_single_lookup_logic(query_text, search_type):
    normalized_query = query_text.strip().lower()
    if not normalized_query:
        return "error", [], "Empty query."
    lookup_result = search_aliases.get(normalized_query)
    if lookup_result:
        lookup_alias_type, canonical_key_string = lookup_result
        if search_type == "model":
            if lookup_alias_type == "name":
                models = canonical_name_to_internal_models.get(canonical_key_string)
                if models:
                    return "success", sorted(list(models)), f"Models for '{canonical_key_string}':"
                else:
                    return "not_found", [], f"No internal models found for '{canonical_key_string}'."
            elif lookup_alias_type == "model":
                return "info", [], f"'{query_text}' is an internal model. Use 'Search Name' to find its name(s)."
        elif search_type == "name":
            if lookup_alias_type == "model":
                names = internal_model_to_canonical_names.get(canonical_key_string)
                if names:
                    return "success", sorted(list(names)), f"Names for internal model '{canonical_key_string}':"
                else:
                    return "not_found", [], f"No device names found for internal model '{canonical_key_string}'."
            elif lookup_alias_type == "name":
                return "info", [], f"'{query_text}' is a device name. Use 'Search Model' to find its internal model(s)."
    return "not_found", [], f"No direct match found for '{query_text}'."


# --- הגדרת אפליקציית Flask ונקודות הקצה (Endpoints) ---
# (ללא שינוי מהגרסה הקודמת)

load_data()
app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/lookup', methods=['GET'])
def lookup():
    query = request.args.get('query', '')
    search_type = request.args.get('type', 'model')
    status, items, message = _perform_single_lookup_logic(query, search_type)
    return jsonify({'status': status, 'items': items, 'message': message})


@app.route('/suggestions')
def suggestions():
    return jsonify(sorted(list(all_suggestions)))


@app.route('/batch_lookup', methods=['POST'])
def batch_lookup():
    queries = request.json.get('queries', [])
    if not queries:
        return jsonify({'error': 'No queries provided'}), 400

    results_output = []
    last_batch_models = set()
    last_batch_names = set()

    for query in queries:
        original_query = query.strip()
        if not original_query:
            continue
        status_model, models_found, msg_model = _perform_single_lookup_logic(original_query, "model")
        status_name, names_found, msg_name = _perform_single_lookup_logic(original_query, "name")
        if status_model == "success":
            results_output.append(f"Input: '{original_query}' -> Models: {','.join(models_found)}")
            last_batch_models.update(models_found)
            for model in models_found:
                last_batch_names.update(internal_model_to_canonical_names.get(model, set()))
        elif status_name == "success":
            results_output.append(f"Input: '{original_query}' -> Names: {','.join(names_found)}")
            last_batch_names.update(names_found)
            last_batch_models.add(original_query)
        else:
            results_output.append(f"Input: '{original_query}' -> No direct match found.")

    return jsonify({
        'results_text': "\n".join(results_output),
        'found_models': sorted(list(last_batch_models)),
        'found_names': sorted(list(last_batch_names))
    })


if __name__ == '__main__':
    app.run(debug=True)