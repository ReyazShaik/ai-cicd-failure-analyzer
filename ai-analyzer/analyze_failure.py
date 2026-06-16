#!/usr/bin/env python3

import argparse
import json
import os
import sys
import textwrap
import urllib.request
import urllib.error
from datetime import datetime


def read_logs(logs_dir: str, limit_chars: int = 16000) -> str:
    collected = []

    if not os.path.isdir(logs_dir):
        return "No logs directory found."

    for root, _, files in os.walk(logs_dir):
        for file in sorted(files):
            path = os.path.join(root, file)
            try:
                with open(path, "r", errors="ignore") as f:
                    content = f.read()
                collected.append(f"\n\n===== FILE: {path} =====\n{content}")
            except Exception as e:
                collected.append(f"\n\n===== FILE: {path} =====\nCould not read file: {e}")

    text = "\n".join(collected)
    return text[-limit_chars:]


def call_ollama(ollama_url: str, model: str, prompt: str) -> str:
    url = f"{ollama_url.rstrip('/')}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "Ollama returned no response.")
    except Exception as e:
        return fallback_analysis(str(e), prompt)


def fallback_analysis(error: str, prompt: str) -> str:
    lower_prompt = prompt.lower()

    if "npm err" in lower_prompt or "npm error" in lower_prompt:
        reason = "The failure appears related to npm dependency installation or package configuration."
        fix = "Check package.json, package-lock.json, package versions, and npm registry access."
    elif "jest" in lower_prompt or "test failed" in lower_prompt:
        reason = "The failure appears related to unit test failure."
        fix = "Review the failing test, expected output, and application route logic."
    elif "dockerfile" in lower_prompt or "kaniko" in lower_prompt or "copy failed" in lower_prompt:
        reason = "The failure appears related to Docker image build."
        fix = "Check Dockerfile COPY paths, build context, file names, and base image."
    elif "trivy" in lower_prompt or "critical" in lower_prompt or "vulnerability" in lower_prompt:
        reason = "The failure appears related to image vulnerability scanning."
        fix = "Upgrade vulnerable packages or use a more secure base image."
    elif "imagepullbackoff" in lower_prompt or "crashloopbackoff" in lower_prompt or "rollout" in lower_prompt:
        reason = "The failure appears related to Kubernetes deployment rollout."
        fix = "Check image name, imagePullSecrets, pod logs, readiness probes, and service configuration."
    else:
        reason = "The pipeline failed, but the exact category could not be confidently detected."
        fix = "Review the failed stage logs and rerun the pipeline after correcting the visible error."

    return f"""
AI engine was not reachable. Fallback analysis was used.

Ollama Error:
{error}

Likely Root Cause:
{reason}

Recommended Fix:
{fix}

Next Action:
Open the Jenkins failed stage logs, fix the issue, commit the change, and rerun the pipeline.
"""


def send_slack(webhook: str, message: str) -> None:
    if not webhook:
        print("No Slack webhook provided. Skipping Slack notification.")
        return

    payload = {
        "text": message
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"Slack notification sent. HTTP {response.status}")
    except urllib.error.HTTPError as e:
        print(f"Slack HTTP error: {e.code} {e.reason}")
    except Exception as e:
        print(f"Slack notification failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--build-url", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--logs-dir", required=True)
    parser.add_argument("--ollama-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--slack-webhook", required=True)

    args = parser.parse_args()

    logs = read_logs(args.logs_dir)

    prompt = f"""
You are a senior DevOps engineer and CI/CD failure analysis expert.

Analyze the following Jenkins pipeline failure logs and produce a clear production-grade RCA.

Return the answer in this exact format:

1. Failed Stage:
2. What Failed:
3. Root Cause:
4. Evidence from Logs:
5. Recommended Fix:
6. Exact Next Action:
7. Prevention for Future:

Pipeline Context:
Job: {args.job}
Build: {args.build}
Failed Stage: {args.stage}
Commit: {args.commit}
Build URL: {args.build_url}

Logs:
{logs}
"""

    analysis = call_ollama(args.ollama_url, args.model, prompt)

    report = f"""
🚨 *AI CI/CD Pipeline Failure Analysis*

*Job:* {args.job}
*Build:* {args.build}
*Failed Stage:* {args.stage}
*Commit:* {args.commit}
*Build URL:* {args.build_url}
*Time:* {datetime.utcnow().isoformat()} UTC

*AI Root Cause Report:*
{analysis}
"""

    os.makedirs("ai-report", exist_ok=True)

    with open("ai-report/failure-analysis.txt", "w") as f:
        f.write(report)

    print(report)

    send_slack(args.slack_webhook, report)


if __name__ == "__main__":
    main()
