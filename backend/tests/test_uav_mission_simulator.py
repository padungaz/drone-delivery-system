import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pytest
from app.services.uav_mission_simulator import (
    UavMissionSimulator,
    calculate_bearing,
    calculate_distance,
)


@pytest.mark.asyncio
async def test_geographic_calculations():
    # Da Nang Home Pad to Destination (~850m)
    lat1, lon1 = 16.0544, 108.2022
    lat2, lon2 = 16.0592, 108.2085

    dist = calculate_distance(lat1, lon1, lat2, lon2)
    assert 700 < dist < 1200, f"Distance should be around 850m, got {dist}"

    bearing = calculate_bearing(lat1, lon1, lat2, lon2)
    assert 0 <= bearing <= 360, f"Bearing should be between 0 and 360, got {bearing}"


@pytest.mark.asyncio
async def test_simulator_lifecycle():
    sim = UavMissionSimulator()
    sim.speed_multiplier = 10.0  # Ultra fast for testing

    # Start flight
    status = await sim.start_flight(
        mission_id=999,
        mission_type="DRONE_DELIVERY",
        home_lat=16.0544,
        home_lon=108.2022,
        target_lat=16.0560,
        target_lon=108.2040,
        speed_multiplier=10.0,
    )
    assert status["is_running"] is True
    assert status["mission_id"] == 999
    assert status["flight_phase"] == "TAKEOFF"

    # Pause flight
    pause_status = await sim.pause_flight()
    assert pause_status["is_paused"] is True
    assert pause_status["current"]["speed"] == 0.0

    # Resume flight
    resume_status = await sim.resume_flight()
    assert resume_status["is_paused"] is False

    # Stop flight
    stop_status = await sim.cancel_flight()
    assert stop_status["is_running"] is False
    assert stop_status["flight_phase"] == "IDLE"


if __name__ == "__main__":
    asyncio.run(test_geographic_calculations())
    asyncio.run(test_simulator_lifecycle())
    print("ALL UAV MISSION SIMULATOR TESTS PASSED!")
