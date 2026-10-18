---
name: Git authorization evidence
description: Distinguish integration setup confirmation from working workspace Git authentication.
---

Do not treat a GitHub connection confirmation as proof that workspace Git can
write to the repository.

**Why:** This workspace continued to reject Git pushes after a connection was
confirmed. Separately authorized GitHub CLI access succeeded; repeated connection
prompts alone did not resolve the failing Git authentication path.

**How to apply:** Diagnose the authorization path used by the failing operation.
Verify repository write access and compare the remote branch SHA after pushing.
Keep credentials in Secrets and use supported credential helpers; never copy
tokens into remotes, files or logs.
