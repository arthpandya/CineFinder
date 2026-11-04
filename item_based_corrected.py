"""
CineFinder - Item-Based Collaborative Filtering
================================================

Run this script from the CineFinder project root:
    python item_based.py

Input files:
    processed/train.csv
    processed/test.csv
    processed/movies_processed.csv

Outputs:
    models/item_based_model.joblib
    results/item_based_metrics.txt

Method:
    - Build a sparse movie-user rating matrix.
    - Find similar movies using cosine similarity.
    - Predict a user's rating from ratings they gave to similar movies.
    - Generate recommendations for a user ID.
"""

from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import mean_absolute_error, mean_squared_error


# -------------------- Configuration --------------------

ROOT_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = ROOT_DIR / "processed"
MODELS_DIR = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"

TRAIN_FILE = PROCESSED_DIR / "train.csv"
TEST_FILE = PROCESSED_DIR / "test.csv"
MOVIES_FILE = PROCESSED_DIR / "movies_processed.csv"

MODEL_FILE = MODELS_DIR / "item_based_model.joblib"
METRICS_FILE = RESULTS_DIR / "item_based_metrics.txt"

N_NEIGHBORS = 21       # Includes the movie itself; we use the other 20.
EVALUATION_LIMIT = 5_000
RANDOM_STATE = 42


def load_data():
    """Load the processed training, testing, and movie metadata files."""
    for file_path in (TRAIN_FILE, TEST_FILE, MOVIES_FILE):
        if not file_path.exists():
            raise FileNotFoundError(
                f"Missing {file_path}. Run preprocess.py from the project root first."
            )

    train = pd.read_csv(TRAIN_FILE)
    test = pd.read_csv(TEST_FILE)
    movies = pd.read_csv(MOVIES_FILE)

    required_columns = {"userId", "movieId", "rating"}
    if not required_columns.issubset(train.columns):
        raise ValueError(f"train.csv must contain columns: {sorted(required_columns)}")

    return train, test, movies


def train_item_based_model(train):
    """
    Fit a nearest-neighbor model on a sparse movie-user matrix.

    Rows represent movies and columns represent users. Cosine similarity
    compares the rating patterns of two movies.
    """
    print("\n[1/4] Building sparse movie-user matrix...")

    user_ids = np.sort(train["userId"].unique())
    movie_ids = np.sort(train["movieId"].unique())

    user_to_index = {user_id: index for index, user_id in enumerate(user_ids)}
    movie_to_index = {movie_id: index for index, movie_id in enumerate(movie_ids)}

    row_indices = train["movieId"].map(movie_to_index).to_numpy()
    col_indices = train["userId"].map(user_to_index).to_numpy()
    values = train["rating"].astype("float32").to_numpy()

    movie_user_matrix = csr_matrix(
        (values, (row_indices, col_indices)),
        shape=(len(movie_ids), len(user_ids)),
        dtype=np.float32,
    )

    print(f"  Matrix shape: {movie_user_matrix.shape[0]:,} movies x "
          f"{movie_user_matrix.shape[1]:,} users")
    print(f"  Non-zero ratings: {movie_user_matrix.nnz:,}")

    print("\n[2/4] Finding similar movies with cosine similarity...")
    neighbor_count = min(N_NEIGHBORS, len(movie_ids))

    neighbors_model = NearestNeighbors(
        metric="cosine",
        algorithm="brute",
        n_neighbors=neighbor_count,
        n_jobs=-1,
    )
    neighbors_model.fit(movie_user_matrix)

    distances, indices = neighbors_model.kneighbors(movie_user_matrix)

    # Exclude each movie's first neighbor (itself).
    neighbor_indices = indices[:, 1:]
    neighbor_similarities = np.clip(1.0 - distances[:, 1:], 0.0, 1.0)

    # Per-user training history, used for recommendations and predictions.
    user_history = {
        int(user_id): group[["movieId", "rating"]].to_numpy()
        for user_id, group in train.groupby("userId", sort=False)
    }

    user_means = train.groupby("userId")["rating"].mean().to_dict()
    global_mean = float(train["rating"].mean())

    model_data = {
        "user_ids": user_ids,
        "movie_ids": movie_ids,
        "movie_to_index": movie_to_index,
        "neighbor_indices": neighbor_indices,
        "neighbor_similarities": neighbor_similarities,
        "user_history": user_history,
        "user_means": user_means,
        "global_mean": global_mean,
        "n_neighbors": neighbor_indices.shape[1],
        "method": "Item-Based Collaborative Filtering (cosine similarity)",
    }

    return model_data


