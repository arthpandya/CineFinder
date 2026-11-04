"""
CineFinder - Explicit-feedback ALS Matrix Factorization

Run from the CineFinder project root:
    python als_model.py

Input files:
    processed/train.csv
    processed/test.csv
    processed/movies_processed.csv

Outputs:
    models/als_model.joblib
    results/als_metrics.txt

This is explicit-rating ALS: it factorizes rating deviations from the
training-set global mean using alternating regularized least squares.
"""

from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics import mean_absolute_error, mean_squared_error


# -------------------- Configuration --------------------

ROOT_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = ROOT_DIR / "processed"
MODELS_DIR = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"

TRAIN_FILE = PROCESSED_DIR / "train.csv"
TEST_FILE = PROCESSED_DIR / "test.csv"
MOVIES_FILE = PROCESSED_DIR / "movies_processed.csv"

MODEL_FILE = MODELS_DIR / "als_model.joblib"
METRICS_FILE = RESULTS_DIR / "als_metrics.txt"

FACTORS = 20
ITERATIONS = 10
REGULARIZATION = 0.1
EVALUATION_LIMIT = 5000
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

    required = {"userId", "movieId", "rating"}
    if not required.issubset(train.columns):
        raise ValueError(f"train.csv must contain columns: {sorted(required)}")
    if not required.issubset(test.columns):
        raise ValueError(f"test.csv must contain columns: {sorted(required)}")
    if not {"movieId", "title", "genres"}.issubset(movies.columns):
        raise ValueError("movies_processed.csv must contain movieId, title, and genres.")

    return train, test, movies


def train_als_model(train):
    """Train explicit-feedback ALS using sparse user-item rating data."""
    print("\n[1/4] Preparing sparse rating matrix...")

    user_ids = np.sort(train["userId"].unique())
    movie_ids = np.sort(train["movieId"].unique())

    user_to_index = {int(value): index for index, value in enumerate(user_ids)}
    movie_to_index = {int(value): index for index, value in enumerate(movie_ids)}

    rows = train["userId"].map(user_to_index).to_numpy()
    cols = train["movieId"].map(movie_to_index).to_numpy()

    global_mean = float(train["rating"].mean())
    residuals = train["rating"].to_numpy(dtype=np.float32) - global_mean

    user_item = csr_matrix(
        (residuals, (rows, cols)),
        shape=(len(user_ids), len(movie_ids)),
        dtype=np.float32,
    )
    item_user = user_item.tocsc()

    print(f"  Matrix shape: {user_item.shape[0]:,} users x {user_item.shape[1]:,} movies")
    print(f"  Non-zero ratings: {user_item.nnz:,}")
    print(f"  Global mean rating: {global_mean:.4f}")

    rng = np.random.default_rng(RANDOM_STATE)
    user_factors = rng.normal(0, 0.05, (len(user_ids), FACTORS)).astype(np.float32)
    item_factors = rng.normal(0, 0.05, (len(movie_ids), FACTORS)).astype(np.float32)

    identity = np.eye(FACTORS, dtype=np.float32) * REGULARIZATION

    print("\n[2/4] Training ALS matrix factorization...")
    start_time = time.time()

    for iteration in range(ITERATIONS):
        # Update each user's latent vector while item vectors are fixed.
        for user_index in range(len(user_ids)):
            start, end = user_item.indptr[user_index:user_index + 2]
            item_indices = user_item.indices[start:end]
            ratings = user_item.data[start:end]

            if len(item_indices) == 0:
                continue

            factors = item_factors[item_indices]
            matrix = factors.T @ factors + identity
            vector = factors.T @ ratings
            user_factors[user_index] = np.linalg.solve(matrix, vector)

        # Update each item's latent vector while user vectors are fixed.
        for item_index in range(len(movie_ids)):
            start, end = item_user.indptr[item_index:item_index + 2]
            user_indices = item_user.indices[start:end]
            ratings = item_user.data[start:end]

            if len(user_indices) == 0:
                continue

            factors = user_factors[user_indices]
            matrix = factors.T @ factors + identity
            vector = factors.T @ ratings
            item_factors[item_index] = np.linalg.solve(matrix, vector)

        print(f"  Iteration {iteration + 1}/{ITERATIONS} completed")

    print(f"  Training time: {time.time() - start_time:.1f} seconds")

    return {
        "user_ids": user_ids,
        "movie_ids": movie_ids,
        "user_to_index": user_to_index,
        "movie_to_index": movie_to_index,
        "user_factors": user_factors,
        "item_factors": item_factors,
        "global_mean": global_mean,
        "method": "Explicit-feedback ALS Matrix Factorization",
        "factors": FACTORS,
        "iterations": ITERATIONS,
        "regularization": REGULARIZATION,
    }


