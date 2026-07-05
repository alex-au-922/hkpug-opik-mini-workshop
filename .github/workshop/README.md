# Encrypted Answer Rubric

`answers.json.cms` is encrypted with OpenSSL CMS using
`answer_key_cert.pem`. GitHub Actions decrypts it with the repository secret
`ANSWER_KEY_PRIVATE_KEY` during issue grading.

Do not commit the plaintext rubric or private key.

Plaintext rubric items use this shape before encryption:

```json
{
  "cases": {
    "001": {
      "A": { "answers": ["short-exact-token"] }
    }
  }
}
```

The grader exact-matches these short answers after trimming whitespace,
collapsing internal whitespace, lowercasing, and removing wrapping backticks.
