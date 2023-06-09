import pickle
from gerrychain import(GeographicPartition, Graph)
import pandas as pd
from collections import Counter
import json
import numpy as np
from plan_analysis import analyze_plan
from interesting_plan import find_interesting_plans
from settings import HUSKIES_HOME
from collections import defaultdict
def get_ensemble(state):
    graph = Graph.from_json(f'{HUSKIES_HOME}/generated/{state}/preprocess/graph{state}.json')
    assignments = []
    for i in range(4):
        some_assignments = pickle.load(
            open(f'{HUSKIES_HOME}/generated/{state}/assignments/assign_{state}_{str(i)}.p', 'rb'))
        assignments += some_assignments
    ensemble = [GeographicPartition(graph, a) for a in assignments]
    return ensemble
def setup_box_w_data(num_incumbents):
    properties = {"area_variations", "vap_total_variations", "vap_white_variations","vap_black_variations", 
                  "vap_hisp_variations","democrat_variations", "republican_variations"}
    box_w_data = dict()
    for property in properties:
        box_w_data[property] = [[] for x in range(num_incumbents)]
    return box_w_data
def map_incumbents(plan_20, plan_new, incumbents):
    incumbent_mappings = dict()
    for i in range(len(incumbents)):
        mapping = dict()
        mapping["incumbent_party"] = incumbents["party"][i]
        for precinct in plan_20.graph.nodes:
            if str(plan_20.graph.nodes[precinct]["geoid20"]) == str(incumbents["geoid20"][i]):
                mapping["id_20"] = plan_20.assignment[precinct]
                break
        for precinct in plan_new.graph.nodes:
            if str(plan_new.graph.nodes[precinct]["geoid20"]) == str(incumbents["geoid20"][i]):
                mapping["id_new"] = plan_new.assignment[precinct]
                break
        incumbent_mappings[incumbents["name"][i]] = mapping
    return incumbent_mappings
def calculate_split(plan, incumbent_mappings):
    precincts = plan.graph.nodes
    dem_winners = 0
    rep_winners = 0
    incumbent_winners = 0
    for district in plan.parts:
        dem_votes = sum(precincts[precinct]["democrat"] for precinct in plan.parts[district])
        rep_votes = sum(precincts[precinct]["republican"] for precinct in plan.parts[district])
        if dem_votes > rep_votes:
            dem_winners += 1
        elif rep_votes > dem_votes:
            rep_winners += 1
        for incumbent in incumbent_mappings:
            if incumbent_mappings[incumbent]["id_new"] == district:
                if incumbent_mappings[incumbent]["incumbent_party"] == "D" and dem_votes > rep_votes:
                    incumbent_winners += 1
                    break
                elif incumbent_mappings[incumbent]["incumbent_party"] == "R" and rep_votes > dem_votes:
                    incumbent_winners += 1
                    break
    return dem_winners, rep_winners, incumbent_winners
def calc_variations(plan_20, plan_new, incumbent_mappings):
    properties = {"vap_total", "area", "vap_black", "vap_white", "vap_hisp", "democrat", "republican"}
    variation_data = {incumbent:{"vap_total_variations":0, "area_variations":0, "vap_black_variations":0,
                                 "vap_white_variations":0, "vap_hisp_variations":0, "democrat_variations":0, 
                                 "republican_variations":0} 
                      for incumbent in incumbent_mappings}
    for incumbent in incumbent_mappings:
        id_20 = incumbent_mappings[incumbent]["id_20"]
        id_new = incumbent_mappings[incumbent]["id_new"]
        precincts_added = plan_new.parts[id_new] - plan_20.parts[id_20]
        for property in properties:
            added = sum(plan_20.graph.nodes[x][property] for x in precincts_added)
            total = sum(plan_20.graph.nodes[x][property] for x in plan_new.parts[id_new])
            variation = added / total
            variation_data[incumbent][property + "_variations"] = variation
    return variation_data
def update_incumbent_summary(incumbent_summary_data, variation_data):
    for incumbent in incumbent_summary_data:
        incumbent_summary_data[incumbent]["area_variations"].append(variation_data[incumbent]["area_variations"])
        incumbent_summary_data[incumbent]["vap_total_variations"].append(variation_data[incumbent]["vap_total_variations"])
def update_box_w_data(box_w_data, variation_data):
    box_w_lists = defaultdict(list)
    for incumbent in variation_data:
        for property in variation_data[incumbent]:
            box_w_lists[property].append(variation_data[incumbent][property])
    for property in box_w_lists:
        sorted_list = sorted(box_w_lists[property])
        for i in range(len(sorted_list)):
            box_w_data[property][i].append(sorted_list[i])
