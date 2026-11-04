
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field


router = APIRouter(prefix="/auth", tags=["Authentication"])

DB_PATH = Path(__file__).resolve().parent.parent / "cinefinder.db"

SECRET_KEY = os.getenv("CINEFINDER_SECRET_KEY", "change-this-before-deployment")
ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()
security = HTTPBearer()


# Database setup
def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_auth_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
                # Add profile fields to existing accounts
        columns = [
            ("first_name", "TEXT"),
            ("last_name", "TEXT"),
            ("date_of_birth", "TEXT"),
            ("gender", "TEXT")
        ]

        existing_columns = [
            row["name"]
            for row in db.execute("PRAGMA table_info(users)").fetchall()
        ]

        for column_name, column_type in columns:
            if column_name not in existing_columns:
                db.execute(
                    f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                )

        # Friend requests
        db.execute("""
            CREATE TABLE IF NOT EXISTS friend_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sender_id, receiver_id),
                FOREIGN KEY(sender_id) REFERENCES users(id),
                FOREIGN KEY(receiver_id) REFERENCES users(id)
            )
        """)

        # Accepted friendships
        db.execute("""
            CREATE TABLE IF NOT EXISTS friendships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, friend_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(friend_id) REFERENCES users(id)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS user_movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                movie_id INTEGER NOT NULL,
                list_type TEXT NOT NULL,
                rating REAL,
                UNIQUE(user_id, movie_id, list_type),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)


# Request models
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)

class FriendRequestModel(BaseModel):
    username: str = Field(min_length=3, max_length=30)

class ProfileUpdateRequest(BaseModel):
    first_name: str = Field(default="", max_length=50)
    last_name: str = Field(default="", max_length=50)
    date_of_birth: str | None = None
    gender: str | None = None


class MovieListRequest(BaseModel):
    movie_id: int = Field(gt=0)
    list_type: str
    rating: float | None = Field(default=None, ge=0.5, le=5.0)


# Token helpers
def create_token(user_id: int):
    expires = datetime.now(timezone.utc) + timedelta(days=7)

    return jwt.encode(
        {"sub": str(user_id), "exp": expires},
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired login")


# Registration
@router.post("/register")
def register(data: RegisterRequest):
    username = data.username.strip().lower()

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    hashed = password_hash.hash(data.password)

    try:
        with get_db() as db:
            cursor = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hashed)
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists")

    return {
        "message": "Account created successfully",
        "user_id": user_id
    }


# Login
@router.post("/login")
def login(data: LoginRequest):
    username = data.username.strip().lower()

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

    if not user or not password_hash.verify(
        data.password, user["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    return {
        "access_token": create_token(user["id"]),
        "token_type": "bearer",
        "username": user["username"],
        "user_id": user["id"]
    }


# Current account
@router.get("/me")
def get_me(user_id: int = Depends(get_current_user)):
    with get_db() as db:
        user = db.execute(
            "SELECT id, username FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    return dict(user)

# Get user profile
@router.get("/profile")
def get_profile(user_id: int = Depends(get_current_user)):
    with get_db() as db:
        user = db.execute(
            """
            SELECT username, first_name, last_name,
                   date_of_birth, gender
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    return dict(user)


# Update user profile
@router.put("/profile")
def update_profile(
    data: ProfileUpdateRequest,
    user_id: int = Depends(get_current_user)
):
    allowed_genders = ["Male", "Female", "Other", "Prefer not to say"]

    if data.gender and data.gender not in allowed_genders:
        raise HTTPException(status_code=400, detail="Invalid gender")

    with get_db() as db:
        db.execute(
            """
            UPDATE users
            SET first_name = ?,
                last_name = ?,
                date_of_birth = ?,
                gender = ?
            WHERE id = ?
            """,
            (
                data.first_name,
                data.last_name,
                data.date_of_birth,
                data.gender,
                user_id
            )
        )

    return {"message": "Profile updated successfully"}

# Change account password
@router.put("/change-password")
def change_password(
    data: ChangePasswordRequest,
    user_id: int = Depends(get_current_user)
):
    with get_db() as db:
        user = db.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user or not password_hash.verify(
            data.current_password, user["password_hash"]
        ):
            raise HTTPException(
                status_code=400,
                detail="Current password is incorrect"
            )

        if data.current_password == data.new_password:
            raise HTTPException(
                status_code=400,
                detail="New password must be different"
            )

        new_hash = password_hash.hash(data.new_password)

        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id)
        )

    return {"message": "Password changed successfully"}

