import joblib
import numpy as np

model = joblib.load("models/item_based_model.joblib")

user_id = 188674
history = model["user_history"][user_id]

rated_items = {
    int(movie_id): float(rating)
    for movie_id, rating in history
}

user_mean = model["user_means"][user_id]

score_totals = {}
similarity_totals = {}

for rated_movie_id, user_rating in rated_items.items():
    source_index = model["movie_to_index"].get(rated_movie_id)

    if source_index is None:
        continue

    neighbors = model["neighbor_indices"][source_index]
    similarities = model["neighbor_similarities"][source_index]

    for neighbor_index, similarity in zip(neighbors, similarities):
        candidate_id = int(model["movie_ids"][neighbor_index])

        if similarity <= 0 or candidate_id in rated_items:
            continue

        score_totals[candidate_id] = (
            score_totals.get(candidate_id, 0)
            + float(similarity) * (user_rating - user_mean)
        )

        similarity_totals[candidate_id] = (
            similarity_totals.get(candidate_id, 0)
            + float(similarity)
        )

raw_scores = [
    (movie_id, user_mean + score_totals[movie_id] / similarity_totals[movie_id])
    for movie_id in score_totals
    if similarity_totals[movie_id] > 0
]

raw_scores.sort(key=lambda x: x[1], reverse=True)

print("\nTop 10 movies with their raw scores:")
for movie_id, score in raw_scores[:10]:
    print("Movie:", movie_id, "| Score:", repr(score))

print("User average:", round(user_mean, 2))
print("\nTop 10 RAW predictions (before clipping):")

for movie_id, score in raw_scores[:10]:
    print(movie_id, round(score, 3))

print("\nMaximum raw score:", round(max(x[1] for x in raw_scores), 3))
print("Minimum raw score:", round(min(x[1] for x in raw_scores), 3))

print("Candidates with score >= 4.99:", sum(1 for x in raw_scores if x[1] >= 4.99))
print("Total candidates:", len(raw_scores))

print("\nChecking movie 1490:")

target_id = 1490
target_index = model["movie_to_index"][target_id]

print("Similar movies rated by this user:")

for neighbor_index, similarity in zip(
    model["neighbor_indices"][target_index],
    model["neighbor_similarities"][target_index]
):
    neighbor_id = int(model["movie_ids"][neighbor_index])

    if neighbor_id in rated_items:
        print(
            "Movie ID:", neighbor_id,
            "| User rating:", rated_items[neighbor_id],
            "| Similarity:", round(float(similarity), 4)
        )