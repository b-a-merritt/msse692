# Abbreviated Annotated Bibliography

## Process Mining

### General

#### Grohs et al (2026) Can Conformance Checking Monitor Process Compliance? A Taxonomy of Regulations for Business Processes
Builds a taxonomy of business-process regulations and examines the mismatch between regulatory requirements and process models. The paper shows how conformance checking can overstate or omit compliance obligations when models overspecify or underspecify regulations.

#### Rozinat et al (2007) Towards an evaluation framework for processing mining algorithms
A framework for comparing the algorithms and process mining techniques to each other.

### Modeling Process

#### Hildebrandt et al (2011) Declarative Event-Based Workflow as Distributed Dynamic Condition Response Graphs
A **declarative model** for modeling process. Description of modeling processes in Di Federico p. 14

#### Maja et al (2007) DECLARE: Full Support for Loosely-Structured Processes
Another **declarative model** for modeling process. Description of modeling processes in Di Federico p. 14

#### Hildebrandt and Mukkamala (2011) Declarative Event-Based Workflow as Distributed Dynamic Condition Response Graphs
Introduces Dynamic Condition Response Graphs as a declarative, event-based workflow model using condition, response, include, and exclude relations between events. The paper extends the model with roles for distributed workflows and maps DCR Graphs to Büchi automata.

#### Pesic et al (2007) DECLARE: Full Support for Loosely-Structured Processes
Presents DECLARE, a workflow-management prototype that uses constraint-based declarative process models for loosely structured processes. The paper argues that DECLARE can preserve flexibility while still supporting model verification, execution, runtime changes, past-execution analysis, and user recommendations.

### Online Conformance Checking

#### Burattin (2018) Streaming process discovery and conformance checking
Defines streaming/online process mining techniques. Analyzes event streams immediately without complete logs. Has multiple methods:

1. Window-based models
1. Problem reduction
1. Offline precomputation

#### Burattin et al (2018) Online Conformance Checking Using Behavioural Patterns
Online conformance checking framework. Uses Petri-net unfoldings to evaluate behavior patterns (incomplete, running cases). Can start from already underway case.

#### Di Federico (2022) Linac: A Smart Environment Simulator of Human Activities
Presents Linac, a configurable smart-environment simulator for generating realistic human-activity sensor streams for process-mining research. The system models floor plans, sensors, agents, non-deterministic movement, time scaling, and MQTT output, and its simulations are compared against CASAS activity

Talks about data collection (test beds, public test beds, and simulators). "The most relevant [feature] is that human beings are flexible in their movements [8]: they do not perform movements in a fixed way but introducing variability. Furthermore, we cannot assume that human beings are all equal, i.e. elderly are slower in the movements, while young people are faster."

Uses MQTT (the IoT standard).

Ultimately about a framework for simulation.

#### Di Federico (2023) A Process Mining Framework to Analyze Variability in Human Behavior
Develops a process-mining framework that turns sensor data into activities, models a person's usual routine, and checks live behavior for meaningful variations. The thesis frames the approach as useful for monitoring daily routines in healthcare contexts, especially for neurodegenerative disorders.

#### Di Federico and Burattin (2023) Do You Behave Always the Same? A Process Mining Approach
Proposes a hybrid model for variable human behavior that combines process flow, declarative constraints, and statistical data. The paper uses this richer model to support conformance checking when control flow alone cannot represent flexible human routines.

#### Pfister et al (2025) Towards a Value-Complemented Framework for Enabling Human Monitoring in Cyber-Physical Systems
**VERY SIMILAR??** -- no, this is a meta framework for requirements elicitation for CPS
Proposes a requirements framework that connects human-monitoring requirements in cyber-physical systems to values such as privacy, security, and self-direction. The framework traces values to actors and design choices so runtime monitoring can account for human values during requirements engineering.

"In this research preview paper, we present our ideas towards incorporating human values in the process of eliciting and specifying requirements for creating runtime monitors that collect human-related data. Our initial conceptual framework for valuecomplemented Human-Monitoring defines key activities, from specifying monitoring use cases to applying value tactics for creating a set of agreed on functional and non-functional monitoring requirements."

## Human in the Loop Cyber Physical Systems

### Realtime actuation

#### Damian and André (2018) Designing Systems to Augment Social Interactions
Monitors social behavior and provides real-time feedback. Uses for social anxiety (?). Analyzes usefulness, timing, distraction, acceptability, privacy, and transparency of such systems.

