"""Small repeatable Linux snapshots, not a benchmark or laptop performance claim."""

import argparse, ast, json, os, statistics, subprocess, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def call(base, path, data=None):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r) if "json" in r.headers.get("Content-Type", "") else r.read()


def rss(pid):
    return int(
        next(
            l
            for l in Path(f"/proc/{pid}/status").read_text().splitlines()
            if l.startswith("VmRSS:")
        ).split()[1]
    )


def cpu(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().split()
    return (int(fields[13]) + int(fields[14])) / os.sysconf("SC_CLK_TCK")


def measure(root, port, operations, lab=False):
    rows = []
    for trial in range(4):
        log = open("/tmp/veus-performance-server.log", "w")
        start = time.perf_counter()
        p = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "veus.studio.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=root,
            stdout=log,
            stderr=log,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(500):
                try:
                    call(base, "/")
                    break
                except OSError:
                    if p.poll() is not None:
                        raise RuntimeError(
                            "Server failed; see /tmp/veus-performance-server.log"
                        )
                    time.sleep(0.01)
            else:
                raise RuntimeError("Startup timeout")
            elapsed = time.perf_counter() - start
            startup_rss = rss(p.pid)
            t = time.perf_counter()
            before = cpu(p.pid)
            time.sleep(1)
            idle = 100 * (cpu(p.pid) - before) / (time.perf_counter() - t)
            design = call(
                base,
                "/api/workbench/v2/design" if operations else "/api/workbench/design",
            )
            latencies = []
            for _ in range(10):
                t = time.perf_counter()
                call(
                    base,
                    "/api/workbench/v2/evaluate"
                    if operations
                    else "/api/workbench/design/validate",
                    design,
                )
                latencies.append((time.perf_counter() - t) * 1000)
            lab_metrics = {}
            if lab:
                from veus.workbench.adapter import ACKNOWLEDGEMENTS

                payload = dict(
                    vehicle=design,
                    acknowledgements=ACKNOWLEDGEMENTS,
                    experiment=dict(kind="acceleration", duration_s=20, dt_s=0.05),
                )
                times = []
                for _ in range(4):
                    begin = time.perf_counter()
                    result = call(base, "/api/lab/run", payload)
                    times.append((time.perf_counter() - begin) * 1000)
                lab_metrics = dict(
                    lab_run_ms_median=statistics.median(times[1:]),
                    lab_payload_bytes=len(
                        json.dumps(result, separators=(",", ":")).encode()
                    ),
                    lab_operation_rss_kib=rss(p.pid),
                )
            rows.append(
                dict(
                    warmup=trial == 0,
                    startup_s=elapsed,
                    startup_rss_kib=startup_rss,
                    operation_rss_kib=rss(p.pid),
                    idle_server_cpu_percent=idle,
                    operation_ms_median=statistics.median(latencies),
                    operation_scope="v2 complete evaluate"
                    if operations
                    else "v1 envelope validate",
                    **lab_metrics,
                )
            )
        finally:
            p.terminate()
            p.wait()
            log.close()
    retained = rows[1:]
    return dict(
        samples=rows,
        median={
            k: statistics.median(r[k] for r in retained)
            for k in [
                "startup_s",
                "startup_rss_kib",
                "operation_rss_kib",
                "idle_server_cpu_percent",
                "operation_ms_median",
            ]
        },
    )


def inventory(root):
    files = [
        p
        for p in root.joinpath("veus").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    py = [p for p in files if p.suffix == ".py"]
    workbench = [p for p in files if "/static/workbench/" in str(p)]
    freeze = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"], text=True
    ).splitlines()
    return dict(
        application_file_bytes=sum(p.stat().st_size for p in files),
        python_bytes=sum(p.stat().st_size for p in py),
        python_physical_lines=sum(len(p.read_text().splitlines()) for p in py),
        python_nonblank_noncomment_lines=sum(
            sum(
                bool(l.strip()) and not l.lstrip().startswith("#")
                for l in p.read_text().splitlines()
            )
            for p in py
        ),
        python_ast_statements=sum(
            sum(isinstance(n, ast.stmt) for n in ast.walk(ast.parse(p.read_text())))
            for p in py
        ),
        workbench_bytes_by_suffix={
            s: sum(p.stat().st_size for p in workbench if p.suffix == s)
            for s in [".html", ".js", ".css", ".svg"]
        },
        installed_distributions=len(freeze),
        freeze=freeze,
        installed_environment_file_bytes=sum(
            p.stat().st_size for p in Path(sys.prefix).rglob("*") if p.is_file()
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=8785)
    parser.add_argument("--v2", action="store_true")
    parser.add_argument("--lab", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "scope": "Warm-up excluded, three repeated Linux samples; 10 ms startup polling, 1 s server idle sample. Server CPU/RSS are not browser memory. Baseline validate and new complete evaluation do different work; their latency is not a speedup comparison. No laptop guarantee.",
        "inventory": inventory(args.root),
        **measure(args.root, args.port, args.v2, args.lab),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["median"])
