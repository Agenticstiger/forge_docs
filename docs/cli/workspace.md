# `fluid workspace`

Team workspace and collaboration features — manage members, contract versions, change requests, and an activity log backed by a local SQLite database.

## Syntax

```bash
fluid workspace ACTION [SUBACTION] [...]
```

## Key options

| Option | Description |
| --- | --- |
| `init NAME [--description TEXT] [--owner NAME]` | Initialize a new workspace under `./.fluid-workspace/`. |
| `info` | Show workspace information (name, description, owner, member/version/change counts). |
| `team list` | List team members. |
| `team add NAME EMAIL [--role {owner,admin,developer,viewer}]` | Add a team member (default role: `developer`). |
| `version create CONTRACT --message MSG [--author NAME]` | Create a new contract version. |
| `version list [--contract PATH]` | List contract versions, optionally filtered by contract. |
| `changes create TITLE CONTRACT [--description TEXT] [--author NAME]` | Create a change request against a contract. |
| `changes list [--status {open,in_review,approved,rejected,merged}]` | List change requests, optionally filtered by status. |
| `changes approve REQUEST_ID [--approver NAME]` | Approve a change request that is currently `in_review`. |
| `activity [--limit N]` | Show the most recent activity log entries (default `--limit 20`). |

## Examples

```bash
fluid workspace init "Data Platform" --owner alice
fluid workspace team add bob bob@example.com --role developer
fluid workspace version create contracts/orders.fluid.yaml --message "Bump schema"
fluid workspace changes list --status open
```

## Notes

- The workspace lives in `./.fluid-workspace/` and stores everything in `workspace.db` (SQLite). A git repo is auto-initialised in that folder when `gitpython` is available.
- All output requires the `rich` library — without it, subcommands print a one-line "requires rich library" message and exit with code 1.
- Version numbers are auto-generated as `v1.<n>.0` based on the count of existing versions for that contract path.
- `changes approve` only succeeds if the request's current status is `in_review`.
- For human-driven development workflows tied to git directly, see [`fluid forge`](./forge.md).
