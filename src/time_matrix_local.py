import json
import os
import osmnx as ox
import networkx as nx
import numpy as np

from config import *


# ------------------------------------------------------------------
# --- Public entry function ---
# ------------------------------------------------------------------

def generate_static_time_matrices_osm(locations, reverse_penalty_factor=3.0, reverse_penalty_const=60):
    ox.settings.log_console = True
    ox.settings.use_cache = True

    for city in locations:
        print("\n====================================\n", city, "\n====================================")
        city_dir = os.path.join(DATA_PATH, city)
        dataset_path = os.path.join(city_dir, FILES["locations"])
        out_json = os.path.join(city_dir, TMP_DIR, FILES["time_matrix_osm"])
        coords = _load_coordinates(dataset_path)
        bbox = _build_bbox(coords)

        # --- Download and prepare graph ---
        G = ox.graph_from_bbox(bbox=bbox, network_type="drive")
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)

        # --- Add penalized reverse edges ---
        G = _add_penalized_reverse_edges(G, reverse_penalty_factor, reverse_penalty_const)

        # --- Snap locations and compute matrix ---
        nodes = ox.distance.nearest_nodes(G, X=[lon for lat, lon in coords], Y=[lat for lat, lon in coords])
        matrix = _compute_time_matrix(G, nodes)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(matrix.tolist(), f, indent=2)
        print("Saved:", out_json)


