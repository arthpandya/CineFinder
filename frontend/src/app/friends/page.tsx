
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users, Search, UserPlus, ArrowLeft, Loader2, CheckCircle,
  UserRound, UserCheck, XCircle, RefreshCw, Trash2, Film,
  Bookmark, Clock, Star, Eye, ArrowLeftRight
} from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type FriendUser = {
  id: number;
  username: string;
  first_name?: string | null;
  last_name?: string | null;
};

type FriendRequest = {
  id: number;
  username: string;
};

type MovieEntry = {
  movie_id: number;
  list_type: string;
  rating: number | null;
};

type MovieInfo = {
  movieId: number;
  title: string;
  genres: string[];
  year?: number | null;
};

type FriendDetails = {
  friend: FriendUser & {
    date_of_birth?: string | null;
    gender?: string | null;
  };
  movies: MovieEntry[];
};

type TabType = "watched" | "watch_later" | "saved" | "rated";

type JointRecommendation = MovieInfo & {
  predicted_rating?: number;
  my_predicted_rating: number;
  friend_predicted_rating: number;
  compatibility_score: number;
};

export default function FriendsPage() {
  const [token, setToken] = useState("");
  const [authReady, setAuthReady] = useState(false);

  const [username, setUsername] = useState("");
  const [results, setResults] = useState<FriendUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [sendingId, setSendingId] = useState<number | null>(null);
  const [sentRequests, setSentRequests] = useState<number[]>([]);

  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);

  const [friends, setFriends] = useState<FriendUser[]>([]);
  const [friendsLoading, setFriendsLoading] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const [selectedFriend, setSelectedFriend] =
    useState<FriendDetails | null>(null);
  const [selectedTab, setSelectedTab] = useState<TabType>("watched");
  const [detailsLoading, setDetailsLoading] = useState(false);

  const [jointRecommendations, setJointRecommendations] = useState<JointRecommendation[]>([]);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [recommendationsMessage, setRecommendationsMessage] = useState("");

  const [movieCatalog, setMovieCatalog] = useState<
    Record<number, MovieInfo>
  >({});

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const savedToken = localStorage.getItem("cinefinder_token");

    if (savedToken) {
      setToken(savedToken);
    }

    setAuthReady(true);
  }, []);

  useEffect(() => {
    if (token) {
      loadRequests();
      loadFriends();
    }
  }, [token]);

  async function apiFetch(path: string, options: RequestInit = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }

    return data;
  }

  async function loadRequests() {
    if (!token) return;

    setRequestsLoading(true);

    try {
      const data = await apiFetch("/auth/friends/requests");
      setRequests(data.requests || []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load requests."
      );
    } finally {
      setRequestsLoading(false);
    }
  }

  async function loadFriends() {
    if (!token) return;

    setFriendsLoading(true);

    try {
      const data = await apiFetch("/auth/friends");
      setFriends(data.friends || []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load friends."
      );
    } finally {
      setFriendsLoading(false);
    }
  }

  async function searchUsers(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage("");
    setError("");
    setResults([]);

    if (username.trim().length < 3) {
      setError("Enter at least 3 characters to search.");
      return;
    }

    setLoading(true);

    try {
      const data = await apiFetch(
        `/auth/friends/search?username=${encodeURIComponent(username.trim())}`
      );

      setResults(data.users || []);

      if (!data.users?.length) {
        setMessage("No users found. Try another username.");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not search users."
      );
    } finally {
      setLoading(false);
    }
  }

  async function sendFriendRequest(user: FriendUser) {
    setSendingId(user.id);
    setMessage("");
    setError("");

    try {
      await apiFetch("/auth/friends/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username }),
      });

      setSentRequests((previous) => [...previous, user.id]);
      setMessage(`Friend request sent to ${user.username}!`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not send request."
      );
    } finally {
      setSendingId(null);
    }
  }

  async function handleRequest(
    requestId: number,
    action: "accept" | "reject"
  ) {
    setProcessingId(requestId);
    setMessage("");
    setError("");

    try {
      await apiFetch(
        `/auth/friends/requests/${requestId}/${action}`,
        { method: "POST" }
      );

      setRequests((previous) =>
        previous.filter((request) => request.id !== requestId)
      );

      if (action === "accept") {
        await loadFriends();
        setMessage("Friend request accepted successfully!");
      } else {
        setMessage("Friend request rejected.");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not process request."
      );
    } finally {
      setProcessingId(null);
    }
  }

  async function loadMovieCatalog() {
    if (Object.keys(movieCatalog).length > 0) return;

    const firstPageResponse = await fetch(
      `${API_BASE}/movies?page=1&limit=100`
    );

    if (!firstPageResponse.ok) {
      throw new Error("Could not load movie information.");
    }

    const firstPage = await firstPageResponse.json();
    const allMovies: MovieInfo[] = [...(firstPage.results || [])];

    const totalPages = Math.ceil((firstPage.total || 0) / 100);

    if (totalPages > 1) {
      const remainingPages = await Promise.all(
        Array.from({ length: totalPages - 1 }, (_, index) =>
          fetch(`${API_BASE}/movies?page=${index + 2}&limit=100`)
            .then((response) => {
              if (!response.ok) {
                throw new Error("Could not load movie information.");
              }
              return response.json();
            })
        )
      );

      remainingPages.forEach((page) => {
        allMovies.push(...(page.results || []));
      });
    }

    const catalog: Record<number, MovieInfo> = {};

    allMovies.forEach((movie) => {
      catalog[movie.movieId] = movie;
    });

    setMovieCatalog(catalog);
    return catalog;
  }

  async function viewFriend(friendId: number) {
    setDetailsLoading(true);
    setError("");
    setSelectedFriend(null);
    setSelectedTab("watched");
    setJointRecommendations([]);
    setRecommendationsMessage("");

    try {
      const data: FriendDetails = await apiFetch(
        `/auth/friends/${friendId}/details`
      );

      setSelectedFriend(data);

      await loadMovieCatalog();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load friend profile."
      );
    } finally {
      setDetailsLoading(false);
    }
  }

  async function generateJointRecommendations() {
    if (!selectedFriend) return;

    setRecommendationsLoading(true);
    setJointRecommendations([]);
    setRecommendationsMessage("");
    setError("");

    try {
      const data = await apiFetch(
        `/social/friends/${selectedFriend.friend.id}/recommendations?limit=20`
      );

      setJointRecommendations(data.results || []);
      setRecommendationsMessage(
        data.message ||
          (data.results?.length
            ? "Recommendations generated."
            : "No shared recommendations found yet.")
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not generate joint recommendations."
      );
    } finally {
      setRecommendationsLoading(false);
    }
  }

  async function removeFriend(friend: FriendUser) {
    const confirmed = window.confirm(
      `Are you sure you want to remove ${friend.username} from your friends?`
    );

    if (!confirmed) return;

    setRemovingId(friend.id);
    setError("");
    setMessage("");

    try {
      await apiFetch(`/auth/friends/${friend.id}`, {
        method: "DELETE",
      });

      setFriends((previous) =>
        previous.filter((item) => item.id !== friend.id)
      );

      if (selectedFriend?.friend.id === friend.id) {
        setSelectedFriend(null);
      }

      setMessage(`${friend.username} has been removed from your friends.`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not remove friend."
      );
    } finally {
      setRemovingId(null);
    }
  }

  if (!authReady) {
    return (
      <main className="min-h-screen bg-[#090b13] flex items-center justify-center text-white">
        <Loader2 className="animate-spin text-purple-400" size={32} />
      </main>
    );
  }

  if (!token) {
    return (
      <main className="min-h-screen bg-[#090b13] flex items-center justify-center p-6 text-white">
        <div className="rounded-2xl border border-white/10 bg-[#121520] p-8 text-center">
          <Users size={42} className="mx-auto mb-4 text-purple-400" />
          <h1 className="text-2xl font-bold mb-3">Login Required</h1>
          <p className="text-gray-400 mb-5">
            Log in to CineFinder to connect with friends.
          </p>
          <Link href="/" className="text-purple-400 hover:text-purple-300">
            Back to CineFinder
          </Link>
        </div>
      </main>
    );
  }

  const activeMovies =
    selectedFriend?.movies.filter(
      (movie) => movie.list_type === selectedTab
    ) || [];

  const tabOptions: {
    id: TabType;
    label: string;
    icon: typeof Eye;
  }[] = [
    { id: "watched", label: "Watched", icon: Eye },
    { id: "watch_later", label: "Watch Later", icon: Clock },
    { id: "saved", label: "Saved", icon: Bookmark },
    { id: "rated", label: "Rated", icon: Star },
  ];

  return (
    <main className="min-h-screen bg-[#090b13] px-5 py-10 text-white">
      <div className="mx-auto max-w-4xl">

        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm text-purple-400 hover:text-purple-300"
        >
          <ArrowLeft size={16} />
          Back to CineFinder
        </Link>

        <div className="mb-8 flex items-center gap-3">
          <div className="rounded-xl bg-purple-500/15 p-3">
            <Users size={27} className="text-purple-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">CineFinder Social</h1>
            <p className="text-sm text-gray-400">
              Find friends and explore their movie interests.
            </p>
          </div>
        </div>

        {message && (
          <div className="mb-5 flex items-center gap-2 rounded-xl border border-green-500/20 bg-green-500/10 p-4 text-sm text-green-400">
            <CheckCircle size={18} />
            {message}
          </div>
        )}

        {error && (
          <div className="mb-5 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* FRIEND PROFILE */}
        {selectedFriend && (
          <section className="mb-8 rounded-2xl border border-purple-500/30 bg-[#121520] p-6">
            <button
              onClick={() => setSelectedFriend(null)}
              className="mb-5 flex items-center gap-2 text-sm text-purple-400 hover:text-purple-300"
            >
              <ArrowLeft size={16} />
              Back to friends
            </button>

            <div className="mb-6 flex items-center gap-4">
              <div className="rounded-full bg-purple-500/15 p-4">
                <UserRound size={32} className="text-purple-400" />
              </div>
              <div>
                <h2 className="text-2xl font-bold">
                  {selectedFriend.friend.first_name ||
                  selectedFriend.friend.last_name
                    ? `${selectedFriend.friend.first_name || ""} ${selectedFriend.friend.last_name || ""}`.trim()
                    : selectedFriend.friend.username}
                </h2>
                <p className="text-sm text-gray-400">
                  @{selectedFriend.friend.username}
                </p>
              </div>
            </div>

            {/* JOINT MOVIE RECOMMENDATIONS */}
            <div className="mb-6 rounded-xl border border-purple-500/20 bg-purple-500/5 p-4">
              <div className="mb-3 flex items-center gap-2">
                <ArrowLeftRight size={19} className="text-purple-400" />
                <div>
                  <h3 className="font-semibold">Recommend Together</h3>
                  <p className="text-xs text-gray-400">
                    Find movies you and @{selectedFriend.friend.username} may both enjoy.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={generateJointRecommendations}
                disabled={recommendationsLoading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-purple-600 px-4 py-3 text-sm font-semibold hover:bg-purple-500 disabled:opacity-50 sm:w-auto"
              >
                {recommendationsLoading ? (
                  <Loader2 size={17} className="animate-spin" />
                ) : (
                  <Film size={17} />
                )}
                {recommendationsLoading ? "Finding movies..." : "Generate Recommendations"}
              </button>

              {recommendationsMessage && (
                <p className="mt-3 text-sm text-gray-300">
                  {recommendationsMessage}
                </p>
              )}

              {jointRecommendations.length > 0 && (
                <div className="mt-4 space-y-3">
                  {jointRecommendations.map((movie) => (
                    <div
                      key={movie.movieId}
                      className="rounded-xl border border-white/10 bg-[#171923] p-4"
                    >
                      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                        <div className="min-w-0">
                          <h4 className="font-semibold">
                            {movie.title}
                          </h4>
                          <p className="mt-1 text-xs text-gray-500">
                            {movie.year || "Year unknown"}
                            {movie.genres?.length
                              ? ` • ${movie.genres.join(", ")}`
                              : ""}
                          </p>
                        </div>
                        <div className="shrink-0 rounded-lg bg-purple-500/15 px-3 py-2 text-center">
                          <p className="text-lg font-bold text-purple-300">
                            {movie.compatibility_score.toFixed(1)}/5
                          </p>
                          <p className="text-[10px] text-gray-400">
                            Compatibility
                          </p>
                        </div>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <div className="rounded-lg bg-white/5 p-2">
                          <p className="text-xs text-gray-500">Your predicted rating</p>
                          <p className="mt-1 flex items-center gap-1 font-semibold text-yellow-400">
                            <Star size={14} fill="currentColor" />
                            {movie.my_predicted_rating.toFixed(1)}/5
                          </p>
                        </div>
                        <div className="rounded-lg bg-white/5 p-2">
                          <p className="text-xs text-gray-500">
                            @{selectedFriend.friend.username}'s predicted rating
                          </p>
                          <p className="mt-1 flex items-center gap-1 font-semibold text-yellow-400">
                            <Star size={14} fill="currentColor" />
                            {movie.friend_predicted_rating.toFixed(1)}/5
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {tabOptions.map((tab) => {
                const Icon = tab.icon;
                const count = selectedFriend.movies.filter(
                  (movie) => movie.list_type === tab.id
                ).length;

                return (
                  <div
                    key={tab.id}
                    className="rounded-xl border border-white/10 bg-[#171923] p-3"
                  >
                    <Icon size={18} className="mb-2 text-purple-400" />
                    <p className="text-xl font-bold">{count}</p>
                    <p className="text-xs text-gray-400">{tab.label}</p>
                  </div>
                );
              })}
            </div>

            <div className="mb-5 flex flex-wrap gap-2">
              {tabOptions.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSelectedTab(tab.id)}
                  className={`rounded-xl px-4 py-2 text-sm font-medium ${
                    selectedTab === tab.id
                      ? "bg-purple-600 text-white"
                      : "border border-white/10 bg-[#171923] text-gray-400 hover:text-white"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {detailsLoading ? (
              <Loader2 className="mx-auto animate-spin text-purple-400" />
            ) : activeMovies.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/10 p-8 text-center">
                <Film size={32} className="mx-auto mb-3 text-gray-600" />
                <p className="text-gray-400">
                  No movies in this collection yet.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {activeMovies.map((entry, index) => {
                  const movie = movieCatalog[entry.movie_id];

                  return (
                    <div
                      key={`${entry.movie_id}-${entry.list_type}-${index}`}
                      className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-[#171923] p-4"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <Film
                          size={22}
                          className="shrink-0 text-purple-400"
                        />
                        <div className="min-w-0">
                          <h3 className="truncate font-semibold">
                            {movie?.title || `Movie #${entry.movie_id}`}
                          </h3>
                          <p className="text-xs text-gray-500">
                            {movie?.year || ""}
                            {movie?.genres?.length
                              ? ` • ${movie.genres.join(", ")}`
                              : ""}
                          </p>
                        </div>
                      </div>

                      {entry.list_type === "rated" &&
                        entry.rating !== null && (
                          <span className="flex shrink-0 items-center gap-1 text-sm text-yellow-400">
                            <Star size={15} fill="currentColor" />
                            {entry.rating}/5
                          </span>
                        )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {/* MY FRIENDS */}
        {!selectedFriend && (
          <section className="mb-8 rounded-2xl border border-white/10 bg-[#121520] p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">My Friends</h2>
                <p className="text-sm text-gray-400">
                  {friends.length} connected friends
                </p>
              </div>
              <button
                onClick={loadFriends}
                disabled={friendsLoading}
                className="rounded-lg border border-white/10 p-2 text-gray-400 hover:text-white"
                title="Refresh friends"
              >
                {friendsLoading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <RefreshCw size={18} />
                )}
              </button>
            </div>

            {friendsLoading && friends.length === 0 ? (
              <Loader2 className="mx-auto animate-spin text-purple-400" />
            ) : friends.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/10 p-8 text-center">
                <Users size={35} className="mx-auto mb-3 text-gray-600" />
                <p className="text-gray-400">You haven't added any friends yet.</p>
                <p className="mt-1 text-xs text-gray-500">
                  Search for users below to connect with them.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {friends.map((friend) => (
                  <div
                    key={friend.id}
                    className="flex flex-col justify-between gap-4 rounded-xl border border-white/10 bg-[#171923] p-4 sm:flex-row sm:items-center"
                  >
                    <div className="flex items-center gap-3">
                      <div className="rounded-full bg-purple-500/15 p-3">
                        <UserRound size={23} className="text-purple-400" />
                      </div>
                      <div>
                        <h3 className="font-semibold">
                          {friend.first_name || friend.last_name
                            ? `${friend.first_name || ""} ${friend.last_name || ""}`.trim()
                            : friend.username}
                        </h3>
                        <p className="text-xs text-gray-500">
                          @{friend.username}
                        </p>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() => viewFriend(friend.id)}
                        className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium hover:bg-purple-500"
                      >
                        <UserRound size={16} />
                        View Profile
                      </button>

                      <button
                        onClick={() => removeFriend(friend)}
                        disabled={removingId === friend.id}
                        title="Remove friend"
                        className="rounded-lg border border-red-500/30 px-3 py-2 text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                      >
                        {removingId === friend.id ? (
                          <Loader2 size={17} className="animate-spin" />
                        ) : (
                          <Trash2 size={17} />
                        )}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {detailsLoading && !selectedFriend && (
          <div className="mb-6 text-center text-sm text-gray-400">
            <Loader2 className="mx-auto mb-2 animate-spin text-purple-400" />
            Loading friend profile...
          </div>
        )}

        {/* INCOMING REQUESTS */}
        {!selectedFriend && (
          <section className="mb-8 rounded-2xl border border-white/10 bg-[#121520] p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">
                  Friend Requests
                  {requests.length > 0 && (
                    <span className="ml-2 rounded-full bg-purple-500/20 px-2 py-1 text-xs text-purple-300">
                      {requests.length}
                    </span>
                  )}
                </h2>
                <p className="mt-1 text-sm text-gray-400">
                  Manage incoming friend requests.
                </p>
              </div>

              <button
                onClick={loadRequests}
                disabled={requestsLoading}
                className="rounded-lg border border-white/10 p-2 text-gray-400 hover:text-white"
                title="Refresh requests"
              >
                {requestsLoading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <RefreshCw size={18} />
                )}
              </button>
            </div>

            {requestsLoading && requests.length === 0 ? (
              <Loader2 className="mx-auto animate-spin text-purple-400" />
            ) : requests.length === 0 ? (
              <p className="py-5 text-center text-sm text-gray-400">
                No pending friend requests.
              </p>
            ) : (
              <div className="space-y-3">
                {requests.map((request) => (
                  <div
                    key={request.id}
                    className="flex flex-col justify-between gap-3 rounded-xl border border-white/10 bg-[#171923] p-4 sm:flex-row sm:items-center"
                  >
                    <div className="flex items-center gap-3">
                      <UserRound size={22} className="text-purple-400" />
                      <span className="font-medium">{request.username}</span>
                    </div>

                    <div className="flex gap-2">
                      <button
                        disabled={processingId === request.id}
                        onClick={() => handleRequest(request.id, "accept")}
                        className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm hover:bg-green-500 disabled:opacity-50"
                      >
                        {processingId === request.id ? (
                          <Loader2 size={16} className="animate-spin" />
                        ) : (
                          <CheckCircle size={16} />
                        )}
                        Accept
                      </button>

                      <button
                        disabled={processingId === request.id}
                        onClick={() => handleRequest(request.id, "reject")}
                        className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-red-500/30 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                      >
                        <XCircle size={16} />
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* SEARCH USERS */}
        {!selectedFriend && (
          <section className="rounded-2xl border border-white/10 bg-[#121520] p-6">
            <h2 className="mb-2 text-xl font-semibold">Find Friends</h2>
            <p className="mb-5 text-sm text-gray-400">
              Search CineFinder users by username.
            </p>

            <form
              onSubmit={searchUsers}
              className="flex flex-col gap-3 sm:flex-row"
            >
              <div className="relative flex-1">
                <Search
                  size={18}
                  className="absolute left-4 top-3.5 text-gray-500"
                />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username..."
                  className="w-full rounded-xl border border-white/10 bg-[#171923] py-3 pl-11 pr-4 text-white outline-none focus:border-purple-500"
                  minLength={3}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="flex items-center justify-center gap-2 rounded-xl bg-purple-600 px-6 py-3 font-semibold hover:bg-purple-500 disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Search size={18} />
                )}
                Search
              </button>
            </form>

            {results.length > 0 && (
              <div className="mt-5 space-y-3">
                {results.map((user) => {
                  const requestSent = sentRequests.includes(user.id);
                  const alreadyFriend = friends.some(
                    (friend) => friend.id === user.id
                  );

                  return (
                    <div
                      key={user.id}
                      className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-[#171923] p-4"
                    >
                      <div className="flex items-center gap-3">
                        <UserRound size={22} className="text-purple-400" />
                        <span className="font-medium">{user.username}</span>
                      </div>

                      <button
                        type="button"
                        disabled={
                          requestSent ||
                          alreadyFriend ||
                          sendingId === user.id
                        }
                        onClick={() => sendFriendRequest(user)}
                        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm ${
                          requestSent || alreadyFriend
                            ? "bg-green-500/10 text-green-400"
                            : "bg-purple-600 hover:bg-purple-500"
                        } disabled:opacity-60`}
                      >
                        {sendingId === user.id ? (
                          <Loader2 size={16} className="animate-spin" />
                        ) : alreadyFriend ? (
                          <UserCheck size={16} />
                        ) : requestSent ? (
                          <CheckCircle size={16} />
                        ) : (
                          <UserPlus size={16} />
                        )}
                        {alreadyFriend
                          ? "Friends"
                          : requestSent
                          ? "Request Sent"
                          : "Add Friend"}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
