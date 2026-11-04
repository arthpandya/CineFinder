$ErrorActionPreference = "Stop"

# Load TMDB access token
$tokenLine = Get-Content ".\api\.env" |
    Where-Object { $_ -match '^TMDB_ACCESS_TOKEN=' } |
    Select-Object -First 1

$token = ($tokenLine -replace '^TMDB_ACCESS_TOKEN=', '').Trim().Trim('"').Trim("'")

if (!$token) {
    throw "TMDB access token not found in api/.env"
}

$headers = @{
    Authorization = "Bearer $token"
    accept = "application/json"
}

# Load MovieLens data
$movies = Import-Csv ".\processed\movies_processed.csv"
$links = Import-Csv ".\dataset\links.csv"

# Create movie ID mapping
$tmdbMap = @{}

foreach ($link in $links) {
    if ($link.tmdbId -and $link.tmdbId -ne "\N") {
        $tmdbMap[$link.movieId] = $link.tmdbId
    }
}

$results = @()
$count = 0

foreach ($movie in $movies) {

    $count++
    $poster = ""

    if ($tmdbMap.ContainsKey($movie.movieId)) {

        $tmdbId = [int]$tmdbMap[$movie.movieId]

        try {
            $url = "https://api.themoviedb.org/3/movie/$tmdbId"

            $data = Invoke-RestMethod `
                -Uri $url `
                -Headers $headers `
                -TimeoutSec 20

            $poster = $data.poster_path
        }
        catch {
            Write-Host "Skipped:" $movie.title
        }
    }

    $results += [PSCustomObject]@{
        movieId = $movie.movieId
        poster_path = $poster
    }

    if ($count % 100 -eq 0) {
        Write-Host "Processed $count / $($movies.Count)"
    }

    Start-Sleep -Milliseconds 50
}

$results | Export-Csv `
    ".\processed\tmdb_posters.csv" `
    -NoTypeInformation

Write-Host "`nPoster fetching completed!"
Write-Host "Movies processed:" $count
Write-Host "Posters found:" (($results | Where-Object { $_.poster_path }).Count)