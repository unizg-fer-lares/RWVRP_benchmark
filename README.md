# VRP Benchmark Dataset

This repository contains a benchmark dataset for variants of the **Vehicle Routing Problem (VRP)** generated using real-world road network data. It also includes scripts used to generate the dataset, enabling reproducibility and further extensions for new variants and ML applications.

The benchmark is designed for **real-world (rich) VRP scenarios**, incorporating multiple constraints and realistic city topologies. All instances are based on real geographic regions, while travel times are derived from road networks using routing services and OpenStreetMap data.
The main goal of this benchmark is to enable **fair comparison of algorithms on standardized yet realistic scenarios**. The dataset covers a wide range of city structures and constraint combinations, allowing researchers to select instances that best match their specific application.

Currently, the benchmark focuses on **DC-to-store distribution scenarios**, characterized by a single depot and moderate time window constraints.
This setup is motivated by practical insights obtained through collaboration with industry partners.
Contributors are encouraged to extend the benchmark to other applications, such as urban delivery systems, taxi systems, public transport routing, and other VRP use cases.


# Benchmark Overview

The benchmark currently contains **80 instances**  
(16 cities × 5 variant combinations), with plans for future expansion.

Supported **Vehicle Routing Problem variants** include:

- **CVRP** – Capacitated Vehicle Routing Problem  
- **VRPTW** – Vehicle Routing Problem with Time Windows  
- **AVRP** – Asymmetric Vehicle Routing Problem  
- **HVRP** – Heterogeneous Vehicle Routing Problem  
- **MTVRP** – Multi-Trip Vehicle Routing Problem  
- **TDVRP** – Time-Dependent Vehicle Routing Problem  

The dataset provides the following **variant combinations**:

1. CVRP + VRPTW + AVRP  
2. CVRP + VRPTW + AVRP + HVRP  
3. CVRP + VRPTW + AVRP + MTVRP
4. CVRP + VRPTW + AVRP + TDVRP
5. CVRP + VRPTW + AVRP + HVRP + MTVRP + TDVRP

**Note:**  
The benchmark is designed to be **flexible and application-driven**, meaning users are not expected to evaluate all instances. Instead, it is recommended to select subsets of instances that best match the target real-world scenario (e.g., problem size, demand structure, and city topology).


# Cities Included in the Dataset

The dataset includes instances generated for cities and regions of different sizes.

## Small (S) instances (50–85 delivery points)

| City / Region       | Instance Name| Type   | Delivery Points | Supermarkets | Convenience | Supermarket TW | Convenience TW |
|---------------------|--------------|--------|-----------------|--------------|-------------|----------------|----------------|
| Genoa               | RW-GE75-VRP  | City   | 75              | 50           | 25          | 06:00–12:00    | 06:00–11:00    |
| Lyon                | RW-LY85-VRP  | City   | 85              | 0            | 85          | —              | 06:00–11:30    |
| Oklahoma City       | RW-OK60-VRP  | Metro  | 60              | 20           | 40          | 06:00–15:00    | 06:00–18:00    |
| Central Dalmatia    | RW-CD50-VRP  | Region | 50              | 50           | 0           | 05:30–10:00    | —              |

## Medium (M) instances (100–170 delivery points)

| City / Region   | Instance Name| Type   | Delivery Points | Supermarkets | Convenience | Supermarket TW | Convenience TW |
|-----------------|--------------|--------|-----------------|--------------|-------------|----------------|----------------|
| Zagreb          | RW-ZG170-VRP | City   | 170             | 0            | 170         | —              | 06:00–12:00    |
| Brasilia        | RW-BR100-VRP | City   | 100             | 100          | 0           | 06:00–14:00    | —              |
| Copenhagen      | RW-CP150-VRP | Metro  | 150             | 100          | 50          | 05:30–11:00    | 05:30–10:30    |
| Ruhr Area       | RW-RU120-VRP | Region | 120             | 40           | 80          | 05:00–12:30    | 05:00–14:00    |

## Large (L) instances (200–340 delivery points)

| City / Region       | Instance Name| Type   | Delivery Points | Supermarkets | Convenience | Supermarket TW | Convenience TW |
|---------------------|--------------|--------|-----------------|--------------|-------------|----------------|----------------|
| Singapore           | RW-SG200-VRP | City   | 200             | 200          | 0           | 06:00–13:30    | —              |
| Melbourne           | RW-ME340-VRP | City   | 340             | 113          | 227         | 06:00–15:00    | 06:00–17:00    |
| Cairo               | RW-CA240-VRP | Metro  | 240             | 160          | 80          | 06:00–16:00    | 06:00–15:30    |
| SF Bay Area         | RW-SF300-VRP | Region | 300             | 0            | 300         | —              | 06:00–16:30    |

## Extra Large (XL) instances (400–1000 delivery points)

| City / Region    | Instance Name| Type   | Delivery Points | Supermarkets | Convenience | Supermarket TW | Convenience TW |
|------------------|--------------|--------|-----------------|--------------|-------------|----------------|----------------|
| London           | RW-LO1000-VRP| City   | 1000            | 0            | 1000        | —              | 06:30–13:00    |
| Istanbul         | RW-IS400-VRP | City   | 400             | 400          | 0           | 05:00–13:00    | —              |
| Mexico City      | RW-MC800-VRP | Metro  | 800             | 267          | 533         | 05:00–14:00    | 05:00–13:30    |
| Greater Bay Area | RW-GB600-VRP | Region | 600             | 400          | 200         | 06:00–15:30    | 06:00–18:00    |


# Instance Naming Convention

When reporting results in scientific papers, please use instance names in the following format:
**RW-<city><N>-<variant>**

Examples:
- **RW-LO1000-VRP**  
  Real-world London instance with 1000 delivery points for the base variant (CVRP + VRPTW + AVRP)
- **RW-LO1000-HVRP**  
  Same instance with heterogeneous vehicle constraints
- **RW-LO1000-HMTTDVRP**  
  Instance including HVRP + MTVRP + TDVRP constraints

This naming convention ensures consistency and comparability across different research works.


# Repository Structure

The repository is divided into two main folders:

- **src/** – contains the code used for dataset generation  
- **data/** – contains all generated files, organized into 16 city folders  

Within the `src/` folder are scripts for dataset generation. Files required to define VRP instances are located directly in the city folders (`data/<city>/`).

Additional files include:
- `data/<city>/src/` – auxiliary files used during dataset generation  
- `data/<city>/maps/` – plots used for validation and visualization  
- `data/<city>/solutions/` – stored solutions  
- `data/<city>/tests/` – additional test files  


# How to use

1) If you are using **TDVRP variants**, before running your algorithm, you need to generate the time-dependent matrix using the generate_full_tdvrp_time_matrix() function to generate "data/<city>/time_matrix_tdvrp.json" file. These files are excluded from repo due to their size.

2) Load the required files depending on your VRP variant:
data/<city>/locations.json – used for all VRP variants
data/<city>/vehicles.json – used if HVRP is not included
data/<city>/vehicles_hvrp.json – used if HVRP is included
data/<city>/time_matrix.json – static time matrix (non-TDVRP)
data/<city>/time_matrix_tdvrp.json – time-dependent matrix (TDVRP)

3) Generate a solution using your VRP algorithm and compare it with the best-known solution for the given instance.


# Future work

The authors of this benchmark plan to include a solution evaluator that will:
- Verify solution feasibility
- Store the best-known solutions
- Extend the number of variants
