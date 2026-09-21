# CIIS failure-lab evidence

Each file records one local experiment. Copy `template.md` and include:

1. date and Kubernetes context;
2. exact command and image tag;
3. precondition output;
4. failure injection;
5. observed recovery or clean failure;
6. cleanup and postcondition;
7. conclusion and any follow-up issue.

Required scenarios:

- API pod replacement;
- worker interruption and SQS visibility-timeout retry;
- readiness failure after a bad image or unavailable dependency;
- PostgreSQL outage and readiness response;
- poison message to DLQ;
- duplicate message acknowledgement;
- Helm rollback;
- missing object failure;
- queue backlog visibility/worker scaling;
- invalid IPDR quarantine.

Do not record a scenario as PASS from a manifest alone; attach the observed
`kubectl`, SQS, job-status, and log output.
