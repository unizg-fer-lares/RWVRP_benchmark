# Building a solution

Each solution contains an `instance_name` whose final suffix identifies the variant, and a `routes` list. Add at most one route entry per vehicle. A route is a list of location IDs; it must start and end at depot `0`. Intermediate depot visits are allowed only in MTVRP, and repeated customer visits are allowed only in SDVRP.

Variant-specific fields and rules:

| Variant feature | How to construct the solution |
|---|---|
| HVRP | A vehicle's `hvrp_capacity` selects its matching travel matrix. Assign routes only to vehicles with the intended capacity. |
| MTVRP | Put `0` between trips to return to the depot. Each depot visit resets the vehicle load and applies the depot's service time. The objective adds 10,000 per used vehicle. |
| TDVRP | Travel time for each leg is selected using that leg's departure time, so route order and service/waiting times affect later travel. |
| SiDVRP | Every vehicle must be able to access every location on its route, as specified by `vehicle_location_accessibility.json`. |
| SDVRP | `demands` is required and must align position-by-position with `route`; use `0` for depot entries and the quantity delivered on that visit for customer entries. Split deliveries across visits or vehicles as needed, but their sum must equal the customer's `demand_sdvrp`. |
| VRPDB | `breaks_after` contains zero-based indexes into `route`. An index schedules a break after that stop and before the next leg; it must identify a customer stop, not a depot. Keep driving between breaks within the vehicle's `driving_before_break_mins` limit. |

For generated SDVRP locations, unloading time at each customer visit is 5 minutes plus the amount delivered on that visit multiplied by 120 seconds per unit for a supermarket or 90 seconds per unit for a convenience store. Thus, each split visit incurs its own 5-minute setup. The depot instead uses its configured `service_time` for every visit, including the start and return.

The validator reports `total_time_consumed` (driving, waiting, service, and breaks), `driving_time` (travel only), and `cost`. Cost is driving time plus the 10,000-per-used-vehicle penalty when the variant includes MTVRP.

# DummyCity validation cases

Run each JSON through `validate(solution, "DummyCity")`. The nine variant files should return `feasible: true`; the two files ending in `_inaccessible` and `_missing_break` should return `feasible: false`.

| File | Main behavior exercised | Expected |
|---|---|---|
| `VRP.json` | Base route, capacity, time windows, and complete service | Feasible |
| `HVRP.json` | 18- and 8-pallet vehicle capacities and matching static matrices | Feasible |
| `MTVRP.json` | Intermediate depot visit and capacity reset | Feasible |
| `TDVRP.json` | Time-dependent matrix selection | Feasible |
| `HMTTDVRP.json` | HVRP-specific time-dependent matrices | Feasible |
| `HSIDVRP.json` | Per-vehicle location accessibility | Feasible |
| `SDVRP.json` | Location 2 split across two vehicles; summed delivery equals demand | Feasible |
| `MTVRPDB.json` | Multiple trips and scheduled breaks | Feasible |
| `RWVRP.json` | Combined HVRP, TDVRP, SDVRP quantities, accessibility, and breaks | Feasible |
| `HSIDVRP_inaccessible.json` | Vehicle 1 visits its forbidden location 1 | Infeasible |
| `MTVRPDB_missing_break.json` | Required break omitted from vehicle 0 route | Infeasible |

The DummyCity fixtures use HVRP capacities 18 and 8 to match the supplied matrix files. Vehicle 1 is denied access to location 1. The depot time window ends at 15:00, matching the vehicles' driver time windows so the longer TDVRP cases can return.

To print the route details for a case, call `validate(solution, "DummyCity", print_routes=True)`. The existing `validate_solutions()` runner in `src/main.py` selects cases through its `test_solution_paths` list.
