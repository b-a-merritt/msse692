# Known limitations

- Delivery sends no external notification; a client must call the delivery endpoint.
- A short acknowledgement from another speaker ends the target's turn and its batch.
- A dropped transcription stream ends capture; speech until the next Start is lost, and that Start creates a new case.
- Discovery requires every topic that preceded each conflict, so with few conversations a coincidental topic can block a match. Evidence uses only earlier batches and is missed when the pattern's last topic and the attack share a batch.
- Model scores and the 0.7 selection threshold are not calibrated accuracy claims.
