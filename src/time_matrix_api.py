import os, json, time, sys, math, requests, copy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import *


# ------------------------------------------------------------------
# --- Time window processor ---
# ------------------------------------------------------------------

def _process_tw(info, end_addition=50):
    start_minute = float('inf')
    end_minute = 0
    for key, time_window in info.items():
        if key in ['supermarket_delivery_tw', 'convenience_delivery_tw']:
            s, e = time_window
            s = int(s.split(':')[0]) * 60 + int(s.split(':')[1])
            e = int(e.split(':')[0]) * 60 + int(e.split(':')[1])
            start_minute = min(start_minute, s)
            end_minute = max(end_minute, e)
    return start_minute, end_minute + end_addition


# ------------------------------------------------------------------
# --- Timezones ---
# ------------------------------------------------------------------

CITY_TIMEZONES = {
    "Genoa": "Europe/Rome",
    "Lyon": "Europe/Paris",
    "Greater Oklahoma City": "America/Chicago",
    "Central Dalmatia": "Europe/Zagreb",
    "Zagreb": "Europe/Zagreb",
    "Brasilia": "America/Sao_Paulo",
    "Greater Copenhagen": "Europe/Copenhagen",
    "Ruhr Area": "Europe/Berlin",
    "Singapore": "Asia/Singapore",
    "Melbourne": "Australia/Melbourne",
    "Greater Cairo": "Africa/Cairo",
    "SF Bay Area": "America/Los_Angeles",
    "London": "Europe/London",
    "Istanbul": "Europe/Istanbul",
    "Tokyo Metro": "Asia/Tokyo",
    "Greater Bay Area": "Asia/Shanghai"
}


# ------------------------------------------------------------------
# --- API call ---
# ------------------------------------------------------------------

def calculate_matrix(origins, destinations, depart_iso_utc):
    url = API_URL
    body = {
        "origins": [{"point": {"latitude": lat, "longitude": lng}} for lat, lng in origins],
        "destinations": [{"point": {"latitude": lat, "longitude": lng}} for lat, lng in destinations],
        "options": {
            "routeType": "fastest",
            "traffic": "historical",
            "departAt": depart_iso_utc
        }
    }
    r = requests.post(url,
                      headers={"Content-Type": "application/json"},
                      params={"key": API_KEY},
                      json=body)
    r.raise_for_status()

    return r.json()


# ------------------------------------------------------------------
# --- Time dependent matrix between clusters (centroids) ---
# ------------------------------------------------------------------

def generate_td_time_matrix(city, city_info):
    POINTS_FILE = os.path.join(DATA_PATH, city, TMP_DIR, FILES["representative_points"])
    OUTPUT_FINAL = os.path.join(DATA_PATH, city, TMP_DIR, FILES["time_matrix_centroids"])
    OUTPUT_PARTIAL = os.path.join(DATA_PATH, city, TMP_DIR, FILES["time_matrix_centroids_INCOMPLETE"])

    if os.path.exists(OUTPUT_FINAL):
        print(f"Final TD matrix already exists for {city}")
        return

    start_min, end_min = _process_tw(city_info)
    LOCAL_TZ = ZoneInfo(CITY_TIMEZONES[city])

    with open(POINTS_FILE, "r", encoding="utf-8") as f:
        points = json.load(f)

    RAW_LOCS = [(p["y_rep"], p["x_rep"]) for p in points]
    N = len(RAW_LOCS)

    results = {}
    if os.path.exists(OUTPUT_PARTIAL):
        print("Resuming incomplete centroid matrix")
        results = json.load(open(OUTPUT_PARTIAL, "r", encoding="utf-8"))

    current_local = datetime.fromisoformat(TIME_MATRIX["date"]).replace(tzinfo=LOCAL_TZ)

    try:
        for minute in [TIME_MATRIX["min_congestion_time"]] + list(range(start_min, end_min, TIME_MATRIX["step_minutes"])):
            local_time = current_local + timedelta(minutes=minute)
            label = local_time.strftime("%H:%M")
            if label in results: continue

            utc_time = local_time.astimezone(timezone.utc)
            depart_iso_utc = utc_time.isoformat().replace("+00:00", "Z")

            print(f"Centroids {label}")

            data = calculate_matrix(RAW_LOCS, RAW_LOCS, depart_iso_utc)

            matrix = [[0]*N for _ in range(N)]
            for cell in data["data"]:
                matrix[cell["originIndex"]][cell["destinationIndex"]] = \
                    cell["routeSummary"]["travelTimeInSeconds"]

            results[label] = {
                "depart_local_time": label,
                "local_timezone": str(LOCAL_TZ),
                "depart_iso_utc": depart_iso_utc,
                "matrix_seconds": matrix
            }

            json.dump(results, open(OUTPUT_PARTIAL, "w", encoding="utf-8"), indent=2)

    except Exception as e:
        print("Error — partial saved")
        sys.exit(1)

    _sort_timestamps(OUTPUT_PARTIAL)
    os.replace(OUTPUT_PARTIAL, OUTPUT_FINAL)
    print("Centroid matrix done")


