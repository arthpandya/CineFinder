
import pandas as pd
import matplotlib.pyplot as plt
import os

print("=" * 45)
print("          CINEFINDER - EDA")
print("=" * 45)

# Load movie information
movies = pd.read_csv("dataset/movies.csv")

print("\n1. MOVIE DATASET")
print("Total Movies:", len(movies))
print("Total Genres:", movies["genres"].nunique())

# Process ratings in chunks
print("\n2. PROCESSING RATINGS")
print("Reading ratings in chunks of 500,000...")

rating_file = "dataset/ratings.csv"

total_ratings = 0
rating_sum = 0
rating_distribution = {}
user_ids = set()
movie_counts = pd.Series(dtype="int64")

for chunk in pd.read_csv(rating_file, chunksize=500000):

    total_ratings += len(chunk)
    rating_sum += chunk["rating"].sum()

    # Rating distribution
    counts = chunk["rating"].value_counts()
    rating_distribution = (
        pd.Series(rating_distribution)
        .add(counts, fill_value=0)
        .to_dict()
    )

    # Unique users
    user_ids.update(chunk["userId"].unique())

    # Movie rating counts
    counts = chunk["movieId"].value_counts()
    movie_counts = movie_counts.add(counts, fill_value=0)

    print("Processed:", f"{total_ratings:,}", "ratings")

# Dataset statistics
print("\n3. DATASET STATISTICS")

print("Total Ratings:", f"{total_ratings:,}")
print("Unique Users:", f"{len(user_ids):,}")
print("Unique Movies Rated:", f"{len(movie_counts):,}")
print("Average Rating:", round(rating_sum / total_ratings, 2))

# Rating distribution
print("\n4. RATING DISTRIBUTION")

rating_distribution = pd.Series(rating_distribution).sort_index()

print(rating_distribution)

# Create results directory
os.makedirs("results", exist_ok=True)

# Rating distribution chart
plt.figure(figsize=(9, 5))

rating_distribution.plot(kind="bar")

plt.title("Movie Rating Distribution")
plt.xlabel("Rating")
plt.ylabel("Number of Ratings")
plt.xticks(rotation=0)
plt.tight_layout()

plt.savefig("results/rating_distribution.png")
plt.show()

# Top 10 most rated movies
print("\n5. TOP 10 MOST RATED MOVIES")

top_movies = movie_counts.nlargest(10).reset_index()
top_movies.columns = ["movieId", "rating_count"]

top_movies["movieId"] = top_movies["movieId"].astype(int)

top_movies = top_movies.merge(movies, on="movieId")

print(top_movies[["title", "rating_count"]].to_string(index=False))

# Top movies chart
plt.figure(figsize=(11, 6))

plt.barh(
    top_movies["title"].iloc[::-1],
    top_movies["rating_count"].iloc[::-1]
)

plt.title("Top 10 Most Rated Movies")
plt.xlabel("Number of Ratings")
plt.ylabel("Movie")

plt.tight_layout()
plt.savefig("results/top_movies.png")
plt.show()

print("\nEDA COMPLETED SUCCESSFULLY!")
print("Charts saved in results/ folder.")
