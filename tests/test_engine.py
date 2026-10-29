# SPDX-License-Identifier: GPL-3.0-or-later
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from veintiuno.engine.cards import Card, Shoe, hand_total  # noqa: E402
from veintiuno.engine.game import (  # noqa: E402
    BETTING, BLACKJACK, BUST, INSURANCE, LOSE, PLAYER, PUSH, ROUND_OVER, SURRENDERED, WIN, Game,
)
from veintiuno.engine.rules import Rules  # noqa: E402
from veintiuno.engine.strategy import DOUBLE, HIT, SPLIT, STAND, SURRENDER, recommend  # noqa: E402

S, H, D, C = range(4)


def cards(*ranks):
    return [Card(r, i % 4) for i, r in enumerate(ranks)]


def game_with(order, rules=None, bankroll=1000, bet=10):
    """Start a round where the shoe deals `order` (player, dealer, player, hole, ...)."""
    game = Game(rules or Rules(), bankroll, rng=random.Random(1))
    game.shoe.stack(cards(*order))
    game.add_chip(bet)
    game.deal()
    return game


class HandTotals(unittest.TestCase):
    def test_soft_and_hard(self):
        self.assertEqual(hand_total(cards(1, 6)), (17, True))
        self.assertEqual(hand_total(cards(1, 6, 10)), (17, False))
        self.assertEqual(hand_total(cards(1, 1, 9)), (21, True))
        self.assertEqual(hand_total(cards(13, 12)), (20, False))

    def test_shoe_size_and_shuffle(self):
        shoe = Shoe(2, 0.75, random.Random(3))
        self.assertEqual(shoe.remaining, 104)
        for _ in range(78):
            shoe.draw()
        self.assertTrue(shoe.needs_shuffle)


