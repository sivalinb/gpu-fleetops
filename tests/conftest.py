import pytest

from fleetops.config import Settings
from fleetops.lab import Lab
from fleetops.service import FleetOps
from fleetops.store import Store
from fleetops.telemetry import Telemetry


@pytest.fixture
def telemetry():
    meter = Telemetry()
    meter.logger.disabled = True
    yield meter
    meter.close()


@pytest.fixture
def store():
    database = Store()
    yield database
    database.close()


@pytest.fixture
def lab(store, telemetry):
    return Lab(store, "test-lab", telemetry, start_time=1700000000)


@pytest.fixture
def service():
    instance = FleetOps(Settings(database_url="sqlite:///:memory:", api_token="operator-test-token"))
    instance.telemetry.logger.disabled = True
    yield instance
    instance.close()
