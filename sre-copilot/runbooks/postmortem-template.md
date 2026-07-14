# Postmortem Template

> **How to use this template**: Fill in each section as soon as the incident is resolved.  
> Complete the draft within 24 hours of resolution. Review with the team within 48 hours.  
> File action items as tickets before closing the postmortem.

---

## Incident Summary

| Field | Value |
|---|---|
| **Incident ID** | INC-YYYY-NNN |
| **Title** | One-sentence description of what failed |
| **Severity** | P1 / P2 / P3 |
| **Service(s) Affected** | e.g., `auth-service`, `checkout-service` |
| **Start Time** | YYYY-MM-DDTHH:MM:SSZ |
| **End Time** | YYYY-MM-DDTHH:MM:SSZ |
| **Total Duration** | HH hours MM minutes |
| **Incident Commander** | @name |
| **Scribe** | @name |
| **Postmortem Author** | @name |
| **Postmortem Review Date** | YYYY-MM-DD |

---

## Impact

*Describe the user-visible impact. Be specific: number of users affected, requests failing, revenue impact estimate, and which operations were unavailable.*

**User Impact**:
- _Example: All users unable to log in via Google OAuth for 47 minutes._
- _Example: ~12% of checkout attempts returned 500 during the degraded window._

**Business Impact**:
- _Example: Estimated N orders unable to be placed during the window._
- _Example: Payment processing halted for all businesses on the platform._

**Error Volume** *(from Gold tables / CloudWatch)*:
- Peak error rate: N errors/minute
- Normal baseline: N errors/minute
- Anomaly ratio (`error_rate_vs_normal`): N.Nx

---

## Timeline

*Use UTC timestamps. Include every significant action, observation, and decision.*

| Time (UTC) | Event |
|---|---|
| `HH:MM` | Incident begins (first alert / user report) |
| `HH:MM` | On-call SRE paged |
| `HH:MM` | Incident declared; bridge call opened |
| `HH:MM` | First hypothesis formed: _describe_ |
| `HH:MM` | Investigation step: _describe what was checked_ |
| `HH:MM` | Root cause confirmed |
| `HH:MM` | Mitigation applied: _describe action taken_ |
| `HH:MM` | Error rate returning to baseline |
| `HH:MM` | Incident resolved; all systems healthy |
| `HH:MM` | Post-incident monitoring window started |
| `HH:MM` | Post-incident monitoring completed; all-clear |

---

## Root Cause

*A concise technical explanation of what went wrong and why. This section should be understandable by someone not on the on-call rotation.*

### Immediate Cause

*The proximate technical event that triggered the incident.*

> Example: The ECS task definition was updated with an incorrect `GOOGLE_CLIENT_ID` value, causing all Google OAuth token verifications to fail with `Token has wrong audience`.

### Contributing Factors

*Conditions that made the incident worse or harder to detect. List each as a bullet.*

- _Example: No automated smoke test on the auth endpoint after deployments._
- _Example: The incorrect env var was copied from a staging config without review._
- _Example: CloudWatch alarm threshold was set too high (> 50% error rate) to catch early degradation._

### Why Did It Happen?

*The systemic or process failure that allowed the immediate cause to occur.*

> Example: The deployment process did not include a required peer review step for environment variable changes. The change was made directly in the ECS console without going through the normal Terraform/CloudFormation pipeline.

---

## Detection

*How was the incident detected? How long did it take from start to detection?*

- **Detected by**: _Automated CloudWatch alarm / User report / SRE Copilot Agent / Manual observation_
- **Time to detect**: _N minutes from incident start_
- **Detection gap**: _If detection was slow, explain why_

*Was the SRE Copilot Agent used during triage? If so, what queries were helpful?*

> Example queries used:
> - "Why is auth-service failing?"
> - "Show auth_failure patterns for the last 2 hours"
> - "What is the error rate vs normal for auth-service?"

---

## Mitigation and Resolution

*Describe each action taken to restore service.*

### Actions Taken

1. **HH:MM** — _Describe action 1 (e.g., rolled back ECS task definition to previous revision)_
2. **HH:MM** — _Describe action 2_
3. **HH:MM** — _Describe action 3_

### What Worked

- _Describe tools / runbooks / commands that were effective_

### What Didn't Work (or Slowed Recovery)

- _Describe any failed attempts or incorrect hypotheses that cost time_

---

## Action Items

*Every action item must have an owner, a priority, and a due date. File as tickets immediately.*

| # | Action Item | Owner | Priority | Due Date | Ticket |
|---|---|---|---|---|---|
| 1 | _Description of the preventive/detective measure_ | @name | High / Medium / Low | YYYY-MM-DD | TICKET-NNN |
| 2 | | | | | |
| 3 | | | | | |

### Action Item Categories

Use these labels to classify action items:

- **Prevent** — Changes that stop this class of incident from recurring
- **Detect** — Monitoring, alerting, or dashboard improvements
- **Mitigate** — Changes that reduce time-to-recovery if it happens again
- **Process** — Improvements to deployment, review, or on-call procedures
- **Runbook** — Updates to this or other runbooks based on lessons learned

---

## Lessons Learned

### What Went Well

*Be specific. What parts of the response were effective?*

- _Example: The SRE Copilot's `query_error_patterns` tool immediately surfaced auth_failure as the dominant category, saving ~10 minutes of manual log analysis._
- _Example: The on-call rotation was staffed and acknowledged the page within 3 minutes._

### What Could Be Improved

*Be specific. Avoid vague statements like "communication could be better".*

- _Example: We had no automated post-deployment smoke test for the auth endpoint._
- _Example: The runbook did not cover the GOOGLE_CLIENT_ID misconfiguration scenario._
- _Example: CloudWatch alarm threshold was too high; a lower threshold would have paged us 20 minutes earlier._

### Surprising Findings

*Anything unexpected discovered during the incident or postmortem review.*

- _Example: Discovered that MongoDB Atlas free tier auto-pauses after 60 days — not documented anywhere in our runbooks._

---

## Supporting Evidence

*Links to logs, dashboards, graphs, or screenshots captured during the incident.*

| Resource | Link / Location |
|---|---|
| CloudWatch Log Insights query | [link or query text] |
| SRE Copilot Agent session | Session ID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| CloudWatch metrics graph | [screenshot or link] |
| MongoDB Atlas metrics | [Atlas UI link] |
| Relevant Git commit / PR | [link] |
| Original alert | [PagerDuty / CloudWatch alarm link] |

---

## Review Sign-off

| Reviewer | Role | Date |
|---|---|---|
| | On-Call SRE | |
| | Platform Lead | |
| | Engineering Manager | |

---

*Filed to `sre-copilot/runbooks/` and synced to the Bedrock Knowledge Base S3 bucket for RAG context.*
