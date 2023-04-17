import geopandas as gpd
from rtree import index
from gerrychain import Graph
from networkx import is_connected, connected_components
def get_precincts(path):
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs("epsg:2248")
    return gdf
def find_neighbors(gdf):
    idx = index.Index()
    for i, geometry in enumerate(gdf.geometry):
        #store the left, right, up, down boundaries of each geometry alongside index
        idx.insert(i, geometry.bounds)
    #neighbors (edges) list
    neighbors = {}
    for i, polygon in enumerate(gdf.geometry):
        # Get the bounds of the polygon
        bounds = polygon.bounds
        
        # Find the intersecting bounds in the index
        intersecting = list(idx.intersection(bounds))
        
        # Get the neighbors by checking for intersection with other polygons
        neighbors[i] = []
        for j in intersecting:
            if i != j:
                other_polygon = gdf.iloc[j].geometry
                if polygon.distance(other_polygon) < 200:
                    neighbors[i].append(j)
    return neighbors
def make_graph(neighbors, path, gdf):
    graph = Graph(neighbors)
    graph.add_data(gdf)
    graph.geometry = gdf.geometry
    #remove islands
    components = list(connected_components(graph))
    biggest_component_size = max(len(c) for c in components)
    islands = [c for c in components if len(c) != biggest_component_size]
    for component in islands:
        for node in component:
            graph.remove_node(node)
    graph.to_json(path, include_geometries_as_geojson=True)
def neighbors(state):
    statePath = './generated/'+ state + '/preprocess/'
    gdf = get_precincts(statePath + 'merged'+ state +'P.geojson')
    neighbors = find_neighbors(gdf)
    make_graph(neighbors, statePath + 'graph'+ state +'.json', gdf)
    gdf = get_precincts(statePath + 'merged'+ state +'P20.geojson')
    neighbors = find_neighbors(gdf)
    make_graph(neighbors, statePath + 'graph'+ state +'20.json', gdf)
def neighbors_all():
    neighbors('NY')
    neighbors('GA')
    neighbors('IL')
if __name__ == '__main__':
    neighbors_all()