#### Fang et al (2025) Mirai: A Wearable Proactive AI "Inner-Voice" for Contextual Nudging
Presents Mirai, a wearable camera-and-speech prototype that anticipates user actions and delivers contextual nudges in a cloned version of the user's voice. The paper demonstrates dietary, productivity, and communication scenarios while noting privacy, agency, and longitudinal-evaluation challenges.

#### Fernandes et al (2025) People 4.0 - A model for Human-in-the-Loop CPS-based systems
Proposes the People 4.0 model for integrating human actions, intentions, emotions, and states throughout a cyber-physical control loop. The paper argues that CPS and IoT systems should treat people as active parts of the loop rather than merely data sources, and it supports the model with implementation examples and case studies.

#### Poss & Schonig (2026) A synergistic engine paradigm for real-time context-aware decision-making integrating declarative processes and event streams
Using declarative evaluation on one CEP engine for event abstraction. Very similar architecture to what we're planning. Will need to describe contribution relative to this.

### Ethical applications

#### De Sanctis et al (2026) Runtime Enforcement for Operationalizing Ethics in Autonomous Systems
Introduces SLEEC@run.time, a runtime ethics-enforcement approach for autonomous systems. It formalizes social, legal, ethical, empathetic, and cultural rules with Abstract State Machines and enforces them through a MAPE-K control loop.

#### Katsaros et al (2022) Reconsidering Tweets: Intervening During Tweet Creation Decreases Offensive Content
Reports a randomized Twitter experiment in which users were prompted to reconsider potentially harmful tweets before publishing. The intervention led prompted users to post about 6% fewer offensive tweets and was also associated with fewer later offensive posts and offensive replies.

#### Schnitker et al (2021) Mixed Results on the Efficacy of the CharacterMe Smartphone App to Improve Self-Control, Patience, and Emotional Regulation Competencies in Adolescents
Evaluates the CharacterMe app with 618 adolescents and finds no overall improvement in self-control, patience, or emotional regulation. The study shows that established character and socioemotional interventions may not transfer effectively to smartphone-based delivery.

#### Umer et al (2025) StressSpeak: A Speech-Driven Framework for Real-Time Personalized Stress Detection and Adaptive Psychological Support
Presents a speech-to-text and language-model pipeline for real-time stress detection and personalized support. The study compares nine model variants across benchmark datasets, latency, false-positive and false-negative patterns, and user-centered validation.

#### Zhang et al (2025) WSCoach: Wearable Real-time Auditory Feedback for Reducing Unwanted Words in Daily Communication
Evaluates WSCoach, a wearable system that detects user-selected unwanted words and provides near-real-time audio feedback. The studies found both real-time and post-conversation feedback helpful, with stronger long-term results for WSCoach.

## Philosophy

### Moral Advisors

#### Giubilini and Savulescu (2018) The Artificial Moral Advisor: The Ideal Observer Meets Artificial Intelligence
Proposes an artificial moral advisor that supports moral decision-making by applying consistent, dispassionate reasoning while taking the user's own values into account. The authors argue that such a system could reduce bias and improve reflective autonomy without imposing a single moral theory.

#### Savulescu and Maslen (2015) Moral Enhancement and Artificial Intelligence: Moral AI?
Explores a personalized moral AI that monitors factors affecting decisions, points out possible biases, and advises users according to their own values. The chapter argues that an agent-tailored moral AI could preserve moral pluralism while helping users overcome limits in human moral psychology. | Not started

## AI

### Morality

#### Saffari et al (2025) Beyond Hate Speech: NLP's Challenges and Opportunities in Uncovering Dehumanizing Language
Evaluates four large language models for detecting dehumanizing language and distinguishing it from other hate-speech types. The paper finds that models confuse dehumanization with related categories and perform unevenly across targeted groups, raising fairness concerns for moderation and analysis.

#### Szutta (2025) Artificial Intelligence as a Moral Mentor
Proposes an AI moral mentor called E-Daimonion that uses emotionally engaging stories to encourage empathy, moral insight, and lasting motivation for ethical behavior. The paper critiques substitution, advisor, and interlocutor models while recognizing risks such as dependence, manipulation, and indoctrination.

#### Volkman and Gabriels (2023) AI Moral Enhancement: Upgrading the Socio-Technical System of Moral Engagement
Rejects the idea of AI as a single moral oracle and instead proposes a modular system of AI interlocutors grounded in diverse wisdom traditions. The paper frames moral enhancement as a socio-technical system that should preserve pluralism and moral engagement.
