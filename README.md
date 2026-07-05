# HKPUG Opik Mini Workshop

Participant repository for the HKPUG Opik trace-debugging mini workshop.

Start here:

- Workshop site: https://alex-au-922.github.io/hkpug-opik-mini-workshop/
- Code pane: https://group-00.opik-workshop.python.hk/code
- Opik pane: https://group-00.opik-workshop.python.hk/opik

## How To Submit

Open a new issue using the **Mini workshop answers** template. Submit one issue
with all six cases:

```text
Case: 001
A:
B:
C:
D:
```

The GitHub Action checks your issue against an encrypted answer rubric and adds
either `passed` or `needs-correction`.

## Workshop Story

A BA has flagged six suspicious support-agent runs before release. You are the
engineer summarizing the debugging session for your manager. Most answers are
inside Opik spans; a few answers require checking the Python code in the code
pane.

## Maintainer Notes

The answer rubric is stored as `.github/workshop/answers.json.cms`, encrypted
with OpenSSL CMS. The private key is stored in the repository secret
`ANSWER_KEY_PRIVATE_KEY`.