def _sort_timestamps(path):
    with open(path, "r") as f:
        data = json.load(f)
    sorted_data = dict(sorted(data.items(), key=lambda x: tuple(map(int, x[0].split(":")))))
    with open(path, "w") as f:
        json.dump(sorted_data, f, indent=2)



# ------------------------------------------------------------------
# --- Time dependent matrices inside clusters ---
# ------------------------------------------------------------------

def generate_td_within_clusters(city, city_info):
    DATA_FILE = os.path.join(DATA_PATH, city, TMP_DIR, FILES["locations_with_clusters"])
    OUTPUT_FINAL = os.path.join(DATA_PATH, city, TMP_DIR, FILES["time_matrix_within_clusters"])
    OUTPUT_PARTIAL = os.path.join(DATA_PATH, city, TMP_DIR, FILES["time_matrix_within_clusters_INCOMPLETE"])

    if os.path.exists(OUTPUT_FINAL):
        print(f"Within-cluster TD already exists for {city}")
        return

    # --- Load dataset ---
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # --- Group by cluster_id (no depot) ---
    clusters = {}
    for idx, loc in enumerate(dataset):
        if loc["location_type"] == "depot":
            continue
        cid = loc["cluster_id"]
        clusters.setdefault(cid, []).append(idx)

    # --- Representatives (farthest point sampling) ---
    def hav(a,b):
        R=6371000
        lat1,lon1=map(math.radians,a); lat2,lon2=map(math.radians,b)
        dlat,dlon=lat2-lat1,lon2-lon1
        h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return 2*R*math.asin(math.sqrt(h))

    reps={}
    for cid,pts in clusters.items():
        coords=[(dataset[i]["y_coor"],dataset[i]["x_coor"]) for i in pts]
        centroid=(sum(p[0] for p in coords)/len(coords),
                  sum(p[1] for p in coords)/len(coords))
        first=min(range(len(coords)),key=lambda i: hav(centroid,coords[i]))
        sel=[pts[first]]
        while len(sel)<min(4,len(pts)):
            cand=max(pts,key=lambda i:
                     min(hav((dataset[i]["y_coor"],dataset[i]["x_coor"]),
                             (dataset[j]["y_coor"],dataset[j]["x_coor"]))
                         for j in sel))
            sel.append(cand)
        reps[cid]=sel

    # --- Time settings ---
    start_min, end_min = _process_tw(city_info)
    LOCAL_TZ = ZoneInfo(CITY_TIMEZONES[city])
    current_local = datetime.fromisoformat(TIME_MATRIX["date"]).replace(tzinfo=LOCAL_TZ)

    results={}
    if os.path.exists(OUTPUT_PARTIAL):
        print("Resuming incomplete within-cluster matrix")
        results=json.load(open(OUTPUT_PARTIAL,"r",encoding="utf-8"))

    # --- Generate matrices ---
    try:
        for minute in [TIME_MATRIX["min_congestion_time"]] + list(range(start_min, end_min, TIME_MATRIX["step_minutes"])):
            local_time=current_local+timedelta(minutes=minute)
            label=local_time.strftime("%H:%M")
            if label in results: continue

            utc_time=local_time.astimezone(timezone.utc)
            depart_iso_utc=utc_time.isoformat().replace("+00:00","Z")
            print(f"Within clusters {label}")

            results[label]={}

            for cid,pts in reps.items():
                coords=[(dataset[i]["y_coor"],dataset[i]["x_coor"]) for i in pts]
                data = calculate_matrix(coords, coords, depart_iso_utc)

                N=len(coords)
                matrix=[[0]*N for _ in range(N)]
                for cell in data["data"]:
                    if "destinationIndex" in cell and "travelTimeInSeconds" in cell:  # Ignores if didn't find travel time
                        matrix[cell["originIndex"]][cell["destinationIndex"]] = cell["routeSummary"]["travelTimeInSeconds"]

                results[label][str(cid)] = {"representatives": pts, "matrix_seconds": matrix}

            json.dump(results,open(OUTPUT_PARTIAL,"w",encoding="utf-8"),indent=2)

    except Exception as e:
        print("Error — partial saved")
        print(str(e))
        sys.exit(1)

    _sort_timestamps(OUTPUT_PARTIAL)
    os.replace(OUTPUT_PARTIAL,OUTPUT_FINAL)
    print("Within-cluster matrix done")



