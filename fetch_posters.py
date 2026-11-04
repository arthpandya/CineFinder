import os
import time
import pandas as pd
import requests
from pathlib import Path
from dotenv import load_dotenv

# Project paths
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "api" / ".env")

API_KEY = os.getenv("TMDB_API_KEY")
ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

if not API_KEY and not ACCESS_TOKEN:
    raise ValueError("TMDB credentials not found in api/.env")

# Load movie data
movies = pd.read_csv(BASE_DIR / "processed" / "movies_processed.csv")
links = pd.read_csv(BASE_DIR / "dataset" / "links.csv")

# Match MovieLens IDs with TMDB IDs
movies = movies.merge(
    links[["movieId", "tmdbId"]],
    on="movieId",
    how="left"
)

headers = {}
if ACCESS_TOKEN:
    headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

results = []

for index, movie in movies.iterrows():
    tmdb_id = movie["tmdbId"]

    if pd.isna(tmdb_id):
        results.append({
            "movieId": movie["movieId"],
            "poster_path": None
        })
        continue

    url = f"https://api.themoviedb.org/3/movie/{int(tmdb_id)}"

    try:
        response = requests.get(
            url,
            headers=headers,
            params={"api_key": API_KEY} if API_KEY else {},
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            poster_path = data.get("poster_path")
        elif response.status_code == 404:
            poster_path = None
        else:
            print("TMDB error:", response.status_code, "Movie:", movie["title"])
            poster_path = None

        results.append({
            "movieId": movie["movieId"],
            "poster_path": poster_path
        })

    except requests.RequestException as error:
        print("Request failed:", movie["title"], error)
        results.append({
            "movieId": movie["movieId"],
            "poster_path": None
        })

    if (index + 1) % 100 == 0:
        print(f"Processed {index + 1}/{len(movies)} movies")

    time.sleep(0.05)

# Save poster information
poster_data = pd.DataFrame(results)

output_path = BASE_DIR / "processed" / "tmdb_posters.csv"
poster_data.to_csv(output_path, index=False)

print("\nPoster fetching completed!")
print("Movies processed:", len(poster_data))
print("Posters found:", poster_data["poster_path"].notna().sum())
print("Saved to:", output_path)