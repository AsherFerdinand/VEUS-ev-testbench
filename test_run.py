"""
VEUS - Entry point test script
"""
from veus.sim.solver import VehiclePowertrain

powertrain = VehiclePowertrain()
state = powertrain.solve_point(velocity_ms=33.33, acceleration_ms2=0.0, soc=0.80)

print("--- VEUS POWERTRAIN TEST RESULT ---")
print(f"Speed:            {state['velocity_kmh']:.1f} km/h")
print(f"Motor RPM:        {state['motor_rpm']:.0f} RPM")
print(f"Active Gear:      Gear {state['current_gear']}")
print(f"Battery Power:    {state['p_battery_kw']:.2f} kW")
print(f"Pack Current:     {state['i_pack_a']:.2f} A")
print(f"Bus Voltage Sag:  {state['v_pack_v']:.1f} V")
print(f"Total Losses:     {state['losses']['total_loss_kw']:.2f} kW")