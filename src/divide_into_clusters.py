import os
import json
import random
import numpy as np
import folium
from sklearn.cluster import KMeans
from collections import defaultdict
from math import hypot

from config import *


# ------------------------------------------------------------------
# --- Public entry function ---
# ------------------------------------------------------------------

def divide_into_clusters(generate_map=True):
    max_share = 0.2
    print("Scanning cities in:", DATA_PATH)

    for city in os.listdir(DATA_PATH):
        city_dir = os.path.join(DATA_PATH, city)
        if not os.path.isdir(city_dir):
            continue
        dataset_path = os.path.join(city_dir, FILES["locations"])
        if not os.path.exists(dataset_path):
            continue
        print(f"\nProcessing: {dataset_path}")

        # --- Load dataset ---
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        coords = np.array([[p["x_coor"], p["y_coor"]] for p in data])
        n_clusters = _choose_n_clusters(len(data))
        print(f"Instance size: {len(data)} → using {n_clusters} clusters")

        # --- Run clustering ---
        labels, centroids = _kmeans_with_capacity(coords, n_clusters, max_share)
        for i, p in enumerate(data):
            p["cluster_id"] = int(labels[i])

        # --- Save clustered dataset ---
        out_json = os.path.join(city_dir, TMP_DIR, FILES["locations_with_clusters"])
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Saved clustered JSON: {out_json}")

        # --- Representative points ---
        rep_points = _compute_representatives(data, centroids)
        out_rep = os.path.join(city_dir, TMP_DIR, FILES["representative_points"])
        with open(out_rep, "w", encoding="utf-8") as f:
            json.dump(rep_points, f, indent=2)
        print(f"Saved representative points JSON: {out_rep}")

        # --- Optional map ---
        if generate_map:
            _build_cluster_map(city, city_dir, data, rep_points)
    print("\n✅ Done: clustering + representative points generated.")


# ------------------------------------------------------------------
# --- Core clustering logic ---
# ------------------------------------------------------------------

def _choose_n_clusters(n_points):
    if 50 <= n_points <= 99:
        return 8
    elif 100 <= n_points <= 199:
        return 10
    elif 200 <= n_points <= 399:
        return 12
    elif 400 <= n_points <= 1000:
        return 14
    return max(4, min(14, n_points // 10))


def _euclid_dist(a, b):
    return hypot(a[0] - b[0], a[1] - b[1])


def _kmeans_with_capacity(coords, n_clusters, max_share):
    n_points = len(coords)
    max_points = int(np.ceil(max_share * n_points))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(coords)
    centroids = kmeans.cluster_centers_.copy()

    for _ in range(10):
        clusters = defaultdict(list)

        # --- Assign points with penalty ---
        for idx, point in enumerate(coords):
            distances = []
            for cid, centroid in enumerate(centroids):
                size = len(clusters[cid])
                alpha = 5.0
                factor = 1 + alpha * max(0, size / max_points - 0.5)
                distances.append(_euclid_dist(point, centroid) * factor)
            min_cluster = np.argmin(distances)
            clusters[min_cluster].append(idx)

        # --- Recompute centroids ---
        for cid in range(n_clusters):
            if clusters[cid]:
                centroids[cid] = np.mean(coords[clusters[cid]], axis=0)

    labels_final = np.zeros(n_points, dtype=int)
    for cid, indices in clusters.items():
        for i in indices:
            labels_final[i] = cid

    return labels_final, centroids


# ------------------------------------------------------------------
# --- Representatives ---
# ------------------------------------------------------------------

def _compute_representatives(data, centroids):
    clusters = defaultdict(list)
    for p in data:
        clusters[p["cluster_id"]].append(p)

    rep_points = []
    for cid, pts in clusters.items():
        centroid = centroids[cid]
        best_point = min(
            pts,
            key=lambda p: _euclid_dist(
                (p["x_coor"], p["y_coor"]),
                centroid
            )
        )
        rep_points.append({
            "cluster_id": int(cid),
            "x_rep": float(best_point["x_coor"]),
            "y_rep": float(best_point["y_coor"]),
            "n_points": len(pts),
            "location_type": best_point["location_type"]
        })

    return rep_points


# ------------------------------------------------------------------
# --- Map builder ---
# ------------------------------------------------------------------

def _build_cluster_map(city, city_dir, data, rep_points):
    lat_center = np.mean([p["y_coor"] for p in data])
    lon_center = np.mean([p["x_coor"] for p in data])

    m = folium.Map(
        location=[lat_center, lon_center],
        zoom_start=11,
        tiles="cartodbpositron"
    )

    # Random colors per cluster
    cluster_colors = {
        cid: "#{:06x}".format(random.randint(0, 0xFFFFFF))
        for cid in set(p["cluster_id"] for p in data)
    }

    # --- Points ---
    for idx, p in enumerate(data):
        tooltip_text = (
            f"ID: {idx} | "
            f"Cluster: {p['cluster_id']} | "
            f"Type: {p['location_type']} | "
            f"Demand: {p['demand']}"
        )

        folium.CircleMarker(
            location=[p["y_coor"], p["x_coor"]],
            radius=5,
            color=cluster_colors[p["cluster_id"]],
            fill=True,
            fill_opacity=0.9,
            tooltip=tooltip_text
        ).add_to(m)

    # --- Representative points ---
    for r in rep_points:
        tooltip_text = (
            f"REPRESENTATIVE | "
            f"Cluster: {r['cluster_id']} | "
            f"N points: {r['n_points']} | "
            f"Type: {r['location_type']}"
        )

        folium.CircleMarker(
            location=[r["y_rep"], r["x_rep"]],
            radius=10,
            color="black",
            fill=True,
            fill_opacity=1.0,
            tooltip=tooltip_text
        ).add_to(m)

    out_map = os.path.join(city_dir, "maps", "clusters_map.html")
    os.makedirs(os.path.dirname(out_map), exist_ok=True)
    m.save(out_map)
    print(f"Saved clusters map: {out_map}")
