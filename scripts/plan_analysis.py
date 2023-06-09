import geopandas as gpd
from settings import HUSKIES_HOME
def calculate_differences(plan_20, plan_new, incumbent_mappings, changes):
    for incumbent in incumbent_mappings:
        id_20 = incumbent_mappings[incumbent]["id_20"]
        id_new = incumbent_mappings[incumbent]["id_new"]
        precincts_added = plan_new.parts[id_new] - plan_20.parts[id_20]
        for change in changes:
            added = sum(plan_20.graph.nodes[x][change] for x in precincts_added)
            total = sum(plan_20.graph.nodes[x][change] for x in plan_new.parts[id_new])
            variation = added / total
            incumbent_mappings[incumbent][change + "_variation"] = variation
def precincts_to_districts(plan_new, path, state):
    precincts = gpd.read_file(path)
    new_districts = [0 for x in range(len(precincts))]
    for i in plan_new.parts:
        for j in plan_new.parts[i]:
            new_districts[j] = i
    precincts["district_id"] = new_districts
    precincts.set_geometry("geometry")
    if state == "NY":
        precincts = precincts.drop(7041)
    new_districts = precincts.dissolve(
        by="district_id",
        aggfunc={key: 'sum' for key in filter(lambda x: x in 
                                              ["pop_total", "vap_total", "vap_white", "vap_black", 
                                               "vap_native", "vap_asian", "vap_hwn", "vap_other", 
                                               "vap_mixed", "vap_hisp", "republican", "democrat"], 
                                               list(precincts.columns))})
    return new_districts
def add_properties(new_districts, changes):
    new_properties = {"incumbent_party"}
    for change in changes:
        new_properties.add(change + "_variation")
    new_districts["incumbent"] = None
    new_districts["winner_party"] = None
    for property in new_properties:
        new_districts[property] = None
    new_districts = new_districts.reset_index(drop=True)
    return new_districts, new_properties
def calc_safe_seats(new_districts):
    new_districts["safe_seat"] = False
    for i in range(len(new_districts)):
        dem_votes = new_districts["democrat"][i]
        rep_votes = new_districts["republican"][i]
        dem_proportion = dem_votes / (dem_votes + rep_votes)
        rep_proportion = rep_votes / (dem_votes + rep_votes)
        if dem_proportion > 0.5:
            new_districts.loc[i, "winner_party"] = "D"
            if dem_proportion > 0.55:
                new_districts.loc[i, "safe_seat"] = True
        else:
            new_districts.loc[i, "winner_party"] = "R"
            if rep_proportion > 0.55:
                new_districts.loc[i, "safe_seat"] = True
    return new_districts
def fill_new_properties(new_districts, new_properties, incumbent_mappings):
    for incumbent in incumbent_mappings:
        new_districts.loc[incumbent_mappings[incumbent]['id_new'], "incumbent"] = incumbent
        for property in new_properties:
            new_districts.loc[incumbent_mappings[incumbent]['id_new'], property] = incumbent_mappings[incumbent][property]
    return new_districts
def analyze_plan(plan_20, plan_new, incumbent_mappings, state):
    changes = {"vap_total", "area", "vap_black", "vap_white", "vap_hisp","democrat", "republican"}
    calculate_differences(plan_20, plan_new, incumbent_mappings, changes)
    new_districts = precincts_to_districts(
        plan_new, 
        f'{HUSKIES_HOME}/generated/{state}/preprocess/merged{state}P.geojson', 
        state)
    new_districts, new_properties = add_properties(new_districts, changes)
    new_districts = calc_safe_seats(new_districts)
    new_districts = fill_new_properties(new_districts, new_properties, incumbent_mappings)
    return new_districts