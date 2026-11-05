"""

CineFinder FastAPI backend.


Run from the CineFinder project root:

    uvicorn api.main:app --reload


Expected files:

    processed/movies_processed.csv

    models/item_based_model.joblib

    models/user_based_model.joblib

    models/als_model.joblib

"""


from contextlib import asynccontextmanager

from pathlib import Path

from typing import Optional

import re
import json
import os
import urllib.request
import urllib.error


import joblib

import numpy as np

import pandas as pd

from fastapi import FastAPI, HTTPException, Query

from pydantic import BaseModel, Field

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse


from api.auth import router as auth_router, init_auth_db

from api.friends import router as friends_router


ROOT_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DIR = ROOT_DIR / "processed"

MODELS_DIR = ROOT_DIR / "models"

RESULTS_DIR = ROOT_DIR / "results"

MOVIES_FILE = PROCESSED_DIR / "movies_processed.csv"

ITEM_MODEL_FILE = MODELS_DIR / "item_based_model.joblib"

USER_MODEL_FILE = MODELS_DIR / "user_based_model.joblib"

ALS_MODEL_FILE = MODELS_DIR / "als_model.joblib"


LINKS_FILE = (
    ROOT_DIR / "links.csv"
    if (ROOT_DIR / "links.csv").exists()
    else PROCESSED_DIR / "links.csv"
)
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
POSTER_CACHE = {}


def load_resources():

    """Load movie metadata and trained recommendation models once at startup."""

    if not MOVIES_FILE.exists():

        raise RuntimeError(f"Movie metadata file not found: {MOVIES_FILE}")


    movies = pd.read_csv(MOVIES_FILE)

    movies["movieId"] = movies["movieId"].astype(int)

    # Load the MovieLens movieId -> TMDB movie ID mapping.
    if LINKS_FILE.exists():
        links = pd.read_csv(LINKS_FILE)
        links["movieId"] = links["movieId"].astype(int)
        links = links.dropna(subset=["tmdbId"]).copy()
        links["tmdbId"] = links["tmdbId"].astype(int)
        tmdb_mapping = dict(zip(links["movieId"], links["tmdbId"]))
    else:
        print(f"WARNING: links.csv not found: {LINKS_FILE}")
        tmdb_mapping = {}


    train_file = PROCESSED_DIR / "train.csv"

    if not train_file.exists():

        raise RuntimeError(f"Training ratings file not found: {train_file}")

    train = pd.read_csv(train_file)


    resources = {
        "movies": movies,
        "train": train,
        "item": None,
        "user": None,
        "als": None,
        "tmdb_mapping": tmdb_mapping,
    }


    for key, model_path in (

        ("item", ITEM_MODEL_FILE),

        ("user", USER_MODEL_FILE),

        ("als", ALS_MODEL_FILE),

    ):

        if model_path.exists():

            resources[key] = joblib.load(model_path)

        else:

            print(f"WARNING: Model not found, {key} recommendations unavailable: {model_path}")


    return resources


@asynccontextmanager

async def lifespan(app: FastAPI):

    app.state.resources = load_resources()

    print("CineFinder API resources loaded.")

    yield

    app.state.resources = None


class UserRating(BaseModel):

    movieId: int

    rating: float = Field(ge=0.5, le=5.0)


class CustomRecommendationRequest(BaseModel):

    ratings: list[UserRating]

    algorithm: str = "item"


app = FastAPI(

    title="CineFinder API",

    description="Movie discovery and collaborative-filtering recommendations.",

    version="1.0.0",

    lifespan=lifespan,

)


init_auth_db()

app.include_router(auth_router)

app.include_router(friends_router)


# For local Next.js development. Update/add your deployed Vercel domain later.

app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        "http://localhost:3000",

        "http://127.0.0.1:3000",

        "https://cine-finder-xi.vercel.app",

    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)


def get_resources():

    resources = getattr(app.state, "resources", None)

    if resources is None:

        raise HTTPException(status_code=503, detail="Recommendation resources are not loaded.")

    return resources


def get_model(resources, model_name: str):

    model = resources.get(model_name)

    if model is None:

        raise HTTPException(

            status_code=503,

            detail=f"The {model_name} model is unavailable. Check the models folder.",

        )

    return model


def movie_to_dict(row):

    """Convert a movie row to JSON-safe values."""

    movie = row.to_dict()

    movie["movieId"] = int(movie["movieId"])

    for key, value in list(movie.items()):

        if pd.isna(value):

            movie[key] = None

    title = str(movie.get("title") or "")

    year_match = re.search(r"**\(**(\d{4})**\)**\s*$", title)

    movie["year"] = int(year_match.group(1)) if year_match else None

    genres = movie.get("genres") or ""

    movie["genres"] = [] if genres in ("", "(no genres listed)") else str(genres).split("|")

    return movie


