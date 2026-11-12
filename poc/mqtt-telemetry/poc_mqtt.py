"""MQTT telemetry POC for V-Twin (#35): producer, consumer and failure scenarios.

Synthetic OBD-II-like samples are published with MQTT v5 / QoS 1 to a local
Mosquitto broker, then consumed by a persistent-session subscriber that checks
the message contract, counts losses, duplicates and reordering, and measures
end-to-end latency. Producer and consumer run on the same host and use the same
wall clock (``time.time_ns``), so latency differences are meaningful here only.

Run from the repository root (Mosquitto must be installed):

    uv run --no-project --with paho-mqtt==2.1.0 python poc/mqtt-telemetry/poc_mqtt.py

This is a POC, not a product integration and not the transport benchmark (#42).
"""

import argparse
import importlib.metadata
import json
import math
import os
import platform
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

HOST = "127.0.0.1"
PORT = 18830
SCHEMA = "vtwin.telemetry-sample"
SCHEMA_VERSION = "0.1.0"
SOURCE_ID = "synthetic-obd-01"
TOPIC = f"vtwin/v1/telemetry/{SOURCE_ID}/obd"
SESSION_EXPIRY_S = 3600
HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------ contract
def make_sample(seq: int, t_s: float) -> dict[str, Any]:
    """One synthetic sample. Signals mirror candidate OBD-II PIDs (docs/engine-data)."""
    rpm = 2000.0 + 1500.0 * math.sin(2 * math.pi * t_s / 20.0)
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "synthetic": True,
        "seq": seq,
        "source_clock": "unix_wall_ns",
        "source_ts_ns": time.time_ns(),
        "signals": {
            "engine_speed_rpm": {"pid": "0C", "value": round(rpm, 1)},
            "engine_load_pct": {"pid": "04", "value": round(30 + 0.01 * (rpm - 500), 1)},
            "coolant_temp_c": {"pid": "05", "value": 88.0},
            "oil_temp_c": {"pid": "5C", "value": None, "missing": "PID not supported"},
        },
    }


def validate(message: Any) -> str | None:
    """Return an error code, or None if the message follows the POC contract."""
    if not isinstance(message, dict):
        return "not_an_object"
    if message.get("schema") != SCHEMA or message.get("schema_version") != SCHEMA_VERSION:
        return "unsupported_schema"
    seq, ts = message.get("seq"), message.get("source_ts_ns")
    if type(seq) is not int or seq < 0 or type(ts) is not int:
        return "invalid_header"
    if message.get("source_clock") != "unix_wall_ns" or not isinstance(
        message.get("signals"), dict
    ):
        return "invalid_header"
    for name, signal_ in message["signals"].items():
        value = signal_.get("value") if isinstance(signal_, dict) else "bad"
        if value is None and not signal_.get("missing"):
            return f"undeclared_missing:{name}"
        if value is not None and (not isinstance(value, int | float) or not math.isfinite(value)):
            return f"invalid_value:{name}"
    return None


# -------------------------------------------------------------------- broker
class Broker:
    def __init__(self) -> None:
        self.binary = shutil.which("mosquitto") or "/opt/homebrew/opt/mosquitto/sbin/mosquitto"
        self.workdir = Path(tempfile.mkdtemp(prefix="vtwin-mqtt-"))
        self.conf = self.workdir / "mosquitto.conf"
        self.process: subprocess.Popen[bytes] | None = None

    def version(self) -> str:
        out = subprocess.run([self.binary, "-h"], capture_output=True, text=True).stdout
        return out.splitlines()[0].strip() if out else "unknown"

    def reset(self, autosave_s: int | None = None) -> None:
        """Start a scenario from an empty broker state (no sessions from earlier runs).

        By default Mosquitto writes its persistence file only on clean shutdown.
        ``autosave_s`` adds a periodic save so sessions survive a crash.
        """
        (self.workdir / "vtwin-poc.db").unlink(missing_ok=True)
        conf = (HERE / "mosquitto.conf").read_text()
        conf += f"\npersistence_location {self.workdir}/\n"
        if autosave_s:
            conf += f"autosave_interval {autosave_s}\nautosave_on_changes false\n"
        self.conf.write_text(conf)

    def start(self) -> None:
        self.process = subprocess.Popen([self.binary, "-c", str(self.conf)])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            probe = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
            try:
                probe.connect(HOST, PORT)
                probe.disconnect()
                return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("Mosquitto did not start; is it installed and port 18830 free?")

    def stop(self, sig: int = signal.SIGTERM) -> None:
        if self.process and self.process.poll() is None:
            self.process.send_signal(sig)
            self.process.wait(timeout=5)
        self.process = None

    def cleanup(self) -> None:
        self.stop()
        shutil.rmtree(self.workdir, ignore_errors=True)


