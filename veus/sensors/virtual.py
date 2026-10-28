"""Tick-driven sample/hold sensors with timestamped, queued packet delivery."""

from dataclasses import dataclass, replace
import heapq
import math
import random
from veus.sensors.config import SensorSuiteConfig


@dataclass(frozen=True)
class Packet:
    source_tick: int | None
    generation_tick: int
    delivery_tick: int
    values: dict[str, float | None]
    valid: bool
    frozen: bool = False


class VirtualSensor:
    def __init__(self, name, config, seed):
        self.name = name
        self.config = config
        self.rng = random.Random(seed)
        self.period = round(100 / config.sampling_hz)
        self.queue = []
        self.latest = None
        self.last_good = None
        self.frozen_reference = None
        self.freezing = False
        self.last_tick = -1
        self.discarded_packets = 0

    def update(self, tick: int, truth: dict, faults: list):
        if tick == self.last_tick:
            return
        if tick < self.last_tick:
            raise ValueError("Sensor time must not move backwards; reset the suite")
        self.last_tick = tick
        self._deliver(tick)
        frozen = any(f.fault == "freeze" for f in faults)
        if frozen and not self.freezing:
            self.frozen_reference = self.last_good
        self.freezing = frozen
        if tick % self.period == 0:
            latency = self.config.latency_s + sum(
                f.parameters["latency_s"] for f in faults if f.fault == "latency"
            )
            delivery = tick + round(latency / 0.01)
            if any(f.fault == "dropout" for f in faults):
                packet = Packet(
                    tick, tick, delivery, {key: None for key in truth}, False
                )
            elif frozen:
                reference = self.frozen_reference
                packet = (
                    replace(
                        reference,
                        generation_tick=tick,
                        delivery_tick=delivery,
                        frozen=True,
                    )
                    if reference
                    else Packet(
                        None, tick, delivery, {key: None for key in truth}, False, True
                    )
                )
            else:
                values = {}
                for key, value in truth.items():
                    std_key = {
                        "speed_ms": "noise_std_ms",
                        "distance_m": "distance_noise_std_m",
                        "closing_speed_ms": "relative_speed_noise_std_ms",
                    }[key]
                    bias_key = {
                        "speed_ms": "bias_ms",
                        "distance_m": "distance_bias_m",
                        "closing_speed_ms": "relative_speed_bias_ms",
                    }[key]
                    variance = getattr(self.config, std_key) ** 2 + sum(
                        f.parameters.get(std_key, 0) ** 2
                        for f in faults
                        if f.fault == "noise"
                    )
                    bias = getattr(self.config, bias_key) + sum(
                        f.parameters.get(bias_key, 0)
                        for f in faults
                        if f.fault == "bias"
                    )
                    values[key] = (
                        None
                        if value is None
                        else value + bias + self.rng.gauss(0, math.sqrt(variance))
                    )
                valid = all(v is not None for v in values.values())
                valid &= all(
                    v is None or v >= 0
                    for k, v in values.items()
                    if k != "closing_speed_ms"
                )
                packet = Packet(tick, tick, delivery, values, valid)
            heapq.heappush(self.queue, (delivery, tick, packet))
            self._deliver(tick)

    def _deliver(self, tick):
        while self.queue and self.queue[0][0] <= tick:
            _, _, packet = heapq.heappop(self.queue)
            # Order by packet creation, not the retained acquisition time of a
            # deliberately frozen reading. Never resurrect an older in-flight packet.
            if self.latest and packet.generation_tick < self.latest.generation_tick:
                self.discarded_packets += 1
                continue
            self.latest = packet
            if packet.valid:
                self.last_good = packet

    def view(self, tick, faults):
        packet = self.latest
        age = (
            (tick - packet.source_tick) * 0.01
            if packet and packet.source_tick is not None
            else None
        )
        stale = age is not None and age > self.config.stale_after_s + 1e-9
        valid = bool(packet and packet.valid and not stale)
        status = (
            "unavailable"
            if not packet or not packet.valid
            else "stale"
            if stale
            else "fault-active"
            if faults
            else "delayed"
            if packet and packet.delivery_tick > packet.generation_tick
            else "valid"
        )
        return dict(
            values=packet.values if packet else {},
            valid=valid,
            status=status,
            age_s=age,
            sample_time_s=packet.source_tick * 0.01
            if packet and packet.source_tick is not None
            else None,
            delivery_time_s=packet.delivery_tick * 0.01 if packet else None,
            frozen=packet.frozen if packet else False,
            discarded_packets=self.discarded_packets,
        )


class SensorSuite:
    def __init__(self, config: SensorSuiteConfig):
        self.config = config
        self.speed = VirtualSensor("speed", config.speed, config.seed)
        self.radar = VirtualSensor("radar", config.radar, config.seed ^ 0x5DEECE66D)
        self.events = []
        self.active = []
        self._active_ids = set()
        self.tick = 0

    def update(self, tick, speed_ms, gap_m, closing_speed_ms):
        self.tick = tick
        active = [
            f
            for f in self.config.faults
            if round(f.start_time_s / 0.01)
            <= tick
            < round((f.start_time_s + f.duration_s) / 0.01)
        ]
        ids = {f.id for f in active}
        for fault in self.config.faults:
            if (fault.id in ids) != (fault.id in self._active_ids):
                self.events.append(
                    dict(
                        id=fault.id,
                        sensor=fault.sensor,
                        fault=fault.fault,
                        event="activated" if fault.id in ids else "deactivated",
                        time_s=tick * 0.01,
                    )
                )
        self.active = active
        self._active_ids = ids
        self.speed.update(
            tick, {"speed_ms": speed_ms}, [f for f in active if f.sensor == "speed"]
        )
        self.radar.update(
            tick,
            {"distance_m": gap_m, "closing_speed_ms": closing_speed_ms},
            [f for f in active if f.sensor == "radar"],
        )

    def views(self):
        return {
            name: getattr(self, name).view(
                self.tick, [f for f in self.active if f.sensor == name]
            )
            for name in ("speed", "radar")
        }
