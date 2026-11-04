
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Profile = {
  username: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  gender: string | null;
};

export default function ProfilePage() {
  const [token, setToken] = useState("");
  const [userMovies, setUserMovies] = useState<
  { movie_id: number; list_type: string; rating: number | null }[]
>([]);

const [activeCollection, setActiveCollection] = useState("saved");
const [allMovies, setAllMovies] = useState<
  {
    movieId: number;
    title: string;
    genres: string[];
    year?: number | null;
  }[]
>([]);
  const [profile, setProfile] = useState<Profile>({
    username: "",
    first_name: "",
    last_name: "",
    date_of_birth: "",
    gender: "",
  });

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const savedToken = localStorage.getItem("cinefinder_token");

    if (!savedToken) {
      setLoading(false);
      return;
    }

    setToken(savedToken);
    fetchUserMovies(savedToken);

    fetch(`${API_BASE}/auth/profile`, {
      headers: {
        Authorization: `Bearer ${savedToken}`,
      },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Could not load your profile.");
        }
        return response.json();
      })
      .then((data) => {
        setProfile({
          username: data.username || "",
          first_name: data.first_name || "",
          last_name: data.last_name || "",
          date_of_birth: data.date_of_birth || "",
          gender: data.gender || "",
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function saveProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage("");
    setError("");
    setSavingProfile(true);

    try {
      const response = await fetch(`${API_BASE}/auth/profile`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          first_name: profile.first_name,
          last_name: profile.last_name,
          date_of_birth: profile.date_of_birth || null,
          gender: profile.gender || null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not update profile.");
      }

      setMessage("Profile updated successfully!");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong."
      );
    } finally {
      setSavingProfile(false);
    }
  }

  async function changePassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage("");
    setError("");

    if (newPassword !== confirmPassword) {
      setError("New password and confirm password do not match.");
      return;
    }

    if (newPassword.length < 6) {
      setError("New password must contain at least 6 characters.");
      return;
    }

    setChangingPassword(true);

    try {
      const response = await fetch(`${API_BASE}/auth/change-password`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not change password.");
      }

      setMessage("Password changed successfully!");

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong."
      );
    } finally {
      setChangingPassword(false);
    }
  }

  
async function fetchUserMovies(savedToken: string) {
  try {
    // Fetch user's collections
    const listResponse = await fetch(`${API_BASE}/auth/lists`, {
      headers: {
        Authorization: `Bearer ${savedToken}`,
      },
    });

    if (!listResponse.ok) {
      throw new Error("Unable to load your collections.");
    }

    const listData = await listResponse.json();
    setUserMovies(listData.movies || []);

    // Fetch all movies in batches of 100
    const firstResponse = await fetch(
      `${API_BASE}/movies?page=1&limit=100`
    );

    if (!firstResponse.ok) {
      throw new Error("Unable to load movie details.");
    }

    const firstData = await firstResponse.json();
    let movies = firstData.results || [];

    const totalPages = Math.ceil(firstData.total / 100);

    for (let page = 2; page <= totalPages; page++) {
      const response = await fetch(
        `${API_BASE}/movies?page=${page}&limit=100`
      );

      if (!response.ok) {
        throw new Error(`Failed to load movies on page ${page}.`);
      }

      const data = await response.json();
      movies = movies.concat(data.results || []);
    }

    setAllMovies(movies);

  } catch (err) {
    setError(
      err instanceof Error ? err.message : "Could not load collections."
    );
  }
}


