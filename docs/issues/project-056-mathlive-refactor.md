# MathLive Decontamination and Rebuild Instructions

## 1) What went wrong

You are inheriting a repository whose MathLive-related area is **untrusted**.

Previous LLM work failed in several serious ways:

* It claimed MathLive bugs were fixed without proving the live notebook/frontend behavior.
* It treated backend state or passing tests as proof of a UI fix.
* It rewrote issue narratives and tests to fit partial patches.
* It mixed small code changes with broad cleanup and documentation edits, making it harder to see what was really fixed.
* It altered or removed notebook evidence in ways that reduced visibility into what was still broken.
* It allowed unresolved MathLive behavior to remain while reporting completion.

Assume the existing MathLive implementation, supporting tests, demos, notebook cells, wrappers, special policies, and issue-driven patches may contain **cruft, obfuscation, hacks, dead code, misleading abstractions, misleading tests, or outright false confidence**.

Your first job is **not to repair that code**. Your first job is to **identify and remove the maximum amount of untrusted MathLive-related functionality** so the rebuild can start from something simple and auditable.

It is acceptable if this removal breaks many notebooks and features. That is expected.

## 2) Main goal

The goal is to:

1. **Identify and eliminate all MathLive-related crap, obfuscation, hacks, and untrusted logic.**
2. **Remove as much MathLive-related code and tests as possible.**
3. **Rebuild MathLive functionality from scratch in small, simple, self-contained phases.**
4. **At the end of each phase, provide a revised repo and update one canonical showcase notebook.**
5. **That notebook must rely on the user for verification.**
6. **The notebook must describe in words what should happen and why.**
7. **The user will do a sanity check of visible functionality.**
8. **Do not expect the user to inspect all code changes. Visible behavior must carry the verification burden.**

## 3) Non-negotiable rules

### Trust model

Treat all existing MathLive-related code as contaminated until proven otherwise.

### Scope discipline

Do not bundle multiple phases into one delivery. Do one phase, stop, return the repo, and wait for the next instruction.

### Simplicity over compatibility

Prefer deletion over repair. Prefer small explicit code over reusable abstractions. Prefer separate simple classes over one clever configurable class. Do not preserve backward compatibility unless the user explicitly asks for it.

### No narrative laundering

Do not rewrite issues, tests, notebooks, docs, or status text to make incomplete work look complete.

### No hidden verification

Do not use browser-side injection, simulated user input, hidden cells, checkpoint artifacts, saved outputs, or any other trick that could make the notebook appear more validated than it really is.

browser-side injection, simulated user input is allowed in explicitly authored notebooks aimed at the user that will help them test things more quickly. HOWEVER, these injections must be 0) clearly marked and they cells with injection or simulated input must contain ONLY that and nothing else 1) they must be explained with markdown cells 2) bypassable - the user should be able to decide NOT to execute injection or simulation, do it on their own, and continue the test. 

### No proxy claims

Do not say a UI bug is fixed because:

* a trait changed
* a test passed
* metadata looks correct
* an issue now sounds coherent

A visible notebook behavior is not fixed until the notebook clearly tells the user what to check and the user can manually verify it.

### One canonical showcase notebook

Create or maintain **one canonical MathLive rebuild showcase notebook** and update it at every phase. Report its path clearly. That notebook is the main verification surface. DO NOT delete existing code because that may be a way to obfuscate and cheat on tests implemented by the user. If there is evidence that code is obsolete, include a comment in those cells explaining WHY you believe that to be true. It is up to the user to accept your explanation and delete the cells. 

### Clear boundaries in every report

At the end of every phase, separate:

* **Implemented**
* **Not implemented yet**
* **What the user must verify manually**
* **What remains uncertain**

## 4) Deliverables required at the end of every phase

Return all of the following:

1. A revised repo implementing only the current phase.
2. The updated canonical showcase notebook.
3. A concise changed-file list with one-line justification per file.
4. A concise removed-file list for MathLive-related deletions.
5. A manual verification checklist in the notebook.
6. A short report that clearly states:

   * what was implemented in this phase
   * what was deliberately left out
   * what the user should test
   * what would count as failure

Do not claim “fixed” or “complete.” Say **ready for user verification**.

## 5) Notebook requirements for every phase

The canonical showcase notebook must:

* be the primary evidence surface for the phase
* explain the phase goal in plain language
* explain what the user should do
* explain what the user should observe
* explain **why** that observation matters
* explain what is intentionally absent in this phase
* avoid hidden automation or browser-side simulation
* avoid saved outputs that imply success
* rely on the user’s manual sanity check

Each visible demo in the notebook must answer:

* What is this phase trying to prove?
* What should happen?
* Why should it happen?
* What would indicate the implementation is still wrong?


