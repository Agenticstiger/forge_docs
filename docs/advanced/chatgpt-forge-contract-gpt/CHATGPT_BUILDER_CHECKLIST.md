# ChatGPT Builder Checklist

Use ChatGPT's GPT editor in configuration view, not the conversational builder.

## 1. Create The GPT

- Open `Explore GPTs`
- Select `Create`
- Switch to the configuration view

## 2. Fill The Basic Fields

Suggested name:

`FLUID Forge Contract Architect`

Suggested description:

`Drafts and reviews FLUID 0.7.2 contracts for Forge, asks provider-specific follow-up questions, and requires validation before anything is treated as final.`

Instructions:

- Paste the full contents of `GPT_INSTRUCTIONS.md`

Conversation starters:

- Paste the entries from `CONVERSATION_STARTERS.md`

Recommended model:

- Pick the strongest reasoning-capable model available in the GPT editor on the day you configure it

## 3. Set Capabilities

Recommended v1 setup:

- `Data Analysis`: On only if users will upload CSVs, JSON schemas, dbt artifacts, or structured metadata
- `Web browsing`: Off
- `Image generation`: Off
- `Actions`: Off
- `External tools/apps`: Off

Reasoning:

- The packet is intentionally knowledge-first
- Turning off extra tools reduces drift and makes failures easier to trace back to instructions or knowledge files

## 4. Upload Knowledge

Upload the files listed in `UPLOAD_MANIFEST.md`.

Guidelines:

- Upload the curated packet, not the whole repo
- Keep the knowledge base text-first and compact
- Remove old or conflicting drafts before publishing updates

## 5. Sharing

Use one of these:

- Private to you
- Workspace/internal only
- Unlisted internal link

Do not publish to the GPT Store for this version.

## 6. Preview Smoke Tests

Run these in Preview before sharing:

1. `Generate a FLUID 0.7.2 contract for a local CSV cleanup pipeline from these fields: order_id, customer_id, amount, order_date.`
2. `Generate a FLUID 0.7.2 contract for a GCP customer metrics table with GDPR residency and AI restrictions.`
3. `Review this contract and tell me what will fail validation:` then paste an intentionally broken contract
4. Upload a small schema-like CSV or JSON artifact and ask the GPT to map it to `exposes[].contract.schema`

## 7. Acceptance Rule

The GPT should never treat output as final until someone runs:

```bash
fluid validate contract.fluid.yaml --strict
fluid plan contract.fluid.yaml --provider <provider> --json
```

If validation has not been run yet, the GPT should label the result `Draft`.
