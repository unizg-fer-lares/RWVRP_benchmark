import json
import os
import osmnx as ox
import networkx as nx
import numpy as np
import re
import folium

from config import *


VEHICLES = {"8_palets":  {"weight": 7.5, "width": 2.50, "height": 4.0, "length": 10.0},
            "18_palets": {"weight": 12.0, "width": 2.50, "height": 4.0, "length": 12.0},
            "26_palets": {"weight": 18.0, "width": 2.55, "height": 4.0, "length": 14.0}}


# ------------------------------------------------------------------
# --- Public entry function ---
# ------------------------------------------------------------------

def generate_static_time_matrices_osm(locations, reverse_penalty_factor=3.0, reverse_penalty_const=60, vehicle_types=None):
    ox.settings.log_console = True
    ox.settings.use_cache = True
    ox.settings.requests_timeout = 300
    ox.settings.max_query_area_size = 1_500_000_000  # max 2_500_000_000

    #ox.settings.overpass_url = "https://overpass.private.coffee/api"
    #ox.settings.overpass_url = "https://maps.mail.ru/osm/tools/overpass/api"



    if vehicle_types is None:
        vehicle_types = VEHICLES

    for city in locations:
        print("\n====================================\n", city, "\n====================================")
        city_dir = os.path.join(DATA_PATH, city)
        dataset_path = os.path.join(city_dir, FILES["locations"])
        coords = _load_coordinates(dataset_path)
        bbox = _build_bbox(coords)

        # --- Download/load OSM graph ---
        west, south, east, north = bbox
        bbox = (west - 0.02, south - 0.02, east + 0.02, north + 0.02)
        graph_path = os.path.join(city_dir, TMP_DIR, "osm_drive.graphml")
        if os.path.exists(graph_path):
            print(f"Loading cached OSM graph: {graph_path}")
            G = ox.load_graphml(graph_path)
        else:
            print("Downloading OSM graph...")
            G = ox.graph_from_bbox(bbox=bbox, network_type="drive")
            G = ox.add_edge_speeds(G)
            G = ox.add_edge_travel_times(G)
            ox.save_graphml(G, graph_path)
            print(f"Saved OSM graph: {graph_path}")

        # Keep original graph for fallback
        G_original = G.copy()

        # --- Snap locations ---
        nodes = ox.distance.nearest_nodes(G, X=[lon for lat, lon in coords], Y=[lat for lat, lon in coords])

        # --- Generate matrix for each vehicle type ---
        matrices = {}
        accessibility_masks = {}
        for vehicle_type, vehicle in vehicle_types.items():
            print(f"\nGenerating matrix for {vehicle_type} (max weight: {vehicle['weight']} t)")

            G_vehicle = _filter_graph_by_vehicle(G, vehicle)
            # Only for 8-palets: OSM sometimes contains one-way/access restrictions that are unrealistic
            # for the actual truck routing. Add a penalized reverse direction as a fallback.
            if vehicle_type == "8_palets":
                G_vehicle = _add_penalized_reverse_edges(G_vehicle, reverse_penalty_factor, reverse_penalty_const)
            
            matrix, accessibility_mask = _compute_time_matrix(G_vehicle, nodes, G_fallback=G_original)

            matrices[vehicle_type] = matrix
            accessibility_masks[vehicle_type] = accessibility_mask
            
            if vehicle_type in ("18_palets", "26_palets"):
                for j in range(len(matrix)):
                    if matrix[0, j] >= 10**9:
                        matrix[0, j] = matrices["8_palets"][0, j] * (1.06 if vehicle_type == "18_palets" else 1.12)
                    if matrix[j, 0] >= 10**9:
                        matrix[j, 0] = matrices["8_palets"][j, 0] * (1.06 if vehicle_type == "18_palets" else 1.12)



            out_json = os.path.join(city_dir, TMP_DIR, f"time_matrix_{vehicle_type}_osm.json")
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(matrix.tolist(), f, indent=2)

            if vehicle_type == "8_palets":
                out_json = os.path.join(city_dir, TMP_DIR, f"time_matrix_osm.json")
                with open(out_json, "w", encoding="utf-8") as f:
                    json.dump(matrix.tolist(), f, indent=2)

            print("Saved:", out_json)
            out_map = os.path.join(city_dir, MAPS_DIR, f"truck_map_{vehicle_type}.html")
            _save_truck_map(G, vehicle, coords, out_map, accessibility_mask=accessibility_masks[vehicle_type])
            print("Map:", os.path.abspath(out_map))
        
        # --- Save accessibility masks ---
        accessibility_masks_path = os.path.join(city_dir, TMP_DIR, "accessibility_masks.json")
        with open(accessibility_masks_path, "w", encoding="utf-8") as f:
            json.dump(accessibility_masks, f, indent=2)
        print(f"Accessibility masks saved to: {accessibility_masks_path}")
        
        # --- Generate vehicle-location accessibility matrix from vehicles.json ---
        vehicles_path = os.path.join(city_dir, FILES["vehicles"])
        if os.path.exists(vehicles_path):
            with open(vehicles_path, "r", encoding="utf-8") as f:
                vehicles = json.load(f)

            capacity_to_type = {8: "8_palets", 18: "18_palets", 26: "26_palets"}
            num_vehicles = len(vehicles)
            num_locations = len(coords)
            vehicle_location_matrix = []

            for vehicle in vehicles:
                hvrp_capacity = vehicle.get("hvrp_capacity")
                vehicle_type = capacity_to_type.get(hvrp_capacity)
                if vehicle_type and vehicle_type in accessibility_masks:
                    mask = accessibility_masks[vehicle_type]
                else:
                    mask = [1] * num_locations
                vehicle_location_matrix.append(mask)

            vehicle_location_data = {
                "type": "vehicle_location_accessibility",
                "description": "Matrix of vehicle-location accessibility (1=accessible, 0=not accessible)",
                "num_vehicles": num_vehicles,
                "num_locations": num_locations,
                "vehicles": [{"id": v["id"], "capacity": v.get("capacity"), "hvrp_capacity": v.get("hvrp_capacity")} for v in vehicles],
                "accessibility_matrix": vehicle_location_matrix
            }

            vehicle_location_path = os.path.join(city_dir, "vehicle_location_accessibility.json")

            with open(vehicle_location_path, "w", encoding="utf-8") as f:
                json.dump(vehicle_location_data, f, indent=2)
            print(f"Vehicle-location accessibility matrix saved to: {vehicle_location_path}")

        else:
            print(f"Warning: vehicles.json not found at {vehicles_path}")




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
    centroid_original_path = os.path.join(city_dir, TMP_DIR, FILES["time_matrix_centroids"])
    correction_factor_path = os.path.join(city_dir, TMP_DIR, "osm_correction_factor.txt")
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

    # --- OSM -> real TomTom 03:30 correction factor ---
    if os.path.exists(centroid_original_path):
        tt_centroids_original = json.load(open(centroid_original_path, "r", encoding="utf-8"))
        # Calculate correction factor from original centroids
        T_0330_cluster = np.array(tt_centroids_original["03:30"]["matrix_seconds"], dtype=float)
        T_0330 = T_0330_cluster[np.ix_(loc_to_cluster_idx, loc_to_cluster_idx)]
        osm_correction_factor = np.mean(T_0330) / np.mean(T_static)
        # Save correction factor for future use
        with open(correction_factor_path, "w", encoding="utf-8") as f:
            f.write(str(osm_correction_factor))
        print(f"Saved OSM correction factor: {osm_correction_factor}")
    elif os.path.exists(correction_factor_path):
        # Load correction factor from saved file
        with open(correction_factor_path, "r", encoding="utf-8") as f:
            osm_correction_factor = float(f.read().strip())
        print(f"Loaded OSM correction factor: {osm_correction_factor}")
    else:
        print("Warning: Neither centroids file nor correction factor file found. Using default factor 1.0")
        osm_correction_factor = 1.0

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
                T_scaled[i, j] = int(round(T_static[i, j] * osm_correction_factor * scale_matrix[ci, cj]))

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