# ------------------------------------------------------------------
# --- Scale matrices generated using API ---
# ------------------------------------------------------------------

def _scale_matrix(matrix, baseline):
    n = len(matrix)
    scaled = []
    for i in range(n):
        row = []
        for j in range(n):
            base = baseline[i][j]
            val = matrix[i][j]
            if base == 0:
                ratio = 1.0
            else:
                ratio = val / base
            row.append(ratio)
        scaled.append(row)
    return scaled


def scale_original_td_matrices(city):
    CENTROIDS_FILE = os.path.join(DATA_PATH, city, TMP_DIR, FILES["time_matrix_centroids"])
    WITHIN_FILE = os.path.join(DATA_PATH, city, TMP_DIR, FILES["time_matrix_within_clusters"])
    CENTROIDS_FILE_SCALED = os.path.join(DATA_PATH, city, TMP_DIR, FILES["time_matrix_centroids_scaled"])
    WITHIN_FILE_SCALED = os.path.join(DATA_PATH, city, TMP_DIR, FILES["time_matrix_within_clusters_scaled"])

    # =========================
    # CENTROIDS SCALE
    # =========================
    with open(CENTROIDS_FILE, "r", encoding="utf-8") as f:
        centroids = json.load(f)
    baseline = centroids["03:30"]["matrix_seconds"]
    scaled_centroids = copy.deepcopy(centroids)
    for t in scaled_centroids:
        scaled_centroids[t]["matrix_seconds"] = _scale_matrix(scaled_centroids[t]["matrix_seconds"], baseline)

    with open(CENTROIDS_FILE_SCALED, "w", encoding="utf-8") as f:
        json.dump(scaled_centroids, f, indent=2)
    print("Saved:", CENTROIDS_FILE_SCALED)

    # =========================
    # WITHIN CLUSTERS SCALE
    # =========================
    with open(WITHIN_FILE, "r", encoding="utf-8") as f:
        within = json.load(f)
    scaled_within = copy.deepcopy(within)
    baseline_clusters = within["03:30"]
    for t in scaled_within:
        for c in scaled_within[t]:
            scaled_within[t][c]["matrix_seconds"] = _scale_matrix(scaled_within[t][c]["matrix_seconds"], baseline_clusters[c]["matrix_seconds"])

    with open(WITHIN_FILE_SCALED, "w", encoding="utf-8") as f:
        json.dump(scaled_within, f, indent=2)
    print("Saved:", WITHIN_FILE_SCALED)
