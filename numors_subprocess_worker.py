from __future__ import annotations

import json
import sys
from pathlib import Path

from toscana_gui.numors.tasks import NumorsExecutionResult, execute_numors_workflow


def _write_stdout_fallback(stdout_file: Path, message: str) -> None:
    try:
        stdout_file.parent.mkdir(parents=True, exist_ok=True)
        with stdout_file.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        return


def _result_to_payload(result: NumorsExecutionResult) -> dict:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "stdout_file": result.stdout_file,
        "logfile": result.logfile,
        "reg_file": result.reg_file,
        "adat_file": result.adat_file,
        "qdat_file": result.qdat_file,
        "run_blocks": list(result.run_blocks),
        "generated_files": list(result.generated_files),
        "plot_files": list(result.plot_files),
        "summary": result.summary,
        "error": result.error,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        sys.stderr.write(
            "Usage: numors_subprocess_worker.py <par_file> <project_root> <run_id> <result_json>\n"
        )
        return 2

    par_file = Path(argv[1]).expanduser()
    project_root = Path(argv[2]).expanduser()
    run_id = str(argv[3])
    result_file = Path(argv[4]).expanduser()

    fallback_stdout = project_root / "processed" / "logfiles" / f"{run_id}-stdout.txt"
    try:
        result = execute_numors_workflow(par_file, project_root, run_id)
    except Exception as exc:
        message = f"Numors subprocess worker failed: {exc}"
        _write_stdout_fallback(fallback_stdout, message)
        result = NumorsExecutionResult(
            run_id=run_id,
            status="failed",
            stdout_file=str(fallback_stdout),
            logfile=None,
            reg_file=None,
            adat_file=None,
            qdat_file=None,
            run_blocks=[],
            generated_files=[],
            plot_files=[],
            summary=f"Processed run `{run_id}`, status: `failed`, error: {exc}",
            error=str(exc),
        )

    payload = _result_to_payload(result)
    try:
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        _write_stdout_fallback(
            Path(result.stdout_file) if result.stdout_file else fallback_stdout,
            f"Could not write result payload to {result_file}: {exc}",
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