class Rounds(unittest.TestCase):
    def test_player_blackjack_pays_3_to_2(self):
        g = game_with([1, 9, 13, 7])
        self.assertEqual(g.phase, ROUND_OVER)
        self.assertEqual(g.hands[0].result, BLACKJACK)
        self.assertEqual(g.bankroll, 1015)

    def test_six_to_five(self):
        g = game_with([1, 9, 13, 7], Rules(blackjack_pays="6:5"))
        self.assertEqual(g.bankroll, 1012)

    def test_dealer_blackjack_peek(self):
        g = game_with([10, 10, 9, 1])
        self.assertEqual(g.phase, ROUND_OVER)
        self.assertEqual(g.hands[0].result, LOSE)
        self.assertEqual(g.bankroll, 990)

    def test_both_blackjack_push(self):
        g = game_with([1, 10, 10, 1])
        self.assertEqual(g.hands[0].result, PUSH)
        self.assertEqual(g.bankroll, 1000)

    def test_hit_bust(self):
        g = game_with([10, 9, 6, 8, 10])
        self.assertEqual(g.phase, PLAYER)
        g.hit()
        self.assertEqual(g.hands[0].result, BUST)
        self.assertEqual(g.bankroll, 990)
        # Dealer doesn't draw when every hand busted.
        self.assertEqual(len(g.dealer.cards), 2)

    def test_stand_and_dealer_busts(self):
        g = game_with([10, 6, 8, 10, 10])
        g.stand()
        self.assertTrue(g.dealer.busted)
        self.assertEqual(g.hands[0].result, WIN)
        self.assertEqual(g.bankroll, 1010)

    def test_dealer_soft17(self):
        order = [10, 1, 8, 6, 4]
        s17 = game_with(order, Rules(dealer_hits_soft17=False, insurance=False))
        s17.stand()
        self.assertEqual(s17.dealer.total, 17)
        self.assertEqual(s17.hands[0].result, WIN)
        h17 = game_with(order, Rules(dealer_hits_soft17=True, insurance=False))
        h17.stand()
        self.assertEqual(h17.dealer.total, 21)
        self.assertEqual(h17.hands[0].result, LOSE)

    def test_double(self):
        g = game_with([5, 9, 6, 7, 10, 10])
        self.assertTrue(g.can_double())
        g.double()
        self.assertEqual(g.hands[0].bet, 20)
        self.assertEqual(g.hands[0].total, 21)
        self.assertEqual(g.dealer.total, 26)
        self.assertEqual(g.bankroll, 1020)

    def test_double_restricted(self):
        g = game_with([5, 9, 3, 7], Rules(double_on="10-11"))
        self.assertFalse(g.can_double())

    def test_split_and_play_both(self):
        g = game_with([8, 10, 8, 7, 3, 10, 10])
        self.assertTrue(g.can_split())
        g.split()
        self.assertEqual(len(g.hands), 2)
        self.assertEqual(g.hands[0].total, 11)
        self.assertTrue(g.can_double())  # double after split allowed by default
        g.stand()
        self.assertEqual(g.hands[1].total, 18)
        g.stand()
        self.assertEqual(g.phase, ROUND_OVER)
        self.assertEqual([h.result for h in g.hands], [LOSE, WIN])
        self.assertEqual(g.bankroll, 1000)

    def test_split_aces_one_card(self):
        g = game_with([1, 9, 1, 7, 13, 5, 10])
        g.split()
        self.assertEqual(g.phase, ROUND_OVER)
        self.assertEqual(g.hands[0].total, 21)
        self.assertFalse(g.hands[0].is_blackjack)
        self.assertEqual(g.hands[0].result, WIN)
        self.assertEqual(g.hands[1].total, 16)

    def test_max_hands(self):
        g = game_with([8, 10, 8, 7, 8, 8, 8], Rules(max_hands=2))
        g.split()
        self.assertFalse(g.can_split())

    def test_surrender(self):
        g = game_with([10, 10, 6, 9])
        self.assertTrue(g.can_surrender())
        g.surrender()
        self.assertEqual(g.hands[0].result, SURRENDERED)
        self.assertEqual(g.bankroll, 995)

    def test_insurance_wins(self):
        g = game_with([10, 1, 9, 13])
        self.assertEqual(g.phase, INSURANCE)
        g.insurance(True)
        self.assertEqual(g.phase, ROUND_OVER)
        self.assertEqual(g.bankroll, 1000)  # lose 10, insurance pays 5 * 2

    def test_insurance_loses(self):
        g = game_with([10, 1, 9, 5])
        g.insurance(True)
        self.assertEqual(g.phase, PLAYER)
        self.assertEqual(g.bankroll, 985)

    def test_no_hole_card_loses_double(self):
        rules = Rules(dealer_peek=False)
        g = game_with([6, 10, 5, 10, 1], rules)
        self.assertEqual(len(g.dealer.cards), 1)
        g.double()
        self.assertTrue(g.dealer.is_blackjack)
        self.assertEqual(g.hands[0].result, LOSE)
        self.assertEqual(g.bankroll, 980)

    def test_betting_limits_and_rebet(self):
        g = Game(Rules(min_bet=5, max_bet=50), 30, rng=random.Random(2))
        self.assertFalse(g.add_chip(100))
        self.assertTrue(g.add_chip(25))
        self.assertFalse(g.add_chip(25))
        g.deal()
        while g.phase not in (ROUND_OVER,):
            if g.phase == INSURANCE:
                g.insurance(False)
            else:
                g.stand()
        g.new_round()
        self.assertEqual(g.phase, BETTING)
        self.assertEqual(g.bet, 0)

    def test_pending_rules_apply_next_round(self):
        g = game_with([10, 9, 6, 8, 10])
        g.set_rules(Rules(decks=2))
        self.assertEqual(g.shoe.decks, 6)
        g.hit()
        g.new_round()
        self.assertEqual(g.shoe.decks, 2)

    def test_random_rounds_conserve_money(self):
        g = Game(Rules(), 10_000, rng=random.Random(7))
        rng = random.Random(9)
        for _ in range(3000):
            if g.is_broke:
                g.rebuy(1000)
            g.add_chip(rng.choice([5, 10, 25]))
            before = g.bankroll
            g.deal()
            while g.phase != ROUND_OVER:
                if g.phase == INSURANCE:
                    g.insurance(rng.random() < 0.3)
                    continue
                action = g.advice()
                {HIT: g.hit, STAND: g.stand, DOUBLE: g.double,
                 SPLIT: g.split, SURRENDER: g.surrender}[action]()
            self.assertAlmostEqual(g.bankroll - before, g.round_net)
            g.new_round()
        self.assertEqual(g.stats.decisions, g.stats.correct_decisions)


class Strategy(unittest.TestCase):
    def rec(self, hand, up, rules=None, double=True, split=True, surrender=True):
        return recommend(cards(*hand), Card(up, S), rules or Rules(),
                         can_double=double, can_split=split, can_surrender=surrender)

    def test_hard(self):
        self.assertEqual(self.rec([10, 6], 10), SURRENDER)
        self.assertEqual(self.rec([10, 6], 10, surrender=False), HIT)
        self.assertEqual(self.rec([10, 2], 4), STAND)
        self.assertEqual(self.rec([10, 2], 3), HIT)
        self.assertEqual(self.rec([6, 5], 10), DOUBLE)
        self.assertEqual(self.rec([6, 5], 1), HIT)
        self.assertEqual(self.rec([6, 5], 1, Rules(dealer_hits_soft17=True)), DOUBLE)

    def test_soft(self):
        self.assertEqual(self.rec([1, 7], 3), DOUBLE)
        self.assertEqual(self.rec([1, 7], 3, double=False), STAND)
        self.assertEqual(self.rec([1, 7], 9), HIT)
        self.assertEqual(self.rec([1, 6], 2), HIT)

    def test_pairs(self):
        self.assertEqual(self.rec([8, 8], 10), SPLIT)
        self.assertEqual(self.rec([1, 1], 1), SPLIT)
        self.assertEqual(self.rec([10, 10], 6), STAND)
        self.assertEqual(self.rec([9, 9], 7), STAND)
        self.assertEqual(self.rec([5, 5], 6), DOUBLE)
        self.assertEqual(self.rec([2, 2], 2, Rules(double_after_split=False)), HIT)


if __name__ == "__main__":
    unittest.main()
