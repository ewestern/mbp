import sys
from flask import Flask, request
from risk.models import *
import json
import random
from ai import *

app = Flask(__name__)

def unpack_json(r):
    board = import_board_data('./risk/board_graph.json')
    me_data = r['you']
    game = r['game']
    me = Player(me_data['name'])
    me.earned_cards_this_turn = me_data['earned_cards_this_turn']
    me.is_eliminated = me_data['is_eliminated']
    me.troops_to_deploy = me_data['troops_to_deploy']
    me.available_actions = me_data['available_actions']
    me.countries = [board.countries[c] for c in me_data['countries']]
    me.cards = [board.cards[c['country_name']] for c in me_data['cards']]
    players = {n:Player(n) for n in game['players'] if n != me.name}
    players[me.name] = me
    players['none'] = None
    for country_name in game['countries']:
        board.countries[country_name].owner = players[game['countries'][country_name]['owner']]
        board.countries[country_name].troops = game['countries'][country_name]['troops']
    return me, players, board

@app.route("/status")
def status():
    print 'got status check'
    return ''

@app.route("/not_turn")
def not_turn():
    print 'got board'
    return ''

@app.route('/turn', methods=['POST'])
def turn():
    ind = "     "
    r = json.loads(request.form['risk'])
    me, players, board = unpack_json(r)
    board.continent_lookup = {c_name : cont for cont_name, cont in board.continents.items() for c_name, country in cont.countries.items()}
    print "Starting turn with the following allocation: \n" + ind + str('\n'.join([ind + c.name + " : " + str(c.troops) for c in me.countries]))
    print "List of countries with total enemy troops bordering: " + str('\n'.join([ind + c.name + " : " + str(sum([e.troops for e in c.border_countries if e.owner != me]))
                                                                        for c in me.countries]))
    print me.available_actions
    if "choose_country" in me.available_actions:
        country_choice = best_country(board, me)
        response = {"action":"choose_country", "data":country_choice.name}
        print "choose: %s" % country_choice.name
        return json.dumps(response)

    elif "spend_cards" in me.available_actions:
        combos = itertools.combinations(me.cards,3)
        potential_sets = [c for c in combos if c[0].is_set_with(c[1],c[2])]
        trade_in = random.choice(potential_sets)
        trade_in = [c.country_name for c in trade_in]
        response = {'action':'spend_cards', 'data':trade_in}
        print "traded in cards %s" % trade_in
        return json.dumps(response)

    elif "deploy_troops" in me.available_actions:
        orders = deploy_troops(me, board)
        response = {"action":"deploy_troops", "data":orders}
        print "deploy orders: %s" % orders
        return json.dumps(response)

    elif "attack" in me.available_actions:
        best = best_attack(me, board)
        if best is None:
            response = {"action":"end_attack_phase"}
            print "I choose not to fight"
        else:

            attacking_country, defending_country = best
            attacking_troops = min(3, attacking_country.troops-1)
            moving_troops = troops_to_move(attacking_country,defending_country,me, board, attacking_troops)
            data = {'attacking_country':attacking_country.name,
                    'defending_country':defending_country.name,
                    'attacking_troops':attacking_troops,
                    'moving_troops':moving_troops}
            response = {'action':'attack', 'data':data}
            print "attacking %s, which has %s troops,  from %s with %s troops, with an occupying force of %s" \
                                                        % (defending_country.name,
                                                            defending_country.troops,
                                                           attacking_country.name,
                                                           attacking_troops,
                                                           moving_troops)
        return json.dumps(response)

    elif "reinforce" in me.available_actions:
        reinforce_countries = [(c1,c2) for c1 in me.countries
                                for c2 in c1.border_countries
                                if c1.troops > 1
                                and c2 in me.countries]

        if not reinforce_countries:
            print "ended turn"
            response = {"action":"end_turn"}
            return json.dumps(response)
        origin_country, destination_country, moving_troops = reinforce(reinforce_countries, me, board)
        print "reinforced %s from %s with %s troops" % (destination_country.name, origin_country.name, moving_troops)
        response = {'action':'reinforce', 'data':{'origin_country':origin_country.name,
                                                  'destination_country':destination_country.name,
                                                  'moving_troops':moving_troops}}
        return json.dumps(response)

    print "something broke"
    return ''

if __name__ == '__main__':
    port = int(sys.argv[1])
    app.run(debug=True, host="0.0.0.0", port=port)
