"use client";







import { useEffect, useMemo, useRef, useState } from "react";



import {



  ArrowDownRight,



  ArrowRight,



  Bookmark,



  Check,



  ChevronDown,



  Clapperboard,
  Clock,



  Compass,



  Film,



  Flame,



  Heart,



  Menu,



  Play,



  Search,



  Sparkles,



  Star,



  TrendingUp,



  X,



} from "lucide-react";







const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";







type Movie = {



  movieId: number;



  title: string;



  genres: string[];



  year?: number | null;



  predicted_rating?: number;



  similarity?: number;



};



type AuthUser = {



  id: number;



  username: string;



};







type UserMovie = {



  movie_id: number;



  list_type: "saved" | "watch_later" | "watched" | "rated";



  rating: number | null;



};



type ModelMetrics = {



  models: {



    item_based: {



      rmse: number;



      mae: number;



      training_ratings: number;



      evaluated_ratings: number;



    };



    user_based: {



      rmse: number;



      mae: number;



      training_ratings: number;



      evaluated_ratings: number;



    };



    als: {



      rmse: number;



      mae: number;



      training_ratings: number;



      evaluated_ratings: number;



    };



  };



  best_model: string;



};







const GENRES = ["All", "Action", "Adventure", "Animation", "Comedy", "Crime", "Drama", "Horror", "Romance", "Sci-Fi", "Thriller"];







const POSTER_STYLES = [



  "poster-one", "poster-two", "poster-three", "poster-four",



  "poster-five", "poster-six", "poster-seven", "poster-eight",



];







function cleanTitle(title: string) {



  return title.replace(/\s*\(\d{4}\)\s*$/, "");



}







function getYear(movie: Movie) {



  if (movie.year) return movie.year;



  const match = movie.title.match(/\((\d{4})\)\s*$/);



  return match ? Number(match[1]) : null;



}







function Poster({ movie, index, large = false }: { movie: Movie; index: number; large?: boolean }) {



  const style = POSTER_STYLES[index % POSTER_STYLES.length];



  const words = cleanTitle(movie.title).split(" ");



  const shortTitle = words.slice(0, 3).join(" ");



  const [posterLoaded, setPosterLoaded] = useState(false);



  useEffect(() => {

    setPosterLoaded(false);

  }, [movie.movieId]);



  return (



    <div className={`poster-art ${style} ${large ? "poster-large" : ""}`}>



      <img

        src={`${API_BASE}/posters/${movie.movieId}`}

        alt={`${cleanTitle(movie.title)} poster`}

        onLoad={() => setPosterLoaded(true)}

        onError={() => setPosterLoaded(false)}

        style={{

          display: posterLoaded ? "block" : "none",

          position: "absolute",

          inset: 0,

          width: "100%",

          height: "100%",

          objectFit: "contain",
          background: "#08090d",

          zIndex: 2,

        }}

      />



      <div className="poster-grain" />



      <span className="poster-kicker">CINEFINDER ORIGINAL PICK</span>



      <div className="poster-orbit" />



      <div className="poster-copy">



        <span className="poster-line" />



        <strong>{shortTitle}</strong>



        <small>{(movie.genres || []).slice(0, 2).join("  /  ") || "CINEMA"}</small>



      </div>



      <span className="poster-year">{getYear(movie) || "FEATURED"}</span>



    </div>



  );



}







function MovieCard({



  movie,



  index,



  onSelect,



}: {



  movie: Movie;



  index: number;



  onSelect: (movie: Movie) => void;



}) {



  return (



    <button className="movie-card" onClick={() => onSelect(movie)} aria-label={`View ${cleanTitle(movie.title)}`}>



      <div className="movie-poster-wrap">



        <Poster movie={movie} index={index} />



        <span className="poster-open"><ArrowDownRight size={17} /></span>



      </div>



      <div className="movie-card-info">



        <div className="movie-card-title">{cleanTitle(movie.title)}</div>



        <div className="movie-card-meta">



          <span>{getYear(movie) || "Movie"}</span>



          <span className="meta-dot" />



          <span>{(movie.genres || [])[0] || "Cinema"}</span>



        </div>



      </div>



    </button>



  );



}