def _num(x):
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        x = x[0] if x else None
    m = re.search(r"\d+(?:[.,]\d+)?", str(x))
    return float(m.group().replace(",", ".")) if m else None


def _can_truck_pass(d, v):
    # Eksplicitne zabrane
    if any(str(d.get(t, "")).lower() in ("no", "false")
           for t in ("hgv", "goods", "motor_vehicle")):
        return False

    # Eksplicitna ograničenja
    for tag, value in (("maxweight", v["weight"]), ("maxwidth",  v["width"]), ("maxheight", v["height"]), ("maxlength", v["length"]), ("width", v["width"]),):
        limit = _num(d.get(tag))
        if limit is not None and value > limit:
            return False

    # Heuristika prema tipu ceste
    highway = d.get("highway", "")
    highway = highway[0] if isinstance(highway, list) else highway
    lanes = _num(d.get("lanes"))

    if highway in {"footway", "path", "steps", "pedestrian", "cycleway"}:
        return False
    if lanes == 1 and highway in {"service", "living_street"}:
        return v["weight"] <= 7.5
    if lanes == 1 and highway == "residential":
        return v["weight"] <= 12.0
    if highway in {"track", "unclassified"}:
        return v["weight"] <= 7.5
    return True


def _filter_graph_by_vehicle(G, vehicle):
    G = G.copy()
    removed = 0
    for u, v, k, d in list(G.edges(keys=True, data=True)):
        if not _can_truck_pass(d, vehicle):
            G.remove_edge(u, v, k)
            removed += 1
        else:
            d["travel_time"] *= _travel_time_factor(d, vehicle)
    print(f"  Removed edges: {removed}")
    return G


