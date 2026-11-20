# 15 - Operations

## Normal Run review

1. Review the last workflow result.
2. Review source success and failure counts.
3. Review validation and Xray test counts.
4. Review observer quorum and disagreement.
5. Review Fixed Verified changes.
6. Review data freshness and output sizes.
7. Review the data branch commit.

## Failed pipeline

Do not publish partial output. Identify the failed stage. Correct the cause. Run the pipeline again. Keep the failed Run report without secrets.

## Observer disagreement

Check each observer result and timestamp. Check the observer service separately. Keep the result as IP Unverified until quorum and consensus are valid.

## Publish failure

Check permission, branch protection, non-fast-forward, conflict, and concurrency. Fetch the latest data branch. Do not use force push.

## Backup and recovery

Back up State and History. Test restore on a temporary branch. Validate schemas and record counts before the next publish.