# Get personal movie lists
@router.get("/lists")
def get_lists(user_id: int = Depends(get_current_user)):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT movie_id, list_type, rating
            FROM user_movies
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        ).fetchall()

    return {"movies": [dict(row) for row in rows]}


# Add or update a personal movie list entry
@router.post("/lists")
def add_to_list(
    data: MovieListRequest,
    user_id: int = Depends(get_current_user)
):
    allowed = ["saved", "watch_later", "watched", "rated"]

    if data.list_type not in allowed:
        raise HTTPException(status_code=400, detail="Invalid list type")

    if data.list_type == "rated" and data.rating is None:
        raise HTTPException(status_code=400, detail="Rating is required")

    if data.list_type != "rated" and data.rating is not None:
        raise HTTPException(status_code=400, detail="Rating only applies to rated movies")

    with get_db() as db:
        db.execute(
            """
            INSERT INTO user_movies (user_id, movie_id, list_type, rating)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, movie_id, list_type)
            DO UPDATE SET rating = excluded.rating
            """,
            (user_id, data.movie_id, data.list_type, data.rating)
        )

    return {"message": "Movie list updated successfully"}


# Remove a movie from a personal list
@router.delete("/lists/{movie_id}/{list_type}")
def remove_from_list(
    movie_id: int,
    list_type: str,
    user_id: int = Depends(get_current_user)
):
    with get_db() as db:
        cursor = db.execute(
            """
            DELETE FROM user_movies
            WHERE user_id = ? AND movie_id = ? AND list_type = ?
            """,
            (user_id, movie_id, list_type)
        )

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Movie not found in this list")

    return {"message": "Movie removed successfully"}


# Search users by username
@router.get("/friends/search")
def search_users(
    username: str,
    user_id: int = Depends(get_current_user)
):
    with get_db() as db:
        users = db.execute(
            """
            SELECT id, username, first_name, last_name
            FROM users
            WHERE username LIKE ? AND id != ?
            LIMIT 20
            """,
            (f"%{username.strip().lower()}%", user_id)
        ).fetchall()

    return {"users": [dict(user) for user in users]}


# Send friend request
@router.post("/friends/request")
def send_friend_request(
    data: FriendRequestModel,
    user_id: int = Depends(get_current_user)
):
    with get_db() as db:
        target = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (data.username.strip().lower(),)
        ).fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        friend_id = target["id"]

        if friend_id == user_id:
            raise HTTPException(status_code=400, detail="Cannot add yourself")

        existing = db.execute(
            """
            SELECT id FROM friendships
            WHERE user_id = ? AND friend_id = ?
            """,
            (user_id, friend_id)
        ).fetchone()

        if existing:
            raise HTTPException(status_code=409, detail="Already friends")

        pending = db.execute(
            """
            SELECT id FROM friend_requests
            WHERE sender_id = ? AND receiver_id = ?
            AND status = 'pending'
            """,
            (user_id, friend_id)
        ).fetchone()

        if pending:
            raise HTTPException(status_code=409, detail="Request already sent")

        reverse = db.execute(
            """
            SELECT id FROM friend_requests
            WHERE sender_id = ? AND receiver_id = ?
            AND status = 'pending'
            """,
            (friend_id, user_id)
        ).fetchone()

        if reverse:
            raise HTTPException(
                status_code=409,
                detail="This user has already sent you a request"
            )

        db.execute(
            """
            INSERT INTO friend_requests (sender_id, receiver_id)
            VALUES (?, ?)
            """,
            (user_id, friend_id)
        )

    return {"message": "Friend request sent successfully"}


