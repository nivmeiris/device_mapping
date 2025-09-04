# Device Model Lookup Tool

A simple web-based utility for converting device marketing names (e.g., "iPhone 15 Pro") to their internal model identifiers (e.g., "iPhone16,1"), and vice versa. This application is built with Python and Flask, providing a user-friendly interface for single and batch lookups.

## Features

* **Single Lookup:** Convert a device name to its internal model(s) or an internal model to its marketing name(s).
* **Batch Lookup:** Process a list of device names and/or models separated by newlines.
* **Autocomplete:** The single lookup field provides suggestions for known devices to speed up searches.
* **Copy to Clipboard:** Easily copy all found models or names from a batch search with a single click.

## Project Structure
/device_mapping
|
|-- app.py                  # The Flask web server that runs the application
|-- requirements.txt        # A list of Python libraries required for the project
|
|-- mapping_devices.txt     # The primary data file for Android devices
|-- device_names.txt        # A data file with additional device aliases
|-- mapping_ios_devices.txt # The data file for iOS devices
|
|-- /templates
|   |-- index.html          # The single HTML file for the user interface
|
|-- README.md               # This file

## Prerequisites

* Python 3 (Python 3.8 or higher is recommended)
* pip (Python's package installer)

## Installation and Running

To run this application locally on your machine, follow these steps.

1.  **Clone the repository:**
    ```bash
    git clone [your-repository-url]
    cd device-lookup-tool
    ```

2.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Flask application:**
    ```bash
    python app.py
    ```

4.  **Access the tool in your browser:**
    Once the server is running, you will see output similar to this:
    ```
     * Running on [http://127.0.0.1:5000](http://127.0.0.1:5000)
    ```
    Open this URL (`http://127.0.0.1:5000`) in your web browser to use the application.

## ❗ Important Usage Notes for Our Platform (Wildcards)

When using the output of this tool to create user segments in our internal platform, certain characters in the model names can cause issues. To prevent these issues, we use a question mark (`?`) as a wildcard to replace problematic characters.

### iOS Devices and Segment Creation

* **The Problem:** Our platform uses a comma (`,`) to separate different devices in a segment list. However, official iOS model identifiers also contain a comma (e.g., `iPhone11,2`). This creates a conflict, as the platform would incorrectly interpret `iPhone11,2` as two separate devices: `iPhone11` and `2`.

* **The Solution:** To avoid this, replace the comma within any iOS model identifier with a question mark (`?`) wildcard. The question mark acts as a substitute for any single character.

    * **Example:**
        * `iPhone11,2` should be entered into the platform as `iPhone11?2`.

    * **Example of a segment with two iOS devices:**
        * To target `iPhone11,1` and `iPhone13,2`, the correct string would be: `iPhone11?1,iPhone13?2`

### Android Devices and Special Characters

* **The Problem:** Some Android model identifiers returned by this tool may contain special characters such as hyphens (`-`), parentheses (`()`), or others. Our SDK may not correctly parse these characters.

* **The Solution:** Replace any special character in an Android model identifier with a question mark (`?`) wildcard.

    * **Example 1:**
        * If the tool returns `SM-G998U`, it should be entered into the platform as `SM?G998U`.

    * **Example 2:**
        * If the tool returns `A3(2017)`, it should be entered as `A3?2017?`.
