Isochrone/accessibility analysis for S8/Meratese stations

Inputs used:
- OSM routing network: /mnt/data/planet_8.872,45.469_9.833,45.883.osm.pbf
- Population raster: /mnt/data/ita_ppp_2020_UNadj.tif (WorldPop 2020, 100m, values treated as persons per grid cell)
- Station coordinates: Trenord GTFS stops.txt from /mnt/data/trenord_gtfs.zip

Stations:
- Lecco
- Lecco Maggianico
- Calolziocorte Olginate
- Airuno
- Olgiate-Calco-Brivio
- Cernusco-Merate
- Osnago
- Carnate Usmate
- Arcore
- Monza
- Sesto S.Giovanni

Time thresholds:
- walking: 5, 10, 15 minutes
- car: 5, 10, 15 minutes

Method:
1. OSM PBF was parsed directly and converted into two routable graphs:
   - walking graph: footways/paths/pedestrian/residential/service/etc., average walking speed 4.8 km/h, steps 3 km/h
   - car graph: drivable OSM highway classes, using OSM maxspeed where available and fallback speeds by road class
2. For car access, directed one-way tags were respected. Travel direction is interpreted as residence-to-station.
3. WorldPop cells were snapped to their nearest walk/car graph node, with off-network access time added.
4. Population counts are sums of WorldPop cell values whose travel time to the station is <= the threshold.
5. Combined catchments are overlap-adjusted: each population cell is counted once if it reaches any station in the group.
6. Exclusive catchments assign each accessible population cell to the station with the shortest travel time.

Key caveats:
- This is an accessibility estimate, not observed station demand.
- Car isochrones represent potential access to the station by car, not parking availability or actual park-and-ride use.
- WorldPop is a modeled population raster, not official ISTAT census population.
- OSM routing quality depends on OSM tags, access restrictions, and completeness.
- The analysis uses 2020 population because the uploaded raster is ita_ppp_2020_UNadj.tif.

Generated files:
- population_by_station_mode_minutes.csv
- population_by_station_pivot.csv
- population_by_station_meratese_only.csv
- combined_catchment_unique_population.csv
- combined_catchment_unique_population_pivot.csv
- exclusive_catchment_population_by_station.csv
- station_coordinates_and_graph_snap.csv
- map_meratese_walk_5_10_15.png
- map_meratese_car_5_10_15.png
- map_s8_corridor_walk_5_10_15.png
- map_s8_corridor_car_5_10_15.png
