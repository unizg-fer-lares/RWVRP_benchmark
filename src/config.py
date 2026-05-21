# config.py

# ------------------------------------------------------------------
# --- General paths ---
# ------------------------------------------------------------------

DATA_PATH = "data"
TMP_DIR = "tmp"


# ------------------------------------------------------------------
# --- API settings ---
# ------------------------------------------------------------------

API_URL = "YOUR_API_URL"
API_KEY = "YOUR_API_KEY"


# ------------------------------------------------------------------
# --- Time matrix settings ---
# ------------------------------------------------------------------

TIME_MATRIX = {
    "date": "2026-01-26",
    "step_minutes": 15,
    "min_congestion_time": 210,  # 03:30
}


# ------------------------------------------------------------------
# --- Output filenames (centralized) ---
# ------------------------------------------------------------------

FILES = {
    "locations": "locations.json",
    "locations_with_clusters": "locations_with_clusters.json",
    "representative_points": "representative_points.json",  # delivery points nearest to cluster centroids 
    "vehicles": "vehicles.json",
    "vehicles_hvrp": "vehicles_hvrp.json",
    "time_matrix_osm": "time_matrix_osm.json",
    "time_matrix_centroids": "time_matrix_centroids.json",
    "time_matrix_centroids_INCOMPLETE": "time_matrix_centroids_INCOMPLETE.json",
    "time_matrix_within_clusters": "time_matrix_within_clusters.json",
    "time_matrix_within_clusters_INCOMPLETE": "time_matrix_within_clusters_INCOMPLETE.json",
    "time_matrix_tdvrp": "time_matrix_tdvrp.json",
    "time_matrix_static": "time_matrix.json",
}