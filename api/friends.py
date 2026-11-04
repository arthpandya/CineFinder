from fastapi import APIRouter, Depends, HTTPException, Query, Request
import numpy as np

from api.auth import get_current_user, get_db

router = APIRouter(prefix="/social", tags=["Social Recommendations"])


def _get_friend_ratings(db, user_id: int):
    rows = db.execute(
        """
        SELECT movie_id, rating
        FROM user_movies
        WHERE user_id = ? AND list_type = 'rated' AND rating IS NOT NULL
        """,
        (user_id,),
    ).fetchall()

    return {int(row["movie_id"]): float(row["rating"]) for row in rows}


def _get_watched_movies(db, user_id: int):
    rows = db.execute(
        """
        SELECT movie_id
        FROM user_movies
        WHERE user_id = ? AND list_type = 'watched'
        """,
        (user_id,),
    ).fetchall()

    return {int(row["movie_id"]) for row in rows}


@router.get("/friends/{friend_id}/recommendations")
def joint_friend_recommendations(
    request: Request,
    friend_id: int,
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user),
):
    """
    Recommend movies for the current user and an accepted friend.

    Uses both users' saved ratings with the existing item-based model.
    Movies watched by either user are excluded.
    """
    if friend_id == user_id:
        raise HTTPException(status_code=400, detail="You cannot recommend movies with yourself.")

    with get_db() as db:
        friendship = db.execute(
            """
            SELECT 1
            FROM friendships
            WHERE user_id = ? AND friend_id = ?
            """,
            (user_id, friend_id),
        ).fetchone()

        if not friendship:
            raise HTTPException(
                status_code=403,
                detail="Joint recommendations are available only with an accepted friend.",
            )

        friend_row = db.execute(
            "SELECT id, username FROM users WHERE id = ?",
            (friend_id,),
        ).fetchone()

        if not friend_row:
            raise HTTPException(status_code=404, detail="Friend not found.")

        my_ratings = _get_friend_ratings(db, user_id)
        friend_ratings = _get_friend_ratings(db, friend_id)

        watched_by_either = (
            _get_watched_movies(db, user_id)
            | _get_watched_movies(db, friend_id)
        )

    if not my_ratings or not friend_ratings:
        raise HTTPException(
            status_code=400,
            detail="Both users must rate at least one movie before joint recommendations can be generated.",
        )

    resources = getattr(request.app.state, "resources", None)
    if resources is None:
        raise HTTPException(status_code=503, detail="Recommendation resources are not loaded.")

    model = resources.get("item")
    if model is None:
        raise HTTPException(status_code=503, detail="The item-based recommendation model is unavailable.")

    movies = resources["movies"]
    movie_to_index = model["movie_to_index"]
    movie_ids = model["movie_ids"]
    neighbor_indices = model["neighbor_indices"]
    neighbor_similarities = model["neighbor_similarities"]

    # Build an independent preference score for each person.
    def score_for_user(ratings):
        known_ratings = {
            movie_id: rating
            for movie_id, rating in ratings.items()
            if movie_id in movie_to_index
        }

        if not known_ratings:
            return {}

        user_mean = float(np.mean(list(known_ratings.values())))
        score_totals = {}
        similarity_totals = {}

        for rated_movie_id, rating in known_ratings.items():
            source_index = movie_to_index.get(rated_movie_id)
            if source_index is None:
                continue

            for neighbor_index, similarity in zip(
                neighbor_indices[source_index],
                neighbor_similarities[source_index],
            ):
                similarity = float(similarity)
                if similarity <= 0:
                    continue

                candidate_id = int(movie_ids[neighbor_index])
                if candidate_id in known_ratings or candidate_id in watched_by_either:
                    continue

                score_totals[candidate_id] = (
                    score_totals.get(candidate_id, 0.0)
                    + similarity * (rating - user_mean)
                )
                similarity_totals[candidate_id] = (
                    similarity_totals.get(candidate_id, 0.0) + similarity
                )

        scores = {}
        for candidate_id, total in score_totals.items():
            similarity_sum = similarity_totals[candidate_id]
            if similarity_sum > 0:
                predicted = user_mean + total / (similarity_sum + 5.0)
                scores[candidate_id] = float(np.clip(predicted, 0.5, 5.0))

        return scores

    my_scores = score_for_user(my_ratings)
    friend_scores = score_for_user(friend_ratings)

    # Favor titles that receive support from both users.
    shared_candidates = set(my_scores) & set(friend_scores)
    combined = []

    movie_lookup = movies.set_index("movieId", drop=False)

    for movie_id in shared_candidates:
        if movie_id in watched_by_either or movie_id not in movie_lookup.index:
            continue

        my_score = my_scores[movie_id]
        friend_score = friend_scores[movie_id]
        average_score = (my_score + friend_score) / 2.0

        # A small agreement bonus favors movies both users are predicted to enjoy.
        agreement = 5.0 - abs(my_score - friend_score)
        compatibility = float(np.clip(average_score + agreement * 0.1, 0.5, 5.0))

        row = movie_lookup.loc[movie_id]
        if hasattr(row, "iloc"):
            row = row.iloc[0]

        movie = row.to_dict()
        for key, value in list(movie.items()):
            if isinstance(value, float) and np.isnan(value):
                movie[key] = None

        title = str(movie.get("title") or "")
        import re
        year_match = re.search(r"\((\d{4})\)\s*$", title)
        genres = movie.get("genres") or ""
        movie["movieId"] = int(movie["movieId"])
        movie["year"] = int(year_match.group(1)) if year_match else None
        movie["genres"] = (
            [] if genres in ("", "(no genres listed)")
            else str(genres).split("|")
        )
        movie["my_predicted_rating"] = round(my_score, 2)
        movie["friend_predicted_rating"] = round(friend_score, 2)
        movie["compatibility_score"] = round(compatibility, 2)
        combined.append(movie)

    combined.sort(key=lambda item: item["compatibility_score"], reverse=True)
    results = combined[:limit]

    return {
        "friend": dict(friend_row),
        "count": len(results),
        "results": results,
        "message": (
            "Recommendations are based on movies both users are predicted to enjoy."
            if results
            else "No shared recommendations found yet. Rate more movies to improve results."
        ),
    }
