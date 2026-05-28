from .flights import FlightsChecker
from .trains import TrainsChecker
from .hotels import HotelsChecker

REGISTRY: dict = {
    "flights": FlightsChecker,
    "trains":  TrainsChecker,
    "hotels":  HotelsChecker,
}