def convert_3d_to_static(city):
    """Converts a full 3D TDVRP matrix into a static VRP matrix by averaging over all time slices."""
    city_dir = os.path.join(DATA_PATH, city)
    input_file = os.path.join(city_dir, FILES["time_matrix_tdvrp"])
    output_file = os.path.join(city_dir, FILES["time_matrix_static"])

    data = json.load(open(input_file, "r", encoding="utf-8"))
    matrices = [np.array(v["matrix_seconds"]) for v in data["matrices"].values()]
    static_matrix = np.mean(matrices, axis=0).round().astype(int).tolist()

    out = {
        "type": "vrp_static_matrix",
        "units": "seconds",
        "matrix_seconds": static_matrix
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("Static VRP matrix saved.")


def generate_full_tdvrp_time_matrix(city):
    # --- File paths ---
    city_dir = os.path.join(DATA_PATH, city)
    dataset_path = os.path.join(city_dir, TMP_DIR, FILES["locations_with_clusters"])
    static_matrix_path = os.path.join(city_dir, TMP_DIR, FILES["time_matrix_osm"])
    centroid_tt_path = os.path.join(city_dir, TMP_DIR, FILES["time_matrix_centroids_scaled"])
    within_tt_path = os.path.join(city_dir, TMP_DIR, FILES["time_matrix_within_clusters_scaled"])
    rep_points_path = os.path.join(city_dir, TMP_DIR, FILES["representative_points"])
    output_path = os.path.join(city_dir, FILES["time_matrix_tdvrp"])

    # --- Load data ---
    locations = json.load(open(dataset_path, "r", encoding="utf-8"))
    T_static = np.array(json.load(open(static_matrix_path, "r", encoding="utf-8")))
    tt_centroids_all = json.load(open(centroid_tt_path, "r", encoding="utf-8"))
    rep_points = json.load(open(rep_points_path, "r", encoding="utf-8"))

    # --- Optional within-cluster file ---
    if os.path.exists(within_tt_path):
        tt_within_all = json.load(open(within_tt_path, "r", encoding="utf-8"))
        use_within = True
        print("Using intra-cluster representative scaling.")
    else:
        tt_within_all = {}
        use_within = False
        print("No within-cluster file found. Using centroid-based intra scaling.")

    # --- Cluster info and order from representative_points ---
    cluster_ids_ordered = [rp["cluster_id"] for rp in rep_points]
    cluster_to_idx = {c: i for i, c in enumerate(cluster_ids_ordered)}

    # --- Process all snapshots ---
    cluster_matrices_snapshots = []
    snapshot_keys = sorted(tt_centroids_all.keys())

    for snapshot_key in snapshot_keys:
        centroid_matrix = np.array(
            tt_centroids_all[snapshot_key]["matrix_seconds"], dtype=float
        )
        full_cluster_matrix = np.array(centroid_matrix, dtype=float)

        # Fill diagonal
        for c in cluster_ids_ordered:
            idx = cluster_to_idx[c]

            if use_within and str(c) in tt_within_all.get(snapshot_key, {}):
                matrix_within = np.array(
                    tt_within_all[snapshot_key][str(c)]["matrix_seconds"],
                    dtype=float
                )
                full_cluster_matrix[idx, idx] = np.mean(matrix_within)
            else:
                row_mean = np.mean(np.delete(full_cluster_matrix[idx, :], idx))
                col_mean = np.mean(np.delete(full_cluster_matrix[:, idx], idx))
                full_cluster_matrix[idx, idx] = (row_mean + col_mean) / 2

        cluster_matrices_snapshots.append(full_cluster_matrix)

    # --- Element-wise minimum across snapshots ---
    cluster_matrices_snapshots = np.stack(cluster_matrices_snapshots, axis=0)
    base_cluster_matrix = np.min(cluster_matrices_snapshots, axis=0)

    # --- Scale matrices per snapshot ---
    scale_matrices = cluster_matrices_snapshots / (base_cluster_matrix + 1e-8)

    print('\n==== RANGE MATRICE:',
          'min', np.min(scale_matrices),
          'max', np.max(scale_matrices),
          'avg', np.average(scale_matrices),
          'med', np.median(scale_matrices))

    # --- Map locations to cluster indices ---
    loc_to_cluster_idx = [cluster_to_idx[loc["cluster_id"]] for loc in locations]
    num_locs = len(locations)

    # --- Build structured output ---
    output_data = {
        "type": "tdvrp_full_matrix",
        "units": "seconds",
        "note": "Inter-cluster scaled using centroid matrix.",
        "matrices": {}
    }

    for t_idx, snapshot_key in enumerate(snapshot_keys):
        if snapshot_key == "03:30":
            continue
        scale_matrix = scale_matrices[t_idx]
        T_scaled = np.zeros((num_locs, num_locs), dtype=float)

        for i in range(num_locs):
            ci = loc_to_cluster_idx[i]
            for j in range(num_locs):
                cj = loc_to_cluster_idx[j]
                T_scaled[i, j] = int(round(T_static[i, j] * scale_matrix[ci, cj]))

        output_data["matrices"][snapshot_key] = {
            "depart_iso_utc": tt_centroids_all[snapshot_key]["depart_iso_utc"],
            "matrix_seconds": T_scaled.tolist()
        }

    # --- Save final JSON ---
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"TDVRP matrix saved to {output_path}")


# ------------------------------------------------------------------
# --- Helper functions ---
# ------------------------------------------------------------------

def _load_coordinates(dataset_path):
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [(p["y_coor"], p["x_coor"]) for p in data]


def _build_bbox(coords):
    lats = [lat for lat, lon in coords]
    lons = [lon for lat, lon in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def _add_penalized_reverse_edges(G, factor, const):
    G_aug = G.copy()
    for u, v, k, data in G.edges(keys=True, data=True):
        if not G.has_edge(v, u):
            penalized_time = data["travel_time"] * factor + const
            G_aug.add_edge(v, u, travel_time=penalized_time, length=data.get("length", 0), speed_kph=data.get("speed_kph", None))

    return G_aug


def _compute_time_matrix(G, nodes):
    N = len(nodes)
    matrix = np.zeros((N, N), dtype=int)
    print(f"Computing {N}x{N} travel-time matrix...")
    for i, source in enumerate(nodes):
        lengths = nx.single_source_dijkstra_path_length(G, source, weight="travel_time")
        for j, target in enumerate(nodes):
            matrix[i, j] = int(lengths[target])

    return matrix
