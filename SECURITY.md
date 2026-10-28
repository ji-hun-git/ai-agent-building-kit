# Security

The template makes specific promises: what the guard strips, redacts and refuses ([`guard.py`](template/kit/guard.py)), and what the policy, the trifecta rule, lockdown and approvals never let run ([`tools.py`](template/kit/tools.py), [`policy.py`](template/kit/policy.py)). A way around any of them is a security bug.

## Reporting

Email [chaejihun@kaist.ac.kr](mailto:chaejihun@kaist.ac.kr) with "security" in the subject instead of opening a public issue. Include the smallest input that gets through and what should have happened. Each fix ships with a regression test built from that input.

## In scope

- Text that gets past a guard rule: the hidden characters, credential and identifier formats, and URL forms it lists.
- A tool or argument that runs despite the policy, the trifecta rule, lockdown or a declined approval.
- A document a user can retrieve without the role its ACL names.
- Input that makes a guard pattern or the retriever slow.

## Out of scope

- What a model says in plain text. No guard can promise that; the policy decides what the model can do.
- Classifier accuracy, and credential formats the guard does not list. Open an issue to add a format.