def predict_rating(model, user_id, movie_id):
    """Predict a rating from the global mean and latent-factor dot product."""
    user_index = model["user_to_index"].get(int(user_id))
    movie_index = model["movie_to_index"].get(int(movie_id))

    if user_index is None or movie_index is None:
        return float(model["global_mean"])

    prediction = model["global_mean"] + float(
        np.dot(
            model["user_factors"][user_index],
            model["item_factors"][movie_index],
        )
    )
    return float(np.clip(prediction, 0.5, 5.0))


def evaluate_model(model, test):
    """Evaluate RMSE and MAE on a reproducible sample of held-out ratings."""
    print("\n[3/4] Evaluating held-out ratings...")

    evaluation_data = test.sample(
        n=min(EVALUATION_LIMIT, len(test)),
        random_state=RANDOM_STATE,
    )

    actual = evaluation_data["rating"].to_numpy(dtype=float)
    predicted = [
        predict_rating(model, row.userId, row.movieId)
        for row in evaluation_data.itertuples(index=False)
    ]
    predicted = np.asarray(predicted, dtype=float)

    rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
    mae = float(mean_absolute_error(actual, predicted))

    print(f"  Evaluated ratings: {len(evaluation_data):,}")
    print(f"  RMSE: {rmse:.4f}")
    print(f"  MAE:  {mae:.4f}")

    return {
        "evaluated_ratings": len(evaluation_data),
        "rmse": rmse,
        "mae": mae,
    }


def recommend_movies(model, train, movies, user_id, top_n=10):
    """Recommend highest-scoring unseen movies for a known user."""
    user_id = int(user_id)
    user_index = model["user_to_index"].get(user_id)

    if user_index is None:
        print(f"\nUser {user_id} is not present in the training data.")
        return pd.DataFrame()

    user_history = train.loc[train["userId"] == user_id, "movieId"]
    rated_movies = set(user_history.astype(int).tolist())

    scores = (
        model["global_mean"]
        + model["item_factors"] @ model["user_factors"][user_index]
    )
    candidate_indices = np.argsort(scores)[::-1]

    recommendations = []
    for movie_index in candidate_indices:
        movie_id = int(model["movie_ids"][movie_index])
        if movie_id in rated_movies:
            continue

        recommendations.append(
            {
                "movieId": movie_id,
                "predicted_rating": float(np.clip(scores[movie_index], 0.5, 5.0)),
            }
        )
        if len(recommendations) >= top_n:
            break

    if not recommendations:
        print("No recommendations could be generated for this user.")
        return pd.DataFrame()

    result = pd.DataFrame(recommendations).merge(
        movies, on="movieId", how="left"
    )
    return result[["movieId", "title", "genres", "predicted_rating"]]


def main():
    print("=" * 55)
    print("       CINEFINDER - ALS MATRIX FACTORIZATION")
    print("=" * 55)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    train, test, movies = load_data()
    print(f"\nTraining rows: {len(train):,}")
    print(f"Testing rows:  {len(test):,}")

    model = train_als_model(train)

    print("\nSaving trained model...")
    joblib.dump(model, MODEL_FILE, compress=3)
    print(f"  Model saved to: {MODEL_FILE}")

    metrics = evaluate_model(model, test)

    with open(METRICS_FILE, "w", encoding="utf-8") as file:
        file.write("CineFinder - ALS Matrix Factorization\n")
        file.write(f"Method: {model['method']}\n")
        file.write(f"Training ratings: {len(train)}\n")
        file.write(f"Factors: {FACTORS}\n")
        file.write(f"Iterations: {ITERATIONS}\n")
        file.write(f"Regularization: {REGULARIZATION}\n")
        file.write(f"Test ratings evaluated: {metrics['evaluated_ratings']}\n")
        file.write(f"RMSE: {metrics['rmse']:.4f}\n")
        file.write(f"MAE: {metrics['mae']:.4f}\n")

    demo_user_id = int(train["userId"].iloc[0])
    print(f"\n[4/4] Example recommendations for user {demo_user_id}:")

    recommendations = recommend_movies(
        model=model,
        train=train,
        movies=movies,
        user_id=demo_user_id,
        top_n=10,
    )

    if not recommendations.empty:
        print(recommendations.to_string(index=False))

    print(f"\nMetrics saved to: {METRICS_FILE}")
    print("\nALS Matrix Factorization completed.")


if __name__ == "__main__":
    main()
