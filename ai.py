import networkx as nx
import json
import random
import math
from operator import itemgetter
from networkx.algorithms.shortest_paths.generic import shortest_path_length

with open('./risk/attacking_win_probs_50_50.json') as prob_file:
    PROBS = {tuple(int(i) for i in k.strip('()').split(',')) : v 
                for k, v in json.load(prob_file).items()}

with open('./risk/expected_troop_loss_50_50.json') as troop_file:
    TROOP_LOSS = {tuple(int(i) for i in k.strip('()').split(',')) : v 
                for k, v in json.load(troop_file).items()}

PREF = 1

def best_country(board, player):
    """

        In the country choice round, the best country choice is the unoccupied country with the highest
        position value

    """
    unoccupied = [c for c in board.countries.values() if not c.owner]
    if unoccupied:
        k = lambda country : position_value(country, board, player)
        return max([c for c in board.countries.values() if not c.owner], key = k)
    return None

def deploy_troops(player, board):
    """
        The best deployment is such that troops are sent proportionally to those countries with the highest
        risk

    :param player:
    :param board:
    :return:
    """
    num_to_deploy = num_troops = player.troops_to_deploy
    risk = country_risk(player, board)
    tv = sum(v for v in risk.values() if v > 0)
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
    # print "Total troops to deploy: %s" % num_to_deploy
    # print "Troop Depoyment: %s" % {c.name: c.troops for c in player.countries}
    return orders

def best_attack(player, board):
    """
        The best attack is simply the attack with the highest expected value.

    :param player:
    :param board:
    :return:
    """
    possible_attacks = [(c1,c2)
                            for c1 in player.countries
                            for c2 in c1.border_countries
                            if c1.troops > 1 
                            and c2 not in player.countries]
    if not possible_attacks: return None
    k = lambda (base, target): ev_attack(base, target, player, board)
    attack = max(possible_attacks, key=k)
    print "EV of attack: " + str(k(attack))
    if k(attack) > 0: return attack


def make_graph(board):
    G = nx.DiGraph()
    for name, country in board.countries.items():
        for c2 in country.border_countries:
            G.add_edge(name, c2.name)    
    return G

def fortify_value(board, country):
    """
        A country's fortifiability value is the inverse of its degree centrality
    """
    G = make_graph(board)
    return 1 / nx.degree_centrality(G)[country.name]

def bonus_value(board, country, player):
    """
        A country's bonus value is the contribution its capture would add to a possible bonus

    """
    continent = board.continent_lookup[country.name]
    unconquered = len(continent.countries) - len([c for c in player.countries if c in continent.countries])
    if unconquered > 0: return 1 + (continent.bonus / unconquered)
    return 1

def position_value(country, board, player):
    """
        The position value of a country increases proportionately to its value as a bonus component
        along with the square of its fortifiability value
    """
    return bonus_value(board, country, player) * fortify_value(board, country)

def ev_attack(base, target, player, board):
    """
        The expected value of an attack increases with the stategic value of the target position, along with
        the expected NET troop gain.

    :param base:
    :param target:
    :param player:
    :param board:
    :return:
    """
    defenders = target.troops
    attackers = base.troops - 1
    if target.owner == base.owner: return 0
    if attackers == 0: return 0
    prob_win_attacker, (a_troop_loss, d_troop_loss), = get_probs_and_troops(attackers, defenders)
    ev_target_position = position_value(target, board, player) * prob_win_attacker
    net_troop_change = d_troop_loss - a_troop_loss
    return ev_target_position * net_troop_change


def get_probs_and_troops(attackers, defenders, n = 50):
    """
        Returns the expected probability of attacker win, and expected troop loss on both sides for a conflaguration
        of a against d troops.

    :param attackers:
    :param defenders:
    :param n:
    :return:
    """
    if attackers > n or defenders > n:
        m = float(max(attackers, defenders))
        attackers = max(1, min(n-1, int(round(n * attackers / m))))
        defenders = min(n-1, max(int(round(n * defenders / m)) , 1))
    return PROBS[(attackers, defenders)], tuple(TROOP_LOSS[(attackers, defenders)])




def country_risk(player, board):
    """
        The risk of a player's countries is the networked troop positions in connected enemy countries

    :param player:
    :param board:
    :return:
    """
    G = make_graph(board)
    def walk(current, visited):
        val = 10e-10
        for neighbor in G.neighbors(current):
            if neighbor not in visited:
                visited.append(neighbor)
                val += sum(c.troops for c in board.countries[neighbor].border_countries if c.owner != player) + \
                0.5 * walk(neighbor, visited)
        return val

    risk = {}
    for country in player.countries:
        visited = []
        risk[country.name] = walk(country.name, visited)
    return risk

def reinforce(reinforce_countries, player, board):
    """
        A reinforcemnt is send to the country with the lowest troop to risk ratio from the boardering country with
        the highest troop to risk ratio.

    :param reinforce_countries:
    :param player:
    :param board:
    :return:
    """
    risk = country_risk(player, board)
    k = lambda (c1, c2): (c1.troops / risk[c1.name]) / (c2.troops / risk[c2.name]) \
        if c1.troops > 1 and risk[c1.name] > 0 and risk[c2.name] > 0 else 0
    a, b = max(reinforce_countries, key = k)
    move = 1
    while (a.troops - move / risk[a.name]) > (b.troops + move / risk[b.name]) and a.troops - move > 1:
        move += 1
    return a, b, move

def troops_to_move(attacking_country, defending_country, player, board, attacking_troops):
    """
        Calculates how many troops to invade with, given a win. Attempts to equalize troop / risk ratios between
        base and target countries

    :param attacking_country:
    :param defending_country:
    :param player:
    :param board:
    :param attacking_troops:
    :return:
    """
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