def find_movie(movies: pd.DataFrame, movie_id: int):

    matched = movies.loc[movies["movieId"] == int(movie_id)]

    if matched.empty:

        raise HTTPException(status_code=404, detail="Movie not found.")

    return movie_to_dict(matched.iloc[0])


def recommend_item_based(model, movies, user_id: int, top_n: int):

    history = model["user_history"].get(int(user_id))


    if history is None or len(history) == 0:

        raise HTTPException(

            status_code=404,

            detail="User not found in the training data."

        )


    rated_items = {

        int(movie_id): float(rating)

        for movie_id, rating in history

    }


    user_mean = model["user_means"].get(

        int(user_id), model["global_mean"]

    )


    score_totals = {}

    similarity_totals = {}


    for rated_movie_id, user_rating in rated_items.items():

        source_index = model["movie_to_index"].get(rated_movie_id)


        if source_index is None:

            continue


        neighbor_indices = model["neighbor_indices"][source_index]

        similarities = model["neighbor_similarities"][source_index]


        for neighbor_index, similarity in zip(neighbor_indices, similarities):

            if similarity <= 0:

                continue


            candidate_id = int(model["movie_ids"][neighbor_index])


            if candidate_id in rated_items:

                continue


            score_totals[candidate_id] = (

                score_totals.get(candidate_id, 0.0)

                + float(similarity) * (user_rating - user_mean)

            )


            similarity_totals[candidate_id] = (

                similarity_totals.get(candidate_id, 0.0)

                + float(similarity)

            )


    scored = []


    for movie_id, total in score_totals.items():

        if similarity_totals[movie_id] > 0:

            score = user_mean + total / (

                similarity_totals[movie_id] + 5.0

            )

            scored.append((movie_id, float(np.clip(score, 0.5, 5.0))))


    scored.sort(key=lambda pair: pair[1], reverse=True)


    result = []

    movie_lookup = movies.set_index("movieId", drop=False)


    for movie_id, score in scored[:top_n]:

        if movie_id in movie_lookup.index:

            item = movie_to_dict(movie_lookup.loc[movie_id])

            item["predicted_rating"] = round(score, 3)

            result.append(item)


    return result


def recommend_for_custom_user(model, movies, ratings, top_n=10):

    rated_items = {

        int(item.movieId): float(item.rating)

        for item in ratings

    }


    if not rated_items:

        raise HTTPException(

            status_code=400,

            detail="Please rate at least one movie."

        )


    baseline = 3.5

    score_totals = {}

    similarity_totals = {}


    for rated_movie_id, user_rating in rated_items.items():

        source_index = model["movie_to_index"].get(rated_movie_id)


        if source_index is None:

            continue


        neighbors = model["neighbor_indices"][source_index]

        similarities = model["neighbor_similarities"][source_index]


        for neighbor_index, similarity in zip(neighbors, similarities):

            if similarity <= 0:

                continue


            candidate_id = int(model["movie_ids"][neighbor_index])


            if candidate_id in rated_items:

                continue


            score_totals[candidate_id] = (

                score_totals.get(candidate_id, 0.0)

                + float(similarity) * (user_rating - baseline)

            )


            similarity_totals[candidate_id] = (

                similarity_totals.get(candidate_id, 0.0)

                + float(similarity)

            )


    scored = []


    for movie_id, total in score_totals.items():

        similarity_sum = similarity_totals[movie_id]


        if similarity_sum > 0:

            score = baseline + (total / similarity_sum) * 0.5


            scored.append((

                movie_id,

                float(np.clip(score, 0.5, 5.0))

            ))


    scored.sort(key=lambda x: x[1], reverse=True)


    movie_lookup = movies.set_index("movieId", drop=False)

    results = []


    for movie_id, score in scored:

        if movie_id in movie_lookup.index:

            item = movie_to_dict(movie_lookup.loc[movie_id])

            item["predicted_rating"] = round(score, 3)

            results.append(item)


            if len(results) >= top_n:

                break


    return results


