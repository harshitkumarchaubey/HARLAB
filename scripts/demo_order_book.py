from harlab.market.matching_engine import MatchingEngine
from harlab.market.market_metrics import order_imbalance, mid_price
from harlab.simulation.market_simulator import seed_demo_market

engine = MatchingEngine()
seed_demo_market(engine)
book = engine.book

print("HARLAB | Demonstration order book")
print("---------------------------------")
print("Bids:", book.depth("buy", 5))
print("Asks:", book.depth("sell", 5))
print("Best bid:", book.best_bid)
print("Best ask:", book.best_ask)
print("Spread:", book.spread)
print("Mid-price:", mid_price(book))
print("Top-level imbalance:", order_imbalance(book))