# ------------------------------------------------------------------ consumer
@dataclass
class Stats:
    seen: set[int] = field(default_factory=set)
    latencies_ms: list[float] = field(default_factory=list)
    duplicates: int = 0
    out_of_order: int = 0
    invalid: dict[str, int] = field(default_factory=dict)
    payload_bytes: list[int] = field(default_factory=list)
    last_seq: int = -1
    sessions_resumed: int = 0
    connects: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def on_payload(self, payload: bytes) -> None:
        received = time.time_ns()
        try:
            message = json.loads(payload)
        except ValueError:
            message = None
        error = validate(message) if message is not None else "not_json"
        with self.lock:
            if error:
                self.invalid[error] = self.invalid.get(error, 0) + 1
                return
            seq = message["seq"]
            if seq in self.seen:
                self.duplicates += 1
                return
            if seq < self.last_seq:
                self.out_of_order += 1
            self.last_seq = max(self.last_seq, seq)
            self.seen.add(seq)
            self.payload_bytes.append(len(payload))
            self.latencies_ms.append((received - message["source_ts_ns"]) / 1e6)


def connect_props() -> Properties:
    props = Properties(PacketTypes.CONNECT)
    props.SessionExpiryInterval = SESSION_EXPIRY_S
    return props


def new_consumer(stats: Stats, client_id: str) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv5
    )
    client.reconnect_delay_set(min_delay=0.1, max_delay=1)

    def on_connect(c: mqtt.Client, _u: Any, flags: Any, reason: Any, _p: Any) -> None:
        with stats.lock:
            stats.connects += 1
            stats.sessions_resumed += int(bool(flags.session_present))
        c.subscribe(TOPIC, qos=1)  # idempotent; needed when the broker lost the session

    client.on_connect = on_connect
    client.on_message = lambda _c, _u, msg: stats.on_payload(msg.payload)
    client.connect_async(HOST, PORT, keepalive=5, clean_start=False, properties=connect_props())
    client.loop_start()
    return client


# ------------------------------------------------------------------ producer
def new_producer(client_id: str) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv5
    )
    client.reconnect_delay_set(min_delay=0.1, max_delay=1)
    client.max_inflight_messages_set(1000)
    client.connect_async(HOST, PORT, keepalive=5, clean_start=False, properties=connect_props())
    client.loop_start()
    return client


def produce(
    client: mqtt.Client, rate_hz: float, duration_s: float, invalid_every: int = 0
) -> dict[str, int]:
    total = int(rate_hz * duration_s)
    period = 1.0 / rate_hz
    start = time.monotonic()
    counts = {"published": 0, "queued_while_disconnected": 0, "invalid_sent": 0}
    for seq in range(total):
        target = start + seq * period
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        if invalid_every and seq % invalid_every == invalid_every - 1:
            bad = make_sample(seq, seq * period)
            bad["signals"]["engine_speed_rpm"]["value"] = "fast"
            client.publish(TOPIC, json.dumps(bad), qos=1)
            counts["invalid_sent"] += 1
            continue
        info = client.publish(TOPIC, json.dumps(make_sample(seq, seq * period)), qos=1)
        counts["published"] += 1
        if info.rc == mqtt.MQTT_ERR_NO_CONN:
            counts["queued_while_disconnected"] += 1
    return counts


