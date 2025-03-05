import os
from fastapi import FastAPI, Query
import subprocess
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import json
from collections import defaultdict
import glob
import mysql.connector


app = FastAPI()

# Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_database_connection():
    conn = mysql.connector.connect(
            host="localhost",
            user="adUser",
            password="Advertiser@123456",
            database="adDB"
        )
    return conn

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

# async def change_status(status: str = "none", index: int = 0):
#     print(f"Updating status: {status}, for index: {index}")

#     try:
#         conn, cursor = get_database_connection()

#         query = "UPDATE real_estate SET status = %s WHERE id = %s"
#         cursor.execute(query, (status, index))

#         conn.commit()

#         print(f"Updated property {index} status to {status}.")

#         cursor.execute("SELECT * FROM real_estate;")
#         columns = [col[0] for col in cursor.description]
#         rows = cursor.fetchall()

#         # Convert tuples to dictionaries
#         data = [dict(zip(columns, row)) for row in rows]


#     except mysql.connector.Error as err:
#         print(f"Error: {err}")
#         data = None  # Return None if an error occurs

    # finally:
    #     cursor.close()
    #     conn.close()

#     return data 

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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)


# CREATE DATABASE adDB;
# CREATE USER 'adUser'@'localhost' IDENTIFIED BY '123456';
# GRANT ALL PRIVILEGES ON mydatabase.* TO 'adUser'@'localhost';
# FLUSH PRIVILEGES;
# EXIT;