def recommend_user_based(model, movies, user_id: int, top_n: int):

    user_index = model["user_to_index"].get(int(user_id))

    if user_index is None:

        raise HTTPException(status_code=404, detail="User not found in the training data.")


    user_mean = model["user_means"].get(int(user_id), model["global_mean"])

    user_row = model["user_movie_matrix"].getrow(user_index)

    already_rated = set(model["movie_ids"][user_row.indices].astype(int))


    score_totals = {}

    similarity_totals = {}


    for neighbor_index, similarity in zip(

        model["neighbor_indices"][user_index],

        model["neighbor_similarities"][user_index],

    ):

        if similarity <= 0:

            continue


        neighbor_id = int(model["user_ids"][neighbor_index])

        neighbor_mean = model["user_means"].get(neighbor_id, model["global_mean"])

        neighbor_row = model["user_movie_matrix"].getrow(neighbor_index)


        for movie_index, rating in zip(neighbor_row.indices, neighbor_row.data):

            movie_id = int(model["movie_ids"][movie_index])

            if movie_id in already_rated:

                continue


            score_totals[movie_id] = (

                score_totals.get(movie_id, 0.0)

                + float(similarity) * (float(rating) - neighbor_mean)

            )

            similarity_totals[movie_id] = (

                similarity_totals.get(movie_id, 0.0) + float(similarity)

            )


    scored = []

    for movie_id, total in score_totals.items():

        if similarity_totals[movie_id] > 0:

            score = user_mean + total / similarity_totals[movie_id]

            scored.append((movie_id, float(np.clip(score, 0.5, 5.0))))

    scored.sort(key=lambda pair: pair[1], reverse=True)


    result = []

    movie_lookup = movies.set_index("movieId", drop=False)

    for movie_id, score in scored[:top_n]:

        if movie_id in movie_lookup.index:

            item = movie_to_dict(movie_lookup.loc[movie_id])

            item["predicted_rating"] = round(score, 3)

            result.append(item)

    return result


def recommend_als(model, train, movies, user_id: int, top_n: int):

    user_index = model["user_to_index"].get(int(user_id))

    if user_index is None:

        raise HTTPException(status_code=404, detail="User not found in the training data.")


    rated_ids = set(

        train.loc[train["userId"] == int(user_id), "movieId"].astype(int).tolist()

    )

    scores = model["global_mean"] + (

        model["item_factors"] @ model["user_factors"][user_index]

    )

    candidate_indices = np.argsort(scores)[::-1]


    result = []

    movie_lookup = movies.set_index("movieId", drop=False)

    for movie_index in candidate_indices:

        movie_id = int(model["movie_ids"][movie_index])

        if movie_id in rated_ids:

            continue

        if movie_id not in movie_lookup.index:

            continue

        item = movie_to_dict(movie_lookup.loc[movie_id])

        item["predicted_rating"] = round(float(np.clip(scores[movie_index], 0.5, 5.0)), 3)

        result.append(item)

        if len(result) >= top_n:

            break

    return result


@app.get("/")

def root():

    return {

        "name": "CineFinder API",

        "status": "running",

        "docs": "/docs",

        "health": "/health",

    }


@app.get("/health")

def health():

    resources = get_resources()

    return {

        "status": "healthy",

        "movies_loaded": len(resources["movies"]),

        "models_loaded": {

            "item_based": resources["item"] is not None,

            "user_based": resources["user"] is not None,

            "als": resources["als"] is not None,

        },

    }


@app.get("/model-metrics")

def model_metrics():

    results_dir = RESULTS_DIR


    metric_files = {

    "item_based": "item_based_metrics.txt",

    "user_based": "user_based_metrics.txt",

    "als": "als_metrics.txt"

}


    results = {}


    for model_name, filename in metric_files.items():

        file_path = results_dir / filename


        if not file_path.exists():

            raise HTTPException(

                status_code=404,

                detail=f"Metrics file not found: {filename}"

            )


        metrics = {}


        with open(file_path, "r", encoding="utf-8") as file:

            for line in file:

                if ":" in line:

                    key, value = line.strip().split(":", 1)


                    if key in ("RMSE", "MAE"):

                        metrics[key.lower()] = float(value.strip())

                    elif key == "Test ratings evaluated":

                        metrics["evaluated_ratings"] = int(value.strip())

                    elif key == "Training ratings":

                        metrics["training_ratings"] = int(value.strip())


        results[model_name] = metrics


    best_model = min(

        results,

        key=lambda name: results[name]["rmse"]

    )


    return {

        "models": results,

        "best_model": best_model

    }


@app.get("/movies")

def list_movies(

    page: int = Query(1, ge=1),

    limit: int = Query(24, ge=1, le=100),

    genre: Optional[str] = None,

):

    movies = get_resources()["movies"]

    filtered = movies


    if genre:

        filtered = filtered[

            filtered["genres"].fillna("").str.split("|").apply(

                lambda genres: genre.lower() in [g.lower() for g in genres]

            )

        ]


    total = len(filtered)

    start = (page - 1) * limit

    page_rows = filtered.iloc[start:start + limit]


    return {

        "page": page,

        "limit": limit,

        "total": total,

        "results": [movie_to_dict(row) for _, row in page_rows.iterrows()],

    }


@app.get("/search")

def search_movies(

    q: str = Query(..., min_length=1, max_length=100),

    limit: int = Query(20, ge=1, le=100),

):

    movies = get_resources()["movies"]

    matched = movies[movies["title"].str.contains(q, case=False, na=False, regex=False)]

    matched = matched.head(limit)

    return {"query": q, "results": [movie_to_dict(row) for _, row in matched.iterrows()]}


