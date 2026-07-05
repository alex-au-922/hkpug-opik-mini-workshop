from __future__ import annotations

import argparse
import json
import os
import re
import string
import sys
import urllib.request
from pathlib import Path
from typing import Any


ANSWER_LABEL_RE = re.compile(r"^\s*([ABCD])\s*[:：-]\s*(.*)$", re.IGNORECASE)
CASE_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:case|question)\s*[:#-]?\s*(\d{3})\b", re.IGNORECASE)
FENCE_RE = re.compile(r"^\s*```")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer-key", required=True, type=Path)
    parser.add_argument("--issue-number", type=int)
    parser.add_argument("--body", type=Path)
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH", ""), type=Path)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    return parser.parse_args()


def normalize(value: str) -> str:
    value = value.lower().replace("non-refundable", "not refundable")
    value = value.replace("thirty", "30")
    translation = str.maketrans("", "", string.punctuation.replace(".", ""))
    return " ".join(value.translate(translation).split())


def contains_term(answer: str, term: str | list[str]) -> bool:
    normalized = normalize(answer)
    if isinstance(term, list):
        return any(normalize(option) in normalized for option in term)
    return normalize(term) in normalized


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def issue_from_api(repo: str, issue_number: int, token: str) -> dict[str, Any]:
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY is required for workflow_dispatch grading.")
    if not token:
        raise SystemExit("GH_TOKEN or GITHUB_TOKEN is required for workflow_dispatch grading.")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def load_issue(args: argparse.Namespace) -> tuple[int, str, str]:
    if args.body:
        return args.issue_number or 0, "local issue", args.body.read_text(encoding="utf-8")

    if args.event_path and args.event_path.is_file():
        event = read_json(args.event_path)
        issue = event.get("issue")
        if isinstance(issue, dict):
            return int(issue["number"]), str(issue.get("title", "")), str(issue.get("body", ""))
        inputs = event.get("inputs")
        if isinstance(inputs, dict) and inputs.get("issue_number"):
            args.issue_number = int(inputs["issue_number"])

    if not args.issue_number:
        raise SystemExit("Could not find an issue body to grade.")
    issue = issue_from_api(args.repo, int(args.issue_number), args.token)
    return int(issue["number"]), str(issue.get("title", "")), str(issue.get("body", ""))


def parse_answers(body: str) -> dict[str, dict[str, str]]:
    answers: dict[str, dict[str, str]] = {}
    current_case = ""
    current_label = ""

    for raw_line in body.splitlines():
        if FENCE_RE.match(raw_line):
            continue
        case_match = CASE_RE.match(raw_line)
        if case_match:
            current_case = case_match.group(1)
            current_label = ""
            answers.setdefault(current_case, {})
            continue

        answer_match = ANSWER_LABEL_RE.match(raw_line)
        if answer_match and current_case:
            current_label = answer_match.group(1).upper()
            answers.setdefault(current_case, {})[current_label] = answer_match.group(2).strip()
            continue

        if current_case and current_label:
            extra = raw_line.strip()
            if extra:
                existing = answers[current_case][current_label]
                answers[current_case][current_label] = f"{existing} {extra}".strip()

    return answers


def grade_answer(answer: str, requirements: list[str | list[str]]) -> bool:
    if not answer.strip():
        return False
    return all(contains_term(answer, term) for term in requirements)


def grade_submission(rubric: dict[str, Any], answers: dict[str, dict[str, str]]) -> dict[str, Any]:
    results = {}
    passed_count = 0
    submitted_count = 0
    wrong_count = 0
    total_count = 0
    for case_id, case_rubric in rubric["cases"].items():
        case_results = {}
        for label in ("A", "B", "C", "D"):
            total_count += 1
            answer = answers.get(case_id, {}).get(label, "")
            submitted = bool(answer.strip())
            ok = submitted and grade_answer(answer, case_rubric[label])
            if submitted:
                submitted_count += 1
            if ok:
                passed_count += 1
            elif submitted:
                wrong_count += 1
            case_results[label] = {"passed": ok, "present": submitted}
        results[case_id] = case_results
    percentage = round((passed_count / total_count) * 100, 2) if total_count else 0.0
    item_value = round(100 / total_count, 2) if total_count else 0.0
    if passed_count == total_count:
        status = "passed"
    elif wrong_count:
        status = "needs-correction"
    else:
        status = "in-progress"
    return {
        "status": status,
        "passed": status == "passed",
        "passed_count": passed_count,
        "submitted_count": submitted_count,
        "wrong_count": wrong_count,
        "not_submitted_count": total_count - submitted_count,
        "total_count": total_count,
        "percentage": percentage,
        "item_value": item_value,
        "cases": results,
    }


def build_report(issue_number: int, score: dict[str, Any]) -> str:
    status = str(score["status"]).replace("-", " ")
    lines = [
        f"### Workshop grading: {status}",
        "",
        f"Score: **{score['percentage']:.2f}%** ({score['passed_count']}/{score['total_count']} complete)",
        "",
        (
            f"Submitted answers: **{score['passed_count']} correct**, "
            f"**{score['wrong_count']} check again**, "
            f"**{score['not_submitted_count']} not submitted**."
        ),
        "",
        (
            f"Each correct answer adds **{score['item_value']:.2f} percentage points**. "
            "Blank answers are neutral; submitted wrong answers are marked `check again`."
        ),
        "",
        "| Case | A | B | C | D |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case_id, case_result in score["cases"].items():
        cells = []
        for label in ("A", "B", "C", "D"):
            item = case_result[label]
            if item["passed"]:
                cells.append("pass")
            elif item["present"]:
                cells.append("check again")
            else:
                cells.append("not submitted")
        lines.append(f"| {case_id} | " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "The checker only reports pass/fail per item and does not expose the hidden answer rubric.",
            f"Issue: #{issue_number}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    issue_number, title, body = load_issue(args)
    rubric = read_json(args.answer_key)
    answers = parse_answers(body)
    score = grade_submission(rubric, answers)
    report = build_report(issue_number, score)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    args.result.write_text(
        json.dumps(
            {
                "issue_number": issue_number,
                "title": title,
                **score,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"graded issue #{issue_number}: {score['passed_count']}/{score['total_count']}")


if __name__ == "__main__":
    main()
