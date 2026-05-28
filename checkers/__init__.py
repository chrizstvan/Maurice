from .flights import FlightsChecker
from .trains import TrainsChecker

# To add a new checker: import it and add one entry here.
# That's the only file you need to touch (besides the new checker file itself
# and adding its routes to config.CHECKER_ROUTES).
REGISTRY: dict = {
    "flights": FlightsChecker,
    "trains":  TrainsChecker,
}