def find_quartiles(box_w_data):
    for property in box_w_data:
        for i in range(len(box_w_data[property])):
            curr_list = box_w_data[property][i]
            box_w_data[property][i] = list(np.percentile(curr_list,[0,25,50,75,100]))
def find_averages(incumbent_summary_data):
    total_geo_var = 0
    total_pop_var = 0
    var_count = 0
    for incumbent in incumbent_summary_data:
        total_geo_var += sum(incumbent_summary_data[incumbent]["area_variations"])
        total_pop_var += sum(incumbent_summary_data[incumbent]["vap_total_variations"])
        var_count += len(incumbent_summary_data[incumbent]["area_variations"])
    return total_geo_var / var_count, total_pop_var / var_count
def get_json(state):
    ensemble_data_path = f'{HUSKIES_HOME}/generated/{state}/enacted_data.json'
    with open(ensemble_data_path, 'r') as f:
        data = json.load(f)
    return data
def analyze_ensemble(state):
    ensemble = get_ensemble(state)
    incumbents = pd.read_csv(f'{HUSKIES_HOME}/data/{state}/incumbents_{state}.csv')
    graph_20 = Graph.from_json(f'{HUSKIES_HOME}/generated/{state}/preprocess/graph{state}20.json')
    plan_20 = GeographicPartition(graph_20, assignment="district_id_20")
    winner_split = Counter()
    total_incumbent_winners = 0
    incumbent_summary_data = {name:{"area_variations":[], "vap_total_variations":[]} for name in incumbents["name"]}
    box_w_data = setup_box_w_data(len(incumbents))
    FAIR_SCORE_INIT, FAVORED_SCORE_INIT, VAR_SCORE_INIT = 1, -100, 0
    interesting_criteria = {"fairest_seat_vote":FAIR_SCORE_INIT,
                            "most_democrat_favored":FAVORED_SCORE_INIT, 
                            "most_republican_favored":FAVORED_SCORE_INIT, 
                            "highest_geo_pop_var":VAR_SCORE_INIT, 
                            "fairest_geo_pop_var":FAIR_SCORE_INIT}
    interesting_plans = {"fair_seat_vote":None, "democrat_favored":None, "republican_favored":None, 
                         "high_geo_pop_var":None, "fair_geo_pop_var":None}
    for plan in ensemble:
        incumbent_mappings = map_incumbents(plan_20,plan,incumbents)
        dem_winners, rep_winners, incumbent_winners = calculate_split(plan, incumbent_mappings)
        winner_split[str(dem_winners) + "/" + str(rep_winners)] += 1
        total_incumbent_winners += incumbent_winners
        variation_data = calc_variations(plan_20, plan, incumbent_mappings)
        update_incumbent_summary(incumbent_summary_data, variation_data)
        update_box_w_data(box_w_data, variation_data)
        find_interesting_plans(plan_20, plan, incumbent_mappings, interesting_criteria, interesting_plans)
    find_quartiles(box_w_data)
    average_geo_var, average_pop_var = find_averages(incumbent_summary_data)
    ensemble_summary = {"num_plans": len(ensemble), 
                        "num_incumbents": len(incumbents), 
                        "avg_incumbent_winners": total_incumbent_winners / len(ensemble), 
                        "avg_geo_var":average_geo_var, 
                        "avg_pop_var":average_pop_var}
    enacted_data = get_json(state)
    state_data = {"name": state, 
                  "ensemble_summary": ensemble_summary, 
                  "winner_split": winner_split, 
                  "box_w_data": box_w_data, 
                  "incumbent_data": incumbent_summary_data,
                  "enacted_data": enacted_data}
    for criteria in interesting_plans:
        incumbent_mappings = map_incumbents(plan_20, interesting_plans[criteria], incumbents)
        interesting_plan = analyze_plan(plan_20, interesting_plans[criteria], incumbent_mappings, state)
        interesting_plan.to_file(f'{HUSKIES_HOME}/generated/{state}/interesting/{criteria}_plan.geojson', driver='GeoJSON')
    with open(f'{HUSKIES_HOME}/generated/{state}/ensemble_data.json', 'w') as outfile:
        json.dump(state_data, outfile)
def analyze_all():
    analyze_ensemble("GA")
    analyze_ensemble("NY")
    analyze_ensemble("IL")
if __name__ == '__main__':
    analyze_all()