export default function Home() {



const [movies, setMovies] = useState<Movie[]>([]);



const [recommendations, setRecommendations] = useState<Movie[]>([]);



// Custom movie ratings



const [ratedMovies, setRatedMovies] = useState<



  { movieId: number; rating: number; title: string }[]



>([]);



const [customRecommendations, setCustomRecommendations] = useState<Movie[]>([]);



const [customLoading, setCustomLoading] = useState(false);







// Movie pagination



const [currentPage, setCurrentPage] = useState(1);



const [totalMovies, setTotalMovies] = useState(0);



const [loadingMore, setLoadingMore] = useState(false);







const [query, setQuery] = useState("");



  const [activeGenre, setActiveGenre] = useState("All");



  const [activeTab, setActiveTab] = useState<"discover" | "recommended">("discover");



  const [apiOnline, setApiOnline] = useState(false);



  const [modelMetrics, setModelMetrics] = useState<ModelMetrics | null>(null);



  const [metricsLoading, setMetricsLoading] = useState(true);



  const [loading, setLoading] = useState(true);



  const [error, setError] = useState("");



  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null);



  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);



  // Authentication



  const [authUser, setAuthUser] = useState<AuthUser | null>(null);



  const [authToken, setAuthToken] = useState("");



  const [authMode, setAuthMode] = useState<"login" | "register" | null>(null);



  const [authUsername, setAuthUsername] = useState("");



  const [authPassword, setAuthPassword] = useState("");



  const [authLoading, setAuthLoading] = useState(false);



  const [authError, setAuthError] = useState("");



  const [userMovies, setUserMovies] = useState<UserMovie[]>([]);
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "title">("newest");
  const [toast, setToast] = useState<{ title: string; message: string; tone: "success" | "error" | "info" } | null>(null);
  const [similarMovies, setSimilarMovies] = useState<Movie[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  function notify(title: string, message: string, tone: "success" | "error" | "info" = "success") {
    setToast({ title, message, tone });
  }

  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if (!selectedMovie) {
      setSimilarMovies([]);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    fetch(`${API_BASE}/movies/${selectedMovie.movieId}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load movie details");
        return response.json();
      })
      .then((data) => {
        if (!cancelled) setSimilarMovies(data.similar_movies || []);
      })
      .catch(() => {
        if (!cancelled) setSimilarMovies([]);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectedMovie?.movieId]);



  async function handleAuth(event: React.FormEvent<HTMLFormElement>) {



  event.preventDefault();



  setAuthLoading(true);



  setAuthError("");







  try {



    const response = await fetch(



      `${API_BASE}/auth/${authMode}`,



      {



        method: "POST",



        headers: {



          "Content-Type": "application/json",



        },



        body: JSON.stringify({



          username: authUsername,



          password: authPassword,



        }),



      }



    );







    const data = await response.json();







    if (!response.ok) {



      throw new Error(data.detail || "Authentication failed");



    }







    if (authMode === "register") {



      setAuthMode("login");



      setAuthPassword("");



      setAuthError("Account created! Please log in.");



      return;



    }







    localStorage.setItem("cinefinder_token", data.access_token);







    setAuthToken(data.access_token);



    setAuthUser({



      id: data.user_id,



      username: data.username,



    });







    const listsResponse = await fetch(`${API_BASE}/auth/lists`, {



  headers: {



    Authorization: `Bearer ${data.access_token}`,



  },



});







if (listsResponse.ok) {



  const listsData = await listsResponse.json();



  setUserMovies(listsData.movies || []);



}







    setAuthMode(null);



    setAuthPassword("");



    setAuthUsername("");







  } catch (error) {



    setAuthError(



      error instanceof Error ? error.message : "Something went wrong"



    );



  } finally {



    setAuthLoading(false);



  }



}







async function updateUserMovieList(



  movie: Movie,



  listType: UserMovie["list_type"],



  rating?: number



) {



  if (!authToken) {



    setAuthMode("login");



    setAuthError("Please log in to save movies.");



    return;



  }







  try {



    const response = await fetch(`${API_BASE}/auth/lists`, {



      method: "POST",



      headers: {



        "Content-Type": "application/json",



        Authorization: `Bearer ${authToken}`,



      },



      body: JSON.stringify({



        movie_id: movie.movieId,



        list_type: listType,



        ...(rating !== undefined ? { rating } : {}),



      }),



    });







    const data = await response.json();







    if (!response.ok) {



      throw new Error(data.detail || "Could not update movie list.");



    }







    const listsResponse = await fetch(`${API_BASE}/auth/lists`, {



      headers: {



        Authorization: `Bearer ${authToken}`,



      },



    });







    if (listsResponse.ok) {
      const listsData = await listsResponse.json();
      setUserMovies(listsData.movies || []);
    }

    const messages: Record<UserMovie["list_type"], { title: string; message: string }> = {
      saved: { title: "Movie saved!", message: "Added to your Saved collection." },
      watch_later: { title: "Added to Watch Later!", message: "You can find it in your Watch Later collection." },
      watched: { title: "Marked as watched!", message: "Added to your Watched collection." },
      rated: { title: "Rating submitted!", message: `Your rating: ${rating ?? "—"}/5.` },
    };
    notify(messages[listType].title, messages[listType].message);
  } catch (error) {
    notify("Could not update movie", error instanceof Error ? error.message : "Something went wrong.", "error");
  }



}







  useEffect(() => {



  const token = localStorage.getItem("cinefinder_token");







  if (!token) return;







  async function restoreSession() {



    try {



      const response = await fetch(`${API_BASE}/auth/me`, {



        headers: {



          Authorization: `Bearer ${token}`,



        },



      });







      if (!response.ok) {



        localStorage.removeItem("cinefinder_token");



        return;



      }







      const user = await response.json();







      setAuthToken(token!);



      setAuthUser(user);







      const listsResponse = await fetch(`${API_BASE}/auth/lists`, {



        headers: {



          Authorization: `Bearer ${token}`,



        },



      });







      if (listsResponse.ok) {



        const listsData = await listsResponse.json();



        setUserMovies(listsData.movies || []);



      }



    } catch (error) {



      console.error("Could not restore login session:", error);



    }



  }







  restoreSession();



}, []);







  useEffect(() => {



    let cancelled = false;



    async function load() {



      setLoading(true);



      try {



        const [movieResponse, recommendationResponse, healthResponse, metricsResponse] = await Promise.all([



  fetch(`${API_BASE}/movies?page=1&limit=48`),



  fetch(`${API_BASE}/recommendations/188674?model=item&limit=10`),



  fetch(`${API_BASE}/health`),



  fetch(`${API_BASE}/model-metrics`),



]);



        if (!movieResponse.ok) throw new Error("Could not load movies from the CineFinder API.");



        const movieData = await movieResponse.json();



        const recommendationData = recommendationResponse.ok ? await recommendationResponse.json() : { results: [] };



        const metricsData = metricsResponse.ok



  ? await metricsResponse.json()



  : null;



        if (!cancelled) {



          setMovies(movieData.results || []);



          setTotalMovies(movieData.total || 0);



          setCurrentPage(1);



          setRecommendations(recommendationData.results || []);



          setApiOnline(healthResponse.ok);



          setError("");



          setModelMetrics(metricsData);



          setMetricsLoading(false);



        }



      } catch {



        if (!cancelled) {



          setError("Can't reach the recommendation server. Start your FastAPI backend and refresh this page.");



          setApiOnline(false);



        }



      } finally {



        if (!cancelled) setLoading(false);



      }



    }



    load();



    return () => { cancelled = true; };



  }, []);







  // Query the complete backend catalogue when the year range changes.
  const yearFilterMounted = useRef(false);
  useEffect(() => {
    if (!yearFilterMounted.current) {
      yearFilterMounted.current = true;
      return;
    }

    let cancelled = false;
    const controller = new AbortController();

    const timeout = setTimeout(async () => {
      const params = new URLSearchParams({ page: "1", limit: "48" });
      if (yearFrom.trim()) params.set("year_from", yearFrom.trim());
      if (yearTo.trim()) params.set("year_to", yearTo.trim());

      setLoading(true);
      try {
        const response = await fetch(`${API_BASE}/movies?${params.toString()}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || "Could not filter movies by year.");
        }
        const data = await response.json();
        if (!cancelled) {
          setMovies(data.results || []);
          setTotalMovies(data.total || 0);
          setCurrentPage(1);
          setError("");
        }
      } catch (filterError) {
        if (!cancelled && !(filterError instanceof DOMException && filterError.name === "AbortError")) {
          setError(filterError instanceof Error ? filterError.message : "Year filter failed.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timeout);
    };
  }, [yearFrom, yearTo]);

  const visibleMovies = useMemo(() => {
    let result = [...movies];
    if (activeGenre !== "All") {
      result = result.filter((movie) => (movie.genres || []).some((genre) => genre.toLowerCase() === activeGenre.toLowerCase()));
    }
    if (query.trim()) {
      result = result.filter((movie) => movie.title.toLowerCase().includes(query.toLowerCase()));
    }
    if (yearFrom) {
      result = result.filter((movie) => {
        const year = getYear(movie);
        return year !== null && year >= Number(yearFrom);
      });
    }
    if (yearTo) {
      result = result.filter((movie) => {
        const year = getYear(movie);
        return year !== null && year <= Number(yearTo);
      });
    }
    result.sort((a, b) => {
      if (sortBy === "title") return cleanTitle(a.title).localeCompare(cleanTitle(b.title));
      const yearA = getYear(a) ?? 0;
      const yearB = getYear(b) ?? 0;
      return sortBy === "newest" ? yearB - yearA : yearA - yearB;
    });
    return result;
  }, [movies, activeGenre, query, yearFrom, yearTo, sortBy]);







  const featuredPool = useMemo(() => {
    const combined = [...recommendations, ...movies];
    const unique = new Map<number, Movie>();
    combined.forEach((movie) => unique.set(movie.movieId, movie));
    return Array.from(unique.values());
  }, [recommendations, movies]);

  const [featuredMovie, setFeaturedMovie] = useState<Movie | null>(null);

  useEffect(() => {
    if (featuredPool.length === 0) {
      setFeaturedMovie(null);
      return;
    }

    setFeaturedMovie((current) => {
      if (current && featuredPool.some((movie) => movie.movieId === current.movieId)) {
        return current;
      }
      return featuredPool[Math.floor(Math.random() * featuredPool.length)];
    });
  }, [featuredPool]);

  useEffect(() => {
    if (featuredPool.length < 2) return;

    let timeoutId: ReturnType<typeof setTimeout>;

    const scheduleNextMovie = () => {
      const delay = Math.floor(Math.random() * 8000) + 4000;
      timeoutId = setTimeout(() => {
        setFeaturedMovie((current) => {
          const candidates = featuredPool.filter(
            (movie) => movie.movieId !== current?.movieId
          );
          if (candidates.length === 0) return current;
          return candidates[Math.floor(Math.random() * candidates.length)];
        });
        scheduleNextMovie();
      }, delay);
    };

    scheduleNextMovie();
    return () => clearTimeout(timeoutId);
  }, [featuredPool]);

  const featured = featuredMovie || featuredPool[0];







  async function handleSearch(value: string) {



    setQuery(value);



    if (value.trim().length >= 2) {



      try {



        const response = await fetch(`${API_BASE}/search?q=${encodeURIComponent(value)}&limit=48`);



        if (response.ok) {



          const data = await response.json();



          setMovies(data.results || []);



        }



      } catch {



        // Keep the currently loaded movies available for local filtering.



      }



    } else if (!value.trim()) {



      try {



        const response = await fetch(`${API_BASE}/movies?page=1&limit=48`);



        if (response.ok) {



          const data = await response.json();



          setMovies(data.results || []);



        }



      } catch {



        // Existing results remain visible.



      }



    }



  }







    async function loadMoreMovies() {



    if (loadingMore || movies.length >= totalMovies) return;







    const nextPage = currentPage + 1;



    setLoadingMore(true);







    try {



      const response = await fetch(



        `${API_BASE}/movies?page=${nextPage}&limit=48${yearFrom ? `&year_from=${encodeURIComponent(yearFrom)}` : ""}${yearTo ? `&year_to=${encodeURIComponent(yearTo)}` : ""}`



      );







      if (!response.ok) {



        throw new Error("Failed to load movies");



      }







      const data = await response.json();







      setMovies((previousMovies) => [



        ...previousMovies,



        ...data.results,



      ]);







      setCurrentPage(nextPage);



      setTotalMovies(data.total);



    } catch (error) {



      console.error(error);



    } finally {



      setLoadingMore(false);



    }



  }











  async function handleRateMovie(movie: Movie, rating: number) {
    setRatedMovies((previous) => {
      const existing = previous.find((item) => item.movieId === movie.movieId);
      if (existing) {
        return previous.map((item) =>
          item.movieId === movie.movieId ? { ...item, rating } : item
        );
      }
      return [...previous, { movieId: movie.movieId, rating, title: movie.title }];
    });

    if (authUser) {
      await updateUserMovieList(movie, "rated", rating);
    } else {
      notify("Rating added!", `You rated ${cleanTitle(movie.title)} ${rating}/5 for this session. Log in to sync it.`);
    }
  }



