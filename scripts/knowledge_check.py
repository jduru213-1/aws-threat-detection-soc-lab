"""
AWS Threat Detection SOC Lab - Knowledge Check (CLI)

Beginner / Mid / Advanced quiz to validate understanding of:
- SOC workflow
- AWS logging pipeline (CloudTrail, Config, VPC Flow Logs)
- Splunk ingestion and indexes
- Terraform + scripts (build/destroy)
- Stratus Red Team integration

Usage:
  python scripts/knowledge_check.py --level beginner
  python scripts/knowledge_check.py --level mid --count 12
  python scripts/knowledge_check.py --level advanced --mode mixed --shuffle
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field
from typing import Literal, Optional

Level = Literal["beginner", "mid", "advanced"]
Mode = Literal["mcq", "fill", "mixed"]

ANSI_ENABLED = sys.stdout.isatty()


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    GRAY = "\033[90m"


def style(s: str, *codes: str) -> str:
    if not ANSI_ENABLED:
        return s
    return "".join(codes) + s + C.RESET


def _supports_unicode() -> bool:
    enc = (getattr(sys.stdout, "encoding", None) or "").lower()
    if "utf" in enc:
        return True
    try:
        "─█".encode(enc or "utf-8")
        return True
    except Exception:
        return False


UNICODE_OK = _supports_unicode()


def hr() -> None:
    ch = "─" if UNICODE_OK else "-"
    print(style(ch * 72, C.GRAY))


def clear_screen() -> None:
    if not ANSI_ENABLED:
        return
    print("\033[2J\033[H", end="")


def progress_bar(i: int, n: int, width: int = 24) -> str:
    if n <= 0:
        return ""
    filled = int(round((i / n) * width))
    filled = max(0, min(width, filled))
    full = "█" if UNICODE_OK else "#"
    empty = " " if UNICODE_OK else "."
    return "[" + (full * filled) + (empty * (width - filled)) + "]"


@dataclass(frozen=True)
class Mcq:
    prompt: str
    options: list[str]
    answer_index: int
    explanation: str
    tags: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Fill:
    prompt: str
    expected: str
    explanation: str
    tags: set[str] = field(default_factory=set)


Question = Mcq | Fill


LAB_FACTS = {
    "indexes": ["aws_cloudtrail", "aws_config", "aws_vpcflow"],
    "splunk_user": "soc-lab-splunk-addon",
    "stratus_user": "soc-lab-stratus",
    "stratus_profile": "stratus-lab",
    "build_script": r"infra\build.sh",
    "destroy_script": r"infra\destroy.sh",
    "configure_stratus_script": r"attacks\configure-stratus.sh",
}

TAG_AWS = "aws"
TAG_SPLUNK = "splunk"
TAG_TERRAFORM = "terraform"
TAG_DOCKER = "docker"
TAG_STRATUS = "stratus"
TAG_SOC = "soc"


# Default rotating subset size per tier (when --count is not provided).
#
# Invariant: DEFAULT_COUNT[tier] MUST be strictly less than the sum of
# BALANCED_MIX[tier] values. Without that slack, any topic pool that runs
# short will silently produce fewer questions than expected.
#
#   beginner  mix_sum=9   default=7   slack=2
#   mid       mix_sum=13  default=11  slack=2
#   advanced  mix_sum=16  default=13  slack=3
DEFAULT_COUNT: dict[Level, int] = {
    "beginner": 7,
    "mid": 11,
    "advanced": 13,
}

# Topic mix per tier when using balanced rotation.
# Rule: sum(values) MUST be strictly greater than DEFAULT_COUNT[tier].
BALANCED_MIX: dict[Level, dict[str, int]] = {
    # sum=9, default=7, slack=2
    "beginner": {TAG_DOCKER: 1, TAG_TERRAFORM: 1, TAG_AWS: 3, TAG_SPLUNK: 3, TAG_STRATUS: 1},
    # sum=13, default=11, slack=2
    "mid": {TAG_AWS: 4, TAG_SPLUNK: 3, TAG_TERRAFORM: 3, TAG_STRATUS: 2, TAG_SOC: 1},
    # sum=16, default=13, slack=3
    "advanced": {TAG_AWS: 4, TAG_SPLUNK: 3, TAG_TERRAFORM: 3, TAG_STRATUS: 2, TAG_SOC: 4},
}


QUESTION_BANK: dict[Level, list[Question]] = {
    "beginner": [
        Mcq(
            prompt="What is Docker used for in this lab?",
            options=[
                "It deploys AWS resources like S3 and CloudTrail",
                "It runs Splunk locally in a container so you can search logs on your machine",
                "It replaces IAM so you don't need AWS credentials",
                "It is required to enable CloudTrail",
            ],
            answer_index=1,
            explanation="Splunk runs in Docker (under `soc/`) so your logging/detection stack is easy to start/stop locally.",
            tags={TAG_DOCKER, TAG_SPLUNK},
        ),
        Mcq(
            prompt="What is Terraform used for in this lab?",
            options=[
                "Creating AWS resources as code (S3 buckets, CloudTrail, Config, VPC Flow Logs, IAM users)",
                "Installing Splunk apps and add-ons",
                "Encrypting CloudTrail logs before upload",
                "Replacing the AWS CLI",
            ],
            answer_index=0,
            explanation="Terraform provisions the AWS-side infrastructure; the `infra` scripts wrap Terraform for you.",
            tags={TAG_TERRAFORM, TAG_AWS},
        ),
        Mcq(
            prompt="What is AWS CloudTrail (in simple terms)?",
            options=[
                "A service that records AWS API activity (who did what, when, from where)",
                "A network firewall for VPCs",
                "A service that stores secrets like passwords and API keys",
                "A tool that scans instances for vulnerabilities",
            ],
            answer_index=0,
            explanation="CloudTrail is your control-plane audit log: it captures management API calls across AWS services.",
            tags={TAG_AWS},
        ),
        Mcq(
            prompt="What is AWS Config (in simple terms)?",
            options=[
                "A service that tracks resource configuration over time (what changed and when)",
                "A service that blocks public S3 access automatically",
                "A log source that replaces CloudTrail",
                "A tool that only monitors EC2 CPU usage",
            ],
            answer_index=0,
            explanation="Config helps you understand configuration drift/changes (e.g., security group or S3 policy changes).",
            tags={TAG_AWS},
        ),
        Mcq(
            prompt="What is a VPC in AWS?",
            options=[
                "A virtual private network boundary for your AWS resources (subnets, routing, security groups)",
                "A single EC2 instance type",
                "A type of S3 bucket encryption",
                "A Splunk index",
            ],
            answer_index=0,
            explanation="A VPC is your isolated virtual network in AWS where many resources live and communicate.",
            tags={TAG_AWS},
        ),
        Mcq(
            prompt="What is the primary goal of this lab?",
            options=[
                "Deploy EC2 instances and benchmark performance",
                "Ingest AWS logs into Splunk for detection practice",
                "Set up Kubernetes monitoring for production clusters",
                "Build a CloudFront-backed static website",
            ],
            answer_index=1,
            explanation="The lab stands up AWS logging (CloudTrail/Config/VPC Flow) and ingests it into Splunk for search/detection.",
            tags={TAG_SOC, TAG_AWS, TAG_SPLUNK},
        ),
        Mcq(
            prompt="Which AWS data sources does this lab ingest?",
            options=[
                "CloudTrail, Config, VPC Flow Logs",
                "GuardDuty, Inspector, Security Hub",
                "ALB logs, RDS logs, CloudWatch Metrics",
                "Route 53 logs, WAF logs, Shield logs",
            ],
            answer_index=0,
            explanation="The stack focuses on CloudTrail + Config + VPC Flow Logs.",
            tags={TAG_AWS},
        ),
        Mcq(
            prompt="What creates Splunk indexes for this lab?",
            options=[
                r"infra\build.sh",
                r"scripts\setup_splunk.py",
                "Splunk Add-on for AWS auto-creates them",
                "Docker Compose automatically provisions them",
            ],
            answer_index=1,
            explanation="`scripts/setup_splunk.py` uses the Splunk SDK to create the indexes.",
            tags={TAG_SPLUNK},
        ),
        Fill(
            prompt="Fill in the 3 Splunk indexes used by this lab (comma-separated).",
            expected=", ".join(LAB_FACTS["indexes"]),
            explanation="These indexes keep the three data sources separate and searchable.",
            tags={TAG_SPLUNK},
        ),
        Mcq(
            prompt=f"What is `{LAB_FACTS['splunk_user']}` used for?",
            options=[
                "Running Terraform apply/destroy",
                "Running Stratus Red Team techniques",
                "Reading the S3 log buckets for ingestion",
                "Managing Splunk admin users",
            ],
            answer_index=2,
            explanation="The Splunk add-on uses this IAM user to list/get objects from the log buckets.",
            tags={TAG_AWS, TAG_SPLUNK},
        ),
        Mcq(
            prompt="Where does Splunk run in this lab?",
            options=[
                "On an EC2 instance deployed by Terraform",
                "In Docker on your local machine",
                "In Splunk Cloud (SaaS)",
                "On an EKS cluster created by the build script",
            ],
            answer_index=1,
            explanation="Splunk runs locally via Docker Compose under `soc/`.",
            tags={TAG_DOCKER, TAG_SPLUNK},
        ),
    ],
    "mid": [
        Mcq(
            prompt="What does `infra\\build.sh` do at a high level?",
            options=[
                "Only formats Terraform code",
                "Runs Terraform init/plan/apply (and installs AWS CLI/Terraform if missing)",
                "Creates Splunk dashboards automatically",
                "Only creates IAM users and nothing else",
            ],
            answer_index=1,
            explanation="`build.sh` wraps Terraform to create AWS resources for the lab.",
            tags={TAG_TERRAFORM, TAG_AWS},
        ),
        Mcq(
            prompt="Which best describes what `infra\\destroy.sh` does before `terraform destroy`?",
            options=[
                "Deletes IAM users only, then exits",
                "Empties S3 buckets (including versioned objects), then runs destroy to remove everything",
                "Stops Docker containers and removes Splunk indexes",
                "Only removes SQS queues and leaves buckets",
            ],
            answer_index=1,
            explanation="Destroy empties buckets first (so deletion succeeds), then runs Terraform destroy.",
            tags={TAG_TERRAFORM, TAG_AWS},
        ),
        Mcq(
            prompt="Why does the lab write `.env.splunk` and `.env.stratus` at repo root?",
            options=[
                "So secrets can be committed to git safely",
                "To avoid re-creating IAM access keys every time and make setup repeatable",
                "To configure Docker networking automatically",
                "To store Terraform state",
            ],
            answer_index=1,
            explanation="Local env files reduce friction and key churn (and are git-ignored).",
            tags={TAG_SOC, TAG_TERRAFORM},
        ),
        Mcq(
            prompt=f"You ran `attacks\\configure-stratus.sh` and now `destroy.sh` fails or refuses to run. What's the most likely cause?",
            options=[
                "Docker isn't running",
                "Terraform is not installed",
                "You are still on the Stratus AWS profile; destroy must use the same build/admin identity that owns the lab",
                "Splunk is offline",
            ],
            answer_index=2,
            explanation="`configure-stratus.sh` sets `AWS_PROFILE` for simulations. Teardown should use your build/admin credentials (the script also blocks running destroy as the Stratus principal).",
            tags={TAG_STRATUS, TAG_TERRAFORM},
        ),
        Mcq(
            prompt="In the Splunk add-on, where do you paste the `soc-lab-splunk-addon` access key and secret?",
            options=[
                "Inputs → CloudTrail → Advanced settings",
                "Configuration → AWS Account",
                "Settings → Indexes",
                "Dashboards → Create",
            ],
            answer_index=1,
            explanation="Keys belong in the add-on's AWS Account configuration; inputs then reference that account.",
            tags={TAG_SPLUNK},
        ),
        Mcq(
            prompt="What is the purpose of `scripts\\setup_splunk.py` in the workflow?",
            options=[
                "It installs the AWS add-on in Splunk",
                "It creates the Splunk indexes required by the lab before ingestion",
                "It deploys CloudTrail to S3",
                "It configures SQS notifications in AWS",
            ],
            answer_index=1,
            explanation="It creates `aws_cloudtrail`, `aws_config`, `aws_vpcflow` via the Splunk SDK.",
            tags={TAG_SPLUNK},
        ),
        Mcq(
            prompt="Why should `infra\\destroy.sh` NOT be run with the Stratus profile/user active?",
            options=[
                "Stratus is read-only and cannot query Splunk",
                "Teardown should use the build/admin identity that created the lab; Stratus is reserved for attack simulation",
                "Terraform cannot run in PowerShell",
                "Destroy requires EC2 access keys",
            ],
            answer_index=1,
            explanation="Separation of roles: Stratus credentials are for simulations; destroy applies Terraform and should run under your lab admin credentials.",
            tags={TAG_STRATUS, TAG_TERRAFORM},
        ),
        Mcq(
            prompt="In the Splunk Add-on for AWS, what must you configure before inputs will work?",
            options=[
                "Only the indexes; everything else is automatic",
                "An AWS Account (keys) and then SQS-based S3 inputs for each queue",
                "A CloudTrail trail ARN in Splunk settings",
                "A GuardDuty detector ID and a KMS key ARN",
            ],
            answer_index=1,
            explanation="You set AWS credentials under Configuration → AWS Account, then create SQS-based S3 inputs for CloudTrail, Config, and VPC Flow (each with its queue and index).",
            tags={TAG_SPLUNK, TAG_AWS},
        ),
        Fill(
            prompt="Fill in the IAM user used by the Splunk add-on (exact name).",
            expected=LAB_FACTS["splunk_user"],
            explanation="This user is the read-only ingestion identity for Splunk.",
            tags={TAG_AWS, TAG_SPLUNK},
        ),
        Fill(
            prompt="Fill in the IAM user used for Stratus Red Team (exact name).",
            expected=LAB_FACTS["stratus_user"],
            explanation="This user is dedicated to generating attack-like API activity.",
            tags={TAG_STRATUS, TAG_AWS},
        ),
        Mcq(
            prompt="What is the fastest way to verify CloudTrail events are searchable once ingestion is working?",
            options=[
                "Check `index=aws_cloudtrail earliest=-1h` in Splunk Search",
                "Ping the S3 bucket URL in a browser",
                "Run `terraform plan`",
                "Restart Docker Desktop",
            ],
            answer_index=0,
            explanation="A quick SPL search validates data is landing in the correct index.",
            tags={TAG_SPLUNK},
        ),
        Mcq(
            prompt="Why keep CloudTrail/Config/VPC Flow in separate indexes?",
            options=[
                "Splunk cannot store multiple sourcetypes in one index",
                "It improves clarity: different retention, searches, troubleshooting, and dashboards per source",
                "AWS requires one index per bucket",
                "It reduces S3 costs",
            ],
            answer_index=1,
            explanation="Separating sources improves operational clarity and makes detection work easier.",
            tags={TAG_SPLUNK, TAG_SOC},
        ),
    ],
    "advanced": [
        Mcq(
            prompt="Which statement best captures 'detection engineering' value in this lab?",
            options=[
                "Collecting logs is enough; detections are optional",
                "Generate known-bad activity (Stratus) and validate it is observable + searchable + actionable",
                "Only VPC Flow Logs matter; CloudTrail is too noisy",
                "Dashboards replace the need for searches",
            ],
            answer_index=1,
            explanation="Senior practice is: generate signal, confirm visibility, write detections, validate and iterate.",
            tags={TAG_SOC, TAG_STRATUS},
        ),
        Mcq(
            prompt="What is the most defensible reason to keep `soc-lab-splunk-addon` least-privilege?",
            options=[
                "So you can share the keys publicly",
                "To reduce blast radius if keys leak; ingestion should not enable write/privilege actions",
                "Because Splunk requires read-only keys",
                "Because IAM users cannot have multiple policies",
            ],
            answer_index=1,
            explanation="Ingestion credentials are high-value; least privilege limits damage if compromised.",
            tags={TAG_SOC, TAG_AWS},
        ),
        Mcq(
            prompt="If you detonate a Stratus technique and nothing appears in Splunk, what is the highest-signal next check?",
            options=[
                "Verify CloudTrail is writing new objects to the CloudTrail S3 bucket (then verify Splunk input is pointed to that bucket/index)",
                "Reinstall Docker Desktop",
                "Change the AWS region in Terraform without re-applying",
                "Delete the Splunk indexes and recreate them",
            ],
            answer_index=0,
            explanation="Prove each hop in the pipeline: technique → CloudTrail → S3 objects → Splunk input → index search.",
            tags={TAG_SOC, TAG_AWS, TAG_SPLUNK, TAG_STRATUS},
        ),
        Fill(
            prompt="Fill in: Destroy should be run with the same credentials as ____ (build or stratus).",
            expected="build",
            explanation="Destroy should run under your build/admin identity. Stratus is only for simulations, not for applying teardown.",
            tags={TAG_TERRAFORM, TAG_STRATUS},
        ),
        Mcq(
            prompt="Which is the best reason to keep a dedicated Stratus user separate from the Splunk ingestion user?",
            options=[
                "Because AWS does not allow one user to have two access keys",
                "To separate attack generation from data collection and keep ingestion keys tightly scoped",
                "Because Splunk can't read from S3 if Stratus exists",
                "So Terraform can run faster",
            ],
            answer_index=1,
            explanation="Separation of duties: attack simulation identity is different from ingestion identity.",
            tags={TAG_SOC, TAG_STRATUS, TAG_AWS},
        ),
        Mcq(
            prompt="A good first 'corporate' dashboard panel built from CloudTrail data would be:",
            options=[
                "Random word cloud of event names",
                "Top eventName over time + high-risk IAM events count (CreateUser, AttachUserPolicy, CreateAccessKey)",
                "A pie chart of AWS regions only",
                "A panel that shows only successful logins",
            ],
            answer_index=1,
            explanation="Useful panels prioritize actionable summaries and drill-down to events.",
            tags={TAG_SPLUNK, TAG_SOC},
        ),
        Mcq(
            prompt="Which troubleshooting order best matches a production-grade ingestion investigation?",
            options=[
                "Restart everything until it works",
                "Start at Splunk only; ignore AWS side",
                "Prove each hop: Stratus/API → CloudTrail event → S3 object → add-on input config → index search",
                "Delete and recreate the entire AWS account",
            ],
            answer_index=2,
            explanation="Advanced debugging is a hop-by-hop proof, not guesswork.",
            tags={TAG_SOC, TAG_AWS, TAG_SPLUNK},
        ),
        Mcq(
            prompt="Why does `build.sh` always run `terraform init` (even when .terraform/ exists)?",
            options=[
                "To download the latest provider versions automatically",
                "To ensure the installed providers match the lock file after any versions.tf change",
                "Because Terraform requires init before every command",
                "To reset Terraform state",
            ],
            answer_index=1,
            explanation="`-upgrade=false` keeps existing versions but re-validates the cache against the lock file, catching stale or missing providers silently introduced by a versions.tf edit.",
            tags={TAG_TERRAFORM, TAG_SOC},
        ),
    ],
}


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AWS Threat Detection SOC Lab knowledge check")
    p.add_argument(
        "--level",
        choices=["beginner", "mid", "advanced", "senior"],
        default="beginner",
        help="Difficulty tier (senior is an alias for advanced).",
    )
    p.add_argument("--mode", choices=["mcq", "fill", "mixed"], default="mixed")
    p.add_argument("--count", type=int, default=0, help="Number of questions (0 = tier default)")
    p.add_argument("--shuffle", action="store_true", help="Shuffle question order")
    p.add_argument("--no-shuffle", action="store_true", help="Disable shuffle (stable order)")
    p.add_argument("--seed", type=int, default=0, help="Random seed for reproducible shuffles")
    p.add_argument("--no-clear", action="store_true", help="Do not clear the screen before starting")
    p.add_argument("--no-balanced", action="store_true", help="Disable topic-balanced selection")
    return p.parse_args(argv)


def iter_questions(level: Level, mode: Mode) -> list[Question]:
    qs = QUESTION_BANK[level]
    if mode == "mixed":
        return list(qs)
    if mode == "mcq":
        return [q for q in qs if isinstance(q, Mcq)]
    return [q for q in qs if isinstance(q, Fill)]


def _tags(q: Question) -> set[str]:
    return q.tags if isinstance(q, (Mcq, Fill)) else set()


def pick_balanced(level: Level, questions: list[Question], count: int) -> list[Question]:
    """
    Pick a balanced subset across topics for the selected tier.
    If any per-topic bucket is short, the remainder is filled from the unused pool.
    The returned list is capped at `count` items.
    """
    mix = BALANCED_MIX.get(level, {})
    selected: list[Question] = []
    used_ids: set[int] = set()

    def add_many(pool: list[Question], n: int) -> None:
        pool = [q for q in pool if id(q) not in used_ids]
        if not pool or n <= 0:
            return
        take = random.sample(pool, k=min(n, len(pool)))
        for q in take:
            used_ids.add(id(q))
            selected.append(q)

    # First pass: satisfy per-topic targets.
    for tag, n in mix.items():
        pool = [q for q in questions if tag in _tags(q)]
        add_many(pool, n)

    # Fill remaining slots from anything not yet selected.
    remaining = count - len(selected)
    if remaining > 0:
        pool = [q for q in questions if id(q) not in used_ids]
        add_many(pool, remaining)

    return selected[:count]


def choose_level_interactively() -> Level:
    hr()
    print(style("AWS Threat Detection SOC Lab — Knowledge Check", C.BOLD))
    print(style("Pick a difficulty tier.", C.DIM))
    hr()
    print(style("  1) beginner", C.CYAN) + style("  (purpose + fundamentals)", C.DIM))
    print(style("  2) mid", C.CYAN) + style("       (AWS concepts + engineering depth)", C.DIM))
    print(style("  3) advanced", C.CYAN) + style("  (pipelines, integrations, troubleshooting)", C.DIM))
    while True:
        raw = input(style("Select 1-3 (or 'q'): ", C.BOLD)).strip()
        if raw.lower() in {"q", "quit", "exit"}:
            raise KeyboardInterrupt
        if raw in {"1", "2", "3"}:
            return {"1": "beginner", "2": "mid", "3": "advanced"}[raw]  # type: ignore[return-value]
        print(style("Enter 1, 2, or 3 (or 'q' to quit).", C.YELLOW))


def ask_mcq(q: Mcq) -> tuple[bool, str]:
    print(style(q.prompt, C.BOLD))
    labels = "ABCD"
    for i, opt in enumerate(q.options, start=0):
        label = labels[i] if i < len(labels) else str(i + 1)
        print(f"  {style(label + ')', C.CYAN)} {opt}")
    while True:
        raw = input(style("Your answer (A-D / 1-4 / q): ", C.BOLD)).strip()
        if raw.lower() in {"q", "quit", "exit"}:
            raise KeyboardInterrupt
        if not raw:
            continue

        upper = raw.upper()
        if upper in {"A", "B", "C", "D"}:
            idx = "ABCD".index(upper)
            if idx < len(q.options):
                correct = idx == q.answer_index
                return correct, q.options[idx]

        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(q.options):
                idx = n - 1
                correct = idx == q.answer_index
                return correct, q.options[idx]

        print(style("Enter A-D or 1-4 (or 'q' to quit).", C.YELLOW))


def ask_fill(q: Fill) -> tuple[str, str]:
    print(style(q.prompt, C.BOLD))
    raw = input(style("Your answer (or 'q'): ", C.BOLD)).strip()
    if raw.lower() in {"q", "quit", "exit"}:
        raise KeyboardInterrupt
    return raw, q.expected


def run_quiz(
    level: Level,
    mode: Mode,
    count: int,
    shuffle: bool,
    seed: int,
    questions: Optional[list[Question]] = None,
) -> int:
    questions = list(questions) if questions is not None else iter_questions(level, mode)
    if seed:
        random.seed(seed)
    if shuffle:
        random.shuffle(questions)

    mcq_total = sum(isinstance(q, Mcq) for q in questions)
    mcq_correct = 0

    results: list[str] = []

    clear_screen()
    hr()
    if UNICODE_OK:
        title = f"Knowledge Check — {level.upper()}  ·  {mode.upper()}"
    else:
        title = f"Knowledge Check - {level.upper()} | {mode.upper()}"
    print(style(title, C.BOLD))
    print(style("Tip: answer fast, then review the 'why'. Type 'q' anytime to quit.", C.DIM))
    hr()
    print("")

    for idx, q in enumerate(questions, start=1):
        bar = progress_bar(idx - 1, len(questions))
        print(style(f"{bar}  Question {idx}/{len(questions)}", C.GRAY))
        try:
            if isinstance(q, Mcq):
                ok, chosen = ask_mcq(q)
                if ok:
                    mcq_correct += 1
                print(style("Correct", C.GREEN) if ok else style("Incorrect", C.RED))
                print(style("Why:", C.DIM), q.explanation)
                results.append(
                    f"- MCQ: {'OK' if ok else 'NO'} {q.prompt}\n"
                    f"  - You: {chosen}\n"
                    f"  - Correct: {q.options[q.answer_index]}\n"
                    f"  - Why: {q.explanation}"
                )
            else:
                given, expected = ask_fill(q)
                print(style("Expected:", C.DIM), expected)
                print(style("Why:", C.DIM), q.explanation)
                results.append(
                    f"- FILL: {q.prompt}\n"
                    f"  - You: {given}\n"
                    f"  - Expected: {expected}\n"
                    f"  - Why: {q.explanation}"
                )
        except EOFError:
            break
        print("")

    hr()
    print(style("Results", C.BOLD))
    if mcq_total:
        pct = int(round((mcq_correct / mcq_total) * 100))
        color = C.GREEN if pct >= 80 else (C.YELLOW if pct >= 60 else C.RED)
        print(
            f"MCQ score: {style(str(mcq_correct), C.BOLD)}"
            f"/{mcq_total}  ({style(str(pct) + '%', color, C.BOLD)})"
        )
    else:
        print("MCQ score: n/a (no multiple-choice questions selected)")
    print("")
    print(style("Answer key / review", C.BOLD))
    for block in results:
        print(block)
        print("")

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    args = parse_args(raw_argv)

    level_value = args.level
    if level_value == "senior":
        level_value = "advanced"

    shuffle_value = True
    if args.no_shuffle:
        shuffle_value = False
    elif "--shuffle" in raw_argv:
        shuffle_value = True

    if "--level" not in raw_argv and sys.stdin.isatty():
        try:
            level_value = choose_level_interactively()
        except KeyboardInterrupt:
            print("\nExiting.")
            return 130

    level: Level = level_value  # type: ignore[assignment]
    count_value = args.count or min(DEFAULT_COUNT[level], len(iter_questions(level, args.mode)))

    all_qs = iter_questions(level, args.mode)
    if shuffle_value:
        random.shuffle(all_qs)
    if not args.no_balanced:
        picked = pick_balanced(level, all_qs, count_value)
    else:
        picked = all_qs[:count_value]

    try:
        return run_quiz(
            level=level,
            mode=args.mode,
            count=len(picked),
            shuffle=False,
            seed=args.seed,
            questions=picked,
        )
    except KeyboardInterrupt:
        print("\nExiting.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