async function removeMovie(movieId: number, listType: string) {
  try {
    const response = await fetch(
      `${API_BASE}/auth/lists/${movieId}/${listType}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error("Could not remove movie.");
    }

    setUserMovies((previous) =>
      previous.filter(
        (item) =>
          !(item.movie_id === movieId && item.list_type === listType)
      )
    );

  } catch (err) {
    setError(
      err instanceof Error ? err.message : "Something went wrong."
    );
  }
}

async function updateMovieRating(movieId: number, rating: number) {
  setError("");
  setMessage("");

  try {
    const response = await fetch(`${API_BASE}/auth/lists`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        movie_id: movieId,
        list_type: "rated",
        rating,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Could not update movie rating.");
    }

    setUserMovies((previous) =>
      previous.map((item) =>
        item.movie_id === movieId && item.list_type === "rated"
          ? { ...item, rating }
          : item
      )
    );

    setMessage("Movie rating updated successfully!");
  } catch (err) {
    setError(
      err instanceof Error ? err.message : "Something went wrong."
    );
  }
}


  const inputClass =
    "w-full rounded-xl border border-white/10 bg-[#171923] px-4 py-3 text-white outline-none transition focus:border-purple-500";

  if (loading) {
    return (
      <main className="min-h-screen bg-[#090b13] p-8 text-white">
        Loading profile...
      </main>
    );
  }

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#090b13] p-6 text-white">
        <div className="rounded-2xl border border-white/10 bg-[#121520] p-8 text-center">
          <h1 className="mb-3 text-2xl font-bold">Login Required</h1>
          <p className="mb-5 text-gray-400">
            Please log in to access your profile.
          </p>
          <Link href="/" className="text-purple-400 hover:text-purple-300">
            Back to CineFinder
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#090b13] px-5 py-10 text-white">
      <div className="mx-auto max-w-3xl">

        <Link
          href="/"
          className="mb-8 inline-block text-sm text-purple-400 hover:text-purple-300"
        >
          ← Back to CineFinder
        </Link>

        <h1 className="mb-2 text-3xl font-bold">My Profile</h1>
        <p className="mb-8 text-gray-400">
          Manage your personal information and account security.
        </p>

        {message && (
          <div className="mb-5 rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-green-400">
            {message}
          </div>
        )}

        {error && (
          <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-400">
            {error}
          </div>
        )}

        {/* Personal Information */}
        <section className="mb-8 rounded-2xl border border-white/10 bg-[#121520] p-6">
          <h2 className="mb-6 text-xl font-semibold">
            Personal Information
          </h2>

          <form onSubmit={saveProfile} className="space-y-5">
            <div>
              <label className="mb-2 block text-sm text-gray-400">
                Username
              </label>
              <input
                value={profile.username}
                disabled
                className={`${inputClass} cursor-not-allowed opacity-60`}
              />
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm text-gray-400">
                  First Name
                </label>
                <input
                  value={profile.first_name}
                  onChange={(e) =>
                    setProfile({ ...profile, first_name: e.target.value })
                  }
                  className={inputClass}
                  placeholder="First name"
                  maxLength={50}
                />
              </div>

              <div>
                <label className="mb-2 block text-sm text-gray-400">
                  Last Name
                </label>
                <input
                  value={profile.last_name}
                  onChange={(e) =>
                    setProfile({ ...profile, last_name: e.target.value })
                  }
                  className={inputClass}
                  placeholder="Last name"
                  maxLength={50}
                />
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm text-gray-400">
                Date of Birth
              </label>
              <input
                type="date"
                value={profile.date_of_birth || ""}
                onChange={(e) =>
                  setProfile({ ...profile, date_of_birth: e.target.value })
                }
                className={inputClass}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm text-gray-400">
                Gender
              </label>
              <select
                value={profile.gender || ""}
                onChange={(e) =>
                  setProfile({ ...profile, gender: e.target.value })
                }
                className={inputClass}
              >
                <option value="">Select gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={savingProfile}
              className="rounded-xl bg-purple-600 px-6 py-3 font-semibold hover:bg-purple-500 disabled:opacity-50"
            >
              {savingProfile ? "Saving..." : "Save Profile"}
            </button>
          </form>
        </section>

        {/* Change Password */}
        
{/* My Collections */}
<section className="mb-8 rounded-2xl border border-white/10 bg-[#121520] p-6">
  <h2 className="mb-2 text-xl font-semibold">My Collections</h2>
  <p className="mb-6 text-sm text-gray-400">
    Your personal movie library.
  </p>

  <div className="mb-6 flex flex-wrap gap-2">
    {[
      { id: "saved", label: "Saved" },
      { id: "watch_later", label: "Watch Later" },
      { id: "watched", label: "Watched" },
      { id: "rated", label: "Rated" },
    ].map((tab) => (
      <button
        key={tab.id}
        onClick={() => setActiveCollection(tab.id)}
        className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
          activeCollection === tab.id
            ? "bg-purple-600 text-white"
            : "bg-white/5 text-gray-400 hover:bg-white/10"
        }`}
      >
        {tab.label}
      </button>
    ))}
  </div>

  <div className="grid gap-3 sm:grid-cols-2">
    {userMovies
      .filter((item) => item.list_type === activeCollection)
      .map((item, index) => {
        const movie = allMovies.find(
          (m) => m.movieId === item.movie_id
        );

        if (!movie) return null;

        return (
          <div
            key={`${item.movie_id}-${item.list_type}-${index}`}
            className="rounded-xl border border-white/10 bg-white/5 p-4"
          >
            <h3 className="font-semibold text-white">
              {movie.title}
            </h3>

            <p className="mt-2 text-xs text-gray-400">
              {movie.year || "Year unavailable"}
            </p>

            <div className="mt-2 flex flex-wrap gap-1">
              {movie.genres.map((genre) => (
                <span
                  key={genre}
                  className="rounded-full bg-purple-500/10 px-2 py-1 text-xs text-purple-300"
                >
                  {genre}
                </span>
              ))}
            </div>

            {item.list_type === "rated" && (
              <div className="mt-3">
                <p className="text-sm text-yellow-400">
                  ★ {item.rating}/5
                </p>

                <button
                  type="button"
                  onClick={() => {
                    const enteredRating = window.prompt(
                      "Enter a new rating (1 to 5):",
                      String(item.rating ?? 5)
                    );

                    if (enteredRating === null) return;

                    const newRating = Number(enteredRating);

                    if (
                      !Number.isInteger(newRating) ||
                      newRating < 1 ||
                      newRating > 5
                    ) {
                      setError("Please enter a whole-number rating from 1 to 5.");
                      return;
                    }

                    updateMovieRating(item.movie_id, newRating);
                  }}
                  className="mt-3 rounded-lg border border-purple-500/30 px-3 py-2 text-sm text-purple-400 hover:bg-purple-500/10"
                >
                  Edit Rating
                </button>
              </div>
            )}
            
            <button
  onClick={() => removeMovie(item.movie_id, item.list_type)}
  className="mt-4 rounded-lg border border-red-500/30 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"
>
  Remove from collection
</button>
          </div>
        );
      })}
  </div>

  {userMovies.filter(
    (item) => item.list_type === activeCollection
  ).length === 0 && (
    <p className="py-8 text-center text-sm text-gray-500">
      No movies in this collection yet.
    </p>
  )}