async function generateCustomRecommendations() {











  setCustomLoading(true);







  try {



    const response = await fetch(



      `${API_BASE}/recommendations/custom?limit=10`,



      {



        method: "POST",



        headers: {



          "Content-Type": "application/json",



        },



        body: JSON.stringify({



          ratings: ratedMovies.map((item) => ({



            movieId: item.movieId,



            rating: item.rating,



          })),



        }),



      }



    );







    if (!response.ok) {



      throw new Error("Could not generate recommendations.");



    }







    const data = await response.json();



    setCustomRecommendations(data.results || []);



  } catch (error) {



    alert(



      error instanceof Error



        ? error.message



        : "Something went wrong."



    );



  } finally {



    setCustomLoading(false);



  }



}







  return (



    <main className="site-shell">



      <div className="ambient ambient-one" />



      <div className="ambient ambient-two" />







      <header className="topbar">



        <a className="brand" href="#" aria-label="CineFinder home">



          <span className="brand-mark"><Clapperboard size={19} strokeWidth={2.1} /></span>



          <span>CINE<span className="brand-accent">FINDER</span><i>.</i></span>



        </a>







        <nav className={`main-nav ${mobileMenuOpen ? "nav-open" : ""}`}>



          <a className="nav-link nav-active" href="#discover" onClick={() => setMobileMenuOpen(false)}>Discover</a>



          <a className="nav-link" href="#recommendations" onClick={() => setMobileMenuOpen(false)}>For you</a>



          <a className="nav-link" href="#genres" onClick={() => setMobileMenuOpen(false)}>Genres</a>



          <a className="nav-link" href="/friends" onClick={() => setMobileMenuOpen(false)}>



  Friends



</a>



        </nav>







        <div className="topbar-actions">



          <label className="search-box">



            <Search size={17} />



            <input value={query} onChange={(event) => handleSearch(event.target.value)} placeholder="Search movies..." />



            <kbd>⌘ K</kbd>



          </label>



          <div className={`api-indicator ${apiOnline ? "online" : "offline"}`} title={apiOnline ? "API connected" : "API disconnected"}>



            <span />



            <span>{apiOnline ? "LIVE" : "OFFLINE"}</span>



          </div>



          {authUser ? (



  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>



    <a



  href="/profile"



  style={{



    color: "#fff",



    fontSize: "13px",



    textDecoration: "none",



    cursor: "pointer",



  }}



>



  Hi, {authUser.username}



</a>



    <button



      className="button-quiet"



      onClick={() => {



        localStorage.removeItem("cinefinder_token");



        setAuthToken("");



        setAuthUser(null);



        setUserMovies([]);



      }}



    >



      Logout



    </button>



  </div>



) : (



  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>



    <button



      className="button-quiet"



      onClick={() => {



        setAuthMode("login");



        setAuthError("");



      }}



    >



      Login



    </button>



    <button



      className="button-primary"



      onClick={() => {



        setAuthMode("register");



        setAuthError("");



      }}



    >



      Register



    </button>



  </div>



)}



          <button className="mobile-menu-button" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} aria-label="Toggle menu">



            {mobileMenuOpen ? <X size={21} /> : <Menu size={21} />}



          </button>



        </div>



      </header>







      {error && <div className="api-warning"><span />{error}</div>}







      <section className="hero" id="discover">



        <div className="hero-content">



          <div className="eyebrow"><span className="eyebrow-line" /> YOUR NEXT GREAT WATCH STARTS HERE</div>



          <h1>Find films that<br />feel <em>like you.</em></h1>



          <p className="hero-description">



            Less scrolling. Better stories. Discover your next favourite through recommendations powered by machine learning.



          </p>



          <div className="hero-actions">



            <a href="#recommendations" className="button-primary"><Sparkles size={16} /> Explore your picks <ArrowRight size={16} /></a>



            <a href="#browse" className="button-quiet"><Play size={15} /> Browse collection</a>



          </div>



          <div className="hero-proof">



            <div className="proof-avatars"><span> C </span><span> F </span><span> + </span></div>



            <div><strong>Powered by your taste</strong><small>Collaborative filtering · MovieLens data</small></div>



          </div>



        </div>







        <div className="hero-visual">



          <div className="hero-visual-glow" />



          {featured ? (



            <div className="featured-poster">



              <Poster key={featured.movieId} movie={featured} index={2} large />



              <div className="featured-caption">



                <div><span className="featured-label">A PICK FOR YOU</span><strong>{cleanTitle(featured.title)}</strong></div>



                <span className="featured-score"><Star size={13} fill="currentColor" /> {featured.predicted_rating?.toFixed(1) || "4.8"}</span>



              </div>



            </div>



          ) : (



            <div className="hero-placeholder"><Film size={52} /><span>YOUR NEXT FAVOURITE</span></div>



          )}



          <div className="floating-note note-top"><Sparkles size={14} /> Curated for your taste</div>



          <div className="floating-note note-bottom"><TrendingUp size={14} /> ML-powered discovery</div>



          <div className="hero-ring ring-one" />



          <div className="hero-ring ring-two" />



        </div>



        <div className="hero-index"><span>01</span><span className="index-rule" /><span>DISCOVER</span></div>



      </section>







      <section className="recommendation-section section-wrap" id="recommendations">



        <div className="section-heading">



          <div>



            <div className="section-kicker"><Sparkles size={14} /> PERSONALIZED FOR YOU</div>



            <h2>Your kind of <em>cinema.</em></h2>



            <p>Recommendations generated by your Item-Based Collaborative Filtering model.</p>



          </div>



          <a href="#browse" className="text-link">Explore collection <ArrowRight size={16} /></a>



        </div>



        <div className="recommendation-strip">



          {recommendations.slice(0, 5).map((movie, index) => (



            <div className="recommendation-tile" key={movie.movieId} onClick={() => setSelectedMovie(movie)} role="button" tabIndex={0} onKeyDown={(event) => event.key === "Enter" && setSelectedMovie(movie)}>



              <div className="recommendation-art"><Poster movie={movie} index={index + 3} /></div>



              <div className="recommendation-copy">



                <span className="recommendation-number">0{index + 1}</span>



                <strong>{cleanTitle(movie.title)}</strong>



                <small><Star size={11} fill="currentColor" /> {movie.predicted_rating?.toFixed(1) || "Recommended"} predicted</small>



              </div>



              <ArrowDownRight className="tile-arrow" size={17} />



            </div>



          ))}



          {!loading && recommendations.length === 0 && <div className="empty-recommendations">Recommendations will appear here when the API is available.</div>}



          {loading && <div className="loading-line">Finding films for you<span>...</span></div>}



        </div>



      </section>