@app.get("/movies/{movie_id}")

def movie_details(movie_id: int):

    resources = get_resources()

    movie = find_movie(resources["movies"], movie_id)


    item_model = resources.get("item")

    similar = []

    if item_model is not None:

        movie_index = item_model["movie_to_index"].get(int(movie_id))

        if movie_index is not None:

            indices = item_model["neighbor_indices"][movie_index]

            similarities = item_model["neighbor_similarities"][movie_index]

            movie_lookup = resources["movies"].set_index("movieId", drop=False)

            for neighbor_index, similarity in zip(indices[:10], similarities[:10]):

                similar_id = int(item_model["movie_ids"][neighbor_index])

                if similar_id in movie_lookup.index:

                    entry = movie_to_dict(movie_lookup.loc[similar_id])

                    entry["similarity"] = round(float(similarity), 4)

                    similar.append(entry)


    return {"movie": movie, "similar_movies": similar}


@app.get("/similar/{movie_id}")

def similar_movies(

    movie_id: int,

    limit: int = Query(10, ge=1, le=30),

):

    resources = get_resources()

    model = get_model(resources, "item")

    movie = find_movie(resources["movies"], movie_id)

    movie_index = model["movie_to_index"].get(int(movie_id))


    if movie_index is None:

        return {"movie": movie, "results": []}


    movie_lookup = resources["movies"].set_index("movieId", drop=False)

    indices = model["neighbor_indices"][movie_index][:limit]

    similarities = model["neighbor_similarities"][movie_index][:limit]


    results = []

    for neighbor_index, similarity in zip(indices, similarities):

        similar_id = int(model["movie_ids"][neighbor_index])

        if similar_id in movie_lookup.index:

            entry = movie_to_dict(movie_lookup.loc[similar_id])

            entry["similarity"] = round(float(similarity), 4)

            results.append(entry)


    return {"movie": movie, "results": results}


@app.get("/recommendations/{user_id}")

def recommendations(

    user_id: int,

    model: str = Query("item", pattern="^(item|user|als)$"),

    limit: int = Query(10, ge=1, le=50),

):

    resources = get_resources()

    selected_model = get_model(resources, model)

    movies = resources["movies"]


    if model == "item":

        results = recommend_item_based(selected_model, movies, user_id, limit)

    elif model == "user":

        results = recommend_user_based(selected_model, movies, user_id, limit)

    else:

        results = recommend_als(selected_model, resources["train"], movies, user_id, limit)


    return {

        "user_id": user_id,

        "algorithm": model,

        "count": len(results),

        "results": results,

    }


# Custom recommendations endpoint

@app.post("/recommendations/custom")

def custom_recommendations(

    request: CustomRecommendationRequest,

    limit: int = Query(10, ge=1, le=50)

):

    resources = get_resources()

    model = get_model(resources, "item")


    results = recommend_for_custom_user(

        model,

        resources["movies"],

        request.ratings,

        limit

    )


    return {

        "algorithm": "item-based",

        "count": len(results),

        "results": results

    }


@app.get("/posters/{movie_id}")
def get_movie_poster(movie_id: int):
    """Redirect to a TMDB poster image without exposing the TMDB token."""
    resources = get_resources()
    tmdb_id = resources["tmdb_mapping"].get(int(movie_id))

    if tmdb_id is None:
        raise HTTPException(status_code=404, detail="TMDB ID not available for this movie.")

    cached_path = POSTER_CACHE.get(int(tmdb_id))
    if cached_path:
        return RedirectResponse(url=TMDB_IMAGE_BASE + cached_path)

    token = os.getenv("TMDB_API_READ_ACCESS_TOKEN")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="TMDB access token is not configured on the backend.",
        )

    tmdb_url = f"https://api.themoviedb.org/3/movie/{int(tmdb_id)}"
    request = urllib.request.Request(
        tmdb_url,
        headers={
            "Authorization": f"Bearer {token}",
            "accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))

        poster_path = data.get("poster_path")
        if not poster_path:
            raise HTTPException(status_code=404, detail="TMDB has no poster for this movie.")

        POSTER_CACHE[int(tmdb_id)] = poster_path
        return RedirectResponse(url=TMDB_IMAGE_BASE + poster_path)

    except urllib.error.HTTPError as error:
        print(f"TMDB API returned HTTP {error.code} for TMDB movie {tmdb_id}.")
        raise HTTPException(status_code=502, detail="TMDB could not provide this movie poster.")
    except urllib.error.URLError as error:
        print(f"Could not connect to TMDB: {error}")
        raise HTTPException(status_code=502, detail="Could not connect to TMDB.")
    except TimeoutError:
        raise HTTPException(status_code=504, detail="TMDB poster request timed out.")
