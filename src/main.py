from locations_generator_osm import initialize_folders, select_input_cities, generate_locations_osm, generate_vehicles
from divide_into_clusters import divide_into_clusters
from time_matrix_local import generate_static_time_matrices_osm, generate_full_tdvrp_time_matrix, convert_3d_to_static
from time_matrix_api import generate_td_time_matrix, generate_td_within_clusters, scale_original_td_matrices
from config import *


""" 
Cities and regions covered in this dataset:
Small (S) instances: "Genoa", "Lyon", "Greater Oklahoma City", "Central Dalmatia"
Medium (M) instances: "Zagreb", "Brasilia", "Greater Copenhagen", "Ruhr Area"
Large (L) instances: "Singapore", "Melbourne", "Greater Cairo", "SF Bay Area" 
Extra large (XL) instances: "London", "Istanbul", "Mexico City Metro", "Greater Bay Area"
"""

city_names = ["Genoa"]
#city_names = ["Genoa", "Lyon", "Greater Oklahoma City", "Central Dalmatia", "Zagreb", "Brasilia", "Greater Copenhagen", "Ruhr Area"]
#city_names = ["Singapore", "Melbourne", "Greater Cairo", "SF Bay Area", "London", "Istanbul", "Mexico City Metro", "Greater Bay Area"]

initialize_folders(city_names)
cities = select_input_cities(cities_to_select=city_names)


# --- Generate location and vehicles ---
#generate_locations_osm(cities)
#divide_into_clusters()
#for city, city_info in cities.items():
#    generate_vehicles(city, heterogeneous=False)
#    generate_vehicles(city, heterogeneous=True)

# --- Generate time matrices ---
#generate_static_time_matrices_osm(city_names)
for city, city_info in cities.items():
    #generate_td_time_matrix(city, city_info)
    #generate_td_within_clusters(city, city_info)
    #scale_original_td_matrices(city)
    generate_full_tdvrp_time_matrix(city)
    #convert_3d_to_static(city)
