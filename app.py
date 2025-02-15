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
def a2_format_markdown():
    file_path = get_abs_path("format.md")
    command = f'npx prettier@3.4.2 --write "{file_path}"'
    return run_shell_command(command)

# Task A3: Count Wednesdays in a list of dates
def a3_dates():
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
def a4_contacts():
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
def a5_logs():
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
def a6_docs():
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
def a7_email():
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
def a10_ticket_sales():
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

#---------------------           ------PHASE B---------------------------------------------------

# Task B1: Ensure file access is restricted to /data directory.
def secure_path(file_path):
    """Ensure file access is restricted to /data directory."""
    abs_path = os.path.abspath(file_path)
    if not abs_path.startswith(os.path.abspath(DATA_DIR)):
        raise PermissionError("Access to files outside /data is not allowed.")
    return abs_path


# Task B2: Prevent file deletion in the system.
def safe_remove(file_path):
    """Prevent file deletion in the system."""
    raise PermissionError("File deletion is not allowed by system policy.")

# Task B3: Fetch data from an API and save it as json file
def fetch_and_save_api_data():
    """ Fetches data from an API and saves it to a file. """
    api_url = "https://api.publicapis.org/entries"  # Example API
    output_file = get_abs_path("api_response.json")

    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an error for bad responses
        data = response.json()

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        return jsonify({"message": "API data fetched and saved successfully."}), 200
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400


# Task B4: Clone a Git repo and make a commit
def clone_and_commit_repo():
    """ Clones a Git repository and makes a commit. """
    repo_url = "https://github.com/example/repository.git"  # Replace with the actual repo URL
    repo_dir = get_abs_path("repository")  # Clone into /data/repository
    commit_message = "Automated commit from script"

    try:
        # Clone the repository if it doesn't exist
        if not os.path.exists(repo_dir):
            subprocess.run(["git", "clone", repo_url, repo_dir], check=True)

        # Change directory to the cloned repo
        os.chdir(repo_dir)

        # Create a dummy file to modify (if required)
        file_path = os.path.join(repo_dir, "new_file.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("This is a test commit.\n")

        # Add, commit, and push changes
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push"], check=True)

        return jsonify({"message": "Repository cloned and committed successfully."}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400


# Task B5: Run a SQL query on a SQLite database
def run_sql_query():
    """ Runs a SQL query on a SQLite database and saves the result to a file. """
    db_path = get_abs_path("database.db")  # Replace with actual database filename
    output_file = get_abs_path("query_results.txt")
    sql_query = "SELECT * FROM users;"  # Replace with your actual query

    try:
        # Check if the database file exists
        if not os.path.exists(db_path):
            return jsonify({"error": "Database file not found."}), 404

        # Connect to the SQLite database and execute the query
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        results = cursor.fetchall()
        conn.close()

        # Save results to a file
        with open(output_file, "w", encoding="utf-8") as f:
            for row in results:
                f.write(", ".join(map(str, row)) + "\n")

        return jsonify({"message": "SQL query executed successfully.", "results": results}), 200
    except sqlite3.Error as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400


# Task B6: Scraping data from a website
def scrape_website():
    """ Scrapes titles (h1 tags) from a website and saves them to a file. """
    url = "https://example.com"  # Replace with the actual website URL
    output_file = get_abs_path("scraped_titles.txt")

    try:
        # Fetch website content
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses

        # Parse HTML content
        soup = BeautifulSoup(response.text, "html.parser")
        titles = [h1.text.strip() for h1 in soup.find_all("h1")]  

        # Save extracted titles to a file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(titles))

        return jsonify({"message": "Website scraped successfully.", "titles": titles}), 200
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400

# Task B7: Compress or Resize an Image
def compress_or_resize_image():
    """ Compresses or resizes an image and saves it as a new file. """
    input_image = get_abs_path("input.jpg")  # Replace with actual input image filename
    output_image = get_abs_path("compressed.jpg")  # Output file
    max_size = (800, 800)  # Resize dimensions (modify as needed)
    quality = 75  # Compression quality (1-100, lower means more compression)

    try:
        # Check if the image file exists
        if not os.path.exists(input_image):
            return jsonify({"error": "Image file not found."}), 404

        # Open the image
        img = Image.open(input_image)

        # Resize the image while maintaining aspect ratio
        img.thumbnail(max_size)

        # Save the compressed/resized image
        img.save(output_image, "JPEG", quality=quality)

        return jsonify({"message": "Image compressed and resized successfully."}), 200
    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400

# Task B9: Convert Markdown to HTML
def convert_markdown_to_html():
    """ Converts Markdown content to HTML. """
    input_file = get_abs_path("sample.md")  # Path to the Markdown file
    output_file = get_abs_path("output.html")  # Output HTML file

    try:
        # Read the Markdown file
        with open(input_file, "r", encoding="utf-8") as f:
            md_content = f.read()

        # Convert Markdown to HTML
        html_content = markdown.markdown(md_content)

        # Save the HTML output
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return jsonify({"message": "Markdown converted to HTML successfully."}), 200
    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400

# Task B10: Filter a CSV file and return JSON data
@app.route("/filter_csv", methods=["GET"])
def filter_csv():
    """ Filters a CSV file based on query parameters and returns JSON data. """
    csv_file = get_abs_path("data.csv")  # Replace with your CSV file path

    try:
        # Load the CSV into a DataFrame
        df = pd.read_csv(csv_file)

        # Get filter parameters from request
        column = request.args.get("column")  # Column name
        value = request.args.get("value")  # Value to filter

        # Validate parameters
        if not column or not value:
            return jsonify({"error": "Missing required parameters: column and value."}), 400
        
        # Apply filter
        if column not in df.columns:
            return jsonify({"error": f"Column '{column}' not found in CSV."}), 400

        filtered_df = df[df[column].astype(str) == value]  # Convert to string for comparison

        # Convert to JSON and return
        return jsonify(filtered_df.to_dict(orient="records")), 200

    except Exception as e:
        return jsonify({"error": "Task execution failed.", "details": str(e)}), 400

# Dictionary to map task descriptions to functions
TASKS = {
    "format_with_prettier": a2_format_markdown,
    "count_wednesdays": a3_dates,
    "sort_contacts": a4_contacts,
    "extract_recent_logs": a5_logs,
    "extract_markdown_headers": a6_docs,
    "extract_email_sender": a7_email,
    "calculate_gold_ticket_sales": a10_ticket_sales,

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
