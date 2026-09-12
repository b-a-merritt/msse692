# ADR 002: Observation-to-Event Construction Boundaries

- **Status:** Accepted
- **Date:** 2026-09-06
- **Decision owner:** Ben Merritt

## Context

Upstream inputs report observations or deterministic derivations from a source such as a transcript, timing stream, or signal measurement. Those observations can
support event construction, but they do not by themselves establish social meaning, speaker intent, sincerity, character, or violation of a norm.

The system needs a clear boundary between provider observations, constructed events, conformance assessment, and intervention decisions. Without that
boundary, a later stage could treat a bounded observation as stronger evidence than the input supports.

## Decision

An upstream provider reports what it observed or deterministically derived. It does not assign social meaning, infer intent, or decide that conduct violates a
norm.

For example, finding a configured term establishes that the term appeared. It does not establish derogation. Whether that observation constructs an event such
as `selected_term_used` depends on the active event definition.

The same rule applies to other behavior:

| Available observation or deterministic condition | Defensible constructed event | Conclusion not supported |
|---|---|---|
| Configured word match | `selected_term_used` | Derogation or harassment |
| Simultaneous speech intervals | `speech_overlap_observed` | Deliberate interruption |
| Turn transition plus overlap rule | `turn_interruption_candidate` | Rudeness or intent |
| Signal level above a threshold | `volume_threshold_exceeded` | Aggression |
| Speech interval exceeds a configured duration | `turn_duration_threshold_exceeded` | Monopolizing or dominating the conversation |
| Speech rate exceeds a configured threshold | `speech_rate_threshold_exceeded` | Anger, anxiety, or aggression |
| Silence after another speaker stops | `response_delay_observed` | Disrespect |
| Explicit repair phrase match | `repair_expression_observed` | Sincere apology |

Processing stages have distinct responsibilities:

1. The provider reports a bounded observation and its source-native quality data, if any.
2. Event construction checks the active event definition and either emits a descriptive event or filters the input.
3. The conformance monitor evaluates constructed events against the fixed model.
4. A separate intervention policy decides whether an eligible assessment should produce a notification or abstain.

A later stage must not rewrite a descriptive event as a claim about intent, character, sincerity, aggression, disrespect, harassment, or another social judgment that the input does not support.

Constructed event names describe the supported evidence. Names such as `speech_overlap_observed`, `volume_threshold_exceeded`, and `repair_expression_observed` state what the system can defend. Names such as `aggression_detected`, `rudeness`, or `apology` claim more than the mocked input establishes and are not allowed.

Source-native quality applies only to the source measurement. A transcription confidence value describes the transcript. It is not the probability that the
speaker was derogatory. A signal-quality value does not establish aggression. Missing information may cause event construction to filter the input, but a
filtered input receives no conformance status.

## Consequences

- Providers must emit bounded observations rather than norm-laden events.
- Event construction must emit only descriptive events supported by the active event definition.
- Repeated observations remain descriptive events in a sequence. They do not justify anything in of themselves.
- Expected examples and tests should use event names that state observable or deterministic evidence, not social judgments.
- Source quality data must not be reused as a probability of intent, sincerity, aggression, harassment, or another unsupported conclusion. This is especially true for sarcastic comments.
- Filtered inputs create no constructed event and receive no conformance status.

This decision does not define the fixed norms, conformance algorithm, assessment window, rule formalism, or intervention strategy.

### Positive

- Activity names and explanations remain limited to the evidence actually reported.
- Separating source quality from social interpretation prevents measurement confidence from being presented as confidence in a moral judgment.

### Negative

- Descriptive observations alone cannot establish intent, sincerity, or the legitimacy of a normative model.
- Each activity requires explicit evidence criteria, limiting what the prototype can claim and increasing definition and testing work.

## Alternatives rejected

### Let providers emit norm-laden events

Rejected because providers can report only what they observed or deterministically derived. A provider event such as `aggression_detected` or `sincere_apology`
would collapse observation, event construction, and social interpretation into one step.

### Convert repeated observations into character labels

Rejected because sequence interpretation belongs to conformance checking. Several `speech_overlap_observed` events may match a modeled undesirable pattern, but
they do not support constructing an event such as `habitual_interrupter`.

### Treat source quality as normative confidence

Rejected because quality data is scoped to the source measurement. A transcript confidence score describes the transcript, not the probability that a speaker was
derogatory, sincere, aggressive, or disrespectful.
