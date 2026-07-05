# HKPUG Opik Mini Workshop

Participant repository for the HKPUG Opik trace-debugging mini workshop.

Start here:

- Workshop site: https://alex-au-922.github.io/hkpug-opik-mini-workshop/
- Code pane: https://group-00.opik-workshop.python.hk/code
- Opik pane: https://group-00.opik-workshop.python.hk/opik

## How To Submit

Open a new issue using the **Mini workshop answers** template. Keep one issue
for your group, and edit it as you answer more cases:

```text
Case: 001
A:
B:
C:
D:
```

Your answers are plain GitHub issue text; you do not need to encrypt anything.
The GitHub Action checks the issue against an encrypted answer rubric and
reports a percentage score. There are 24 answer items, so each correct answer
adds 4.17 percentage points. Blank answers are neutral; submitted wrong answers
are marked `check again`.

## Workshop Story

A BA has flagged six suspicious support-agent runs before release. You are the
engineer summarizing the debugging session for your manager. Most answers are
inside Opik spans; a few answers require checking the Python code in the code
pane.

## Maintainer Notes

The answer rubric is stored as `.github/workshop/answers.json.cms`, encrypted
with OpenSSL CMS. The private key is stored in the repository secret
`ANSWER_KEY_PRIVATE_KEY`.
