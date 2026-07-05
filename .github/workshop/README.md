# Encrypted Answer Rubric

`answers.json.cms` is encrypted with OpenSSL CMS using
`answer_key_cert.pem`. GitHub Actions decrypts it with the repository secret
`ANSWER_KEY_PRIVATE_KEY` during issue grading.

Do not commit the plaintext rubric or private key.

