from risk.models import *
from ai import *
import unittest2

class Test(unittest2.TestCase):
    def setUp(self):
        self.board = import_board_data('risk/board_graph.json')
        self.players  = [Player('Peter'), Player('Paul'), Player('Mary')]

    def test_choose_country(self):
        while True:
            for player in self.players:
                country_choice = best_country(board)
                if country_choice:
                    player.choose_country(country_choice)
                else:
                    break

    def test_deploy_troops(self):
        for player in self.players:
            orders = deploy_troops(player)
            for country, num in orders.items():
                player.deploy_troops(country, num)

    def test_