# ----------------------------------------------------------------- scenarios
def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def run_scenario(
    broker: Broker,
    name: str,
    rate_hz: float,
    duration_s: float,
    event: str | None = None,
    invalid_every: int = 0,
    autosave_s: int | None = None,
) -> dict[str, Any]:
    broker.reset(autosave_s)
    broker.start()
    stats = Stats()
    tag = f"{name}-{time.time_ns()}"
    consumer = new_consumer(stats, f"consumer-{tag}")
    time.sleep(0.5)  # persistent subscription exists before the first sample
    producer = new_producer(f"producer-{tag}")
    time.sleep(0.2)
    holder = {"consumer": consumer}

    def inject() -> None:
        time.sleep(duration_s * 0.3)
        if event in {"broker_restart", "broker_crash"}:
            broker.stop(signal.SIGTERM if event == "broker_restart" else signal.SIGKILL)
            time.sleep(3)
            broker.start()
        elif event == "consumer_outage":
            holder["consumer"].disconnect()
            holder["consumer"].loop_stop()
            time.sleep(4)
            holder["consumer"] = new_consumer(stats, f"consumer-{tag}")

    injector = threading.Thread(target=inject) if event else None
    if injector:
        injector.start()
    t0 = time.monotonic()
    counts = produce(producer, rate_hz, duration_s, invalid_every)
    publish_s = time.monotonic() - t0
    if injector:
        injector.join()
    expected = counts["published"]
    deadline = time.monotonic() + 15
    while len(stats.seen) < expected and time.monotonic() < deadline:
        time.sleep(0.05)
    drain_s = time.monotonic() - t0 - publish_s
    producer.disconnect()
    producer.loop_stop()
    holder["consumer"].disconnect()
    holder["consumer"].loop_stop()
    broker.stop()
    lat = stats.latencies_ms
    return {
        "scenario": name,
        "event": event,
        "broker_autosave_s": autosave_s,
        "rate_hz": rate_hz,
        "duration_s": duration_s,
        **counts,
        "received_unique": len(stats.seen),
        "lost": expected - len(stats.seen),
        "duplicates_discarded": stats.duplicates,
        "out_of_order": stats.out_of_order,
        "invalid_rejected": stats.invalid,
        "consumer_connects": stats.connects,
        "consumer_sessions_resumed": stats.sessions_resumed,
        "latency_ms": {
            "p50": percentile(lat, 0.50),
            "p95": percentile(lat, 0.95),
            "max": max(lat) if lat else None,
            "mean": statistics.fmean(lat) if lat else None,
        },
        "payload_bytes_mean": statistics.fmean(stats.payload_bytes)
        if stats.payload_bytes
        else None,
        "publish_wall_s": round(publish_s, 3),
        "drain_after_publish_s": round(drain_s, 3),
    }


SCENARIOS: dict[str, dict[str, Any]] = {
    "nominal_obd_10hz": {"rate_hz": 10, "duration_s": 20},
    "load_can_500hz": {"rate_hz": 500, "duration_s": 10},
    "stress_2000hz": {"rate_hz": 2000, "duration_s": 10},
    "invalid_inputs": {"rate_hz": 50, "duration_s": 10, "invalid_every": 25},
    "consumer_outage": {"rate_hz": 50, "duration_s": 20, "event": "consumer_outage"},
    "broker_restart": {"rate_hz": 50, "duration_s": 20, "event": "broker_restart"},
    "broker_crash": {"rate_hz": 50, "duration_s": 20, "event": "broker_crash"},
    "broker_crash_autosave_1s": {
        "rate_hz": 50,
        "duration_s": 20,
        "event": "broker_crash",
        "autosave_s": 1,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--only", nargs="*", choices=sorted(SCENARIOS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    broker = Broker()
    results = []
    try:
        for name in args.only or list(SCENARIOS):
            for rep in range(args.repeat):
                result = run_scenario(broker, name, **SCENARIOS[name])
                result["repetition"] = rep + 1
                results.append(result)
                print(
                    json.dumps(
                        {
                            k: result[k]
                            for k in (
                                "scenario",
                                "repetition",
                                "published",
                                "received_unique",
                                "lost",
                                "duplicates_discarded",
                            )
                        }
                    ),
                    flush=True,
                )
    finally:
        broker.cleanup()
    report = {
        "record_type": "mqtt_poc_report",
        "created_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "data": "synthetic, declared (no vehicle)",
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "paho_mqtt": importlib.metadata.version("paho-mqtt"),
            "broker": broker.version(),
            "cpu_count": os.cpu_count(),
        },
        "settings": {
            "protocol": "MQTT v5",
            "qos": 1,
            "clean_start": False,
            "session_expiry_s": SESSION_EXPIRY_S,
            "topic": TOPIC,
            "payload": "JSON",
            "scenarios": SCENARIOS,
        },
        "results": results,
    }
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