# View incoming friend requests
@router.get("/friends/requests")
def get_friend_requests(user_id: int = Depends(get_current_user)):
    with get_db() as db:
        requests = db.execute(
            """
            SELECT fr.id, u.id AS user_id, u.username,
                   u.first_name, u.last_name
            FROM friend_requests fr
            JOIN users u ON u.id = fr.sender_id
            WHERE fr.receiver_id = ? AND fr.status = 'pending'
            """,
            (user_id,)
        ).fetchall()

    return {"requests": [dict(request) for request in requests]}


# Accept friend request
@router.post("/friends/requests/{request_id}/accept")
def accept_friend_request(
    request_id: int,
    user_id: int = Depends(get_current_user)
):
    with get_db() as db:
        request = db.execute(
            """
            SELECT sender_id FROM friend_requests
            WHERE id = ? AND receiver_id = ? AND status = 'pending'
            """,
            (request_id, user_id)
        ).fetchone()

        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        friend_id = request["sender_id"]

        db.execute(
            """
            UPDATE friend_requests
            SET status = 'accepted'
            WHERE id = ?
            """,
            (request_id,)
        )

        db.execute(
            """
            INSERT OR IGNORE INTO friendships (user_id, friend_id)
            VALUES (?, ?)
            """,
            (user_id, friend_id)
        )

        db.execute(
            """
            INSERT OR IGNORE INTO friendships (user_id, friend_id)
            VALUES (?, ?)
            """,
            (friend_id, user_id)
        )

    return {"message": "Friend request accepted"}


# Reject friend request
@router.post("/friends/requests/{request_id}/reject")
def reject_friend_request(
    request_id: int,
    user_id: int = Depends(get_current_user)
):
    with get_db() as db:
        cursor = db.execute(
            """
            UPDATE friend_requests
            SET status = 'rejected'
            WHERE id = ? AND receiver_id = ? AND status = 'pending'
            """,
            (request_id, user_id)
        )

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Request not found")

    return {"message": "Friend request rejected"}


# View accepted friends
@router.get("/friends")
def get_friends(user_id: int = Depends(get_current_user)):
    with get_db() as db:
        friends = db.execute(
            """
            SELECT u.id, u.username, u.first_name, u.last_name
            FROM friendships f
            JOIN users u ON u.id = f.friend_id
            WHERE f.user_id = ?
            """,
            (user_id,)
        ).fetchall()

    return {"friends": [dict(friend) for friend in friends]}


# Remove a friend
@router.delete("/friends/{friend_id}")
def remove_friend(
    friend_id: int,
    user_id: int = Depends(get_current_user)
):
    with get_db() as db:
        db.execute(
            """
            DELETE FROM friendships
            WHERE (user_id = ? AND friend_id = ?)
               OR (user_id = ? AND friend_id = ?)
            """,
            (user_id, friend_id, friend_id, user_id)
        )

    return {"message": "Friend removed successfully"}


# View an accepted friend's profile and movie collections
@router.get("/friends/{friend_id}/details")
def get_friend_details(
    friend_id: int,
    user_id: int = Depends(get_current_user)
):
    with get_db() as db:
        friendship = db.execute(
            """
            SELECT id
            FROM friendships
            WHERE user_id = ? AND friend_id = ?
            """,
            (user_id, friend_id)
        ).fetchone()

        if not friendship:
            raise HTTPException(
                status_code=403,
                detail="You can only view the profile of an accepted friend"
            )

        friend = db.execute(
            """
            SELECT id, username, first_name, last_name,
                   date_of_birth, gender
            FROM users
            WHERE id = ?
            """,
            (friend_id,)
        ).fetchone()

        if not friend:
            raise HTTPException(status_code=404, detail="Friend not found")

        movies = db.execute(
            """
            SELECT movie_id, list_type, rating
            FROM user_movies
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (friend_id,)
        ).fetchall()

    return {
        "friend": dict(friend),
        "movies": [dict(movie) for movie in movies]
    }
