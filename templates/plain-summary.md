# Plain-language summary comment (rule R10)
Post ONE extra comment with this shape when a PR is final (findings fixed, ready for the last review or merge). Write for someone who does not program: no jargon, or explain a term in five words. Diagrams may use the whole page; the repo host renders fenced `mermaid` blocks. Sign it `**<Role> · <Vendor>:**`. The technical comments stay as they are.

## What this changes (2 to 4 sentences)
...

## How it works (workflow diagram)
```mermaid
flowchart LR
  A[Input arrives] --> B[The app checks it]
  B --> C{Is it clear?}
  C -- yes --> D[Done automatically]
  C -- not sure --> E[A person decides, with a reason]
```

## Before and after (branches or behaviour)
```mermaid
gitGraph
  commit id: "main"
  branch feature
  commit id: "this change"
  checkout main
  merge feature
```
Plus a small "Before / After" table of what a person sees.

## What a person will notice
- ...

## What did NOT change / what could go wrong
- ...

## How we know it works
- tests, who reviewed, CI status, numbers (say which are measured and which are estimates)

## Status
- approvals with exact commits; what still must happen before merge