def _travel_time_factor(edge, vehicle):
    highway = edge.get("highway", "")
    highway = highway[0] if isinstance(highway, list) else highway
    weight = vehicle["weight"]
    if weight <= 7.5:
        return 1.00

    factors = {"primary":       (1.03, 1.06),
               "secondary":     (1.03, 1.06),
               "tertiary":      (1.06, 1.12),
               "residential":   (1.06, 1.12),
               "unclassified":  (1.06, 1.12),
               "road":          (1.06, 1.12),
               "service":       (1.08, 1.16),
               "living_street": (1.08, 1.16)}
    factor_12t, factor_18t = factors.get(highway, (1.00, 1.00))
    return factor_12t if weight <= 12.0 else factor_18t


def _save_truck_map(G, vehicle, coords, path, accessibility_mask=None):
    m = folium.Map(location=[coords[0][0], coords[0][1]], zoom_start=13)
    for u, v, k, d in G.edges(keys=True, data=True):
        geom = d.get("geometry")
        if geom is None:
            continue
        color = "green" if _can_truck_pass(d, vehicle) else "red"
        folium.PolyLine([(lat, lon) for lon, lat in geom.coords], color=color, weight=3, opacity=0.7).add_to(m)

    if accessibility_mask is not None:
        for i, (lat, lon) in enumerate(coords):
            accessible = bool(accessibility_mask[i])
            color = "green" if accessible else "red"
            folium.Marker(location=[lat, lon], icon=folium.Icon(color=color, icon="shopping-cart", prefix="fa"), popup=folium.Popup(f"Location {i}", max_width=150)).add_to(m)

    m.save(path)






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


def _compute_time_matrix(G, nodes, G_fallback=None):
    """
    Compute travel time matrix.
    If G_fallback is provided, use it for unreachable pairs in G.
    Returns: (matrix, accessibility_mask)
    - matrix: N x N travel times (int, seconds)
    - accessibility_mask: N array where mask[i] = 1 if location i is accessible from >= 5 others
    """
    N = len(nodes)
    matrix = np.zeros((N, N), dtype=int)
    accessibility_count = np.zeros(N, dtype=int)
    
    print(f"Computing {N}x{N} travel-time matrix...")

    for i, source in enumerate(nodes):
        # Calculate primary graph distances once for this source
        lengths = nx.single_source_dijkstra_path_length(G, source, weight="travel_time")

        # Calculate fallback distances ONCE per source, instead of once for every unreachable target.
        if G_fallback is not None:
            fallback_lengths = nx.single_source_dijkstra_path_length(G_fallback, source, weight="travel_time")
        else:
            fallback_lengths = None

        for j, target in enumerate(nodes):
            if target in lengths:
                matrix[i, j] = int(lengths[target])
                if i != j:  # Don't count self-loops for accessibility
                    accessibility_count[j] += 1
            elif fallback_lengths is not None:
                matrix[i, j] = int(fallback_lengths[target]) if target in fallback_lengths else 10**9
            else:
                matrix[i, j] = 10**9

    # Accessibility mask: 1 if location is reachable from >= 5 other locations
    accessibility_mask = (accessibility_count >= 5).astype(int).tolist()
    
    # Depot (index 0) is always accessible
    accessibility_mask[0] = 1
    
    return matrix, accessibility_mask


