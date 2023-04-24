import geopandas as gpd
from rtree import index
from gerrychain import Graph
from networkx import connected_components
from settings import HUSKIES_HOME
def get_precincts(path):
    gdf = gpd.read_file(path)
    FEET_CRS = "epsg:2248"
    gdf = gdf.to_crs(FEET_CRS)
    return gdf
def find_neighbors(gdf):
    idx = index.Index()
    for i, geometry in enumerate(gdf.geometry):
        idx.insert(i, geometry.bounds)
    neighbors = {}
    for i, polygon in enumerate(gdf.geometry):
        bounds = polygon.bounds
        intersecting = list(idx.intersection(bounds))
        neighbors[i] = set()
        for j in intersecting:
            if i != j:
                other_polygon = gdf.iloc[j].geometry
                NEIGHBOR_DISTANCE_MAX = 200
                if polygon.distance(other_polygon) < NEIGHBOR_DISTANCE_MAX:
                    neighbors[i].add(j)
    return neighbors
def make_graph(neighbors, path, gdf):
    graph = Graph(neighbors)
    graph.add_data(gdf)
    graph.geometry = gdf.geometry
    components = list(connected_components(graph))
    biggest_component_size = max(len(c) for c in components)
    islands = [c for c in components if len(c) != biggest_component_size]
    for component in islands:
        for node in component:
            graph.remove_node(node)
    graph.to_json(path, include_geometries_as_geojson=True)
def neighbors(state):
    statePath = f'{HUSKIES_HOME}/generated/{state}/preprocess/'
    gdf = get_precincts(f'{statePath}merged{state}P.geojson')
    neighbors = find_neighbors(gdf)
    make_graph(neighbors, f'{statePath}graph{state}.json', gdf)
    gdf = get_precincts(f'{statePath}merged{state}P20.geojson')
    neighbors = find_neighbors(gdf)
    make_graph(neighbors, f'{statePath}graph{state}20.json', gdf)
def neighbors_all():
    neighbors('NY')
    neighbors('GA')
    neighbors('IL')
if __name__ == '__main__':
    neighbors_all()