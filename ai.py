import networkx as nx
import json

with open('risk/probabilities.json') as prob_file:
    PROBS = {tuple(int(i) for i in k.strip('()').split(',')) : v 
                for k, v in json.load(prob_file).items(prob_file)}    

with open('risk/troop_loss.json') as troop_file:
    TROOP_LOSS = {tuple(int(i) for i in k.strip('()').split(',')) : v 
                for k, v in json.load(troop_file).items()}

PREF = 1

def best_country(board):
    unoccupied = [c for c in board.countries.values() if not c.owner]
    if unoccupied:
        k = lambda country : position_value(country, board)
        return max([c for c in board.countries.values() if not c.owner], key = k)
    return None

def deploy_troops(player):
    num_troops = player.troops_to_deploy
    risk = country_risk(player)
    tv = sum(risk.values())
    return {country : int(round(num_troops * val / tv)) for country, val in risk.items()}

def best_attack(player, board):
    possible_attacks = [(c1,c2)
                            for c1 in player.countries
                            for c2 in c1.border_countries
                            if c1.troops > 1 
                            and c2 not in player.countries]
    k = lambda (base, target): ev_attack(base, target, player, board)
    attack = max(possible_attacks, key=k)
    if k(attack) > 0: return attack


def make_graph(board):    
    G = nx.DiGraph()
    for name, country in board.countries.items():
        for c2 in country.border_countries:
            G.add_edge(name, c2.name)    
    return G


def fortify_value(board, country):
    G = make_graph(board)
    return 1 / nx.degree_centrality(G)[country.name]

def bonus_value(country, board, player):
    continent = board.continent_lookup[country.name]
    unconquered = len(continent.countries) - len([c for c in player.countries if c in continent.countries])
    if unconquered > 0: return continent.bonus / unconquered
    return 0

def ev_attack(base, target, player, board):
    if target.owner == player.name: return 0
    defenders = target.troops
    attackers = base.troops - 1
    probs, troops = get_probs_and_troops(attackers, defenders)
    ev_position = position_value(target, board, player) * probs
    return ev_position + (PREF * troops)

def get_probs_and_troops(attackers, defenders, n = 100):
    if attackers > n or defenders > n:
        m = float(max(attackers, defenders))
        attackers, defenders = int(round(n * attackers)) / int(round(m, n * defenders / m))
    return PROBS[(attackers, defenders)], TROOP_LOSS[(attackers, defenders)]

def position_value(country, board, player):
    return bonus_value(board, country, player) + fortify_value(board, country)


def country_risk(player):
    risk = {}
    for country in player.countries:
        for bc in country.border_countries:
            if bc not in player.countries:
                ev = ev_attack(bc, country, bc.owner)
                if country.name in risk: risk[country.name] += ev
                else: risk[country.name] = ev
    return risk

def reinforce(reinforce_countries, player):
    risk = country_risk(player)
    k = lambda (c1, c2): (c1.troops / risk[c1.name]) / (c2.troops / risk[c2.name])
    a, b = max(reinforce_countries, key = k)
    for move in range(1, a.troops):
        cont = (a.troops - move / risk[a.name]) > (b.troops + move / risk[b.name])
        if not cont:
            return a, b, move

