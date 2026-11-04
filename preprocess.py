"""
CineFinder - MovieLens 32M preprocessing
----------------------------------------
Run from the CineFinder project root:
    python preprocess.py

This script:
1. Reads ratings.csv in chunks and takes a reproducible random sample.
2. Filters users and movies with too few ratings.
3. Creates a per-user train/test split.
4. Saves processed CSV files under processed/.

The original dataset files are never modified.
"""

from pathlib import Path
import pandas as pd

# -------------------- Configuration --------------------

DATASET_DIR = Path("dataset")
OUTPUT_DIR = Path("processed")

RATINGS_FILE = DATASET_DIR / "ratings.csv"
MOVIES_FILE = DATASET_DIR / "movies.csv"

# MovieLens 32M contains 32,000,204 ratings.
TOTAL_RATINGS_IN_SOURCE = 32_000_204

TARGET_SAMPLE_SIZE = 1_000_000
CHUNK_SIZE = 500_000
RANDOM_STATE = 42

# Keep users and movies with at least this many ratings in the sample.
MIN_USER_RATINGS = 10
MIN_MOVIE_RATINGS = 10

TEST_FRACTION = 0.20


def check_input_files():
    """Stop early with a helpful message if the expected files are missing."""
    missing = [str(path) for path in (RATINGS_FILE, MOVIES_FILE) if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Could not find: "
            + ", ".join(missing)
            + "\nExpected dataset/movies.csv and dataset/ratings.csv."
        )


def create_random_sample():
    """
    Sample a small proportion from every chunk.

    The source file is ordered by userId, so taking only the first N rows
    would heavily bias the sample toward early user IDs. Sampling each
    chunk avoids that problem.
    """
    sample_fraction = TARGET_SAMPLE_SIZE / TOTAL_RATINGS_IN_SOURCE
    sampled_chunks = []
    rows_read = 0

    print("\n[1/5] Reading ratings in chunks and creating a random sample...")

    for chunk_number, chunk in enumerate(
        pd.read_csv(RATINGS_FILE, chunksize=CHUNK_SIZE),
        start=1,
    ):
        rows_read += len(chunk)

        sampled_chunk = chunk.sample(
            frac=sample_fraction,
            random_state=RANDOM_STATE + chunk_number,
        )
        sampled_chunks.append(sampled_chunk)

        print(f"  Read {rows_read:,} ratings")

    if not sampled_chunks:
        raise ValueError("No ratings were read. Check that ratings.csv is not empty.")

    ratings = pd.concat(sampled_chunks, ignore_index=True)
    ratings = ratings.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

    print(f"  Random sample created: {len(ratings):,} ratings")
    return ratings


def clean_and_filter(ratings):
    """Remove invalid rows and filter low-activity users and movies."""
    print("\n[2/5] Cleaning and filtering ratings...")

    original_rows = len(ratings)

    ratings = ratings.dropna(subset=["userId", "movieId", "rating"]).copy()
    ratings = ratings.drop_duplicates(subset=["userId", "movieId"])

    ratings["userId"] = ratings["userId"].astype("int32")
    ratings["movieId"] = ratings["movieId"].astype("int32")
    ratings["rating"] = ratings["rating"].astype("float32")

    ratings = ratings[
        ratings["rating"].between(0.5, 5.0)
    ].copy()

    # Remove users with too few ratings in the sampled data.
    user_counts = ratings["userId"].value_counts()
    active_users = user_counts[user_counts >= MIN_USER_RATINGS].index
    ratings = ratings[ratings["userId"].isin(active_users)].copy()

    # Remove movies with too few ratings in the remaining sample.
    movie_counts = ratings["movieId"].value_counts()
    active_movies = movie_counts[movie_counts >= MIN_MOVIE_RATINGS].index
    ratings = ratings[ratings["movieId"].isin(active_movies)].copy()

    if ratings.empty:
        raise ValueError(
            "No ratings remain after filtering. Lower MIN_USER_RATINGS "
            "or MIN_MOVIE_RATINGS and run again."
        )

    print(f"  Rows before cleaning: {original_rows:,}")
    print(f"  Rows after filtering: {len(ratings):,}")
    print(f"  Users retained: {ratings['userId'].nunique():,}")
    print(f"  Movies retained: {ratings['movieId'].nunique():,}")

    return ratings


def make_train_test_split(ratings):
    """
    Hold out 20% of each user's ratings for testing.

    Splitting within each user helps ensure that users in the test set
    also have ratings available in the training set.
    """
    print("\n[3/5] Creating per-user train/test split...")

    test = (
        ratings.groupby("userId", group_keys=False)
        .sample(frac=TEST_FRACTION, random_state=RANDOM_STATE)
    )

    train = ratings.drop(index=test.index)

    train = train.reset_index(drop=True)
    test = test.reset_index(drop=True)

    print(f"  Training ratings: {len(train):,}")
    print(f"  Testing ratings:  {len(test):,}")

    return train, test


def save_outputs(train, test):
    """Save the processed datasets and a matching movie metadata file."""
    print("\n[4/5] Saving processed files...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    movies = pd.read_csv(MOVIES_FILE)
    used_movie_ids = set(train["movieId"]) | set(test["movieId"])
    processed_movies = movies[movies["movieId"].isin(used_movie_ids)].copy()

    train_path = OUTPUT_DIR / "train.csv"
    test_path = OUTPUT_DIR / "test.csv"
    movies_path = OUTPUT_DIR / "movies_processed.csv"

    train.to_csv(train_path, index=False)
    test.to_csv(test_path, index=False)
    processed_movies.to_csv(movies_path, index=False)

    print(f"  Saved: {train_path}")
    print(f"  Saved: {test_path}")
    print(f"  Saved: {movies_path}")

    return processed_movies


def print_summary(train, test, movies):
    """Print a concise summary for the project log/report."""
    print("\n[5/5] PREPROCESSING SUMMARY")
    print("=" * 45)
    print(f"Training ratings : {len(train):,}")
    print(f"Testing ratings  : {len(test):,}")
    print(f"Users            : {train['userId'].nunique():,}")
    print(f"Movies           : {movies['movieId'].nunique():,}")
    print(f"Average train rating: {train['rating'].mean():.3f}")
    print(f"Average test rating : {test['rating'].mean():.3f}")
    print(f"Output folder    : {OUTPUT_DIR.resolve()}")
    print("=" * 45)
    print("Preprocessing completed successfully.")


def main():
    print("=" * 45)
    print("       CINEFINDER - DATA PREPROCESSING")
    print("=" * 45)

    check_input_files()

    ratings = create_random_sample()
    ratings = clean_and_filter(ratings)
    train, test = make_train_test_split(ratings)
    movies = save_outputs(train, test)
    print_summary(train, test, movies)


if __name__ == "__main__":
    main()
