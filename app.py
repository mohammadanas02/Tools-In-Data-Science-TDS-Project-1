from flask import Flask, request, jsonify
import subprocess
import json
import pandas as pd
import os
from PIL import Image
import openai
import requests
from datetime import datetime
from dateutil import parser
from bs4 import BeautifulSoup
import markdown
import pytesseract
from PIL import Image
import sqlite3

app = Flask(__name__)

# Base data directory
DATA_DIR = os.path.abspath("data")  # Ensures correct absolute path


def get_abs_path(filename):
    """Ensure that the path is correctly resolved without duplication"""
    return os.path.abspath(os.path.join(DATA_DIR, os.path.basename(filename)))


def read_file(file_path):
    """Generic function to read a file"""
    abs_path = get_abs_path(file_path)

    if not os.path.exists(abs_path):
        return jsonify({"error": "File not found.", "path": abs_path}), 404

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content}), 200
    except Exception as e:
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

# Function to execute shell commands
def run_shell_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return jsonify({"message": "Task executed successfully."}), 200
    else:
        return jsonify({"error": "Task execution failed.", "details": result.stderr}), 400

# Task A2: Format file using Prettier
def format_with_prettier():
    file_path = get_abs_path("format.md")
    command = f'npx prettier@3.4.2 --write "{file_path}"'
    return run_shell_command(command)

# Task A3: Count Wednesdays in a list of dates
def count_wednesdays():
    input_file = get_abs_path("dates.txt")
    output_file = get_abs_path("dates-wednesdays.txt")

    if not os.path.exists(input_file):
        return jsonify({"error": "File not found."}), 404

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            dates = f.readlines()

        wednesday_count = 0
        for date_str in dates:
            date_str = date_str.strip()
            try:
                # Automatically detect the correct format
                parsed_date = parser.parse(date_str)  # This handles multiple formats
                if parsed_date.weekday() == 2:  # 2 = Wednesday
                    wednesday_count += 1
            except ValueError:
                continue  # Skip invalid dates instead of failing

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(str(wednesday_count))

        return jsonify({"message": "Task executed successfully.", "wednesday_count": wednesday_count}), 200
    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400

# Task A4: Sort Contacts.
def sort_contacts():
    input_file = get_abs_path("contacts.json")
    output_file = get_abs_path("contacts-sorted.json")

    if not os.path.exists(input_file):
        return jsonify({"error": "File not found."}), 404

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            contacts = json.load(f)  # Load JSON data

        if not isinstance(contacts, list):
            return jsonify({"error": "Invalid JSON format. Expected a list."}), 400

        # Sorting by last_name first, then by first_name
        contacts.sort(key=lambda x: (x.get("last_name", ""), x.get("first_name", "")))

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=4)  # Write sorted JSON with indentation

        return jsonify({"message": "Contacts sorted successfully."}), 200
    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400

# Task A5: Extract first line of 10 most recent log files
def extract_recent_logs():
    logs_dir = get_abs_path("logs")  # Directory containing log files
    output_file = get_abs_path("logs-recent.txt")

    if not os.path.exists(logs_dir) or not os.path.isdir(logs_dir):
        return jsonify({"error": "Log directory not found."}), 404

    try:
        # Get a list of all .log files sorted by modification time (newest first)
        log_files = sorted(
            [f for f in os.listdir(logs_dir) if f.endswith(".log")],
            key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)),
            reverse=True
        )[:10]  # Take the 10 most recent log files

        extracted_lines = []
        for log_file in log_files:
            log_path = os.path.join(logs_dir, log_file)
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    extracted_lines.append(f"{log_file}: {first_line}")
            except Exception as e:
                extracted_lines.append(f"{log_file}: Error reading file ({str(e)})")

        # Write extracted lines to the output file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(extracted_lines))

        return jsonify({"message": "Recent log lines extracted successfully.", "log_count": len(extracted_lines)}), 200
    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400
    

# Task A6: Extract H1 headers from Markdown files (Recursive Search)
def extract_markdown_headers():
    docs_dir = get_abs_path("docs")  # Base docs directory
    output_file = get_abs_path("docs/index.json")

    if not os.path.exists(docs_dir):
        return jsonify({"error": "Docs directory not found."}), 404

    index = {}

    try:
        # Recursively walk through all subdirectories
        for root, _, files in os.walk(docs_dir):
            for file in files:
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, docs_dir)  # Keep relative path

                    # Read the file and extract the first H1 header
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("# "):  # First H1 found
                                index[relative_path] = line[2:].strip()
                                break

        # Save extracted headers to index.json
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=4)

        # Return only the success message
        return jsonify({"message": "Task executed successfully."}), 200
    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400