# ------------------------------------------------------------------
# --- Heterogeneous matrices (scaled by vehicle type OSM) ---
# ------------------------------------------------------------------

def generate_heterogeneous_matrices(city):
    """
    Generate heterogeneous VRP and TDVRP matrices using vehicle-specific OSM travel times.
    Formula: hvrp_matrix[vehicle_type] = base_matrix * osm_matrix[vehicle_type] / osm_base_matrix
    """
    city_dir = os.path.join(DATA_PATH, city)
    tmp_dir = os.path.join(city_dir, TMP_DIR)

    # Load base matrices
    base_vrp_path = os.path.join(city_dir, FILES["time_matrix_static"])
    base_tdvrp_path = os.path.join(city_dir, FILES["time_matrix_tdvrp"])
    osm_base_path = os.path.join(tmp_dir, "time_matrix_osm.json")

    print(f"\n=== Generating heterogeneous matrices for {city} ===")
    # Load base matrices
    with open(base_vrp_path, "r", encoding="utf-8") as f:
        base_vrp_data = json.load(f)
        base_vrp = np.array(base_vrp_data["matrix_seconds"], dtype=float)

    with open(base_tdvrp_path, "r", encoding="utf-8") as f:
        base_tdvrp_data = json.load(f)

    with open(osm_base_path, "r", encoding="utf-8") as f:
        osm_base = np.array(json.load(f), dtype=float)

    # Prevent division by zero
    osm_base_safe = np.where(osm_base == 0, 1, osm_base)

    # Generate for each vehicle type
    for vehicle_type in VEHICLES.keys():
        osm_vehicle_path = os.path.join(tmp_dir, f"time_matrix_{vehicle_type}_osm.json")

        if not os.path.exists(osm_vehicle_path):
            print(f"OSM matrix not found for {vehicle_type}: {osm_vehicle_path}")
            continue

        with open(osm_vehicle_path, "r", encoding="utf-8") as f:
            osm_vehicle = np.array(json.load(f), dtype=float)

        # --- VRP matrix ---
        hvrp_matrix = (base_vrp * osm_vehicle / osm_base_safe).round().astype(int)
        hvrp_matrix = hvrp_matrix.tolist()
        hvrp_vrp_data = {
            "type": base_vrp_data["type"],
            "units": base_vrp_data["units"],
            "matrix_seconds": hvrp_matrix
        }
        hvrp_vrp_path = os.path.join(city_dir, f"time_matrix_hvrp_{vehicle_type}.json")
        with open(hvrp_vrp_path, "w", encoding="utf-8") as f:
            json.dump(hvrp_vrp_data, f, indent=2)
        print(f"Saved: {hvrp_vrp_path}")

        # --- TDVRP matrices ---
        hvrp_tdvrp_data = {k: v for k, v in base_tdvrp_data.items() if k != "matrices"}
        hvrp_tdvrp_data["note"] = f"Heterogeneous matrix for {vehicle_type}"
        hvrp_tdvrp_data["matrices"] = {}

        for snapshot_key, snapshot_data in base_tdvrp_data["matrices"].items():
            base_matrix_snap = np.array(snapshot_data["matrix_seconds"], dtype=float)
            hvrp_matrix_snap = (base_matrix_snap * osm_vehicle / osm_base_safe).round().astype(int)
            hvrp_tdvrp_data["matrices"][snapshot_key] = {"depart_iso_utc": snapshot_data["depart_iso_utc"],
                                                         "matrix_seconds": hvrp_matrix_snap.tolist()}

        hvrp_tdvrp_path = os.path.join(city_dir, f"time_matrix_tdvrp_hvrp_{vehicle_type}.json")
        with open(hvrp_tdvrp_path, "w", encoding="utf-8") as f:
            json.dump(hvrp_tdvrp_data, f, indent=2)
        print(f"Saved: {hvrp_tdvrp_path}")
