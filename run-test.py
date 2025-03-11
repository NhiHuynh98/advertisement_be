import os
import tempfile
from fastapi import FastAPI, File, UploadFile, Query
import subprocess
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import json
from collections import defaultdict
import glob
import mysql.connector
from playwright.sync_api import sync_playwright
import time
from pydantic import BaseModel
from typing import List, Any
from pathlib import Path


app = FastAPI()

# Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = None
login_done = False

@app.get("/login")
def login():
    global storage, login_done
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Set to True if you don't need a UI
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.facebook.com/login")

        while not login_done:
            pass  # Wait for the user to confirm login
        
        time.sleep(5)
        storage = context.storage_state()
        print("Login confirmed, proceeding...")
        with open("fb_session.json", "w") as f:
            json.dump(storage, f)
        browser.close()
        login_done = False
      

@app.get("/confirm")
def save_facebook_session():
    global login_done
    login_done = True


def get_database_connection():
    conn = mysql.connector.connect(
            host="localhost",
            user="adUser",
            password="Advertiser@123456",
            database="adDB"
        )
    return conn

class AddLinkRequest(BaseModel):
    links: str
    location: object

@app.post("/add-links")
async def add_links(data: AddLinkRequest):
    try:
        values_dict = data.model_dump()
        links = values_dict.get("links")
        location = values_dict.get("location")
        location_short = location.get("value")
        location_long = location.get("label")

        conn = get_database_connection()

        with conn.cursor() as cursor:
            # Fetch all matching records (prevents "Unread result found")
            cursor.execute("SELECT links FROM locationGroup WHERE location_short = %s;", (location_short,))
            rows = cursor.fetchall()  # ✅ Use fetchall() to consume all results

            # Extract the first row if exists
            existing_link = json.loads(rows[0][0]) if rows else []  # ✅ Safe extraction
            print("existing_link", existing_link)

            # Process new links
            new_links = links.split("\n")
            print("sss", new_links)

            updatedLink = list(set(existing_link + new_links)) if existing_link else new_links

            if rows:
                cursor.execute(
                    "UPDATE locationGroup SET links = %s WHERE location_short = %s", 
                    (json.dumps(updatedLink), location_short)
                )
            else:
                cursor.execute(
                    "INSERT INTO locationGroup (location_short, location_long, links) VALUES (%s, %s, %s)", 
                    (location_short, location_long, json.dumps(new_links))
                )

            conn.commit() 

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
    finally:
        cursor.close()
        conn.close()

@app.get("/get-location")
async def get_location():
    try:
        conn = get_database_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT location_short, location_long FROM locationGroup;")
            rows = cursor.fetchall()

            unique_locations = list({(row[0], row[1]) for row in rows})

            locations = [{"value": short, "label": long} for short, long in unique_locations]

            return {"result": locations}

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
    finally:
        cursor.close()
        conn.close()

@app.get("/get-group-url")
def get_group_url_with_location(location: str = "hcm"):
    try:
        conn = get_database_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT links FROM locationGroup WHERE location = %s", (location,))

            rows = cursor.fetchall()
            merged_links = []
            for row in rows:
                links_list = json.loads(row[0])
                merged_links.extend(links_list)

            conn.commit()

            return { "result": list(set(merged_links)) } 
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")

    finally:
        cursor.close()
        conn.close()
    

async def merge_json_files(*filenames):
    merged_data = []

    for file in filenames:
        with open(file, "r") as f:
            data = json.load(f)
            if isinstance(data, list):  
                merged_data.extend(data)  # Merge lists
            else:
                print(f"Skipping {file}: Not a list")

    return merged_data

# async def merge_json_files(*filenames):
#     merged_data = []

#     for file in filenames:
#         try:
#             async with open(file, 'r') as f:
#                 data = json.load(f)
                
#                 if isinstance(data, list):  
#                     merged_data.extend(data)  # ✅ Use `extend` to flatten lists

#         except Exception as e:
#             print(f"Error reading {file}: {e}")  # Handle file errors

#     return merged_data  # ✅ Return the merged list instead of just the first element