# Task A7: Extract senders email.
def extract_email_sender():
    """Extracts sender's email from email.txt and writes it to email-sender.txt"""
    input_file = get_abs_path("email.txt")
    output_file = get_abs_path("email-sender.txt")

    if not os.path.exists(input_file):
        return jsonify({"error": "File not found."}), 404

    try:
        # Read email content
        with open(input_file, "r", encoding="utf-8") as f:
            email_content = f.read()

        # Ensure AI Proxy token is available
        ai_proxy_token = os.environ.get("AIPROXY_TOKEN")
        if not ai_proxy_token:
            return jsonify({"error": "AI Proxy token is missing."}), 400

        # Call AI Proxy API
        API_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {ai_proxy_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Extract the sender's email address from the given email."},
                {"role": "user", "content": email_content}
            ],
            "max_tokens": 50
        }

        response = requests.post(API_URL, json=payload, headers=headers)
        response_data = response.json()

        # Extract sender email
        sender_email = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if not sender_email:
            sender_email = "Extraction failed."

        # Save extracted email to output file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(sender_email)

        return jsonify({"message": "Task executed successfully."}), 200

    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400

# # Task A8: Extracting Credit card number from Image.
# def extract_credit_card_number():
#     image_path = get_abs_path("credit_card.png")
#     output_file = get_abs_path("credit-card.txt")
    
#     if not os.path.exists(image_path):
#         return jsonify({"error": "Image file not found."}), 404
    
#     try:
#         image = Image.open(image_path)
#         extracted_text = pytesseract.image_to_string(image, config='--psm 6')
        
#         # Call AI Proxy API to clean extracted text
#         ai_proxy_token = os.environ.get("AIPROXY_TOKEN")
#         if not ai_proxy_token:
#             return jsonify({"error": "AI Proxy token is missing."}), 400
        
#         API_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
#         headers = {
#             "Authorization": f"Bearer {ai_proxy_token}",
#             "Content-Type": "application/json"
#         }
        
#         payload = {
#             "model": "gpt-4o-mini",
#             "messages": [
#                 {"role": "system", "content": "Extract and format the credit card number from the given text."},
#                 {"role": "user", "content": extracted_text}
#             ],
#             "max_tokens": 50
#         }
        
#         response = requests.post(API_URL, json=payload, headers=headers)
#         response_data = response.json()
        
#         card_number = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        
#         if not card_number:
#             return jsonify({"error": "Failed to extract card number."}), 400
        
#         # Remove spaces and save to file
#         formatted_number = card_number.replace(" ", "")
#         with open(output_file, "w", encoding="utf-8") as f:
#             f.write(formatted_number)
        
#         return jsonify({"message": "Credit card number extracted successfully."}), 200
    
#     except Exception as e:
#         return jsonify({"error": "Task execution failed.", "details": str(e)}), 400


# Task A10: Calculate total sales for "Gold" tickets
def calculate_gold_ticket_sales():
    db_path = get_abs_path("ticket-sales.db")
    output_file = get_abs_path("ticket-sales-gold.txt")

    if not os.path.exists(db_path):
        return jsonify({"error": "Database file not found."}), 404

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(units * price) FROM tickets WHERE type = 'Gold'")
        total_sales = cursor.fetchone()[0] or 0
        conn.close()

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(str(total_sales))

        return jsonify({"message": "Gold ticket sales calculated successfully.", "total_sales": total_sales}), 200
    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400




# Dictionary to map task descriptions to functions
TASKS = {
    "format_with_prettier": format_with_prettier,
    "count_wednesdays": count_wednesdays,
    "sort_contacts": sort_contacts,
    "extract_recent_logs": extract_recent_logs,
    "extract_markdown_headers": extract_markdown_headers,
    "extract_email_sender": extract_email_sender,
    "calculate_gold_ticket_sales": calculate_gold_ticket_sales,

}

# API endpoint to execute tasks
@app.route('/run', methods=['GET', 'POST'])
def run_task():
    task_name = request.args.get('task')
    if not task_name:
        return jsonify({"error": "Missing task description."}), 400

    task_function = TASKS.get(task_name.lower().replace(" ", "_"))  # Normalize task name
    if task_function:
        return task_function()
    else:
        return jsonify({"error": "Invalid task description."}), 400

# API endpoint to read file contents
@app.route('/read', methods=['GET'])
def read_file_endpoint():
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({"error": "Missing file path."}), 400
    return read_file(file_path)

# Run Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
