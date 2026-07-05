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
MAX_EXACT_ANSWER_CHARS = 80
MAX_EXACT_ANSWER_WORDS = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer-key", required=True, type=Path)
    parser.add_argument("--issue-number", type=int)
    parser.add_argument("--comment-id", type=int)
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


def normalize_exact(value: str) -> str:
    value = value.strip()
    while len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    return " ".join(value.lower().split())


def is_short_answer(answer: str) -> bool:
    words = answer.strip().split()
    return len(answer.strip()) <= MAX_EXACT_ANSWER_CHARS and len(words) <= MAX_EXACT_ANSWER_WORDS


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


def issue_comment_from_api(repo: str, comment_id: int, token: str) -> dict[str, Any]:
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY is required for workflow_dispatch grading.")
    if not token:
        raise SystemExit("GH_TOKEN or GITHUB_TOKEN is required for workflow_dispatch grading.")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/comments/{comment_id}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def issue_number_from_url(url: str) -> int:
    match = re.search(r"/issues/(\d+)$", url)
    if not match:
        raise SystemExit(f"Could not find issue number in URL: {url}")
    return int(match.group(1))


def load_submission(args: argparse.Namespace) -> dict[str, Any]:
    if args.body:
        return {
            "issue_number": args.issue_number or 0,
            "title": "local submission",
            "body": args.body.read_text(encoding="utf-8"),
            "submission_kind": "local",
            "submission_url": "",
            "comment_id": args.comment_id,
        }

    if args.event_path and args.event_path.is_file():
        event = read_json(args.event_path)
        issue = event.get("issue")
        comment = event.get("comment")
        if isinstance(issue, dict) and isinstance(comment, dict):
            return {
                "issue_number": int(issue["number"]),
                "title": str(issue.get("title", "")),
                "body": str(comment.get("body", "")),
                "submission_kind": "comment",
                "submission_url": str(comment.get("html_url", "")),
                "comment_id": int(comment["id"]),
            }
        if isinstance(issue, dict):
            return {
                "issue_number": int(issue["number"]),
                "title": str(issue.get("title", "")),
                "body": str(issue.get("body", "")),
                "submission_kind": "issue",
                "submission_url": str(issue.get("html_url", "")),
                "comment_id": args.comment_id,
            }
        inputs = event.get("inputs")
        if isinstance(inputs, dict) and inputs.get("comment_id"):
            args.comment_id = int(inputs["comment_id"])
        elif isinstance(inputs, dict) and inputs.get("issue_number"):
            args.issue_number = int(inputs["issue_number"])

    if args.comment_id:
        comment = issue_comment_from_api(args.repo, int(args.comment_id), args.token)
        return {
            "issue_number": issue_number_from_url(str(comment["issue_url"])),
            "title": "issue comment",
            "body": str(comment.get("body", "")),
            "submission_kind": "comment",
            "submission_url": str(comment.get("html_url", "")),
            "comment_id": int(comment["id"]),
        }

    if not args.issue_number:
        raise SystemExit("Could not find an issue or comment body to grade.")
    issue = issue_from_api(args.repo, int(args.issue_number), args.token)
    return {
        "issue_number": int(issue["number"]),
        "title": str(issue.get("title", "")),
        "body": str(issue.get("body", "")),
        "submission_kind": "issue",
        "submission_url": str(issue.get("html_url", "")),
        "comment_id": args.comment_id,
    }


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


def grade_answer(answer: str, requirements: dict[str, Any] | list[str | list[str]]) -> bool:
    if not answer.strip():
        return False
    if isinstance(requirements, dict):
        accepted = requirements.get("answers")
        if not isinstance(accepted, list):
            raise SystemExit("Exact answer rubric items must contain an answers list.")
        normalized_answer = normalize_exact(answer)
        return is_short_answer(answer) and any(normalize_exact(str(item)) == normalized_answer for item in accepted)
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


def build_report(submission: dict[str, Any], score: dict[str, Any]) -> str:
    status = str(score["status"]).replace("-", " ")
    scope = "this comment" if submission["submission_kind"] == "comment" else "this submission"
    lines = [
        f"### Workshop grading: {status}",
        "",
        f"Score for {scope}: **{score['percentage']:.2f}%** ({score['passed_count']}/{score['total_count']} complete)",
        "",
        (
            f"Submitted answers: **{score['passed_count']} correct**, "
            f"**{score['wrong_count']} check again**, "
            f"**{score['not_submitted_count']} not submitted**."
        ),
        "",
        (
            f"Each correct answer adds **{score['item_value']:.2f} percentage points**. "
            "Use short exact answers; blank answers are neutral and submitted wrong answers are marked `check again`."
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
            f"Issue: #{submission['issue_number']}",
        ]
    )
    if submission["submission_url"]:
        lines.append(f"Graded submission: {submission['submission_url']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    submission = load_submission(args)
    rubric = read_json(args.answer_key)
    answers = parse_answers(submission["body"])
    score = grade_submission(rubric, answers)
    report = build_report(submission, score)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    args.result.write_text(
        json.dumps(
            {
                "issue_number": submission["issue_number"],
                "title": submission["title"],
                "submission_kind": submission["submission_kind"],
                "submission_url": submission["submission_url"],
                "comment_id": submission["comment_id"],
                **score,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"graded issue #{submission['issue_number']}: {score['passed_count']}/{score['total_count']}")


if __name__ == "__main__":
    main()