def delete_json_files():
    directory = "."

    # Get all files that start with "crawled_data_"
    files_to_delete = glob.glob(os.path.join(directory, "crawled_data_*"))

    # Delete each file
    for file in files_to_delete:
        try:
            os.remove(file)
            print(f"Deleted: {file}")
        except Exception as e:
            print(f"Error deleting {file}: {e}")

@app.get("/run-tests")
async def run_tests(page: str = "1"):
    try:
        # Set environment variable for Playwright
        env = os.environ.copy()
        env["PAGE_NUMBER"] = str(page)  # Ensure page is a string
        
        # Run Playwright tests
        result = subprocess.run(
            ["npx", "playwright", "test"], env=env,
            capture_output=True, text=True
        )
        
        # Merge JSON data from multiple files
        json_files = glob.glob("crawled_data_*.json")
        json_data = await merge_json_files(*json_files)  # Ensure this function is async
        print("json_data", json_data)

        # Establish async DB connection
        conn = get_database_connection()
        with conn.cursor() as cursor:
            # Clear existing data
            cursor.execute("DELETE FROM real_estate;")

            # Insert new data
            query = """
            INSERT INTO real_estate (title, details, price, area_price, total_area, location_time, link, user)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = [
                (
                    item["title"],
                    item["details"],
                    item["price"],
                    item["area_price"],
                    item["total_area"],
                    item["location_time"],
                    item["link"],
                    item["user"],
                )
                for item in json_data
            ]
            cursor.executemany(query, values)
            conn.commit()
            print("JSON data inserted successfully!")

            # Delete JSON files
            # delete_json_files()

            # Fetch data from the database
            cursor.execute("SELECT * FROM real_estate;")
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            # Convert tuples to dictionaries
            data = [dict(zip(columns, row)) for row in rows]

        return {"output": data}

    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()

@app.get("/change-status")
async def change_status(status: str = "none", index: int = 0):
    print(f"Updating status: {status}, for index: {index}")

    try:
        # Get database connection
        conn = get_database_connection()
        
        with conn.cursor() as cursor:
            query = "UPDATE real_estate SET status = %s WHERE id = %s"
            cursor.execute(query, (status, index))
            conn.commit()

            print(f"Updated property {index} status to {status}.")

            # Fetch updated records
            cursor.execute("SELECT * FROM real_estate;")
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            # Convert tuples to dictionaries
            data = [dict(zip(columns, row)) for row in rows]

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        data = None  # Return None if an error occurs

    finally:
        cursor.close()
        conn.close()

    return data

UPLOAD_DIR = Path("images")
os.makedirs(UPLOAD_DIR, exist_ok=True) 

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    print("sdsdsd", file)
    file_location = UPLOAD_DIR/file.filename 

    with open(file_location, "wb") as f:
        f.write(await file.read())

    return {"filename": file.filename, "path": str(file_location)}


FB_EMAIL = "0853771565"
FB_PASSWORD = "Tuyetnhi98@"

# List of Facebook group URLs where you want to post
GROUP_URLS = [
    "https://www.facebook.com/groups/821840388272394",
    "https://www.facebook.com/duyanh01011996",
    "https://www.facebook.com/thanhthanh.thanhthanh.798278",
    # "https://www.facebook.com/profile.php?id=100011907707044",
]

# The message you want to post
POST_MESSAGE = "🚀 Đây là tin nhắn tự động, Nhi code test"
IMAGE_PATH = [
    "./images/test.jpeg",
    "./images/test_2.jpeg",
    "./images/test_3.jpeg"
]

class PostRequest(BaseModel):
    page: str
    messages: str
    page_url: str
    page: str
    filePayload: List[Any]

def process_input(input_string):
    values_list = [line.strip() for line in input_string.split("\n") if line.strip()]
    return values_list

def paginate(items, limit):
    start_index = 0
    end_index = start_index + limit
    return items[start_index:end_index]

@app.post("/post-news")
def auto_post_facebook(data: PostRequest):
    values_dict = data.dict()
    POST_MESSAGE = values_dict.get("messages", "Default Text")
    IMAGE_PAYLOAD = values_dict.get("filePayload", None)
    page_url = values_dict.get("page_url", None)
    page = values_dict.get("page", None)

    GROUP_URLS = paginate(process_input(page_url), 2)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Keep False for debugging
        context = browser.new_context(storage_state="fb_session.json")  # Load session
        page = context.new_page()

        page.goto("https://www.facebook.com/", timeout=10000)
        print("✅ Logged in using saved session!")

        for group_url in GROUP_URLS:
            print(f"Posting to: {group_url}")
            page.goto(group_url, timeout=120000)
            # page.wait_for_load_state("networkidle")
            page.wait_for_load_state("domcontentloaded", timeout=60000)  # Faster page detection


            try:
                post_container = page.locator("//div[@role='button']//span[starts-with(text(), 'Write something to') or text() = 'Bạn viết gì đi...']")

                post_container.wait_for(timeout=5000)
                post_container.click()
                time.sleep(10)

                button_upload = page.locator('div[role="button"][aria-label*="Ảnh/video"]')
                button_upload.click()
                time.sleep(5)

                if not isinstance(IMAGE_PAYLOAD, list):
                    IMAGE_PAYLOAD = [IMAGE_PAYLOAD]  # Ensure it's a list

                uploaded_file_paths = []

                for file_data in IMAGE_PAYLOAD:
                    if isinstance(file_data, dict):
                        file_name = file_data.get("name", "uploaded_file")
                        file_buffer = file_data.get("buffer", [])

                        # Validate buffer
                        if not isinstance(file_buffer, list):
                            raise ValueError(f"Invalid buffer format: Expected list, got {type(file_buffer)}")

                        try:
                            file_bytes = bytes(file_buffer)
                        except Exception as e:
                            raise ValueError("Error converting buffer to bytes") from e

                        # Save file to 'images/' folder
                        file_path = os.path.join(UPLOAD_DIR, file_name)
                        with open(file_path, "wb") as f:
                            f.write(file_bytes)

                        uploaded_file_paths.append(file_path)
                        print(f"File saved at: {file_path}")

                # Upload files in Playwright
                if uploaded_file_paths:
                    file_input = page.locator('input[type="file"][accept*="image"][multiple]')
                    file_input.set_input_files(uploaded_file_paths)
                    print("Files set for upload:", uploaded_file_paths)
                else:
                    print("No valid files to upload")
                
                time.sleep(5)

                input_box = page.locator('div[role="textbox"][aria-label*="Write"], div[role="textbox"][aria-label*="Tạo bài"], div[role="textbox"][aria-label*="viết"]')
                input_box.fill(POST_MESSAGE)
                page.wait_for_timeout(2000)

                post_button = page.locator('div[role="button"][aria-label="Đăng"]')
                post_button.click()

                print(f"✅ Successfully posted in: {group_url}")
                
                page.wait_for_timeout(10000)  # Wait before next post
            except Exception as e:
                print(f"⚠️ Skipping {group_url} due to error: {e}")
                continue  

        browser.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)


# CREATE DATABASE adDB;
# CREATE USER 'adUser'@'localhost' IDENTIFIED BY '123456';
# GRANT ALL PRIVILEGES ON mydatabase.* TO 'adUser'@'localhost';
# FLUSH PRIVILEGES;
# EXIT;


# CREATE TABLE json_table (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     data JSON,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# INSERT INTO json_table (data) 
# VALUES ('{"name": "John Doe", "email": "john@example.com", "age": 30}');

# sudo mysql -u root -p

# CREATE TABLE locationGroup (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     location VARCHAR(255),
#     links JSON
# );

# INSERT INTO locationGroup (location, links) 
# VALUES ('hcm', '["https://www.facebook.com/groups/821840388272394", "https://www.facebook.com/duyanh01011996"]');

# INSERT INTO locationGroup (location, links) 
# VALUES ('hn', '["https://www.facebook.com/duyanh01011996"]');

# INSERT INTO locationGroup (location, links) 
# VALUES ('New York', '["https://group1.com", "https://group2.com", "https://group3.com"]');

# UPDATE locationGroup 
# SET location_short = location, 
#     location_long = 
#         CASE 
#             WHEN location = 'hcm' THEN 'Ho Chi Minh'
#             WHEN location = 'hn' THEN 'Ha Noi'
#             WHEN location = 'dn' THEN 'Da Nang'
#             ELSE location
#         END;