</section>

        <section className="rounded-2xl border border-white/10 bg-[#121520] p-6">
          <h2 className="mb-2 text-xl font-semibold">Change Password</h2>
          <p className="mb-6 text-sm text-gray-400">
            Update your password to keep your account secure.
          </p>

          <form onSubmit={changePassword} className="space-y-5">
            <div>
              <label className="mb-2 block text-sm text-gray-400">
                Current Password
              </label>
              <div className="relative">
                <input
                  type={showCurrent ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className={inputClass}
                  placeholder="Enter current password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  className="absolute right-4 top-3 text-sm text-purple-400"
                >
                  {showCurrent ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm text-gray-400">
                New Password
              </label>
              <div className="relative">
                <input
                  type={showNew ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className={inputClass}
                  placeholder="Enter new password"
                  minLength={6}
                  maxLength={128}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-4 top-3 text-sm text-purple-400"
                >
                  {showNew ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm text-gray-400">
                Confirm New Password
              </label>
              <div className="relative">
                <input
                  type={showConfirm ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className={inputClass}
                  placeholder="Confirm new password"
                  minLength={6}
                  maxLength={128}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-4 top-3 text-sm text-purple-400"
                >
                  {showConfirm ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={changingPassword}
              className="rounded-xl bg-purple-600 px-6 py-3 font-semibold hover:bg-purple-500 disabled:opacity-50"
            >
              {changingPassword ? "Changing..." : "Change Password"}
            </button>
          </form>
        </section>

      </div>
    </main>
  );
}
