"""
CineFinder - User-Based Collaborative Filtering

Run from the CineFinder project root:
    python user_based.py

Input files:
    processed/train.csv
    processed/test.csv
    processed/movies_processed.csv

Outputs:
    models/user_based_model.joblib
    results/user_based_metrics.txt
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

MODEL_FILE = MODELS_DIR / "user_based_model.joblib"
METRICS_FILE = RESULTS_DIR / "user_based_metrics.txt"

N_NEIGHBORS = 21       # Includes the user itself; use the other 20.
EVALUATION_LIMIT = 5000
RANDOM_STATE = 42


def load_data():
    """Load processed training, testing, and movie metadata files."""
    for file_path in (TRAIN_FILE, TEST_FILE, MOVIES_FILE):
        if not file_path.exists():
            raise FileNotFoundError(
                f"Missing {file_path}. Run preprocess.py from the project root first."
            )

    train = pd.read_csv(TRAIN_FILE)
    test = pd.read_csv(TEST_FILE)
    movies = pd.read_csv(MOVIES_FILE)

    required = {"userId", "movieId", "rating"}
    if not required.issubset(train.columns):
        raise ValueError(f"train.csv must contain columns: {sorted(required)}")
    if not required.issubset(test.columns):
        raise ValueError(f"test.csv must contain columns: {sorted(required)}")
    if not {"movieId", "title", "genres"}.issubset(movies.columns):
        raise ValueError("movies_processed.csv must contain movieId, title, and genres.")

    return train, test, movies


def train_user_based_model(train):
    """Build a sparse user-movie matrix and find similar users."""
    print("\n[1/4] Building sparse user-movie matrix...")

    user_ids = np.sort(train["userId"].unique())
    movie_ids = np.sort(train["movieId"].unique())

    user_to_index = {int(user_id): index for index, user_id in enumerate(user_ids)}
    movie_to_index = {int(movie_id): index for index, movie_id in enumerate(movie_ids)}

    row_indices = train["userId"].map(user_to_index).to_numpy()
    col_indices = train["movieId"].map(movie_to_index).to_numpy()
    values = train["rating"].astype("float32").to_numpy()

    user_movie_matrix = csr_matrix(
        (values, (row_indices, col_indices)),
        shape=(len(user_ids), len(movie_ids)),
        dtype=np.float32,
    )

    print(
        f"  Matrix shape: {user_movie_matrix.shape[0]:,} users x "
        f"{user_movie_matrix.shape[1]:,} movies"
    )
    print(f"  Non-zero ratings: {user_movie_matrix.nnz:,}")

    print("\n[2/4] Finding similar users with cosine similarity...")
    neighbor_count = min(N_NEIGHBORS, len(user_ids))

    neighbors_model = NearestNeighbors(
        metric="cosine",
        algorithm="brute",
        n_neighbors=neighbor_count,
        n_jobs=-1,
    )
    neighbors_model.fit(user_movie_matrix)

    # Query in batches to keep temporary distance arrays manageable.
    all_indices = []
    all_distances = []
    batch_size = 2000

    for start in range(0, len(user_ids), batch_size):
        end = min(start + batch_size, len(user_ids))
        distances, indices = neighbors_model.kneighbors(
            user_movie_matrix[start:end],
            n_neighbors=neighbor_count,
        )
        all_indices.append(indices)
        all_distances.append(distances)
        print(f"  Processed users: {end:,}/{len(user_ids):,}")

    indices = np.vstack(all_indices)
    distances = np.vstack(all_distances)

    # Exclude the query user itself (normally the first neighbor).
    neighbor_indices = indices[:, 1:]
    neighbor_similarities = np.clip(1.0 - distances[:, 1:], 0.0, 1.0)

    user_means = train.groupby("userId")["rating"].mean().to_dict()
    global_mean = float(train["rating"].mean())

    model_data = {
        "user_ids": user_ids,
        "movie_ids": movie_ids,
        "user_to_index": user_to_index,
        "movie_to_index": movie_to_index,
        "user_movie_matrix": user_movie_matrix,
        "neighbor_indices": neighbor_indices,
        "neighbor_similarities": neighbor_similarities,
        "user_means": {int(k): float(v) for k, v in user_means.items()},
        "global_mean": global_mean,
        "method": "User-Based Collaborative Filtering (cosine similarity)",
    }

    return model_data


def predict_rating(model, user_id, target_movie_id):
    """Predict a user's rating using ratings from similar users."""
    user_id = int(user_id)
    target_movie_id = int(target_movie_id)

    user_index = model["user_to_index"].get(user_id)
    movie_index = model["movie_to_index"].get(target_movie_id)

    user_mean = model["user_means"].get(user_id, model["global_mean"])

    if user_index is None or movie_index is None:
        return float(user_mean)

    neighbor_indices = model["neighbor_indices"][user_index]
    similarities = model["neighbor_similarities"][user_index]

    weighted_deviation = 0.0
    similarity_sum = 0.0

    for neighbor_index, similarity in zip(neighbor_indices, similarities):
        if similarity <= 0:
            continue

        neighbor_rating = model["user_movie_matrix"][neighbor_index, movie_index]
        if neighbor_rating == 0:
            continue

        neighbor_id = int(model["user_ids"][neighbor_index])
        neighbor_mean = model["user_means"].get(neighbor_id, model["global_mean"])

        weighted_deviation += float(similarity) * (
            float(neighbor_rating) - neighbor_mean
        )
        similarity_sum += float(similarity)

    if similarity_sum > 0:
        prediction = user_mean + weighted_deviation / similarity_sum
    else:
        prediction = user_mean

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
    """Recommend unseen movies using similar users' rating deviations."""
    user_id = int(user_id)
    user_index = model["user_to_index"].get(user_id)

    if user_index is None:
        print(f"\nUser {user_id} is not present in the training data.")
        return pd.DataFrame()

    user_mean = model["user_means"].get(user_id, model["global_mean"])
    user_row = model["user_movie_matrix"].getrow(user_index)
    already_rated = set(model["movie_ids"][user_row.indices].astype(int))

    score_totals = {}
    similarity_totals = {}

    neighbor_indices = model["neighbor_indices"][user_index]
    similarities = model["neighbor_similarities"][user_index]

    for neighbor_index, similarity in zip(neighbor_indices, similarities):
        if similarity <= 0:
            continue

        neighbor_id = int(model["user_ids"][neighbor_index])
        neighbor_mean = model["user_means"].get(neighbor_id, model["global_mean"])
        neighbor_row = model["user_movie_matrix"].getrow(neighbor_index)

        for movie_index, rating in zip(neighbor_row.indices, neighbor_row.data):
            movie_id = int(model["movie_ids"][movie_index])

            if movie_id in already_rated:
                continue

            deviation = float(rating) - neighbor_mean
            score_totals[movie_id] = (
                score_totals.get(movie_id, 0.0) + float(similarity) * deviation
            )
            similarity_totals[movie_id] = (
                similarity_totals.get(movie_id, 0.0) + float(similarity)
            )

    if not score_totals:
        print("No recommendations could be generated for this user.")
        return pd.DataFrame()

    rows = []
    for movie_id, total in score_totals.items():
        score = user_mean + total / similarity_totals[movie_id]
        rows.append(
            {
                "movieId": movie_id,
                "predicted_rating": float(np.clip(score, 0.5, 5.0)),
            }
        )

    recommendations = pd.DataFrame(rows)
    recommendations = recommendations.sort_values(
        "predicted_rating", ascending=False
    ).head(top_n)

    recommendations = recommendations.merge(movies, on="movieId", how="left")
    return recommendations[["movieId", "title", "genres", "predicted_rating"]]


def main():
    print("=" * 55)
    print("       CINEFINDER - USER-BASED COLLABORATIVE FILTERING")
    print("=" * 55)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    train, test, movies = load_data()
    print(f"\nTraining rows: {len(train):,}")
    print(f"Testing rows:  {len(test):,}")

    model = train_user_based_model(train)

    print("\nSaving trained model...")
    joblib.dump(model, MODEL_FILE, compress=3)
    print(f"  Model saved to: {MODEL_FILE}")

    metrics = evaluate_model(model, test)

    with open(METRICS_FILE, "w", encoding="utf-8") as file:
        file.write("CineFinder - User-Based Collaborative Filtering\n")
        file.write(f"Method: {model['method']}\n")
        file.write(f"Training ratings: {len(train)}\n")
        file.write(f"Test ratings evaluated: {metrics['evaluated_ratings']}\n")
        file.write(f"RMSE: {metrics['rmse']:.4f}\n")
        file.write(f"MAE: {metrics['mae']:.4f}\n")

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
    print("\nUser-Based Collaborative Filtering completed.")


if __name__ == "__main__":
    main()
