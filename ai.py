import networkx as nx
import json
import random
import math
from operator import itemgetter

PREF = 3

with open('./risk/attacking_win_probs_50_50.json') as prob_file:
    PROBS = {tuple(int(i) for i in k.strip('()').split(',')) : v 
                for k, v in json.load(prob_file).items()}

with open('./risk/expected_troop_loss_50_50.json') as troop_file:
    TROOP_LOSS = {tuple(int(i) for i in k.strip('()').split(',')) : v 
                for k, v in json.load(troop_file).items()}

def best_country(G, board, player):
    """

        In the country choice round, the best country choice is the unoccupied country with the highest
        position value

    """
    unoccupied = [c for c in board.countries.values() if not c.owner]

    if unoccupied:
        k = lambda country : position_value(G, country, board, player)
        # print "Country value map: " + str({c.name : k(c) for c in unoccupied})
        return max(unoccupied, key = k)
    return None

def deploy_troops(G, player, board):
    """
        The best deployment is such that troops are sent proportionally to those countries with the highest
        risk

    :param player:
    :param board:
    :return:
    """

    num_to_deploy = num_troops = player.troops_to_deploy
    risk = country_risk(G, player, board)
    print "%s troops to deploy, with a risk schedule of %s" % (num_troops, str(risk))
    tv = sum(v for v in risk.values() if v > 0)
    orders = {}
    for country, val in sorted(risk.items(), key = itemgetter(1), reverse = True):
        if num_troops == 0: break
        if val > 10e-10:
            tps = min(num_troops, math.ceil(num_to_deploy * float(val) / tv))
            orders[country] = tps
            num_troops -= tps
    return orders


def best_attack(G, player, board):
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
    k = lambda (base, target): ev_attack(G, base, target, player, board)
    base, target = attack = max(possible_attacks, key = k)
    if k(attack) > 5:
        print "%s attacking %s, with an attack estimated value of %s" % (base.name, target.name, k((base, target)))
        return attack
    # attacks = sorted(possible_attacks, key=k, reverse = True)
    # while attacks:
    #     base, target = attacks.pop(0)
    #     if base.troops > 3:
    #         print "%s attacking %s, with an attack estimated value of %s" % (base.name, target.name, k((base, target)))
    #         return base, target
    # return None
    # print "EV of attack: " + str(k(attack))
    # # put provision for spreading self too thin
    # if k(attack) > 0: return attack


def make_graph(board):
    G = nx.Graph()
    for name, country in board.countries.items():
        for c2 in country.border_countries:
            if not G.has_edge(name, c2.name):
                G.add_edge(name, c2.name)
    return G

# def fortify_value(G, country):
#     """
#         A country's fortifiability value is the inverse of its degree centrality
#     """
#     val = nx.degree_centrality(G)[country.name]
#     print "DEGREE CENTRALITY: %s" % val
#     # G = make_graph(board)
#     return 1 / val

def bonus_value(board, country, player):
    """
        A country's bonus value is the contribution its capture would add to a possible bonus

    :param board:
    :param country:
    :param player:
    """
    continent = board.continent_lookup[country.name]
    # print "%s countries in %s, of which player has %s" % (len(continent.countries), continent.name, len([c for c in player.countries if c in continent.countries]))
    unconquered = len(continent.countries) - len([c for c in player.countries if c in continent.countries])
    if unconquered > 0: return float(continent.bonus) / unconquered
    return 1

def position_value(G, country, board, player):
    """
        The position value of a country increases proportionately to its value as a bonus component
        along with the square of its fortifiability value
    """
    fort = nx.degree_centrality(G)[country.name]
    clustering = nx.clustering(G, player.countries + [country.name])[country.name]
    return  math.sqrt(clustering) / fort

def ev_attack(G, base, target, player, board):
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
    ev_target_position = position_value(G, target, board, player) * prob_win_attacker
    troop_change_ratio = d_troop_loss / a_troop_loss
    return troop_change_ratio * ev_target_position
    # * troop_change_ratio


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


def country_risk(G, player, board):
    """
        The risk of a player's countries is the networked troop positions in connected enemy countries

    :param player:
    :param board:
    :return:
    """
    # G = make_graph(board)
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


# def country_risk(G, player, board):
#     return {c.name : max(10e-10, sum(e.troops for e in c.border_countries if e.owner != player)) for c in player.countries}


def reinforce(G, reinforce_countries, player, board):
    """
        A reinforcemnt is send to the country with the lowest troop to risk ratio from the boardering country with
        the highest troop to risk ratio.

    :param reinforce_countries:
    :param player:
    :param board:
    :return:
    """
    risk = country_risk(G, player, board)
    k = lambda (c1, c2): (float(c1.troops) / risk[c1.name]) / (float(c2.troops) / risk[c2.name])
    a, b = max(reinforce_countries, key = k)
    move = 1
    while (a.troops - move / risk[a.name]) > (b.troops + move / risk[b.name]) and a.troops - move > 1:
        move += 1
    return a, b, move

def troops_to_move(G, attacking_country, defending_country, player, board, attacking_troops):
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
                val = ev_attack(G, attacking_country, defending_country, player, board)
                t[country.name] += val

    staying, moving = (attacking_country.troops - attacking_troops), 0
    ratio= 10
    while ratio > 1 and staying > 1:
        moving += 1
        staying -= 1
        ratio = (staying / t[attacking_country.name]) / (moving/ t[defending_country.name])
    return moving