## Phase 1: Minimal raw Math input bridge based on MathLive

### Goal

Reintroduce MathLive and stabilize the basic generic MathLive field contract.


### Why

Prove that a basic MathLive field can render and synchronize a value between frontend and backend before adding any semantic behavior.
The foundation must be trustworthy before adding specialized behavior.


### Requirements
Setup a subfolder in src related to math input functionality. It will be done through mathlive but this should NOT be exposed. Mathlive is the backend.
Define a class that represents a math input widget (generic). 


Keep the implementation small. Focus only on:

* initialization from Python
* display
* user edits flowing back to Python
* ability to set value from Python. 
* clear serialization/value contract
* predictable behavior on rerun or reset

* minimal API surface
* no special menu logic
* no context-aware behavior
* no custom semantic rules
* no dynamic role switching

Documentation must be comprehensive and up to quality of the rest of the toolkit.



### Notebook must show

* the field renders
* initial value set from Python
* the user can edit it
* the backend can read the new value
* a visible confirmation of round-trip behavior

### Not implemented yet

No restrictions, no role-aware behavior, no context suggestions, no unknown-name policy.

Stop and return the repo.


### Not implemented yet

Still no identifier-specific behavior and no special menu restrictions.

Stop and return the repo.

---

## Phase 4: Minimal identifier field as a separate, simple feature

### Goal

Introduce identifier-specific behavior in the simplest possible way.

### Why

This is the first phase where role-aware UI behavior is allowed, but it must be visibly verifiable and kept small.

### Requirements

* prefer a separate simple identifier implementation over clever role mutation
* explicitly restrict irrelevant generic MathLive actions
* do not include broad semantic intelligence
* do not guess policies implicitly

At this stage, the identifier field should visibly differ from a generic expression field in a way the user can check directly.

### Notebook must show

* a generic expression field
* an identifier field
* instructions to open each menu and compare them
* a plain-language explanation of why the identifier field is more constrained

### Notebook must explicitly tell the user to verify

* which menu items should not appear in the identifier field
* why those items are inappropriate there

### Not implemented yet

No complex context-driven suggestions unless they are the sole feature of the next phase.

Stop and return the repo.

---

## Phase 5: Explicit context-aware identifier behavior

### Goal

Add one simple, explicit context policy for identifiers.

### Why

Only after the identifier field visibly behaves differently should context awareness be added.

### Requirements

Pick one small, explicit policy, for example:

* identifiers may come only from a provided context, or
* provided context names are suggested, with a clearly stated rule for unknown names

Keep it simple and transparent. No hidden heuristics. No clever inference. No bundled extras.

### Notebook must show

* the provided context
* what names should be accepted or suggested
* what should happen for unknown names
* why that rule exists

### Notebook must instruct the user to try specific examples and compare the observed behavior to the stated rule.

Stop and return the repo.

---

## Phase 6 and beyond: Only one advanced feature per phase

Do not add advanced behavior unless the user explicitly asks.

Any later phase must:

* add exactly one visible capability
* keep the notebook verification simple
* avoid bundling unrelated cleanup or abstractions
* explain why the new capability is worth the added complexity

## 8) Rules for tests during the rebuild

During Phase 0, remove MathLive-related tests along with the old implementation.

During rebuild phases, only add tests that directly support the current minimal implementation.

Allowed tests:

* small contract tests
* direct value synchronization tests
* explicit behavior tests tied to the current phase

Not allowed:

* tests about issue wording
* tests about notebook honesty wording
* tests whose main function is to support a narrative
* broad speculative tests for features not implemented yet

Tests are secondary evidence. The notebook is primary.

## 9) Forbidden behaviors

Do not do any of the following:

* claim a frontend bug is fixed without a visible notebook demo
* modify issue wording to make the current phase sound more complete
* keep old abstractions “just in case”
* preserve hidden compatibility layers
* add browser-side injection to simulate edits
* save notebook outputs that imply manual verification has already happened
* combine decontamination with feature rebuild in one delivery
* implement multiple new visible behaviors in a single phase
* use one generic over-configured class where two tiny explicit classes would be simpler
* silently expand the scope of the phase

## 10) What to say at the end of each phase

End every phase with a short report in this format:

* **Phase completed:** [name]
* **Implemented in this phase:** [visible behaviors only]
* **Not implemented yet:** [explicit list]
* **Files changed:** [concise list]
* **Files removed:** [concise list]
* **Notebook path:** [canonical showcase notebook]
* **User verification needed:** [manual checklist summary]
* **Uncertainties:** [anything not yet proven]

Do not say “fully fixed,” “resolved,” or “complete.”

Say: **ready for user verification**.

---

A good final operating principle is this:

**Delete first. Rebuild small. Prove only one visible thing at a time. Let the user verify behavior, not the narrative.**
