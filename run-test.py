import os
from fastapi import FastAPI, Query
import subprocess
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import json
from collections import defaultdict
import glob

app = FastAPI()

# Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def merge_json_files(*filenames):
    merged_data = {}

    for file in filenames:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):  
            # If top-level data is a list, merge it under a common key
            merged_data.setdefault("data", []).extend(data)
        elif isinstance(data, dict):
            for key, value in data.items():
                if key in merged_data:
                    if isinstance(merged_data[key], list) and isinstance(value, list):
                        merged_data[key].extend(value)  # Merge lists
                    elif isinstance(merged_data[key], dict) and isinstance(value, dict):
                        merged_data[key].update(value)  # Merge dictionaries
                    else:
                        merged_data[key] = value  # Override scalar values
                else:
                    merged_data[key] = value  # Add new key-value pair

    return merged_data
@app.get("/run-tests")
async def run_tests(page: str = 1):
    try:
        # Run Playwright tests and capture the output
         # Set environment variable for Playwright
        env = os.environ.copy()
        env["PAGE_NUMBER"] = page if page else 1
        
        result = subprocess.run(
            ["npx", "playwright", "test"], env=env,
            capture_output=True, text=True
        )
        json_files = glob.glob("*.json")
        result_1 = merge_json_files(*json_files)

        output_file = "merged_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_1, f, indent=2)

        return {"output": result.stdout}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
