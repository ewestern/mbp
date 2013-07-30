import networkx as nx
import json
import random
import math
from operator import itemgetter

with open('./risk/attacking_win_probs_10_10.json') as prob_file:
    PROBS = {tuple(int(i) for i in k.strip('()').split(',')) : v 
                for k, v in json.load(prob_file).items()}

with open('./risk/expected_troop_loss_10_10.json') as troop_file:
    TROOP_LOSS = {tuple(int(i) for i in k.strip('()').split(',')) : v 
                for k, v in json.load(troop_file).items()}

PREF = 1

def best_country(board, player):
    unoccupied = [c for c in board.countries.values() if not c.owner]
    if unoccupied:
        k = lambda country : position_value(country, board, player)
        return max([c for c in board.countries.values() if not c.owner], key = k)
    return None

def deploy_troops(player, board):
    num_to_deploy = num_troops = player.troops_to_deploy
    risk = country_risk(player, board)
    tv = sum(risk.values())
    orders = {}
    if sum(risk.values()) <= 10e-10 * len(risk):
        return {random.choice(risk.keys()) : num_troops}
    while num_troops > 0:
        if len(risk) == 0: break
        country, val = max(risk.items(), key=itemgetter(1))
        del risk[country]
        if val > 10e-10:
            tps = max(math.ceil(num_to_deploy * val / tv), num_troops)
            # tps = max(1, int(round())
            orders[country] = tps
            num_troops -= tps
    return orders

def best_attack(player, board):
    possible_attacks = [(c1,c2)
                            for c1 in player.countries
                            for c2 in c1.border_countries
                            if c1.troops > 1 
                            and c2 not in player.countries]
    if not possible_attacks: return None
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

def bonus_value(board, country, player):
    continent = board.continent_lookup[country.name]
    unconquered = len(continent.countries) - len([c for c in player.countries if c in continent.countries])
    if unconquered > 0: return continent.bonus / unconquered
    return 0

def ev_attack(base, target, player, board):
    defenders = target.troops
    attackers = base.troops - 1
    if target.owner == player.name: return 0
    if attackers == 0: return 0
    probs, troops = get_probs_and_troops(attackers, defenders)
    ev_position = position_value(target, board, player) * probs
    return ev_position + (PREF * troops)

def get_probs_and_troops(attackers, defenders, n = 9):
    if attackers > n or defenders > n:
        m = float(max(attackers, defenders))
        attackers = max(1, min(n-1, int(round(n * attackers / m))))
        defenders = min(n-1, max(int(round(n * defenders / m)) , 1))
    return PROBS[(attackers, defenders)], TROOP_LOSS[(attackers, defenders)]

def position_value(country, board, player):
    return bonus_value(board, country, player) + fortify_value(board, country)


def country_risk(player, board):
    risk = {}
    for country in player.countries:
        risk[country.name] = 1e-10
        for bc in country.border_countries:
            if bc not in player.countries:
                r = ev_attack(bc, country, bc.owner, board)
                risk[country.name] += r
    return risk

def reinforce(reinforce_countries, player, board):
    risk = country_risk(player, board)
    k = lambda (c1, c2): (c1.troops / risk[c1.name]) / (c2.troops / risk[c2.name])
    a, b = max(reinforce_countries, key = k)
    for move in range(1, int(a.troops)):
        cont = (a.troops - move / risk[a.name]) > (b.troops + move / risk[b.name])
        if not cont:
            return a, b, move

def troops_to_move(attacking_country, defending_country, player, board, attacking_troops):
    t = {}
    for country in [attacking_country, defending_country]:
        t[country.name] = 10e-10
        for border in country.border_countries:
            if border not in player.countries:
                val = ev_attack(attacking_country, defending_country, player, board)
                t[country.name] += val

    staying, moving = (attacking_country.troops - attacking_troops), 0
    ratio= 10
    while ratio > 1 and staying > 1:
        moving += 1
        staying -= 1
        ratio = (staying / t[attacking_country.name]) / (moving/ t[defending_country.name])
    return moving