<section className="rating-section section-wrap" id="rate-movies">



  <div className="section-heading">



    <div>



      <div className="section-kicker">



        <Star size={14} /> TRAIN YOUR TASTE



      </div>



      <h2>Build your <em>taste profile.</em></h2>



      <p>Search for movies above, then rate films below to get recommendations based on your preferences.</p>



    </div>



    <div className="collection-count">



      <strong>{ratedMovies.length}/5</strong>



      <span>MOVIES RATED</span>



    </div>



  </div>







  <div className="movie-grid">



    {visibleMovies.slice(0, 8).map((movie, index) => {



      const existingRating = ratedMovies.find(



        (item) => item.movieId === movie.movieId



      )?.rating || 0;







      return (



        <div



  className="recommendation-tile"



  key={movie.movieId}



  style={{



    display: "flex",



    flexDirection: "column",



    minWidth: 0,



    padding: "16px",



    boxSizing: "border-box",



  }}



>



          <div className="recommendation-art">



            <Poster movie={movie} index={index} />



          </div>



          <div



  className="recommendation-copy"



  style={{ width: "100%", minWidth: 0 }}



>



            <strong>{cleanTitle(movie.title)}</strong>



            <small>Rate this movie</small>



            <div



              style={{



              display: "flex",



              gap: "2px",



              marginTop: "10px",



              flexWrap: "nowrap",



              width: "140px",



              alignItems: "center",



            }}



            >



              {[1, 2, 3, 4, 5].map((rating) => (



                <button



                  key={rating}



                  onClick={() => handleRateMovie(movie, rating)}



                  aria-label={`Rate ${movie.title} ${rating} stars`}



                  style={{



                    background: "transparent",



                    border: "none",



                    cursor: "pointer",



                    padding: "2px",



                    width: "24px",



                    minWidth: "24px",



                    height: "28px",



                    display: "flex",



                    alignItems: "center",



                    justifyContent: "center",



                    flexShrink: 0,



                    color: rating <= existingRating ? "#f5b942" : "#777",



                  }}



                >



                  <Star size={19} fill={rating <= existingRating ? "currentColor" : "none"} />



                </button>



              ))}



            </div>



          </div>



        </div>



      );



    })}



  </div>







  <div style={{ marginTop: "28px" }}>



    <h3>Your ratings ({ratedMovies.length})</h3>







    {ratedMovies.map((item) => (



      <div key={item.movieId} style={{ margin: "10px 0" }}>



        {item.title} — {item.rating}/5 ⭐



      </div>



    ))}







    <button



      className="button-primary"



      onClick={generateCustomRecommendations}



      disabled={customLoading || ratedMovies.length === 0}



      style={{ marginTop: "16px" }}



    >



      {customLoading



  ? "Generating..."



  : ratedMovies.length === 0



    ? "Rate at least 1 movie"



    : "Generate My Recommendations"}



      <ArrowRight size={16} />



    </button>



  </div>







 {customRecommendations.length > 0 && (



  <div style={{ marginTop: "35px" }}>



    <h2>Your personalized recommendations</h2>







    <div className="custom-recommendation-grid">



      {customRecommendations.map((movie, index) => (



        <div className="custom-recommendation-item" key={movie.movieId}>



          <MovieCard



            movie={movie}



            index={index}



            onSelect={setSelectedMovie}



          />







          <div className="custom-prediction">



            <Star size={13} fill="currentColor" />



            <span>



              Predicted rating: {movie.predicted_rating?.toFixed(2) || "N/A"}/5



            </span>



          </div>



        </div>



      ))}



    </div>



  </div>



)}



