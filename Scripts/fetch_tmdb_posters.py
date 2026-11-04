import os
import time
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Project folder
ROOT_DIR = Path(__file__).resolve().parent.parent

# Load TMDB credentials from .env
load_dotenv(ROOT_DIR / ".env")
ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

if not ACCESS_TOKEN:
    raise ValueError(
        "TMDB_ACCESS_TOKEN not found. Check your E:\\CineFinder\\.env file."
    )

# File paths
MOVIES_FILE = ROOT_DIR / "dataset" / "movies.csv"
OUTPUT_FILE = ROOT_DIR / "data" / "tmdb_posters.csv"

if not MOVIES_FILE.exists():
    raise FileNotFoundError(
        f"Movie dataset not found at: {MOVIES_FILE}"
    )

# TMDB API setup
BASE_URL = "https://api.themoviedb.org/3"

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "accept": "application/json"
})

# Load MovieLens dataset
movies = pd.read_csv(MOVIES_FILE)

if "movieId" not in movies.columns or "title" not in movies.columns:
    raise ValueError("movies.csv must contain movieId and title columns.")

# Resume from existing output if available
if OUTPUT_FILE.exists():
    previous = pd.read_csv(OUTPUT_FILE)
    results = previous.to_dict("records")
else:
    results = []

processed_ids = {
    int(row["movieId"])
    for row in results
    if pd.notna(row.get("movieId"))
}

print(f"Total movies: {len(movies)}")
print(f"Already processed: {len(processed_ids)}")
print("Starting TMDB poster search...\n")

for index, movie in movies.iterrows():

    movie_id = int(movie["movieId"])

    if movie_id in processed_ids:
        continue

    title = str(movie["title"]).strip()

    # Extract release year from title, if available
    year = None

    if "(" in title and ")" in title:
        possible_year = title.rsplit("(", 1)[-1].split(")", 1)[0]

        if possible_year.isdigit() and len(possible_year) == 4:
            year = possible_year

    clean_title = title.rsplit(" (", 1)[0].strip()

    params = {"query": clean_title}

    if year:
        params["year"] = year

    try:
        response = session.get(
            f"{BASE_URL}/search/movie",
            params=params,
            timeout=20
        )
        response.raise_for_status()

        matches = response.json().get("results", [])

        # Prefer exact title matches where possible
        match = None

        for candidate in matches:
            if candidate.get("title", "").lower() == clean_title.lower():
                match = candidate
                break

        if match is None and matches:
            match = matches[0]

        results.append({
            "movieId": movie_id,
            "title": title,
            "tmdb_id": match.get("id") if match else None,
            "poster_path": match.get("poster_path") if match else None
        })

        processed_ids.add(movie_id)

    except requests.RequestException as error:
        print(f"Error for {title}: {error}")
        time.sleep(2)
        continue

    # Save progress every 50 successful searches
    if len(results) % 50 == 0:
        pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
        print(f"Processed {len(results)}/{len(movies)} movies")

    # Avoid sending requests too quickly
    time.sleep(0.25)

# Save final results
pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)

matched = sum(
    1 for row in results
    if pd.notna(row.get("poster_path"))
)

print("\nPoster search completed!")
print(f"Total processed: {len(results)}")
print(f"Movies with posters: {matched}")
print(f"Movies without posters: {len(results) - matched}")
print(f"Output file: {OUTPUT_FILE}")