def predict_rating(model, user_id, target_movie_id):
    """Predict a user's rating using ratings of similar movies."""
    target_index = model["movie_to_index"].get(int(target_movie_id))
    history = model["user_history"].get(int(user_id))

    if target_index is None:
        return model["user_means"].get(int(user_id), model["global_mean"])

    if history is None or len(history) == 0:
        return model["global_mean"]

    rated_items = {
        int(movie_id): float(rating)
        for movie_id, rating in history
    }

    similar_indices = model["neighbor_indices"][target_index]
    similarities = model["neighbor_similarities"][target_index]

    weighted_sum = 0.0
    similarity_sum = 0.0

    for neighbor_index, similarity in zip(similar_indices, similarities):
        if similarity <= 0:
            continue

        neighbor_movie_id = int(model["movie_ids"][neighbor_index])
        if neighbor_movie_id in rated_items:
            weighted_sum += float(similarity) * rated_items[neighbor_movie_id]
            similarity_sum += float(similarity)

    if similarity_sum > 0:
        prediction = weighted_sum / similarity_sum
    else:
        prediction = model["user_means"].get(int(user_id), model["global_mean"])

    return float(np.clip(prediction, 0.5, 5.0))


def evaluate_model(model, test):
    """Evaluate RMSE and MAE on a reproducible sample of held-out ratings."""
    print("\n[3/4] Evaluating held-out ratings...")

    evaluation_data = test.sample(
        n=min(EVALUATION_LIMIT, len(test)),
        random_state=RANDOM_STATE,
    )

    actual = evaluation_data["rating"].to_numpy(dtype=float)
    predicted = []

    start_time = time.time()

    for row in evaluation_data.itertuples(index=False):
        predicted.append(predict_rating(model, row.userId, row.movieId))

    predicted = np.asarray(predicted, dtype=float)

    rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
    mae = float(mean_absolute_error(actual, predicted))

    print(f"  Evaluated ratings: {len(evaluation_data):,}")
    print(f"  RMSE: {rmse:.4f}")
    print(f"  MAE:  {mae:.4f}")
    print(f"  Evaluation time: {time.time() - start_time:.1f} seconds")

    return {
        "evaluated_ratings": len(evaluation_data),
        "rmse": rmse,
        "mae": mae,
    }


def recommend_movies(model, movies, user_id, top_n=10):
    """Recommend unseen movies by aggregating similar-movie evidence."""
    history = model["user_history"].get(int(user_id))

    if history is None or len(history) == 0:
        print(f"\nUser {user_id} is not present in the training data.")
        return pd.DataFrame()

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

            candidate_movie_id = int(model["movie_ids"][neighbor_index])

            if candidate_movie_id in rated_items:
                continue

            score_totals[candidate_movie_id] = (
                score_totals.get(candidate_movie_id, 0.0)
                + float(similarity) * (user_rating - user_mean)
            )

            similarity_totals[candidate_movie_id] = (
                similarity_totals.get(candidate_movie_id, 0.0)
                + float(similarity)
            )

    if not score_totals:
        print("No recommendations could be generated for this user.")
        return pd.DataFrame()

    recommendations = pd.DataFrame([
        {
            "movieId": movie_id,
            "predicted_rating": float(np.clip(
                user_mean + score_totals[movie_id] / (
                    similarity_totals[movie_id] + 5.0
                ),
                0.5,
                5.0
            ))
        }
        for movie_id in score_totals
        if similarity_totals[movie_id] > 0
    ])

    recommendations = recommendations.sort_values(
        "predicted_rating", ascending=False
    ).head(top_n)

    recommendations = recommendations.merge(movies, on="movieId", how="left")

    return recommendations[["movieId", "title", "genres", "predicted_rating"]]


def main():
    print("=" * 55)
    print("       CINEFINDER - ITEM-BASED COLLABORATIVE FILTERING")
    print("=" * 55)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    train, test, movies = load_data()
    print(f"\nTraining rows: {len(train):,}")
    print(f"Testing rows:  {len(test):,}")

    model = train_item_based_model(train)

    print("\nSaving trained model...")
    joblib.dump(model, MODEL_FILE, compress=3)
    print(f"  Model saved to: {MODEL_FILE}")

    metrics = evaluate_model(model, test)

    with open(METRICS_FILE, "w", encoding="utf-8") as file:
        file.write("CineFinder - Item-Based Collaborative Filtering\n")
        file.write(f"Method: {model['method']}\n")
        file.write(f"Training ratings: {len(train)}\n")
        file.write(f"Test ratings evaluated: {metrics['evaluated_ratings']}\n")
        file.write(f"RMSE: {metrics['rmse']:.4f}\n")
        file.write(f"MAE: {metrics['mae']:.4f}\n")

    # Demonstrate recommendations for a user in the training data.
    demo_user_id = int(train["userId"].iloc[0])

    print(f"\n[4/4] Example recommendations for user {demo_user_id}:")
    recommendations = recommend_movies(
        model=model,
        movies=movies,
        user_id=demo_user_id,
        top_n=10,
    )

    if not recommendations.empty:
        print(recommendations.to_string(index=False))

    print(f"\nMetrics saved to: {METRICS_FILE}")
    print("\nItem-Based Collaborative Filtering completed.")


if __name__ == "__main__":
    main()