</section>







      <section className="browse-section section-wrap" id="browse">



        <div className="section-heading browse-heading">



          <div>



            <div className="section-kicker"><Compass size={14} /> THE COLLECTION</div>



            <h2>Explore the <em>library.</em></h2>



            <p>A handpicked starting point from the MovieLens collection.</p>



          </div>



          <div className="collection-count"><strong>{visibleMovies.length.toLocaleString()}</strong><span>FILMS SHOWN</span></div>



        </div>







        <div className="genre-bar" id="genres">



          <div className="genre-label"><span>FILTER BY</span><ChevronDown size={13} /></div>



          <div className="genre-list">



            {GENRES.map((genre) => (



              <button key={genre} className={`genre-chip ${activeGenre === genre ? "genre-selected" : ""}`} onClick={() => setActiveGenre(genre)}>



                {genre === "All" && <Flame size={13} />}{genre}



              </button>



            ))}



          </div>



        </div>







        <div className="advanced-filters">
          <label>
            <span>YEAR FROM</span>
            <input type="number" min="1888" max="2035" placeholder="Any" value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} />
          </label>
          <label>
            <span>YEAR TO</span>
            <input type="number" min="1888" max="2035" placeholder="Any" value={yearTo} onChange={(event) => setYearTo(event.target.value)} />
          </label>
          <label>
            <span>SORT BY</span>
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value as "newest" | "oldest" | "title")}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="title">Title A–Z</option>
            </select>
          </label>
          <button className="filter-reset" onClick={() => { setActiveGenre("All"); setYearFrom(""); setYearTo(""); setSortBy("newest"); setQuery(""); }}>
            Reset filters
          </button>
        </div>

        <div className="movie-grid">



          {visibleMovies.map((movie, index) => (



            <MovieCard key={movie.movieId} movie={movie} index={index} onSelect={setSelectedMovie} />



          ))}



        </div>







        {!query.trim() && movies.length < totalMovies && (



  <div style={{ textAlign: "center", margin: "40px 0" }}>



    <button



      className="button-primary"



      onClick={loadMoreMovies}



      disabled={loadingMore}



    >



      {loadingMore ? "Loading..." : "Load More Movies"}



    </button>







    <p style={{ marginTop: "12px", color: "#999" }}>



      Showing {movies.length} of {totalMovies} movies



    </p>



  </div>



)}







        {!loading && visibleMovies.length === 0 && <div className="no-results"><Search size={25} /><strong>No films found</strong><span>Try another title or genre.</span></div>}



        {loading && <div className="loading-grid">{Array.from({ length: 8 }).map((_, index) => <div className="skeleton-card" key={index} />)}</div>}



      </section>







      <section className="bottom-cta section-wrap">



        <div className="cta-icon"><Heart size={21} /></div>



        <div><span className="section-kicker">GOOD STORIES FIND THEIR WAY</span><h2>Make room for your next <em>favourite.</em></h2></div>



        <a href="#discover" className="button-primary">Back to top <ArrowRight size={16} /></a>



      </section>







      <footer className="footer section-wrap">



        <a className="brand footer-brand" href="#"><span className="brand-mark"><Clapperboard size={17} /></span><span>CINE<span className="brand-accent">FINDER</span><i>.</i></span></a>



        <span>Built with machine learning. Made for movie lovers.</span>



        <span>© 2026 CINEFINDER</span>



      </footer>







      {toast && (
        <div className={`toast-notification toast-${toast.tone}`} role="status" aria-live="polite">
          <span className="toast-icon">
            {toast.tone === "success" ? <Check size={18} /> : toast.tone === "error" ? <X size={18} /> : <Sparkles size={18} />}
          </span>
          <span className="toast-copy">
            <strong>{toast.title}</strong>
            <small>{toast.message}</small>
          </span>
          <button onClick={() => setToast(null)} aria-label="Dismiss notification"><X size={16} /></button>
        </div>
      )}

      {authMode && (



  <div



    className="modal-backdrop"



    onClick={() => setAuthMode(null)}



  >



    <div



      className="movie-modal"



      onClick={(event) => event.stopPropagation()}



      style={{ maxWidth: "420px", width: "90%", padding: "32px" }}



    >



      <button



        className="modal-close"



        onClick={() => setAuthMode(null)}



      >



        <X size={19} />



      </button>







      <div className="section-kicker">



        <Clapperboard size={15} /> CINEFINDER ACCOUNT



      </div>







      <h2 style={{ marginTop: "15px" }}>



        {authMode === "login" ? "Welcome back." : "Create your account."}



      </h2>







      <p style={{ color: "#aaa", marginBottom: "24px" }}>



        {authMode === "login"



          ? "Log in to access your personal movie collection."



          : "Join CineFinder and save your favourite films."}



      </p>







      <form onSubmit={handleAuth}>



        <input



          type="text"



          placeholder="Username"



          value={authUsername}



          onChange={(event) => setAuthUsername(event.target.value)}



          minLength={3}



          maxLength={30}



          required



          style={{



            width: "100%",



            padding: "14px",



            marginBottom: "14px",



            borderRadius: "8px",



            background: "#171717",



            color: "white",



            border: "1px solid #444",



          }}



        />







        <input



          type="password"



          placeholder="Password"



          value={authPassword}



          onChange={(event) => setAuthPassword(event.target.value)}



          minLength={6}



          required



          style={{



            width: "100%",



            padding: "14px",



            marginBottom: "18px",



            borderRadius: "8px",



            background: "#171717",



            color: "white",



            border: "1px solid #444",



          }}



        />







        {authError && (



          <p style={{ color: "#f5b942", marginBottom: "15px" }}>



            {authError}



          </p>



        )}







        <button



          type="submit"



          className="button-primary"



          disabled={authLoading}



          style={{ width: "100%", justifyContent: "center" }}



        >



          {authLoading



            ? "Please wait..."



            : authMode === "login"



              ? "Login"



              : "Create Account"}



        </button>



      </form>







      <p style={{ marginTop: "20px", textAlign: "center", color: "#aaa" }}>



        {authMode === "login"



          ? "Don't have an account?"



          : "Already have an account?"}







        <button



          type="button"



          onClick={() => {



            setAuthMode(authMode === "login" ? "register" : "login");



            setAuthError("");



          }}



          style={{



            background: "none",



            border: "none",



            color: "#f5b942",



            cursor: "pointer",



            marginLeft: "6px",



          }}



        >



          {authMode === "login" ? "Register" : "Login"}



        </button>



      </p>



    </div>



  </div>



)}







      {selectedMovie && (



        <div className="modal-backdrop" onClick={() => setSelectedMovie(null)}>



          <div className="movie-modal" onClick={(event) => event.stopPropagation()}>



            <button className="modal-close" onClick={() => setSelectedMovie(null)} aria-label="Close"><X size={19} /></button>



            <Poster movie={selectedMovie} index={4} large />



            <div className="modal-details">
              <span className="section-kicker">CINEFINDER MOVIE DETAILS</span>
              <h2>{cleanTitle(selectedMovie.title)}</h2>
              <p className="detail-meta">{getYear(selectedMovie) || "Release year unavailable"} · {(selectedMovie.genres || []).join(" / ") || "Genres unavailable"}</p>
              {selectedMovie.predicted_rating !== undefined && (
                <div className="modal-rating"><Star size={15} fill="currentColor" /> Predicted rating {selectedMovie.predicted_rating.toFixed(2)} / 5</div>
              )}

              <div className="detail-rating-control">
                <span>YOUR RATING</span>
                <div>
                  {[1, 2, 3, 4, 5].map((rating) => (
                    <button key={rating} aria-label={`Rate ${rating} stars`} onClick={() => handleRateMovie(selectedMovie, rating)}>
                      <Star size={19} fill={(ratedMovies.find((item) => item.movieId === selectedMovie.movieId)?.rating || 0) >= rating ? "currentColor" : "none"} />
                    </button>
                  ))}
                </div>
              </div>

              <div className="detail-actions">
                <button className="button-quiet" onClick={() => updateUserMovieList(selectedMovie, "saved")}><Bookmark size={15} /> Save</button>
                <button className="button-quiet" onClick={() => updateUserMovieList(selectedMovie, "watch_later")}><Clock size={15} /> Watch later</button>
                <button className="button-quiet" onClick={() => updateUserMovieList(selectedMovie, "watched")}><Check size={15} /> Watched</button>
              </div>

              <div className="similar-movies">
                <div className="similar-heading">SIMILAR MOVIES</div>
                {detailLoading ? (
                  <p>Finding similar movies…</p>
                ) : similarMovies.length ? (
                  <div className="similar-list">
                    {similarMovies.slice(0, 4).map((movie) => (
                      <button key={movie.movieId} onClick={() => setSelectedMovie(movie)}>
                        <span>{cleanTitle(movie.title)}</span>
                        <small>{getYear(movie) || "Year n/a"}</small>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p>Similar movie recommendations are not available for this title.</p>
                )}
              </div>
              <button className="button-primary modal-action" onClick={() => setSelectedMovie(null)}><Check size={16} /> Done</button>
            </div>



          </div>



        </div>



      )}



    </main>



  );



}
